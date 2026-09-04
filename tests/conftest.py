"""Configuración compartida de pytest: usa una base de datos temporal para
que los tests nunca toquen recordatorios.db real."""

import os
import sys
import tempfile
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO))

# Tiene que fijarse ANTES de importar storage: DB_PATH se lee una sola vez,
# al importar el módulo.
_db_fd, _DB_PATH_TEST = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DB_PATH"] = _DB_PATH_TEST
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "0:token-de-prueba")

import pytest

import storage

TABLAS = ("recordatorios", "gastos", "logros", "chats")


@pytest.fixture(autouse=True)
def _base_de_datos_limpia():
    """Cada test arranca con las tablas vacías, para que no se pisen entre sí."""
    storage.inicializar_db()
    with storage.conectar() as conn:
        for tabla in TABLAS:
            conn.execute(f"DELETE FROM {tabla}")
    yield
