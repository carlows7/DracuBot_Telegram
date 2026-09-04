"""Tests del resumidor extractivo (sin red, sin costo)."""

from resumen import resumir_texto

TEXTO_LARGO = (
    "El café es una de las bebidas más consumidas del mundo. "
    "Se produce a partir de las semillas tostadas del cafeto. "
    "Existen muchas variedades, siendo la arábica y la robusta las más comunes. "
    "El proceso de tostado influye mucho en el sabor final. "
    "Argentina y México consumen grandes cantidades de café cada año. "
    "Los estudios muestran que el consumo moderado puede tener beneficios. "
    "Sin embargo, el exceso puede causar insomnio y ansiedad."
)


def test_resumir_texto_devuelve_menos_oraciones():
    resumen = resumir_texto(TEXTO_LARGO, max_oraciones=2)
    assert resumen
    assert len(resumen) < len(TEXTO_LARGO)
    assert resumen.count(".") <= 3


def test_resumir_texto_corto_lo_devuelve_igual():
    corto = "Una sola oración."
    assert resumir_texto(corto, max_oraciones=3) == corto
