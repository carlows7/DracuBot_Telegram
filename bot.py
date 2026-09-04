"""Bot de Telegram para recordatorios y agenda personal (openclawT)."""

import logging
import os
from datetime import datetime, time
from html import escape

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import storage
from frases import obtener_frase_random
from resumen import buscar_url_wikipedia, extraer_texto_de_url, resumir_texto
from tiempo import ahora_local, interpretar_recordatorio

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


# Estructura del menú de 2 niveles: categoría -> lista de comandos.
CATEGORIAS = {
    "agenda": ("🗓️ AgendaDrac", ["recordar", "lista", "borrar"]),
    "gastos": ("🩸 OrganizadorGastos", ["gasto", "extra", "gastos", "duplicados", "limpiar", "ahorro"]),
    "resumenes": ("📜 ResumenesDrac", ["resumen"]),
}

# Texto de uso/ejemplo que se muestra al elegir un comando puntual.
USO_COMANDOS = {
    "recordar": (
        "/recordar <cuándo> <mensaje> - invoca un recordatorio\n"
        "ej: /recordar mañana a las 3 llamar al banco\n"
        "ej: /recordar en 10 minutos sacar la comida del horno\n"
        "ej: /recordar hoy a las 20:30 tomar la pastilla\n"
        "ej: /recordar el viernes a las 18 reunión\n"
        "ej: /recordar 13 de octubre caminata por Michoacán"
    ),
    "lista": "/lista - revela tus recordatorios pendientes",
    "borrar": "/borrar <id> - destierra un recordatorio",
    "gasto": (
        "/gasto <monto> <descripción> - anota un gasto fijo (agenda semanal)\n"
        "ej: /gasto 500 supermercado"
    ),
    "extra": (
        "/extra <monto> <descripción> - anota un gasto imprevisto\n"
        "ej: /extra 200 arreglo del auto"
    ),
    "gastos": "/gastos - resumen de gastos del mes, fijos y no definidos",
    "duplicados": "/duplicados - borra gastos repetidos (mismo monto, descripción, fecha)",
    "limpiar": (
        "/limpiar <descripción> - borra gastos del mes con esa descripción\n"
        "ej: /limpiar supermercado"
    ),
    "ahorro": "/ahorro - meta de ahorro sugerida según tu historial",
    "resumen": (
        "/resumen <texto, link o tema> - resume un texto, una página web o busca un tema\n"
        "ej: /resumen la primera guerra mundial"
    ),
}

# Comandos que no necesitan datos: se ejecutan directo al tocar el botón.
COMANDOS_SIN_DATOS = {"lista", "gastos", "ahorro", "duplicados"}

# Para los comandos que sí necesitan datos: qué pedirle al usuario que escriba
# (sin la barra "/", porque la respuesta se manda como mensaje de texto normal).
PEDIDO_DATOS = {
    "recordar": (
        "✍️ Escribime <cuándo> <mensaje>\n"
        "ej: mañana a las 3 llamar al banco\n"
        "ej: en 10 minutos sacar la comida del horno\n"
        "ej: hoy a las 20:30 tomar la pastilla\n"
        "ej: el viernes a las 18 reunión\n"
        "ej: 13 de octubre caminata por Michoacán"
    ),
    "borrar": "✍️ Escribime el id del recordatorio a borrar\nej: 3",
    "gasto": "✍️ Escribime <monto> <descripción>\nej: 500 supermercado",
    "extra": "✍️ Escribime <monto> <descripción>\nej: 200 arreglo del auto",
    "limpiar": "✍️ Escribime la descripción a borrar de este mes\nej: supermercado",
    "resumen": "✍️ Escribime el texto, el link o el tema que querés resumir.\nej: la primera guerra mundial",
}


def _teclado_categorias() -> InlineKeyboardMarkup:
    botones = [
        [InlineKeyboardButton(titulo, callback_data=f"cat:{clave}")]
        for clave, (titulo, _) in CATEGORIAS.items()
    ]
    return InlineKeyboardMarkup(botones)


def _teclado_comandos(categoria: str) -> InlineKeyboardMarkup:
    _, comandos = CATEGORIAS[categoria]
    botones = [
        [InlineKeyboardButton(f"/{comando}", callback_data=f"cmd:{categoria}:{comando}")]
        for comando in comandos
    ]
    botones.append([InlineKeyboardButton("⬅️ Menú principal", callback_data="menu")])
    return InlineKeyboardMarkup(botones)


