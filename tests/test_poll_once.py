"""Tests de la lógica de poll_once.py que no depende de la red real
(no probamos _procesar_actualizaciones_telegram ni _procesar_banco acá,
esos sí necesitan una conexión real)."""

import asyncio
from datetime import timedelta

import poll_once
import storage
from tiempo import ahora_local

CHAT = 555


class _BotFalso:
    def __init__(self):
        self.mensajes_mandados = []

    async def send_message(self, chat_id, text):
        self.mensajes_mandados.append((chat_id, text))


class _AppFalsa:
    def __init__(self, bot_falso):
        self.bot = bot_falso


def test_procesa_recordatorio_vencido_y_lo_marca():
    ahora = ahora_local()
    rid = storage.crear_recordatorio(CHAT, "ya pasó", ahora - timedelta(minutes=1))
    bot_falso = _BotFalso()

    asyncio.run(poll_once._procesar_recordatorios_vencidos(_AppFalsa(bot_falso)))

    assert len(bot_falso.mensajes_mandados) == 1
    chat_id, texto = bot_falso.mensajes_mandados[0]
    assert chat_id == CHAT
    assert "ya pasó" in texto
    assert storage.listar_pendientes(CHAT) == []  # ya quedó marcado como enviado


def test_procesa_recurrente_pendiente_una_sola_vez():
    ahora = ahora_local()
    hora_pasada = ahora - timedelta(minutes=5)
    storage.crear_recordatorio_recurrente(
        CHAT, "tomar la pastilla", ahora, "diario", hora_pasada.hour, hora_pasada.minute
    )
    bot_falso = _BotFalso()
    app_falsa = _AppFalsa(bot_falso)

    asyncio.run(poll_once._procesar_recordatorios_vencidos(app_falsa))
    assert len(bot_falso.mensajes_mandados) == 1

    # Si se vuelve a correr en el mismo día, no debe volver a mandarlo.
    asyncio.run(poll_once._procesar_recordatorios_vencidos(app_falsa))
    assert len(bot_falso.mensajes_mandados) == 1


def test_no_manda_recordatorio_que_todavia_no_llega():
    ahora = ahora_local()
    storage.crear_recordatorio(CHAT, "todavía no", ahora + timedelta(hours=1))
    bot_falso = _BotFalso()

    asyncio.run(poll_once._procesar_recordatorios_vencidos(_AppFalsa(bot_falso)))

    assert bot_falso.mensajes_mandados == []
