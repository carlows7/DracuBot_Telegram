"""Persistencia de recordatorios en SQLite, para que sobrevivan a reinicios del bot."""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent / "recordatorios.db"))


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db():
    with conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                mensaje TEXT NOT NULL,
                fecha_hora TEXT NOT NULL,
                enviado INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                monto REAL NOT NULL,
                descripcion TEXT NOT NULL,
                fecha TEXT NOT NULL,
                categoria TEXT NOT NULL DEFAULT 'fijo'
            )
            """
        )
        columnas = [f["name"] for f in conn.execute("PRAGMA table_info(gastos)").fetchall()]
        if "categoria" not in columnas:
            # Compatibilidad con bases creadas antes de agregar categorías.
            conn.execute("ALTER TABLE gastos ADD COLUMN categoria TEXT NOT NULL DEFAULT 'fijo'")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                valor INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                UNIQUE(chat_id, tipo, valor)
            )
            """
        )


def crear_recordatorio(chat_id: int, mensaje: str, fecha_hora: datetime) -> int:
    with conectar() as conn:
        cursor = conn.execute(
            "INSERT INTO recordatorios (chat_id, mensaje, fecha_hora) VALUES (?, ?, ?)",
            (chat_id, mensaje, fecha_hora.isoformat()),
        )
        return cursor.lastrowid


def listar_pendientes(chat_id: int) -> list[sqlite3.Row]:
    with conectar() as conn:
        return conn.execute(
            "SELECT * FROM recordatorios WHERE chat_id = ? AND enviado = 0 ORDER BY fecha_hora",
            (chat_id,),
        ).fetchall()


def listar_todos_pendientes() -> list[sqlite3.Row]:
    # Se usa al arrancar el bot para reprogramar los recordatorios que quedaron pendientes.
    with conectar() as conn:
        return conn.execute(
            "SELECT * FROM recordatorios WHERE enviado = 0 ORDER BY fecha_hora"
        ).fetchall()


def marcar_enviado(recordatorio_id: int):
    with conectar() as conn:
        conn.execute(
            "UPDATE recordatorios SET enviado = 1 WHERE id = ?", (recordatorio_id,)
        )


def borrar_recordatorio(chat_id: int, recordatorio_id: int) -> bool:
    with conectar() as conn:
        cursor = conn.execute(
            "DELETE FROM recordatorios WHERE id = ? AND chat_id = ?",
            (recordatorio_id, chat_id),
        )
        return cursor.rowcount > 0


def registrar_chat(chat_id: int):
    # Guarda el chat para poder mandarle el resumen matutino automático.
    with conectar() as conn:
        conn.execute("INSERT OR IGNORE INTO chats (chat_id) VALUES (?)", (chat_id,))


def listar_chats() -> list[int]:
    with conectar() as conn:
        return [r["chat_id"] for r in conn.execute("SELECT chat_id FROM chats").fetchall()]


def crear_gasto(
    chat_id: int, monto: float, descripcion: str, categoria: str = "fijo", fecha: str | None = None
) -> int:
    fecha = fecha or datetime.now().date().isoformat()
    with conectar() as conn:
        cursor = conn.execute(
            "INSERT INTO gastos (chat_id, monto, descripcion, fecha, categoria) VALUES (?, ?, ?, ?, ?)",
            (chat_id, monto, descripcion, fecha, categoria),
        )
        return cursor.lastrowid


def gastos_del_mes(chat_id: int, anio: int, mes: int) -> list[sqlite3.Row]:
    patron = f"{anio:04d}-{mes:02d}%"
    with conectar() as conn:
        return conn.execute(
            "SELECT * FROM gastos WHERE chat_id = ? AND fecha LIKE ? ORDER BY fecha",
            (chat_id, patron),
        ).fetchall()


def gastos_del_dia(chat_id: int, fecha: str) -> list[sqlite3.Row]:
    with conectar() as conn:
        return conn.execute(
            "SELECT * FROM gastos WHERE chat_id = ? AND fecha = ? ORDER BY id",
            (chat_id, fecha),
        ).fetchall()


