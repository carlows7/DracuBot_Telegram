"""Lee (solo lectura) las notificaciones del banco que llegan por Gmail
y las traduce a un formato simple para mandar por Telegram.

Nunca inicia sesión en la banca en línea ni ejecuta movimientos: solo lee
correos que el banco ya mandó, usando IMAP con una contraseña de aplicación
de Gmail (no la contraseña normal de la cuenta)."""

import asyncio
import email
import imaplib
import logging
import os
import re
import ssl
import threading
import time
from email.header import decode_header

import certifi
from bs4 import BeautifulSoup
from imapclient import IMAPClient

logger = logging.getLogger(__name__)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
REMITENTE_BANCO = os.getenv("REMITENTE_BANCO", "notificaciones@bancocuscatlan.com")

# En algunas instalaciones de Python en macOS (python.org) el contexto SSL por
# defecto no encuentra los certificados raíz del sistema; usamos el bundle de
# certifi explícitamente para que la verificación TLS funcione siempre.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

IMAP_HOST = "imap.gmail.com"


def _decodificar(valor) -> str:
    if not valor:
        return ""
    partes = decode_header(valor)
    resultado = ""
    for texto, codificacion in partes:
        if isinstance(texto, bytes):
            resultado += texto.decode(codificacion or "utf-8", errors="ignore")
        else:
            resultado += texto
    return resultado


def _html_a_texto(html: str) -> str:
    sopa = BeautifulSoup(html, "html.parser")
    for etiqueta in sopa(["script", "style"]):
        etiqueta.decompose()
    # separador de línea por cada <tr>/<td>/<p>/<br> para conservar la estructura
    # de "Etiqueta" / "Valor" que usan las tablas de estos correos.
    texto = sopa.get_text(separator="\n")
    lineas = [l.strip() for l in texto.splitlines()]
    return "\n".join(l for l in lineas if l)


def _cuerpo_texto_plano(mensaje) -> str:
    html_encontrado = None
    if mensaje.is_multipart():
        for parte in mensaje.walk():
            if parte.get_content_type() == "text/plain":
                payload = parte.get_payload(decode=True)
                if payload:
                    charset = parte.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="ignore")
            if parte.get_content_type() == "text/html" and html_encontrado is None:
                payload = parte.get_payload(decode=True)
                if payload:
                    charset = parte.get_content_charset() or "utf-8"
                    html_encontrado = payload.decode(charset, errors="ignore")
        return _html_a_texto(html_encontrado) if html_encontrado else ""

    payload = mensaje.get_payload(decode=True)
    if not payload:
        return ""
    charset = mensaje.get_content_charset() or "utf-8"
    texto = payload.decode(charset, errors="ignore")
    if mensaje.get_content_type() == "text/html":
        return _html_a_texto(texto)
    return texto


def _extraer_campo(cuerpo: str, etiqueta: str) -> str | None:
    # Los correos del banco listan "Etiqueta:" y el valor en la línea siguiente.
    patron = re.compile(rf"{re.escape(etiqueta)}\s*:?\s*\n\s*(.+)", re.IGNORECASE)
    match = patron.search(cuerpo)
    return match.group(1).strip() if match else None


def _detectar_tipo(asunto: str, cuerpo: str) -> str:
    asunto_bajo = asunto.lower()
    cuerpo_bajo = cuerpo.lower()

    if "retiro" in asunto_bajo:
        return "retiro_sin_tarjeta"
    if "inicio de sesión" in asunto_bajo or "inicio de sesion" in asunto_bajo:
        return "inicio_sesion"
    if "compra" in asunto_bajo or "consumo con tarjeta" in cuerpo_bajo:
        return "compra"
    if "recibido un abono" in cuerpo_bajo:
        return "deposito_recibido"
    if "realizado una transferencia" in cuerpo_bajo or "envió una transferencia" in cuerpo_bajo:
        return "transferencia_enviada"
    return "otro"


