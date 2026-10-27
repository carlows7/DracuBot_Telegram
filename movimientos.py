"""Registro de movimientos de la cuenta a partir de los avisos del banco.

Cada correo del banco se guarda como una fila ("aviso"). Un mismo movimiento
suele llegar en varios correos (ej. una transferencia manda "en proceso",
"exitosa" y un aviso de cargo), así que los totales se calculan al leer,
consolidando los avisos que describen el mismo movimiento en vez de sumarlos
todos. Nunca se guarda el texto del correo, solo monto, fecha y tipo."""

import hashlib
import os
import re

# tipo de notificación -> (fuente, dirección). "fuente" distingue el tipo de
# correo para poder consolidar duplicados entre fuentes distintas.
FUENTES = {
    "deposito_recibido": ("abono", "entra"),
    "credito_recibido": ("credito_alerta", "entra"),
    "compra": ("compra", "sale"),
    "debito_cuenta": ("debito_alerta", "sale"),
    "transferencia_enviada": ("transf_ok", "sale"),
    "transferencia_proceso": ("transf_proceso", "sale"),
    "transferencia_rechazada": ("transf_rechazada", "sale"),
    "retiro_sin_tarjeta": ("retiro", "sale"),
}

MESES_NOMBRES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def cuentas_propias() -> dict[str, str]:
    """Lee CUENTAS_PROPIAS del .env: '8878=carlos,1234=otra'. Cada entrada es
    los últimos 4 dígitos de la cuenta y, opcional, una palabra del nombre del
    titular (sirve para los avisos de transferencia que no traen la cuenta
    origen y solo saludan por nombre). Vacío = no se filtra: se cuentan todas."""
    cuentas = {}
    for parte in os.getenv("CUENTAS_PROPIAS", "").split(","):
        parte = parte.strip()
        if not parte:
            continue
        numero, _, titular = parte.partition("=")
        cuentas[numero.strip()] = titular.strip().lower()
    return cuentas


def _ultimos4(texto) -> str | None:
    m = re.search(r"(\d{4})\D*$", str(texto or ""))
    return m.group(1) if m else None


def extraer(n: dict) -> dict | None:
    """Convierte una notificación parseada en un aviso de movimiento, o None si
    no es un movimiento de dinero (inicios de sesión, avisos de seguridad...)."""
    tipo = n.get("tipo")
    if tipo not in FUENTES:
        return None
    fuente, direccion = FUENTES[tipo]
    monto = n.get("monto_num")
    if monto is None and fuente != "retiro":
        return None  # no se pudo leer el monto: mejor no inventar uno
    fecha = n.get("fecha") or n.get("fecha_correo")
    if not fecha:
        return None
    clave = n.get("message_id") or hashlib.sha1(
        f"{n.get('asunto')}|{n.get('crudo')}|{fecha}".encode()
    ).hexdigest()
    return {
        "message_id": clave,
        "fuente": fuente,
        "direccion": direccion,
        "cuenta": _ultimos4(n.get("cuenta")),
        "titular": (n.get("titular") or "").lower() or None,
        "fecha": fecha,
        "monto": monto,
        "banco_contraparte": n.get("banco_contraparte"),
    }


def _cuenta_efectiva(fila, cuentas: dict[str, str]) -> str | None:
    """Cuenta a la que se atribuye el aviso. Con filtro (CUENTAS_PROPIAS):
    la cuenta si es una de las propias; si el aviso no trae cuenta, la del
    titular que coincida por nombre; si no, None (no es de las tuyas)."""
    cuenta, titular = fila["cuenta"], fila["titular"] or ""
    if not cuentas:
        return cuenta or "?"
    if cuenta:
        return cuenta if cuenta in cuentas else None
    for numero, palabra in cuentas.items():
        if palabra and palabra in titular:
            return numero
    return None


