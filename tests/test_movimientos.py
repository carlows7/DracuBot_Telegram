"""Tests del registro de movimientos: parseo de cada aviso, consolidación de
duplicados, almacenamiento y el comando /mes."""

from datetime import datetime

import bot
import movimientos
import storage
from bancos import cuscatlan

CREDITO = (
    "Estimado Señor/Señora: CARLOS ALESSANDRO DURAN ORELLANA\n"
    "Le informamos que se ha recibido un crédito en su cuenta XXXXXXXXXX8878 por\n"
    "USD 3.00 el día 2026-08-11 23:19.\nPara cualquier duda..."
)
DEBITO = (
    "Estimado Señor/Señora: CARLOS DURAN\n"
    "Le informamos que se hizo un débito en su cuenta XXXXXXXXXX8878 por USD5.00 el día 2026-08-12 16:20.\n"
)
COMPRA = (
    "Le informamos que se hizo un consumo con tarjeta de débito en su cuenta "
    "XXXXXXXXXX8878 por USD5.00 el día 2026-08-12 16:20."
)
PROCESO = """Transferencias
Transfer365
Hola, Carlos Alessandro
Le informamos que el resultado de la transferencia
está:
en proceso.
Cuenta origen
Carlos Duran
***********8878
Cuenta de Ahorro - Banco Cuscatlan
Cuenta destino
Erika Argueta
******1880
BANCO AGRICOLA
Monto
$25.00
Tipo
Transferencia a Cuenta de Ahorro
Fecha y hora
02/08/2026 19:26:14
"""
EXITOSA = """TRANSACCIÓN EXITOSA
Buen día,
Carlos Alessandro
Le informamos el resultado de su operación
Transfer365
Banco Destino:
BANCO AGRICOLA
Beneficiario:
Erika
Monto:
25.00
Fecha y hora:
02/08/2026 07:26:20 P.M.
No Referencia:
BACUS123
"""
RECHAZADA = """TRANSACCIÓN RECHAZADA
Hola, Carlos Alessandro
Transfer365
Monto:
10.00
Fecha y hora:
20/02/2026 12:22:13 A.M.
Motivo de Rechazo:
SV04-COINCIDENCIA EN LISTAS NEGRAS
"""
ABONO = """TRANSACCIÓN EXITOSA
Buen día, CARLOS ALESSANDRO

Le informamos que ha recibido un abono a su CUENTA DE AHORRO X8878 en concepto de
Transfer365

Banco origen:
B. AGRICOLA

Monto:
USD60.00

Fecha y hora:
29/08/2026 01:54:32 P.M.
"""
RETIRO = (
    "Hola, Carlos Alessandro\nEl código generado para retiro de efectivo sin Tarjeta es el siguiente:\n"
    "Código de retiro\n5808623\nVigencia de código\n2 Horas\nFecha y hora\n07/08/2026 20:21:23"
)


def _n(asunto, cuerpo, i):
    n = cuscatlan.parsear(asunto, cuerpo)
    n["message_id"] = f"m{i}"
    n["fecha_correo"] = "2026-08-30"
    return movimientos.extraer(n)


def test_parsea_credito_y_debito():
    c = cuscatlan.parsear("Ha recibido un Deposito a cuenta", CREDITO)
    assert (c["tipo"], c["monto_num"], c["cuenta"], c["fecha"]) == ("credito_recibido", 3.0, "8878", "2026-08-11")
    d = cuscatlan.parsear("Cargo a su cuenta CUSCATLAN mayor a", DEBITO)
    assert (d["tipo"], d["monto_num"], d["fecha"]) == ("debito_cuenta", 5.0, "2026-08-12")


def test_parsea_transferencias():
    p = cuscatlan.parsear("Transferencias interbancarias Transfer365", PROCESO)
    assert (p["tipo"], p["monto_num"], p["cuenta"], p["fecha"]) == ("transferencia_proceso", 25.0, "8878", "2026-08-02")
    assert "AGRICOLA" in p["banco_contraparte"]
    e = cuscatlan.parsear("Transfer365", EXITOSA)
    assert (e["tipo"], e["monto_num"], e["fecha"]) == ("transferencia_enviada", 25.0, "2026-08-02")
    assert e["titular"] == "Carlos Alessandro"
    r = cuscatlan.parsear("Transfer365", RECHAZADA)
    assert r["tipo"] == "transferencia_rechazada"


