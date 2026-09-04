"""Prueba _proxima_ocurrencia() de bot.py directamente: esta es la función
donde faltaba importar timedelta y rompía con NameError al crear un
recordatorio recurrente por Telegram."""

from datetime import datetime

import bot
from tiempo import ahora_local


def test_proxima_ocurrencia_diaria_no_rompe():
    fecha = bot._proxima_ocurrencia(hora=8, minuto=0, dia_semana=None)
    assert isinstance(fecha, datetime)
    assert fecha.hour == 8
    assert fecha.minute == 0
    assert fecha > ahora_local() - bot.timedelta(days=1)


def test_proxima_ocurrencia_semanal_no_rompe():
    fecha = bot._proxima_ocurrencia(hora=9, minuto=0, dia_semana=0)  # lunes
    assert isinstance(fecha, datetime)
    assert fecha.weekday() == 0
    assert fecha.hour == 9
