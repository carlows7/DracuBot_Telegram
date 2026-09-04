"""Interpreta en lenguaje natural cuándo tiene que dispararse un recordatorio."""

import re
from datetime import datetime, timedelta

DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

UNIDADES = {"minuto": "minutes", "hora": "hours", "dia": "days", "día": "days"}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def ahora_local() -> datetime:
    # Con tzinfo: la librería del bot asume UTC en datetimes naive,
    # lo que dispara los recordatorios de inmediato si el sistema no está en UTC.
    return datetime.now().astimezone()


def _normalizar_unidad(unidad: str) -> str:
    unidad = unidad.rstrip("s")  # minutos -> minuto, horas -> hora, dias -> dia
    return UNIDADES[unidad]


def _hora_desde_grupos(hora: str, minuto: str | None, calificador: str | None) -> tuple[int, int]:
    h = int(hora)
    m = int(minuto) if minuto else 0
    calificador = (calificador or "").lower()

    if "pm" in calificador or "tarde" in calificador or "noche" in calificador:
        if h < 12:
            h += 12
    elif "am" in calificador or "mañana" in calificador:
        if h == 12:
            h = 0

    return h % 24, m


# Cada patrón intenta matchear al PRINCIPIO del texto. Lo que sigue después
# del match se toma como el mensaje del recordatorio.
_CALIF = r"(am|pm|de la mañana|de la manana|de la tarde|de la noche)?"
_HORA = rf"(\d{{1,2}})(?::(\d{{2}}))?\s*{_CALIF}"

PATRONES = [
    # "en 10 minutos", "en 2 horas", "en 1 día", "en una hora"
    (re.compile(rf"^en\s+(un|una|\d+)\s+(minutos?|horas?|d[ií]as?)\s+", re.IGNORECASE), "relativo"),
    # "pasado mañana a las 9"
    (re.compile(rf"^pasado\s+mañana\s+a\s+las?\s+{_HORA}\s+", re.IGNORECASE), "pasado_mañana"),
    # "mañana a las 15:00"
    (re.compile(rf"^mañana\s+a\s+las?\s+{_HORA}\s+", re.IGNORECASE), "mañana"),
    # "hoy a las 20:30"
    (re.compile(rf"^hoy\s+a\s+las?\s+{_HORA}\s+", re.IGNORECASE), "hoy"),
    # "el viernes a las 18", "este lunes a las 9", "próximo martes a las 10"
    (
        re.compile(
            rf"^(?:el|este|próximo|proximo)?\s*"
            rf"(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+a\s+las?\s+{_HORA}\s+",
            re.IGNORECASE,
        ),
        "dia_semana",
    ),
    # "05/09/2026 a las 14:00" o "05/09 a las 14:00"
    (
        re.compile(rf"^(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{4}}))?\s+a\s+las?\s+{_HORA}\s+", re.IGNORECASE),
        "fecha_absoluta",
    ),
    # "13 de octubre", "13 de octubre a las 10", "13 de octubre de 2026 a las 10"
    (
        re.compile(
            rf"^(\d{{1,2}})\s+de\s+({'|'.join(MESES)})(?:\s+de\s+(\d{{4}}))?"
            rf"(?:\s+a\s+las?\s+{_HORA})?\s+",
            re.IGNORECASE,
        ),
        "fecha_textual",
    ),
    # Compatibilidad con el formato viejo: "05/09/2026 14:00"
    (re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})\s+", re.IGNORECASE), "fecha_absoluta_vieja"),
    # "a las 20:30" (sin decir hoy/mañana: hoy si no pasó, si no mañana)
    (re.compile(rf"^a\s+las?\s+{_HORA}\s+", re.IGNORECASE), "solo_hora"),
    # Compatibilidad con el formato viejo: "10m", "2h", "1d"
    (re.compile(r"^(\d+)([mhd])\s+", re.IGNORECASE), "relativo_viejo"),
    # Compatibilidad con el formato viejo: "20:30" suelto
    (re.compile(r"^(\d{1,2}):(\d{2})\s+", re.IGNORECASE), "solo_hora_vieja"),
]


