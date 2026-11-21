"""RN-12: tarifas de la mensualidad, sin base de datos."""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from conftest import ADMIN_PRUEBA

from app.schemas.vehiculo import VehiculoCrear
from app.services.vehiculo import VehiculoError, create_vehicle
from app.tarifas import CAMIONETA, CARRO, MENSAJE_CARRO_CAMIONETA, MENSAJE_MOTO, MOTO, mensaje_tarifa, valor_corresponde


def test_tarifas_definidas_en_un_solo_lugar():
    assert CARRO == Decimal("250000") and CAMIONETA == Decimal("250000") and MOTO == Decimal("100000")


@pytest.mark.parametrize("tipo, valor", [("CARRO", "250000"), ("CAMIONETA", "250000"), ("MOTO", "100000"),
                                         ("CARRO", "250000.00")])
def test_valor_igual_a_la_tarifa_se_acepta(tipo, valor):
    assert valor_corresponde(tipo, Decimal(valor))


@pytest.mark.parametrize("tipo, valor", [("CARRO", "100000"), ("MOTO", "250000"), ("CAMIONETA", "100000"),
                                         ("CARRO", "249999.99"), ("MOTO", "100000.01"), ("BUS", "250000")])
def test_valor_distinto_a_la_tarifa_se_rechaza(tipo, valor):
    assert not valor_corresponde(tipo, Decimal(valor))


def test_mensajes():
    assert mensaje_tarifa("CARRO") == mensaje_tarifa("CAMIONETA") == MENSAJE_CARRO_CAMIONETA
    assert mensaje_tarifa("MOTO") == MENSAJE_MOTO
    assert "$250.000" in MENSAJE_CARRO_CAMIONETA and "$100.000" in MENSAJE_MOTO


@pytest.mark.parametrize("tipo, valor, mensaje", [("CARRO", "100000", MENSAJE_CARRO_CAMIONETA),
                                                  ("MOTO", "250000", MENSAJE_MOTO)])
def test_crear_vehiculo_con_valor_incorrecto_no_guarda_nada(tipo, valor, mensaje):
    session = MagicMock()
    datos = VehiculoCrear(placa="KDT482", color="Gris", modelo=2021, marca="Mazda", tipo=tipo, cliente_id=1,
                          linea="3", fecha_pago=date(2026, 10, 5), valor=valor, medio="EFECTIVO")
    with pytest.raises(VehiculoError) as error:
        create_vehicle(session, datos, ADMIN_PRUEBA)
    assert error.value.status_code == 422 and error.value.detail == mensaje
    session.add.assert_not_called()
    session.commit.assert_not_called()
