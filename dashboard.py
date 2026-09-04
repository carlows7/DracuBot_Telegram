"""Dashboard web local: un panel en el navegador con gráficos de tus gastos.

Corre solo en tu compu (127.0.0.1), no se expone a internet. Se abre con:

    python3 dashboard.py

y después andá a http://127.0.0.1:5050 en el navegador.
"""

import base64
import io

import matplotlib

matplotlib.use("Agg")  # sin ventana, solo generar imágenes
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from flask import Flask, render_template_string

load_dotenv()

import storage
from tiempo import ahora_local

app = Flask(__name__)

COLOR_FONDO = "#1e1922"
COLOR_TEXTO = "#ece6ea"
COLOR_MUTED = "#a99cae"
COLOR_BORDE = "#35293a"
COLOR_ACENTO = "#240b94"
COLOR_ACENTO2 = "#b21313"

PLANTILLA = """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Dashboard de Draculin</title>
<style>
  body {
    background: #16131b;
    color: #ece6ea;
    font-family: -apple-system, "Segoe UI", sans-serif;
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
  }
  h1 { color: #c92f52; margin-bottom: 0.2rem; }
  .subtitulo { color: #a99cae; margin-top: 0; }
  .tarjetas { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.5rem 0; }
  .tarjeta {
    background: #1e1922;
    border: 1px solid #35293a;
    border-radius: 8px;
    padding: 1rem 1.4rem;
    flex: 1;
    min-width: 160px;
  }
  .tarjeta .valor { font-size: 1.8rem; font-weight: 600; color: #c9a24b; }
  .tarjeta .etiqueta { color: #a99cae; font-size: 0.85rem; }
  .graficos { display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1.5rem 0; }
  .graficos img { max-width: 100%; border-radius: 8px; }
  h2 { color: #ece6ea; border-bottom: 1px solid #35293a; padding-bottom: 0.4rem; }
  ul { padding-left: 1.2rem; color: #d8cdd0; }
  li { margin-bottom: 0.3rem; }
  .vacio { color: #a99cae; font-style: italic; }
</style>
</head>
<body>
  <h1>🧛 Dashboard de Draculin</h1>
  <p class="subtitulo">Reporte de {{ mes }}</p>

  <div class="tarjetas">
    <div class="tarjeta">
      <div class="valor">${{ '%.2f'|format(total_mes) }}</div>
      <div class="etiqueta">Gastado este mes</div>
    </div>
    <div class="tarjeta">
      <div class="valor">🔥 {{ racha }}</div>
      <div class="etiqueta">Días seguidos anotando</div>
    </div>
    <div class="tarjeta">
      <div class="valor">🏆 {{ logros|length }}</div>
      <div class="etiqueta">Logros desbloqueados</div>
    </div>
    <div class="tarjeta">
      <div class="valor">📌 {{ pendientes|length }}</div>
      <div class="etiqueta">Recordatorios pendientes</div>
    </div>
  </div>

  <div class="graficos">
    <div>
      <h2>Gasto por día</h2>
      {% if grafico_dia %}
        <img src="data:image/png;base64,{{ grafico_dia }}">
      {% else %}
        <p class="vacio">Sin gastos registrados este mes.</p>
      {% endif %}
    </div>
    <div>
      <h2>Fijos vs. no definidos</h2>
      <img src="data:image/png;base64,{{ grafico_cat }}">
    </div>
  </div>

  <h2>Recordatorios pendientes</h2>
  {% if pendientes %}
    <ul>
    {% for r in pendientes %}
      <li>#{{ r['id'] }} — {{ r['fecha_hora'][:16] }} — {{ r['mensaje'] }}</li>
    {% endfor %}
    </ul>
  {% else %}
    <p class="vacio">Ni un alma pendiente en la cripta.</p>
  {% endif %}

  <h2>Logros desbloqueados</h2>
  {% if logros %}
    <ul>
    {% for l in logros %}
      {% if l['tipo'] == 'racha' %}
        <li>🔥 {{ l['valor'] }} días seguidos</li>
      {% else %}
        <li>🏆 {{ l['valor'] }} gastos registrados</li>
      {% endif %}
    {% endfor %}
    </ul>
  {% else %}
    <p class="vacio">Todavía no hay logros desbloqueados.</p>
  {% endif %}

</body>
</html>
"""


def _grafico_a_base64(fig) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def _estilizar_ejes(ax):
    ax.set_facecolor(COLOR_FONDO)
    ax.tick_params(colors=COLOR_MUTED)
    for spine in ax.spines.values():
        spine.set_color(COLOR_BORDE)
    ax.title.set_color(COLOR_TEXTO)
    ax.yaxis.label.set_color(COLOR_MUTED)
    ax.xaxis.label.set_color(COLOR_MUTED)


def _grafico_gastos_por_dia(chat_id: int, anio: int, mes: int) -> str | None:
    gastos = storage.gastos_del_mes(chat_id, anio, mes)
    if not gastos:
        return None

    por_dia: dict[str, float] = {}
    for g in gastos:
        dia = g["fecha"][8:10]
        por_dia[dia] = por_dia.get(dia, 0) + g["monto"]

    dias = sorted(por_dia)
    montos = [por_dia[d] for d in dias]

    fig, ax = plt.subplots(figsize=(6.5, 3.2), facecolor=COLOR_FONDO)
    _estilizar_ejes(ax)
    ax.bar(dias, montos, color=COLOR_ACENTO)
    ax.set_ylabel("USD")
    return _grafico_a_base64(fig)


def _grafico_categorias(chat_id: int, anio: int, mes: int) -> str:
    gastos = storage.gastos_del_mes(chat_id, anio, mes)
    fijos = sum(g["monto"] for g in gastos if g["categoria"] == "fijo")
    no_definidos = sum(g["monto"] for g in gastos if g["categoria"] != "fijo")

    fig, ax = plt.subplots(figsize=(3.6, 3.2), facecolor=COLOR_FONDO)
    ax.set_facecolor(COLOR_FONDO)
    if fijos or no_definidos:
        ax.pie(
            [fijos, no_definidos],
            labels=["Fijos", "No definidos"],
            colors=[COLOR_ACENTO, COLOR_ACENTO2],
            autopct="%1.0f%%",
            textprops={"color": COLOR_TEXTO},
        )
    else:
        ax.text(0.5, 0.5, "Sin datos", ha="center", va="center", color=COLOR_MUTED)
        ax.axis("off")
    return _grafico_a_base64(fig)


@app.route("/")
def index():
    chats = storage.listar_chats()
    if not chats:
        return "No hay ningún chat registrado todavía. Mandale /start al bot en Telegram primero."

    chat_id = chats[0]
    ahora = ahora_local()

    return render_template_string(
        PLANTILLA,
        mes=ahora.strftime("%m/%Y"),
        total_mes=storage.total_mes(chat_id, ahora.year, ahora.month),
        racha=storage.racha_actual(chat_id),
        logros=storage.listar_logros(chat_id),
        pendientes=storage.listar_pendientes(chat_id),
        grafico_dia=_grafico_gastos_por_dia(chat_id, ahora.year, ahora.month),
        grafico_cat=_grafico_categorias(chat_id, ahora.year, ahora.month),
    )


def main():
    print("🧛 Dashboard corriendo en http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
