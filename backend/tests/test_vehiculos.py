from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from conftest import ADMIN_PRUEBA

from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear
from app.services.vehiculo import VehiculoError, delete_vehicle


@pytest.mark.parametrize("field", ["placa", "color", "modelo", "marca", "tipo"])
def test_patch_rejects_explicit_null(field):
    with pytest.raises(ValidationError):
        VehiculoActualizar(**{field: None})


@pytest.mark.parametrize("field", ["placa", "color", "marca", "tipo"])
def test_patch_rejects_blank_text(field):
    with pytest.raises(ValidationError):
        VehiculoActualizar(**{field: " \t\n"})


def test_patch_only_supplied_fields_and_no_id():
    assert VehiculoActualizar(placa=" abc123 ").model_dump(exclude_unset=True) == {"placa": "ABC123"}
    assert VehiculoActualizar().model_dump(exclude_unset=True) == {}
    with pytest.raises(ValidationError):
        VehiculoActualizar(id=1)


def test_creation_requires_every_field():
    with pytest.raises(ValidationError):
        VehiculoCrear(placa="ABC123")


def test_delete_foreign_key_conflict_rolls_back_without_related_deletes():
    session = MagicMock()
    vehicle = session.get.return_value
    vehicle.id, vehicle.placa, vehicle.tipo = 1, "ABC123", "MOTO"
    driver_error = Exception("private database details")
    driver_error.sqlstate = "23503"
    driver_error.diag = SimpleNamespace(constraint_name="some_foreign_key")
    session.commit.side_effect = IntegrityError("DELETE", {}, driver_error)
    with pytest.raises(VehiculoError) as result:
        delete_vehicle(session, 1, ADMIN_PRUEBA)
    assert result.value.status_code == 409
    assert "private" not in result.value.detail
    session.rollback.assert_called_once()
    session.delete.assert_called_once_with(vehicle)


@pytest.mark.parametrize("entrada, esperado", [
    ("ABC123", "ABC123"), (" abc123 ", "ABC123"), ("ABC-123", "ABC123"), ("abc 123", "ABC123"),
    ("ABC12D", "ABC12D"), ("xyz-12a", "XYZ12A"),
])
def test_placa_colombiana_se_normaliza(entrada, esperado):
    datos = {"color": "Azul", "modelo": 2025, "marca": "Marca", "tipo": "MOTO", "cliente_id": 1,
             "linea": "NMax", "fecha_pago": "2026-10-05", "valor": "120000", "medio": "EFECTIVO"}
    assert VehiculoCrear(placa=entrada, **datos).placa == esperado
    assert VehiculoActualizar(placa=entrada).placa == esperado


@pytest.mark.parametrize("placa", [
    "AAAAA", "TEST", "ABC12", "ABC1234", "AB1234", "1234AB", "ÑBC123", "ABC12@", "A-B-C-1-2-3-4",
])
def test_placa_no_colombiana_es_rechazada(placa):
    datos = {"color": "Azul", "modelo": 2025, "marca": "Marca", "tipo": "MOTO", "cliente_id": 1,
             "linea": "NMax", "fecha_pago": "2026-10-05", "valor": "120000", "medio": "EFECTIVO"}
    with pytest.raises(ValidationError):
        VehiculoCrear(placa=placa, **datos)
    with pytest.raises(ValidationError):
        VehiculoActualizar(placa=placa)


# ---------- RF-04: el vehículo nuevo guarda su primer pago; la fecha de pago ya no se edita ----------

DATOS_VEHICULO = {"placa": "KDT482", "color": "Gris", "modelo": 2021, "marca": "Mazda", "tipo": "CARRO",
                  "cliente_id": 1, "linea": "3", "fecha_pago": "2026-10-05", "valor": "120000",
                  "medio": "EFECTIVO"}


@pytest.mark.parametrize("campo", ["fecha_pago", "valor", "medio"])
def test_creacion_exige_los_datos_del_primer_pago(campo):
    VehiculoCrear(**DATOS_VEHICULO)
    with pytest.raises(ValidationError):
        VehiculoCrear(**{k: v for k, v in DATOS_VEHICULO.items() if k != campo})


@pytest.mark.parametrize("cambio", [{"valor": "0"}, {"valor": "-5000"}, {"valor": "12.345"}, {"valor": None},
                                    {"medio": "TARJETA"}, {"medio": None}])
def test_creacion_rechaza_primer_pago_invalido(cambio):
    with pytest.raises(ValidationError):
        VehiculoCrear(**{**DATOS_VEHICULO, **cambio})


@pytest.mark.parametrize("campo, valor", [("fecha_pago", "2026-10-05"), ("fecha_vencimiento", "2026-12-01"),
                                          ("valor", "1000"), ("medio", "QR")])
def test_actualizar_no_edita_la_mensualidad_ni_el_pago(campo, valor):
    with pytest.raises(ValidationError):
        VehiculoActualizar(**{campo: valor})
