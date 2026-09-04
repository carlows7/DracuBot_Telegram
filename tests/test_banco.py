"""Tests del sistema de bancos: registro multi-banco + adaptador de Cuscatlán."""

import bancos
from bancos import cuscatlan

DEPOSITO = """TRANSACCIÓN EXITOSA
Buen día, CARLOS ALESSANDRO DURAN

Le informamos que ha recibido un abono a su CUENTA DE AHORRO X8878.

Banco origen:
B. AGRICOLA

Originado por:
CARLOS ERNESTO DURAN CHAVEZ

Monto:
USD60.00

Fecha y hora:
29/08/2026 01:54:32 P.M.

No Referencia:
VPE459225528100000000112429554
"""

COMPRA = (
    "Estimado Señor/Señora: CARLOS DURAN\n"
    "Le informamos que se hizo un consumo con tarjeta de débito en su cuenta "
    "XXXXXXXXXX8878 por USD3.85 el día 2026-09-01 22:07."
)

RETIRO = (
    "Hola, Carlos\n"
    "El código generado para retiro de efectivo sin Tarjeta es el siguiente:\n"
    "Código de retiro\n5808623\nVigencia de código\n2 Horas\n"
    "Fecha y hora\n01/09/2026 21:45:34"
)

INICIO_SESION = (
    "Hola, Carlos\n"
    "Le notificamos que se ha iniciado una sesión con su usuario de Banca Digital.\n"
    "Detalles de la sesión\nFecha de inicio:\n04/09/2026 12:18:53\n"
    "Dirección IP:\n179.5.155.29\nInformación del navegador:\nAPP - iPhone 13 - iOS 26.6"
)


def test_registro_conoce_cuscatlan():
    assert "notificaciones@bancocuscatlan.com" in bancos.todos_los_remitentes()
    assert bancos.adaptador_para("notificaciones@bancocuscatlan.com") is cuscatlan
    assert bancos.adaptador_para("otro@banco-desconocido.com") is None


def test_parsea_deposito_recibido():
    r = cuscatlan.parsear("TRANSACCIÓN EXITOSA", DEPOSITO)
    assert r["tipo"] == "deposito_recibido"
    assert r["monto"] == "USD60.00"
    assert r["contraparte"] == "CARLOS ERNESTO DURAN CHAVEZ"
    assert r["banco"] == "Banco Cuscatlán"


def test_parsea_compra():
    r = cuscatlan.parsear("Alerta de compra con Tarjeta de Debito mayor a", COMPRA)
    assert r["tipo"] == "compra"
    assert r["monto"] == "USD3.85"


def test_parsea_retiro_sin_tarjeta():
    r = cuscatlan.parsear("Retiro sin tarjeta", RETIRO)
    assert r["tipo"] == "retiro_sin_tarjeta"
    assert r["codigo_retiro"] == "5808623"


def test_parsea_inicio_sesion():
    r = cuscatlan.parsear("Nuevo inicio de sesión", INICIO_SESION)
    assert r["tipo"] == "inicio_sesion"
    assert r["ip"] == "179.5.155.29"
