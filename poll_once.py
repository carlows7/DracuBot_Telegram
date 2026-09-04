"""Punto de entrada para GitHub Actions: corre el bot UNA sola pasada y sale,
en vez de quedarse escuchando para siempre (como hace bot.py con Mac + launchd).

En cada corrida:
1. Procesa los mensajes de Telegram que llegaron desde la última corrida.
2. Manda los recordatorios (de una vez o recurrentes) cuya hora ya llegó.
3. Revisa el correo del banco una vez (sin IMAP IDLE: acá no hay forma de
   "quedarse escuchando", así que es un chequeo puntual por corrida).
4. Manda el reporte matutino / aviso nocturno si corresponde y todavía no
   se mandaron hoy.

La base de datos (recordatorios.db) vive en un repo aparte, PRIVADO, para no
exponer tus gastos y recordatorios en el repo público del código. Ver
.github/workflows/poll.yml para cómo se sincroniza.
"""

import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()

from telegram.ext import Application

import bot
import storage
from banco import buscar_notificaciones_nuevas
from tiempo import ahora_local

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class _ContextoFalso:
    """Los handlers de los avisos diarios (resumen_matutino, aviso_nocturno)
    solo usan context.bot — no hace falta un ContextTypes real de PTB."""

    def __init__(self, bot_):
        self.bot = bot_


async def _procesar_actualizaciones_telegram(app: Application):
    offset = storage.obtener_offset_telegram()
    actualizaciones = await app.bot.get_updates(offset=offset, timeout=10)
    for actualizacion in actualizaciones:
        await app.process_update(actualizacion)
        offset = actualizacion.update_id + 1
    if actualizaciones:
        storage.guardar_offset_telegram(offset)
    logger.info("Actualizaciones de Telegram procesadas: %d", len(actualizaciones))


async def _procesar_recordatorios_vencidos(app: Application):
    ahora = ahora_local()

    for r in storage.recordatorios_vencidos(ahora):
        await app.bot.send_message(chat_id=r["chat_id"], text=f"🧛🦇 Ha llegado la hora... {r['mensaje']}")
        storage.marcar_enviado(r["id"])

    for r in storage.recurrentes_pendientes(ahora):
        await app.bot.send_message(chat_id=r["chat_id"], text=f"🔁🧛 {r['mensaje']}")
        storage.marcar_ultimo_envio(r["id"], ahora.date().isoformat())


async def _procesar_banco(app: Application):
    try:
        notificaciones = buscar_notificaciones_nuevas()
    except Exception:
        logger.exception("Error revisando el correo del banco")
        return
    if notificaciones:
        await bot.procesar_notificaciones_banco(app.bot, notificaciones)


async def _procesar_jobs_diarios(app: Application):
    ahora = ahora_local()
    hoy = ahora.date().isoformat()
    contexto = _ContextoFalso(app.bot)

    if ahora.hour == 8 and not storage.ya_se_mando_hoy("resumen_matutino", hoy):
        await bot.resumen_matutino(contexto)
        storage.marcar_enviado_hoy("resumen_matutino", hoy)

    if ahora.hour == 22 and not storage.ya_se_mando_hoy("aviso_nocturno", hoy):
        await bot.aviso_nocturno(contexto)
        storage.marcar_enviado_hoy("aviso_nocturno", hoy)


async def correr_una_pasada():
    if not bot.TOKEN:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN.")

    storage.inicializar_db()

    app = Application.builder().token(bot.TOKEN).build()
    bot.registrar_handlers(app)

    await app.initialize()
    try:
        await _procesar_actualizaciones_telegram(app)
        await _procesar_recordatorios_vencidos(app)
        await _procesar_banco(app)
        await _procesar_jobs_diarios(app)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(correr_una_pasada())