def test_el_abono_recibido_sigue_siendo_deposito_recibido():
    a = cuscatlan.parsear("Transfer365", ABONO)
    assert a["tipo"] == "deposito_recibido"
    assert (a["monto_num"], a["cuenta"], a["fecha"]) == (60.0, "8878", "2026-08-29")


def test_extraer_ignora_lo_que_no_es_dinero():
    assert movimientos.extraer({"tipo": "inicio_sesion", "fecha_correo": "2026-08-01"}) is None
    assert movimientos.extraer({"tipo": "compra", "monto_num": None, "fecha_correo": "2026-08-01"}) is None


def test_consolidar_no_cuenta_dos_veces_el_mismo_movimiento():
    cuentas = {"8878": "carlos"}
    filas = [
        # transferencia de $25: en proceso + exitosa (sin cuenta, por nombre) = UNA salida
        _n("Transferencias interbancarias Transfer365", PROCESO, 1),
        _n("Transfer365", EXITOSA, 2),
        # compra de $5 + su aviso de débito = UNA salida
        _n("Alerta de compra", COMPRA, 3),
        _n("Cargo a su cuenta", DEBITO, 4),
        # abono de $60 (un solo aviso) y crédito de $3
        _n("Transfer365", ABONO, 5),
        _n("Ha recibido un Deposito a cuenta", CREDITO, 6),
        # transferencia rechazada: no mueve dinero
        _n("Transfer365", RECHAZADA, 7),
        _n("Retiro sin tarjeta", RETIRO, 8),
    ]
    r = movimientos.consolidar(filas, cuentas)
    assert r["entra"] == 63.0 and r["n_entra"] == 2
    assert r["sale"] == 30.0 and r["n_sale"] == 2
    assert r["compras"] == 5.0 and r["transferencias"] == 25.0 and r["otros_cargos"] == 0
    assert r["neto"] == 33.0
    assert r["retiros_sin_monto"] == 1


def test_consolidar_filtra_cuentas_ajenas():
    ajena = COMPRA.replace("8878", "9425")
    filas = [_n("Alerta de compra", COMPRA, 1), _n("Alerta de compra", ajena, 2)]
    assert movimientos.consolidar(filas, {"8878": "carlos"})["sale"] == 5.0
    assert movimientos.consolidar(filas, {})["sale"] == 10.0  # sin filtro cuenta todo


def test_guardar_movimiento_no_duplica_el_mismo_correo():
    aviso = _n("Alerta de compra", COMPRA, 1)
    assert storage.guardar_movimiento(aviso) is True
    assert storage.guardar_movimiento(aviso) is False
    assert len(storage.movimientos_del_mes(2026, 8)) == 1
    assert storage.movimientos_del_mes(2026, 9) == []


def test_formatear_resumen():
    filas = [_n("Alerta de compra", COMPRA, 1), _n("Transfer365", ABONO, 2)]
    r = movimientos.consolidar(filas, {"8878": "carlos"})
    texto = movimientos.formatear_resumen(2026, 8, r, {"8878": "carlos"})
    assert "agosto 2026" in texto and "$60.00" in texto and "$5.00" in texto and "+$55.00" in texto
    vacio = movimientos.formatear_resumen(2026, 1, movimientos.consolidar([], {}), {})
    assert "No encontré movimientos" in vacio


def test_interpretar_mes():
    hoy = datetime(2026, 10, 27)
    assert bot.interpretar_mes([], hoy) == (2026, 10)
    assert bot.interpretar_mes(["anterior"], hoy) == (2026, 9)
    assert bot.interpretar_mes(["septiembre"], hoy) == (2026, 9)
    assert bot.interpretar_mes(["diciembre"], hoy) == (2025, 12)  # el más reciente que no es futuro
    assert bot.interpretar_mes(["09/2026"], hoy) == (2026, 9)
    assert bot.interpretar_mes(["marzo", "2025"], hoy) == (2025, 3)
    assert bot.interpretar_mes(["blah"], hoy) is None
    assert bot.interpretar_mes(["13/2026"], hoy) is None


def test_el_mes_anterior_desde_enero_cruza_el_anio():
    assert bot.interpretar_mes(["anterior"], datetime(2027, 1, 15)) == (2026, 12)