def consolidar(filas, cuentas: dict[str, str] | None = None) -> dict:
    """Totales de un conjunto de avisos, sin contar dos veces el mismo movimiento.

    Los avisos se agrupan por (cuenta, día, monto). Dentro de cada grupo, cada
    fuente cuenta los mismos movimientos, así que se toma la fuente que más
    contó en vez de sumarlas:
    - entradas = max(abonos, avisos de crédito)
    - transferencias = max(exitosas, en proceso - rechazadas)
    - salidas = max(compras + transferencias, avisos de débito)
    Los retiros sin tarjeta no traen monto: solo se cuentan."""
    cuentas = cuentas if cuentas is not None else cuentas_propias()
    grupos: dict[tuple, dict[str, int]] = {}
    retiros = 0
    for f in filas:
        cuenta = _cuenta_efectiva(f, cuentas)
        if cuenta is None:
            continue
        if f["fuente"] == "retiro":
            retiros += 1
            continue
        clave = (cuenta, f["fecha"], round(f["monto"], 2))
        g = grupos.setdefault(clave, {})
        g[f["fuente"]] = g.get(f["fuente"], 0) + 1

    r = {
        "entra": 0.0, "n_entra": 0,
        "sale": 0.0, "n_sale": 0,
        "compras": 0.0, "n_compras": 0,
        "transferencias": 0.0, "n_transferencias": 0,
        "otros_cargos": 0.0, "n_otros_cargos": 0,
        "retiros_sin_monto": retiros,
    }
    for (_cuenta, _fecha, monto), g in grupos.items():
        entra = max(g.get("abono", 0), g.get("credito_alerta", 0))
        compras = g.get("compra", 0)
        transf = max(g.get("transf_ok", 0), g.get("transf_proceso", 0) - g.get("transf_rechazada", 0), 0)
        sale = max(compras + transf, g.get("debito_alerta", 0))
        otros = sale - compras - transf

        r["entra"] += entra * monto
        r["n_entra"] += entra
        r["sale"] += sale * monto
        r["n_sale"] += sale
        r["compras"] += compras * monto
        r["n_compras"] += compras
        r["transferencias"] += transf * monto
        r["n_transferencias"] += transf
        r["otros_cargos"] += otros * monto
        r["n_otros_cargos"] += otros
    for k in ("entra", "sale", "compras", "transferencias", "otros_cargos"):
        r[k] = round(r[k], 2)
    r["neto"] = round(r["entra"] - r["sale"], 2)
    return r


def formatear_resumen(anio: int, mes: int, r: dict, cuentas: dict[str, str] | None = None) -> str:
    cuentas = cuentas if cuentas is not None else cuentas_propias()
    cuenta_txt = f" · cuenta {', '.join(cuentas)}" if cuentas else ""
    lineas = [f"🏦 Tu banco en {MESES_NOMBRES[mes - 1]} {anio}{cuenta_txt}", ""]
    if r["n_entra"] == 0 and r["n_sale"] == 0:
        lineas.append("🦇 No encontré movimientos de ese mes en los avisos del banco.")
        return "\n".join(lineas)

    lineas.append(f"📥 Entró: ${r['entra']:,.2f} ({r['n_entra']} movimientos)")
    lineas.append(f"📤 Salió: ${r['sale']:,.2f} ({r['n_sale']} movimientos)")
    if r["n_compras"]:
        lineas.append(f"   🛒 Compras con tarjeta: ${r['compras']:,.2f} ({r['n_compras']})")
    if r["n_transferencias"]:
        lineas.append(f"   🔁 Transferencias enviadas: ${r['transferencias']:,.2f} ({r['n_transferencias']})")
    if r["n_otros_cargos"]:
        lineas.append(f"   ➖ Otros cargos: ${r['otros_cargos']:,.2f} ({r['n_otros_cargos']})")
    signo = "+" if r["neto"] >= 0 else "−"
    lineas.append("")
    lineas.append(f"⚖️ Diferencia: {signo}${abs(r['neto']):,.2f}")
    if r["retiros_sin_monto"]:
        lineas.append(
            f"\n🏧 {r['retiros_sin_monto']} retiro(s) sin tarjeta: el banco no avisa el monto, no están en lo que salió."
        )
    lineas.append("\nSolo cuenta lo que el banco avisó por correo; no es un estado de cuenta oficial.")
    return "\n".join(lineas)