def total_mes(chat_id: int, anio: int, mes: int) -> float:
    return sum(g["monto"] for g in gastos_del_mes(chat_id, anio, mes))


def meses_con_gastos(chat_id: int) -> list[str]:
    # Devuelve los meses (formato "aaaa-mm") en los que hay al menos un gasto registrado.
    with conectar() as conn:
        filas = conn.execute(
            "SELECT DISTINCT substr(fecha, 1, 7) AS mes FROM gastos WHERE chat_id = ? ORDER BY mes",
            (chat_id,),
        ).fetchall()
    return [f["mes"] for f in filas]


def eliminar_gastos_duplicados(chat_id: int) -> int:
    # Considera duplicado un gasto con el mismo monto, descripción, fecha y categoría.
    # Conserva el más antiguo (id más chico) de cada grupo y borra el resto.
    with conectar() as conn:
        cursor = conn.execute(
            """
            DELETE FROM gastos
            WHERE chat_id = ? AND id NOT IN (
                SELECT MIN(id) FROM gastos
                WHERE chat_id = ?
                GROUP BY monto, descripcion, fecha, categoria
            )
            """,
            (chat_id, chat_id),
        )
        return cursor.rowcount


def eliminar_gastos_por_descripcion_mes(chat_id: int, anio: int, mes: int, texto: str) -> int:
    patron_mes = f"{anio:04d}-{mes:02d}%"
    patron_texto = f"%{texto}%"
    with conectar() as conn:
        cursor = conn.execute(
            "DELETE FROM gastos WHERE chat_id = ? AND fecha LIKE ? AND descripcion LIKE ? COLLATE NOCASE",
            (chat_id, patron_mes, patron_texto),
        )
        return cursor.rowcount


def fechas_con_gasto(chat_id: int) -> set[str]:
    with conectar() as conn:
        filas = conn.execute(
            "SELECT DISTINCT fecha FROM gastos WHERE chat_id = ?", (chat_id,)
        ).fetchall()
    return {f["fecha"] for f in filas}


def racha_actual(chat_id: int) -> int:
    # Días consecutivos (terminando hoy o ayer) con al menos un gasto anotado.
    # Si hoy todavía no anotó nada, la racha no se corta todavía: se cuenta desde ayer.
    fechas = fechas_con_gasto(chat_id)
    cursor = datetime.now().date()
    if cursor.isoformat() not in fechas:
        cursor -= timedelta(days=1)

    racha = 0
    while cursor.isoformat() in fechas:
        racha += 1
        cursor -= timedelta(days=1)
    return racha


def contar_gastos_totales(chat_id: int) -> int:
    with conectar() as conn:
        fila = conn.execute(
            "SELECT COUNT(*) AS total FROM gastos WHERE chat_id = ?", (chat_id,)
        ).fetchone()
    return fila["total"]


def ya_tiene_logro(chat_id: int, tipo: str, valor: int) -> bool:
    with conectar() as conn:
        fila = conn.execute(
            "SELECT 1 FROM logros WHERE chat_id = ? AND tipo = ? AND valor = ?",
            (chat_id, tipo, valor),
        ).fetchone()
    return fila is not None


def registrar_logro(chat_id: int, tipo: str, valor: int) -> bool:
    # Devuelve True solo si es la primera vez que se desbloquea (para no avisar repetido).
    with conectar() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO logros (chat_id, tipo, valor, fecha) VALUES (?, ?, ?, ?)",
            (chat_id, tipo, valor, datetime.now().isoformat()),
        )
        return cursor.rowcount > 0


def listar_logros(chat_id: int) -> list[sqlite3.Row]:
    with conectar() as conn:
        return conn.execute(
            "SELECT * FROM logros WHERE chat_id = ? ORDER BY tipo, valor", (chat_id,)
        ).fetchall()
