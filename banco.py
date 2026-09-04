"""Motor genérico de lectura de notificaciones bancarias por Gmail (IMAP).

El parseo de cada banco vive en el paquete bancos/ (un adaptador por banco):
este módulo solo se encarga de conectarse, vigilar la bandeja con IMAP IDLE,
y despachar cada correo al adaptador que corresponda según el remitente.

Nunca inicia sesión en la banca en línea ni ejecuta movimientos: solo lee
correos que el banco ya mandó, usando IMAP con una contraseña de aplicación
de Gmail (no la contraseña normal de la cuenta)."""

import asyncio
import email
import imaplib
import logging
import os
import ssl
import threading
import time
from email.header import decode_header
from email.utils import parseaddr

import certifi
from bs4 import BeautifulSoup
from imapclient import IMAPClient

import bancos

logger = logging.getLogger(__name__)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

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


def _criterio_busqueda() -> str:
    # Arma "OR FROM a OR FROM b FROM c" para que el IMAP filtre en el servidor
    # solo los correos de los bancos registrados (nunca toca el resto del inbox).
    remitentes = bancos.todos_los_remitentes()
    criterio = f'FROM "{remitentes[0]}"'
    for remitente in remitentes[1:]:
        criterio = f'OR {criterio} FROM "{remitente}"'
    return f"(UNSEEN {criterio})"


def buscar_notificaciones_nuevas() -> list[dict]:
    """Busca correos no leídos de cualquier banco registrado, los parsea con
    el adaptador que corresponda y los marca como leídos. Devuelve una lista
    de notificaciones parseadas (puede estar vacía)."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not bancos.todos_los_remitentes():
        return []

    notificaciones = []
    conexion = imaplib.IMAP4_SSL(IMAP_HOST, timeout=15)
    try:
        conexion.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        conexion.select("INBOX")

        _, datos = conexion.search(None, _criterio_busqueda())
        ids = datos[0].split()

        for id_correo in ids:
            _, datos_msj = conexion.fetch(id_correo, "(RFC822)")
            mensaje = email.message_from_bytes(datos_msj[0][1])

            _, direccion = parseaddr(mensaje.get("From", ""))
            adaptador = bancos.adaptador_para(direccion)
            if adaptador is not None:
                asunto = _decodificar(mensaje.get("Subject"))
                cuerpo = _cuerpo_texto_plano(mensaje)
                notificaciones.append(adaptador.parsear(asunto, cuerpo))

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
