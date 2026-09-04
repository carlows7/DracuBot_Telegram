"""Tests del intérprete de lenguaje natural para recordatorios."""

import pytest

from tiempo import interpretar_recordatorio, interpretar_recurrente


@pytest.mark.parametrize(
    "texto,mensaje_esperado",
    [
        ("mañana a las 3 llamar al banco", "llamar al banco"),
        ("en 10 minutos sacar la comida", "sacar la comida"),
        ("hoy a las 20:30 tomar la pastilla", "tomar la pastilla"),
        ("el viernes a las 18 reunión", "reunión"),
        ("13 de octubre caminata por Michoacán", "caminata por Michoacán"),
        ("10m Llamar al banco", "Llamar al banco"),
        ("20:30 Tomar la pastilla", "Tomar la pastilla"),
        ("8pm gimnasio hoy", "gimnasio"),
        ("1 de la tarde almuerzo mañana", "almuerzo"),
        ("a las 20:30 tomar la pastilla mañana", "tomar la pastilla"),
    ],
)
def test_interpreta_fecha_reconocida(texto, mensaje_esperado):
    fecha, mensaje = interpretar_recordatorio(texto)
    assert fecha is not None
    assert mensaje == mensaje_esperado


def test_rechaza_texto_sin_fecha():
    fecha, _ = interpretar_recordatorio("esto no significa nada como fecha")
    assert fecha is None


def test_recurrente_diario():
    info, mensaje = interpretar_recurrente("todos los días a las 8 tomar la pastilla")
    assert info == {"tipo": "diario", "dia_semana": None, "hora": 8, "minuto": 0}
    assert mensaje == "tomar la pastilla"


def test_recurrente_semanal():
    info, mensaje = interpretar_recurrente("todos los lunes a las 9 reunión de equipo")
    assert info["tipo"] == "semanal"
    assert info["dia_semana"] == 0
    assert mensaje == "reunión de equipo"


def test_recurrente_no_matchea_uno_normal():
    info, _ = interpretar_recurrente("mañana a las 3 llamar al banco")
    assert info is None