def _teclado_comando(categoria: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Volver", callback_data=f"cat:{categoria}")],
            [InlineKeyboardButton("🏠 Menú principal", callback_data="menu")],
        ]
    )


def _teclado_resumen() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("➖ Más corto", callback_data="resumen:menos"),
            InlineKeyboardButton("➕ Más largo", callback_data="resumen:mas"),
        ]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.registrar_chat(update.effective_chat.id)
    await update.message.reply_text(
        "🧛 He despertado de mi ataúd para servir tus recordatorios, chuladaaaa.\n\n"
        "Elegí una categoría para ver sus comandos:\n\n"
        "🦇 Cada mañana a las 8:00 te mando un reporte con tus pendientes y gastos.\n"
        "🌙 Cada noche a las 22:00 te aviso para que anotes los gastos del día.\n\n"
        f"💬 {obtener_frase_random()}",
        reply_markup=_teclado_categorias(),
    )


class _UpdateDesdeCallback:
    """Envoltorio mínimo para reusar los handlers de comandos al ejecutarlos
    desde un botón en vez de un mensaje /comando real."""

    def __init__(self, query):
        self.message = query.message
        self.effective_chat = query.message.chat


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    datos = query.data

    if datos == "menu":
        await query.edit_message_text(
            "🧛 Elegí una categoría para ver sus comandos:",
            reply_markup=_teclado_categorias(),
        )
        return

    if datos.startswith("cat:"):
        categoria = datos.split(":", 1)[1]
        titulo, _ = CATEGORIAS[categoria]
        await query.edit_message_text(
            f"{titulo}\nElegí un comando:",
            reply_markup=_teclado_comandos(categoria),
        )
        return

    if datos.startswith("cmd:"):
        _, categoria, comando = datos.split(":", 2)

        if comando in COMANDOS_SIN_DATOS:
            # No necesita datos: lo ejecutamos directo y mostramos el resultado real.
            handler = globals()[comando]
            await handler(_UpdateDesdeCallback(query), context)
            await query.edit_message_text(
                f"✅ /{comando} ejecutado (mirá el resultado arriba 👆)",
                reply_markup=_teclado_comando(categoria),
            )
        else:
            # Necesita datos: le pedimos que los escriba y los procesamos en su próximo mensaje.
            context.user_data["esperando_comando"] = comando
            await query.edit_message_text(
                PEDIDO_DATOS[comando],
                reply_markup=_teclado_comando(categoria),
            )
        return

    if datos in ("resumen:mas", "resumen:menos"):
        texto = context.user_data.get("resumen_texto")
        if texto is None:
            await query.edit_message_text("🦇 Ese resumen ya expiró, pedí uno nuevo con /resumen.")
            return

        oraciones = context.user_data.get("resumen_oraciones", 3)
        if datos == "resumen:mas":
            oraciones = min(oraciones + 2, 12)
        else:
            oraciones = max(oraciones - 2, 1)
        context.user_data["resumen_oraciones"] = oraciones

        resultado = resumir_texto(texto, max_oraciones=oraciones)
        await query.edit_message_text(
            f"🧛 En pocas palabras:\n\n{resultado}",
            reply_markup=_teclado_resumen(),
        )
        return


async def manejar_respuesta_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comando = context.user_data.pop("esperando_comando", None)
    if not comando:
        return  # Mensaje de texto normal, no es una respuesta al menú.

    context.args = update.message.text.split()
    handler = globals()[comando]
    await handler(update, context)


