"""Resumidor extractivo simple: puntúa oraciones por frecuencia de palabras
y devuelve las más relevantes, sin depender de ninguna IA externa."""

import re
from collections import Counter

import requests
from bs4 import BeautifulSoup

STOPWORDS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las",
    "por", "un", "para", "con", "no", "una", "su", "al", "lo", "como",
    "más", "pero", "sus", "le", "ya", "o", "este", "sí", "porque", "esta",
    "entre", "cuando", "muy", "sin", "sobre", "también", "me", "hasta",
    "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos",
    "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos",
    "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo", "otro",
    "otras", "otra", "él", "tanto", "esa", "estos", "mucho", "quienes",
    "nada", "muchos", "cual", "poco", "ella", "estar", "estas", "algunas",
    "algo", "nosotros", "es", "son", "fue", "ser", "han", "está",
}


def resumir_texto(texto: str, max_oraciones: int = 3) -> str:
    todas = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto.strip()) if o.strip()]
    # Descarta fragmentos muy cortos (citas, referencias) que no sirven como resumen.
    oraciones = [o for o in todas if len(o.split()) >= 6] or todas
    if len(oraciones) <= max_oraciones:
        return " ".join(oraciones)

    palabras = re.findall(r"\b\w+\b", texto.lower())
    frecuencias = Counter(p for p in palabras if p not in STOPWORDS and len(p) > 2)

    puntajes = []
    for indice, oracion in enumerate(oraciones):
        palabras_oracion = re.findall(r"\b\w+\b", oracion.lower())
        if not palabras_oracion:
            continue
        puntaje = sum(frecuencias.get(p, 0) for p in palabras_oracion) / len(palabras_oracion)
        puntajes.append((puntaje, indice, oracion))

    mejores = sorted(puntajes, key=lambda x: x[0], reverse=True)[:max_oraciones]
    mejores_en_orden = sorted(mejores, key=lambda x: x[1])
    return " ".join(oracion for _, _, oracion in mejores_en_orden)


def extraer_texto_de_url(url: str) -> str:
    respuesta = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    respuesta.raise_for_status()
    sopa = BeautifulSoup(respuesta.text, "html.parser")
    for etiqueta in sopa(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        etiqueta.decompose()

    # Los párrafos <p> son el cuerpo real del artículo: evita notas al pie,
    # listas de referencias y menús que ensucian el resumen.
    parrafos = [p.get_text(separator=" ") for p in sopa.find_all("p")]
    texto = " ".join(parrafos) if parrafos else sopa.get_text(separator=" ")
    return re.sub(r"\s+", " ", texto).strip()


def buscar_url_wikipedia(tema: str) -> str | None:
    """Busca el artículo de Wikipedia en español que mejor matchea el tema.
    Devuelve la URL del artículo, o None si no encontró nada."""
    respuesta = requests.get(
        "https://es.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": tema,
            "srlimit": 1,
            "format": "json",
        },
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    respuesta.raise_for_status()
    resultados = respuesta.json().get("query", {}).get("search", [])
    if not resultados:
        return None

    titulo = resultados[0]["title"].replace(" ", "_")
    return f"https://es.wikipedia.org/wiki/{titulo}"
