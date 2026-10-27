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


def _monto_numero(texto: str | None) -> float | None:
    """'USD 1,234.50' / '$25.00' / '10.00' -> 1234.5 / 25.0 / 10.0."""
    if not texto:
        return None
    m = re.search(r"(\d[\d,]*\.\d{1,2}|\d[\d,]*)", texto)
    return float(m.group(1).replace(",", "")) if m else None


def _fecha_iso(texto: str | None) -> str | None:
    """Acepta 2026-08-11 23:19 o 14/12/2025 08:34:26 P.M. y devuelve YYYY-MM-DD."""
    if not texto:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", texto)
    if m:
        return f"{m[3]}-{m[2]}-{m[1]}"
    return None


def _ultimos4(texto: str | None) -> str | None:
    """Últimos 4 dígitos de un número de cuenta enmascarado (XXXXXX8878, ***8878, X8878)."""
    m = re.search(r"[X*]+(\d{4})", texto or "")
    return m.group(1) if m else None


def _titular(cuerpo: str) -> str | None:
    m = re.search(
        r"(?:Hola|Buen d[ií]a|Buenas tardes|Buenas noches)\s*,\s*\n?\s*([^\n]+)", cuerpo, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"Estimado Se[ñn]or/Se[ñn]ora:\s*([^\n]+)", cuerpo, re.IGNORECASE)
    return m.group(1).strip() if m else None


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
    if "recibido un crédito" in cuerpo_bajo or "recibido un credito" in cuerpo_bajo:
        return "credito_recibido"
    if "se hizo un débito" in cuerpo_bajo or "se hizo un debito" in cuerpo_bajo:
        return "debito_cuenta"
    if "transfer" in asunto_bajo:
        if "rechazo" in cuerpo_bajo or "rechazada" in cuerpo_bajo:
            return "transferencia_rechazada"
        if "en proceso" in cuerpo_bajo:
            return "transferencia_proceso"
        if "exitosa" in cuerpo_bajo:
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
    elif tipo in ("transferencia_proceso", "transferencia_rechazada") or (
        tipo == "transferencia_enviada" and "Cuenta origen" in cuerpo
    ):
        lineas = [l.strip() for l in cuerpo.splitlines() if l.strip()]

        def _despues(etiqueta: str, saltos: int = 1) -> str | None:
            for i, l in enumerate(lineas):
                if l.lower().rstrip(": ") == etiqueta.lower() and i + saltos < len(lineas):
                    return lineas[i + saltos]
            return None

        base.update(
            monto=_extraer_campo(cuerpo, "Monto"),
            fecha_hora=_extraer_campo(cuerpo, "Fecha y hora"),
            cuenta=_ultimos4(_despues("Cuenta origen", 2)),
            banco_contraparte=_extraer_campo(cuerpo, "Banco Destino") or _despues("Cuenta destino", 3),
            referencia=_extraer_campo(cuerpo, "No Referencia") or _extraer_campo(cuerpo, "Número de referencia"),
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
    elif tipo in ("credito_recibido", "debito_cuenta"):
        # Avisos en prosa: "... en su cuenta XXXXXXXXXX8878 por USD3.00 el día 2026-08-11 23:19."
        monto = re.search(r"por\s+(USD\s?[\d,.]+)", cuerpo, re.IGNORECASE)
        fecha = re.search(r"el\s+d[ií]a\s+(\d{4}-\d{2}-\d{2}[^\n.]*\d)", cuerpo, re.IGNORECASE)
        cuenta = re.search(r"cuenta\s+([X*]*\d{4})", cuerpo, re.IGNORECASE)
        base.update(
            monto=monto.group(1) if monto else None,
            fecha_hora=fecha.group(1) if fecha else None,
            cuenta=_ultimos4(cuenta.group(1)) if cuenta else None,
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

    # Campos normalizados que usa el registro de movimientos (ver movimientos.py).
    base["monto_num"] = _monto_numero(base.get("monto"))
    base["fecha"] = _fecha_iso(base.get("fecha_hora"))
    base["titular"] = _titular(cuerpo)
    if tipo in ("deposito_recibido",) and not base.get("cuenta"):
        base["cuenta"] = _ultimos4(cuerpo)
    return base