async def enviar_recordatorio(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id, recordatorio_id, mensaje = job.data["chat_id"], job.data["id"], job.data["mensaje"]
    await context.bot.send_message(
        chat_id=chat_id, text=f"🧛🦇 Ha llegado la hora... {mensaje}"
    )
    storage.marcar_enviado(recordatorio_id)


def programar_job(app: Application, recordatorio_id: int, chat_id: int, mensaje: str, fecha: datetime):
    app.job_queue.run_once(
        enviar_recordatorio,
        when=fecha,
        data={"id": recordatorio_id, "chat_id": chat_id, "mensaje": mensaje},
        name=str(recordatorio_id),
    )


async def recordar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /recordar <cuándo> <mensaje>\n"
            "ej: /recordar mañana a las 3 llamar al banco\n"
            "ej: /recordar en 10 minutos sacar la comida del horno\n"
            "ej: /recordar el viernes a las 18 reunión\n"
            "ej: /recordar hoy a las 20:30 tomar la pastilla\n"
            "ej: /recordar 13 de octubre caminata por Michoacán"
        )
        return

    texto = " ".join(context.args)
    fecha, mensaje = interpretar_recordatorio(texto)

    if fecha is None:
        await update.message.reply_text(
            "🦇 No entendí cuándo, chuladaaaa. Probá algo como:\n"
            "'mañana a las 3 llamar al banco'\n"
            "'en 10 minutos sacar la comida'\n"
            "'el viernes a las 18 reunión'\n"
            "'13 de octubre caminata por Michoacán'"
        )
        return

    if not mensaje:
        await update.message.reply_text("🦇 Falta el mensaje del recordatorio, chuladaaaa.")
        return

    chat_id = update.effective_chat.id
    recordatorio_id = storage.crear_recordatorio(chat_id, mensaje, fecha)
    programar_job(context.application, recordatorio_id, chat_id, mensaje, fecha)

    await update.message.reply_text(
        f"🧛 Aguardaré en las sombras hasta el {fecha.strftime('%d/%m/%Y %H:%M')} (id {recordatorio_id})."
    )


async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    pendientes = storage.listar_pendientes(chat_id)
    if not pendientes:
        await update.message.reply_text("🦇 Ni un alma pendiente en mi cripta.")
        return

    lineas = ["🧛 Esto es lo que aguarda en las sombras:"]
    lineas += [
        f"#{r['id']} - {datetime.fromisoformat(r['fecha_hora']).strftime('%d/%m/%Y %H:%M')} - {r['mensaje']}"
        for r in pendientes
    ]
    await update.message.reply_text("\n".join(lineas))


async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /borrar <id>")
        return

    try:
        recordatorio_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("🦇 El id tiene que ser un número, chuladaaaa.")
        return

    chat_id = update.effective_chat.id
    if storage.borrar_recordatorio(chat_id, recordatorio_id):
        # Cancela el job programado si todavía no se disparó.
        for job in context.application.job_queue.get_jobs_by_name(str(recordatorio_id)):
            job.schedule_removal()
        await update.message.reply_text(f"🧛 El recordatorio #{recordatorio_id} se ha desvanecido en la niebla.")
    else:
        await update.message.reply_text("🦇 No encuentro ese recordatorio en mi cripta.")


async def _registrar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE, categoria: str, etiqueta: str):
    if len(context.args) < 2:
        await update.message.reply_text(
            f"Uso: /{etiqueta} <monto> <descripción>\nej: /{etiqueta} 500 supermercado"
        )
        return

    try:
        monto = float(context.args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("🦇 El monto tiene que ser un número, chuladaaaa.")
        return

    descripcion = " ".join(context.args[1:])
    chat_id = update.effective_chat.id
    storage.crear_gasto(chat_id, monto, descripcion, categoria=categoria)

    ahora = ahora_local()
    total_mes = storage.total_mes(chat_id, ahora.year, ahora.month)
    await update.message.reply_text(
        f"🩸 Anoté ${monto:.2f} en '{descripcion}' ({categoria}).\n"
        f"Llevás ${total_mes:.2f} gastados este mes."
    )


async def gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _registrar_gasto(update, context, categoria="fijo", etiqueta="gasto")


async def extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _registrar_gasto(update, context, categoria="no definido", etiqueta="extra")


def _bloque_categoria(titulo: str, gastos: list) -> list[str]:
    if not gastos:
        return []
    lineas = [f"\n{titulo}"]
    lineas += [
        f"  • {g['fecha']}  ${g['monto']:>8.2f}  {escape(g['descripcion'])}" for g in gastos
    ]
    subtotal = sum(g["monto"] for g in gastos)
    lineas.append(f"  <i>Subtotal: ${subtotal:.2f}</i>")
    return lineas


async def gastos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ahora = ahora_local()
    gastos = storage.gastos_del_mes(chat_id, ahora.year, ahora.month)
    if not gastos:
        await update.message.reply_text("🦇 Ningún gasto registrado este mes.")
        return

    # gastos_del_mes ya viene ordenado por fecha ascendente.
    fijos = [g for g in gastos if g["categoria"] == "fijo"]
    no_definidos = [g for g in gastos if g["categoria"] != "fijo"]

    lineas = [f"🩸 <b>Gastos de {ahora.strftime('%m/%Y')}</b>"]
    lineas += _bloque_categoria("📅 <b>Fijos</b> (agenda semanal)", fijos)
    lineas += _bloque_categoria("🎲 <b>No definidos</b> (imprevistos)", no_definidos)

    total = sum(g["monto"] for g in gastos)
    lineas.append("\n━━━━━━━━━━━━━━━")
    lineas.append(f"💰 <b>Total del mes: ${total:.2f}</b>")

    await update.message.reply_text("\n".join(lineas), parse_mode="HTML")


async def duplicados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    borrados = storage.eliminar_gastos_duplicados(chat_id)
    if borrados:
        await update.message.reply_text(
            f"🧛 Encontré y desterré {borrados} gasto(s) duplicado(s) de tu cripta."
        )
    else:
        await update.message.reply_text("🦇 No encontré gastos repetidos.")


async def limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "Uso: /limpiar <descripción> - borra los gastos de este mes con esa descripción\n"
            "ej: /limpiar supermercado"
        )
        return

    texto = " ".join(context.args)
    ahora = ahora_local()
    borrados = storage.eliminar_gastos_por_descripcion_mes(chat_id, ahora.year, ahora.month, texto)
    if borrados:
        await update.message.reply_text(
            f"🩸 Desterré {borrados} gasto(s) de '{texto}' de este mes."
        )
    else:
        await update.message.reply_text(f"🦇 No encontré gastos de '{texto}' este mes.")


