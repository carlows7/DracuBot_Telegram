"""Tests del banco de frases random."""

from frases import FRASES, obtener_frase_random


def test_hay_variedad_de_frases():
    assert len(FRASES) >= 79


def test_obtener_frase_devuelve_algo_de_la_lista():
    for _ in range(20):
        assert obtener_frase_random() in FRASES
