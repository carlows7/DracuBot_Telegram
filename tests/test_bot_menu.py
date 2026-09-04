"""Verifica que el menú de botones (categorías/comandos) esté bien armado:
todo comando referenciado tiene una función real y su texto de ayuda."""

import bot


def _todos_los_comandos():
    comandos = set()
    for _titulo, lista in bot.CATEGORIAS.values():
        comandos.update(lista)
    return comandos


def test_todos_los_comandos_mapean_a_una_funcion():
    for comando in _todos_los_comandos():
        assert callable(bot.__dict__.get(comando)), f"falta la función '{comando}'"


def test_comandos_sin_datos_tienen_texto_de_uso():
    assert bot.COMANDOS_SIN_DATOS.issubset(set(bot.USO_COMANDOS.keys()))


def test_comandos_con_datos_tienen_prompt_de_pedido():
    con_datos = _todos_los_comandos() - bot.COMANDOS_SIN_DATOS
    assert con_datos.issubset(set(bot.PEDIDO_DATOS.keys()))