async def ahorro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ahora = ahora_local()
    mes_actual = f"{ahora.year:04d}-{ahora.month:02d}"
    meses_previos = [m for m in storage.meses_con_gastos(chat_id) if m != mes_actual]

    if not meses_previos:
        await update.message.reply_text(
            "🦇 Todavía no tengo un mes completo de gastos tuyos.\n"
            "Seguí registrando con /gasto y en unas semanas te sugiero una meta de ahorro."
        )
        return

    promedios = [storage.total_mes(chat_id, int(m[:4]), int(m[5:7])) for m in meses_previos]
    promedio = sum(promedios) / len(promedios)
    meta_gasto = promedio * 0.9
    ahorro_sugerido = promedio - meta_gasto
    gastado_este_mes = storage.total_mes(chat_id, ahora.year, ahora.month)
    restante = meta_gasto - gastado_este_mes

    lineas = [
        "🧛 Tu plan de ahorro, basado en tu historial:",
        f"Promedio mensual de gastos: ${promedio:.2f}",
        f"Meta sugerida de gasto: ${meta_gasto:.2f} (10% menos)",
        f"Ahorro sugerido: ${ahorro_sugerido:.2f} por mes",
        f"\nLlevás gastado este mes: ${gastado_este_mes:.2f}",
    ]
    if restante >= 0:
        lineas.append(f"Te quedan ${restante:.2f} dentro de tu meta. 🦇")
    else:
        lineas.append(f"Ya te pasaste de la meta por ${-restante:.2f}. 🩸")

    await update.message.reply_text("\n".join(lineas))


async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /resumen <texto, link o tema>\nej: /resumen la primera guerra mundial")
        return

    entrada = " ".join(context.args)
    max_oraciones = 3

    if entrada.startswith("http://") or entrada.startswith("https://"):
        try:
            texto = extraer_texto_de_url(entrada)
        except requests.RequestException:
            await update.message.reply_text("🦇 No pude leer ese link, chuladaaaa.")
            return

    elif len(entrada.split()) <= 8:
        # Es corto: lo tratamos como un tema y lo busco en Wikipedia, no como texto a resumir.
        try:
            url = buscar_url_wikipedia(entrada)
        except requests.RequestException:
            await update.message.reply_text("🦇 No pude buscar eso, chuladaaaa.")
            return
        if url is None:
            await update.message.reply_text(f"🦇 No encontré nada sobre '{entrada}'.")
            return
        try:
            texto = extraer_texto_de_url(url)
        except requests.RequestException:
            await update.message.reply_text("🦇 Encontré el artículo pero no pude leerlo.")
            return
        max_oraciones = 5

    else:
        texto = entrada
        if len(texto.split()) < 20:
            await update.message.reply_text("🦇 Es muy corto para resumir, ya está resumido.")
            return

    context.user_data["resumen_texto"] = texto
    context.user_data["resumen_oraciones"] = max_oraciones

    resultado = resumir_texto(texto, max_oraciones=max_oraciones)
    await update.message.reply_text(
        f"🧛 En pocas palabras:\n\n{resultado}", reply_markup=_teclado_resumen()
    )


