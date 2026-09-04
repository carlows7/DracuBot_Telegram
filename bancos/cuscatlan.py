"""Adaptador de notificaciones para Banco Cuscatlán de El Salvador.

Cada adaptador de banco es un módulo con:
- REMITENTE: la dirección de correo desde la que llegan sus notificaciones
- NOMBRE: nombre para mostrar
- parsear(asunto, cuerpo) -> dict: interpreta el correo ya convertido a texto
"""

import re

REMITENTE = "notificaciones@bancocuscatlan.com"
NOMBRE = "Banco Cuscatlán"


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


def parsear(asunto: str, cuerpo: str) -> dict:
    tipo = _detectar_tipo(asunto, cuerpo)
    base = {"tipo": tipo, "banco": NOMBRE, "asunto": asunto, "crudo": cuerpo.strip()[:500]}

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