def interpretar_recordatorio(texto: str) -> tuple[datetime | None, str]:
    """Recibe todo el texto después de /recordar y devuelve (fecha, mensaje).
    Si no reconoce ninguna expresión de tiempo al principio, fecha es None.
    """
    texto = texto.strip()
    ahora = ahora_local()

    for patron, tipo in PATRONES:
        match = patron.match(texto)
        if not match:
            continue

        mensaje = texto[match.end():].strip()

        if tipo == "relativo":
            cantidad_txt, unidad = match.groups()
            cantidad = 1 if cantidad_txt in ("un", "una") else int(cantidad_txt)
            delta = {_normalizar_unidad(unidad): cantidad}
            return ahora + timedelta(**delta), mensaje

        if tipo == "relativo_viejo":
            cantidad, unidad = match.groups()
            delta = {{"m": "minutes", "h": "hours", "d": "days"}[unidad.lower()]: int(cantidad)}
            return ahora + timedelta(**delta), mensaje

        if tipo in ("pasado_mañana", "mañana", "hoy"):
            hora, minuto, calif = match.groups()
            h, m = _hora_desde_grupos(hora, minuto, calif)
            dias = {"hoy": 0, "mañana": 1, "pasado_mañana": 2}[tipo]
            fecha = (ahora + timedelta(days=dias)).replace(hour=h, minute=m, second=0, microsecond=0)
            return fecha, mensaje

        if tipo == "dia_semana":
            nombre_dia, hora, minuto, calif = match.groups()
            objetivo = DIAS_SEMANA[nombre_dia.lower().replace("á", "a").replace("é", "e")]
            h, m = _hora_desde_grupos(hora, minuto, calif)
            dias_hasta = (objetivo - ahora.weekday()) % 7
            fecha = (ahora + timedelta(days=dias_hasta)).replace(hour=h, minute=m, second=0, microsecond=0)
            if fecha <= ahora:
                fecha += timedelta(days=7)
            return fecha, mensaje

        if tipo == "fecha_absoluta":
            dia, mes, anio, hora, minuto, calif = match.groups()
            anio = int(anio) if anio else ahora.year
            h, m = _hora_desde_grupos(hora, minuto, calif)
            try:
                fecha = ahora.replace(
                    year=anio, month=int(mes), day=int(dia), hour=h, minute=m, second=0, microsecond=0
                )
            except ValueError:
                return None, texto
            return fecha, mensaje

        if tipo == "fecha_textual":
            dia, mes_nombre, anio, hora, minuto, calif = match.groups()
            mes = MESES[mes_nombre.lower()]
            if hora is not None:
                h, m = _hora_desde_grupos(hora, minuto, calif)
            else:
                h, m = 9, 0  # sin hora explícita: 9 de la mañana por defecto

            anio_dado = anio is not None
            anio = int(anio) if anio_dado else ahora.year
            try:
                fecha = ahora.replace(
                    year=anio, month=mes, day=int(dia), hour=h, minute=m, second=0, microsecond=0
                )
            except ValueError:
                return None, texto
            if not anio_dado and fecha <= ahora:
                # No dijo el año y esa fecha ya pasó este año: asumimos el año que viene.
                fecha = fecha.replace(year=anio + 1)
            return fecha, mensaje

        if tipo == "fecha_absoluta_vieja":
            dia, mes, anio, hora, minuto = match.groups()
            try:
                fecha = ahora.replace(
                    year=int(anio), month=int(mes), day=int(dia),
                    hour=int(hora), minute=int(minuto), second=0, microsecond=0,
                )
            except ValueError:
                return None, texto
            return fecha, mensaje

        if tipo == "solo_hora":
            hora, minuto, calif = match.groups()
            h, m = _hora_desde_grupos(hora, minuto, calif)
            fecha = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
            if fecha <= ahora:
                fecha += timedelta(days=1)
            return fecha, mensaje

        if tipo == "solo_hora_vieja":
            hora, minuto = match.groups()
            fecha = ahora.replace(hour=int(hora), minute=int(minuto), second=0, microsecond=0)
            if fecha <= ahora:
                fecha += timedelta(days=1)
            return fecha, mensaje

    return None, texto