async def resumen_matutino(context: ContextTypes.DEFAULT_TYPE):
    ahora = ahora_local()
    for chat_id in storage.listar_chats():
        pendientes = storage.listar_pendientes(chat_id)
        gastado = storage.total_mes(chat_id, ahora.year, ahora.month)

        lineas = [f"🧛 Reporte del {ahora.strftime('%d/%m/%Y')}:"]
        if pendientes:
            lineas.append(f"\n📌 Recordatorios pendientes ({len(pendientes)}):")
            lineas += [
                f"  #{r['id']} - {datetime.fromisoformat(r['fecha_hora']).strftime('%d/%m %H:%M')} - {r['mensaje']}"
                for r in pendientes[:5]
            ]
        else:
            lineas.append("\n📌 Sin recordatorios pendientes.")

        lineas.append(f"\n🩸 Gastado este mes: ${gastado:.2f}")
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lineas))


async def aviso_nocturno(context: ContextTypes.DEFAULT_TYPE):
    ahora = ahora_local()
    fecha_hoy = ahora.date().isoformat()
    for chat_id in storage.listar_chats():
        gastos_hoy = storage.gastos_del_dia(chat_id, fecha_hoy)

        lineas = ["🌙🧛 Antes de dormir... ¿anotaste todos tus gastos de hoy?"]
        if gastos_hoy:
            total_hoy = sum(g["monto"] for g in gastos_hoy)
            lineas.append(f"\nHoy llevás registrado: ${total_hoy:.2f}")
            lineas += [f"  - ${g['monto']:.2f} - {g['descripcion']}" for g in gastos_hoy]
            lineas.append("\nSi te falta alguno, usá /gasto o /extra antes de dormir.")
        else:
            lineas.append("\n🦇 No tenés ningún gasto anotado hoy. Usá /gasto o /extra.")

        await context.bot.send_message(chat_id=chat_id, text="\n".join(lineas))


def reprogramar_pendientes(app: Application):
    # Al reiniciar el bot, los jobs en memoria se pierden: hay que recrearlos desde la DB.
    ahora = ahora_local()
    for r in storage.listar_todos_pendientes():
        fecha = datetime.fromisoformat(r["fecha_hora"])
        if fecha.tzinfo is None:
            # Recordatorios creados antes de que las fechas fueran timezone-aware.
            fecha = fecha.replace(tzinfo=ahora.tzinfo)
        if fecha <= ahora:
            fecha = ahora  # se dispara casi de inmediato en vez de perderse
        programar_job(app, r["id"], r["chat_id"], r["mensaje"], fecha)


def main():
    if not TOKEN:
        raise SystemExit(
            "Falta TELEGRAM_BOT_TOKEN. Copiá .env.example a .env y completá tu token de BotFather."
        )

    storage.inicializar_db()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("recordar", recordar))
    app.add_handler(CommandHandler("lista", lista))
    app.add_handler(CommandHandler("borrar", borrar))
    app.add_handler(CommandHandler("gasto", gasto))
    app.add_handler(CommandHandler("extra", extra))
    app.add_handler(CommandHandler("gastos", gastos))
    app.add_handler(CommandHandler("duplicados", duplicados))
    app.add_handler(CommandHandler("limpiar", limpiar))
    app.add_handler(CommandHandler("ahorro", ahorro))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_respuesta_menu))

    reprogramar_pendientes(app)
    app.job_queue.run_daily(
        resumen_matutino, time=time(hour=8, minute=0, tzinfo=ahora_local().tzinfo)
    )
    app.job_queue.run_daily(
        aviso_nocturno, time=time(hour=22, minute=0, tzinfo=ahora_local().tzinfo)
    )

    logger.info("Bot iniciado, esperando mensajes...")
    app.run_polling()


if __name__ == "__main__":
    main()
