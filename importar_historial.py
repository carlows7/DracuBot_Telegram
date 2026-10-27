"""Carga UNA vez el historial de movimientos desde los correos del banco que
ya están en tu Gmail, para que /mes y el resumen de fin de mes tengan también
los meses anteriores. Es de solo lectura sobre Gmail (no marca nada como
leído) y se puede correr más de una vez: los correos ya guardados se saltan.

Uso:  python3 importar_historial.py"""

import logging

from dotenv import load_dotenv

load_dotenv()

import movimientos
import storage
from banco import leer_historial

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)


def main():
    storage.inicializar_db()
    leidos = nuevos = 0
    for n in leer_historial():
        leidos += 1
        aviso = movimientos.extraer(n)
        if aviso and storage.guardar_movimiento(aviso):
            nuevos += 1
        if leidos % 50 == 0:
            logging.info("Leídos %d correos, %d movimientos nuevos", leidos, nuevos)
    logging.info("Listo: %d correos leídos, %d movimientos guardados.", leidos, nuevos)


if __name__ == "__main__":
    main()