def parsear_notificacion(asunto: str, cuerpo: str) -> dict:
    tipo = _detectar_tipo(asunto, cuerpo)
    base = {"tipo": tipo, "asunto": asunto, "crudo": cuerpo.strip()[:500]}

    if tipo == "deposito_recibido":
        base.update(
            monto=_extraer_campo(cuerpo, "Monto"),
            banco_contraparte=_extraer_campo(cuerpo, "Banco origen"),
            contraparte=_extraer_campo(cuerpo, "Originado por"),
            fecha_hora=_extraer_campo(cuerpo, "Fecha y hora"),
            referencia=_extraer_campo(cuerpo, "No Referencia"),
        )
    elif tipo == "transferencia_enviada":
        base.update(
            monto=_extraer_campo(cuerpo, "Monto"),
            banco_contraparte=_extraer_campo(cuerpo, "Banco destino"),
            contraparte=_extraer_campo(cuerpo, "Originado por"),
            fecha_hora=_extraer_campo(cuerpo, "Fecha y hora"),
            referencia=_extraer_campo(cuerpo, "No Referencia"),
        )
    elif tipo == "compra":
        # Este correo viene en prosa, no en tabla de "Etiqueta: Valor".
        monto = re.search(r"por\s+(USD\s?[\d,.]+)", cuerpo, re.IGNORECASE)
        fecha = re.search(r"el\s+d[ií]a\s+([\d/-]+[^\n.]*\d)", cuerpo, re.IGNORECASE)
        cuenta = re.search(r"cuenta\s+([A-Z0-9]+)", cuerpo, re.IGNORECASE)
        base.update(
            monto=monto.group(1) if monto else None,
            fecha_hora=fecha.group(1) if fecha else None,
            cuenta=cuenta.group(1) if cuenta else None,
        )
    elif tipo == "retiro_sin_tarjeta":
        base.update(
            codigo_retiro=_extraer_campo(cuerpo, "Código de retiro"),
            vigencia=_extraer_campo(cuerpo, "Vigencia de código"),
            fecha_hora=_extraer_campo(cuerpo, "Fecha y hora"),
        )
    elif tipo == "inicio_sesion":
        base.update(
            fecha_hora=_extraer_campo(cuerpo, "Fecha de inicio"),
            ip=_extraer_campo(cuerpo, "Dirección IP"),
            navegador=_extraer_campo(cuerpo, "Información del navegador"),
        )

    return base


def buscar_notificaciones_nuevas() -> list[dict]:
    """Busca correos no leídos del banco, los parsea y los marca como leídos.
    Devuelve una lista de notificaciones parseadas (puede estar vacía)."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return []

    notificaciones = []
    conexion = imaplib.IMAP4_SSL(IMAP_HOST, timeout=15)
    try:
        conexion.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        conexion.select("INBOX")

        _, datos = conexion.search(None, f'(UNSEEN FROM "{REMITENTE_BANCO}")')
        ids = datos[0].split()

        for id_correo in ids:
            _, datos_msj = conexion.fetch(id_correo, "(RFC822)")
            mensaje = email.message_from_bytes(datos_msj[0][1])
            asunto = _decodificar(mensaje.get("Subject"))
            cuerpo = _cuerpo_texto_plano(mensaje)
            notificaciones.append(parsear_notificacion(asunto, cuerpo))
            conexion.store(id_correo, "+FLAGS", "\\Seen")
    finally:
        try:
            conexion.close()
        except imaplib.IMAP4.error:
            pass
        conexion.logout()

    return notificaciones


def vigilar_banco(en_nueva_notificacion, loop, detener: threading.Event | None = None):
    """Corre en un hilo aparte (bloqueante): usa IMAP IDLE para enterarse al
    instante cuando llega un correo nuevo del banco, en vez de consultar cada
    tanto (polling). Cuando detecta algo, llama a `en_nueva_notificacion`
    (una función async) en el loop de asyncio del bot."""
    while detener is None or not detener.is_set():
        try:
            with IMAPClient(IMAP_HOST, ssl=True, ssl_context=_SSL_CONTEXT, timeout=30) as cliente:
                cliente.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                cliente.select_folder("INBOX")
                logger.info("Vigilancia IMAP IDLE conectada")

                while detener is None or not detener.is_set():
                    cliente.idle()
                    # Cada 5 minutos se corta el IDLE igual, para mantener la
                    # conexión viva (buena práctica del protocolo IMAP).
                    respuestas = cliente.idle_check(timeout=300)
                    cliente.idle_done()

                    if respuestas:
                        notificaciones = buscar_notificaciones_nuevas()
                        if notificaciones:
                            asyncio.run_coroutine_threadsafe(
                                en_nueva_notificacion(notificaciones), loop
                            )
        except Exception:
            logger.exception("Se perdió la conexión IDLE con Gmail, reintentando en 30s")
            time.sleep(30)
