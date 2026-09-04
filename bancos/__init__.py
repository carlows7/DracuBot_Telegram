"""Registro de bancos soportados.

Para agregar un banco nuevo:
1. Creá un archivo acá adentro (ej. bancos/agricola.py) con REMITENTE, NOMBRE
   y una función parsear(asunto, cuerpo) -> dict, igual que cuscatlan.py.
2. Importalo abajo y agregalo a la lista MODULOS.

El motor de banco.py no necesita cambios: detecta el banco automáticamente
según la dirección de correo remitente de cada notificación.
"""

from . import cuscatlan

MODULOS = [cuscatlan]

REGISTRO = {modulo.REMITENTE.lower(): modulo for modulo in MODULOS}


def adaptador_para(remitente: str):
    return REGISTRO.get(remitente.lower())


def todos_los_remitentes() -> list[str]:
    return list(REGISTRO.keys())
