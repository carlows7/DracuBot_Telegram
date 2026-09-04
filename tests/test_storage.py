"""Tests de persistencia: recordatorios, gastos, racha y logros."""

from datetime import datetime, timedelta

import storage
from tiempo import ahora_local

CHAT = 999


def test_crear_listar_borrar_recordatorio():
    rid = storage.crear_recordatorio(CHAT, "probar cosas", ahora_local() + timedelta(hours=1))
    assert isinstance(rid, int) and rid > 0

    pendientes = storage.listar_pendientes(CHAT)
    assert len(pendientes) == 1
    assert pendientes[0]["mensaje"] == "probar cosas"

    assert storage.borrar_recordatorio(CHAT, rid) is True
    assert storage.listar_pendientes(CHAT) == []


def test_editar_recordatorio():
    rid = storage.crear_recordatorio(CHAT, "original", ahora_local() + timedelta(hours=1))
    nueva_fecha = ahora_local() + timedelta(hours=2)
    assert storage.editar_recordatorio(CHAT, rid, "editado", nueva_fecha) is True
    assert storage.listar_pendientes(CHAT)[0]["mensaje"] == "editado"


def test_recordatorio_recurrente_no_se_duplica_al_reprogramar():
    proxima = ahora_local() + timedelta(hours=1)
    storage.crear_recordatorio_recurrente(CHAT, "tomar la pastilla", proxima, "diario", 8, 0)

    # No debe aparecer en listar_todos_pendientes (evita re-agendarlo dos veces).
    assert storage.listar_todos_pendientes() == []
    # Pero sí en listar_pendientes, para que /lista lo muestre.
    assert len(storage.listar_pendientes(CHAT)) == 1
    assert len(storage.listar_recurrentes()) == 1


def test_gastos_suma_duplicados_y_limpieza():
    ahora = ahora_local()
    fecha = f"{ahora.year:04d}-{ahora.month:02d}-01"
    storage.crear_gasto(CHAT, 500, "supermercado", categoria="fijo", fecha=fecha)
    storage.crear_gasto(CHAT, 500, "supermercado", categoria="fijo", fecha=fecha)  # duplicado
    storage.crear_gasto(CHAT, 200, "arreglo del auto", categoria="no definido", fecha=fecha)

    assert len(storage.gastos_del_mes(CHAT, ahora.year, ahora.month)) == 3
    assert storage.total_mes(CHAT, ahora.year, ahora.month) == 1200

    assert storage.eliminar_gastos_duplicados(CHAT) == 1
    assert len(storage.gastos_del_mes(CHAT, ahora.year, ahora.month)) == 2

    assert storage.eliminar_gastos_por_descripcion_mes(CHAT, ahora.year, ahora.month, "supermercado") == 1
    restantes = storage.gastos_del_mes(CHAT, ahora.year, ahora.month)
    assert len(restantes) == 1
    assert restantes[0]["descripcion"] == "arreglo del auto"


def test_editar_gasto():
    gid = storage.crear_gasto(CHAT, 100, "gasto original")
    assert storage.editar_gasto(CHAT, gid, 250, "gasto editado") is True

    ahora = ahora_local()
    gasto = storage.gastos_del_mes(CHAT, ahora.year, ahora.month)[0]
    assert gasto["monto"] == 250
    assert gasto["descripcion"] == "gasto editado"

    assert storage.editar_gasto(CHAT, 999999, 1, "no existe") is False


def test_racha_y_logros():
    hoy = datetime.now().date()
    for i in range(1, 4):
        storage.crear_gasto(CHAT, 10, "test", fecha=(hoy - timedelta(days=i)).isoformat())

    assert storage.racha_actual(CHAT) == 3  # sin anotar hoy todavía

    storage.crear_gasto(CHAT, 10, "test hoy", fecha=hoy.isoformat())
    assert storage.racha_actual(CHAT) == 4

    assert storage.registrar_logro(CHAT, "racha", 3) is True
    assert storage.registrar_logro(CHAT, "racha", 3) is False  # no duplica el aviso
    assert storage.ya_tiene_logro(CHAT, "racha", 3) is True
