from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from pydantic import ValidationError
import sqlalchemy as sa

from app.schemas.cliente import ClienteActualizar, ClienteCrear
from app.schemas.estancia import EntradaCrear, SalidaCrear, normalizar_recibo
from app.models import Pago, Vehiculo
from app.services.mensualidad import calcular_vencimiento, evaluar_mensualidad

HOY = date(2026, 10, 18)


def mensualidad(fecha_pago: date | None, cliente_id: int | None = 1):
    vence = fecha_pago + timedelta(days=30) if fecha_pago else None
    return evaluar_mensualidad(cliente_id, fecha_pago, vence, HOY)


def test_ejemplos_del_documento_rn06():
    # Pago el 05/10/2026 → vence el 04/11/2026; el 18/10 está vigente (HU-04, criterio 1).
    vigente = mensualidad(date(2026, 10, 5))
    assert vigente.estado == "VIGENTE" and vigente.permite_ingreso
    assert vigente.fecha_vencimiento == date(2026, 11, 4) and vigente.dias == 17
    assert vigente.mensaje == "Mensualidad vigente hasta 04/11/2026."


def test_vencida_bloquea_ingreso():
    # Venció el 15/10/2026 y llega el 18/10/2026 (HU-04, criterio 2).
    vencida = mensualidad(date(2026, 9, 15))
    assert vencida.estado == "VENCIDA" and not vencida.permite_ingreso
    assert vencida.dias == 3 and "vencida hace 3 días" in vencida.mensaje
    assert "hace 1 día " in mensualidad(date(2026, 9, 17)).mensaje


def test_vence_hoy_permite_y_avisa():
    # HU-04, criterio 3.
    hoy = mensualidad(HOY - timedelta(days=30))
    assert hoy.estado == "VENCE_HOY" and hoy.permite_ingreso and "vence hoy" in hoy.mensaje


@pytest.mark.parametrize("cliente_id, fecha_pago, estado", [(None, date(2026, 10, 5), "SIN_CLIENTE"),
                                                            (1, None, "SIN_PAGO")])
def test_vehiculo_sin_cliente_o_sin_pago_no_ingresa(cliente_id, fecha_pago, estado):
    resultado = mensualidad(fecha_pago, cliente_id)
    assert resultado.estado == estado and not resultado.permite_ingreso


@pytest.mark.parametrize("valor, esperado", [("E-000245", "E-000245"), ("e000245", "E-000245"), (" 245 ", "E-000245"),
                                             ("E-1234567", "E-1234567")])
def test_recibo_se_normaliza(valor, esperado):
    assert normalizar_recibo(valor) == esperado


@pytest.mark.parametrize("valor", ["", "E-", "ABC", "E-0", "0", "E-12A"])
def test_recibo_invalido(valor):
    with pytest.raises(ValueError):
        normalizar_recibo(valor)


def test_entrada_no_acepta_celda_y_exige_puerta():
    # RF-05: la celda la asigna el sistema y se registra la puerta.
    with pytest.raises(ValidationError):
        EntradaCrear(placa="ABC123", operador_id=1, puerta_id=1, celda_id=1)
    with pytest.raises(ValidationError):
        EntradaCrear(placa="ABC123", operador_id=1)


def test_salida_por_placa_o_recibo_con_puerta():
    # RF-07: placa o recibo (o ambos, que el servidor verifica) y la puerta de salida.
    # Iteración 2: el usuario y la puerta salen de la sesión (RF-01, RF-03), no del cuerpo.
    assert SalidaCrear(placa="abc-123").placa == "ABC123"
    assert SalidaCrear(numero_recibo="e231").numero_recibo == "E-000231"
    with pytest.raises(ValidationError, match="placa o el número del recibo"):
        SalidaCrear()
    with pytest.raises(ValidationError):
        SalidaCrear(placa="ABC123", operador_id=1)


def test_cliente_normaliza_documento_telefono_y_correo():
    cliente = ClienteCrear(tipo_documento="CC", numero_documento="1.036.458.221", nombres=" Laura ",
                           apellidos="Gómez", telefono="+57 300 123 4567", correo=" Laura@Correo.COM ")
    assert cliente.numero_documento == "1036458221"
    assert cliente.telefono == "3001234567"
    assert cliente.correo == "laura@correo.com"
    assert cliente.nombres == "Laura"
    assert ClienteCrear(tipo_documento="CE", numero_documento="AB123", nombres="A", apellidos="B",
                        telefono="6011234567", correo="").correo is None


@pytest.mark.parametrize("campo, valor", [("tipo_documento", "DNI"), ("numero_documento", "12"),
                                          ("telefono", "12345"), ("correo", "sin-arroba"), ("nombres", " ")])
def test_cliente_invalido(campo, valor):
    datos = {"tipo_documento": "CC", "numero_documento": "1036458221", "nombres": "Laura", "apellidos": "Gómez",
             "telefono": "3001234567", "correo": None, campo: valor}
    with pytest.raises(ValidationError):
        ClienteCrear(**datos)


def test_actualizar_cliente_rechaza_nulos_salvo_correo():
    with pytest.raises(ValidationError):
        ClienteActualizar(nombres=None)
    assert ClienteActualizar(correo=None).model_dump(exclude_unset=True) == {"correo": None}


# ---------- Iteración 3, RF-02: nueva mensualidad desde la fecha de corte ----------

@pytest.mark.parametrize("corte, pago, esperado", [
    # Ejemplo del profesor: hasta 01/11, paga el 05/11 (tarde) → 01/11 + 30 = 01/12.
    (date(2026, 11, 1), date(2026, 11, 5), date(2026, 12, 1)),
    # Mes de 31 días: corte 01/12 → 31/12, no 01/01.
    (date(2026, 12, 1), date(2026, 12, 1), date(2026, 12, 31)),
    # Primer pago de un vehículo nuevo (RN-08): pago 19/11 → 19/12.
    (None, date(2026, 11, 19), date(2026, 12, 19)),
    # Pago adelantado (RN-09): corte 03/12, paga el 23/11 → 02/01/2027.
    (date(2026, 12, 3), date(2026, 11, 23), date(2027, 1, 2)),
])
def test_ejemplos_del_documento_rf02(corte, pago, esperado):
    assert calcular_vencimiento(corte, pago) == esperado


def test_el_vencimiento_no_depende_del_dia_en_que_se_paga():
    # HU-02, criterio 5: con corte anterior, siempre corte + 30 días.
    corte = date(2026, 11, 1)
    for pago in (date(2026, 10, 20), corte, date(2026, 11, 5), date(2026, 12, 15)):
        assert calcular_vencimiento(corte, pago) == date(2026, 12, 1)


@pytest.mark.parametrize("corte, pago", [
    (None, None), (None, "2026-11-19"), (None, datetime(2026, 11, 19, 8)),
    ("2026-11-01", date(2026, 11, 5)), (datetime(2026, 11, 1), date(2026, 11, 5)),
])
def test_calcular_vencimiento_rechaza_valores_que_no_son_fechas(corte, pago):
    with pytest.raises(ValueError):
        calcular_vencimiento(corte, pago)


def test_registrar_vehiculo_con_fecha_de_pago_es_el_primer_pago():
    # RN-08 desde el alta del vehículo (RF-02 de la iteración 1): pago 05/10 → vence 04/11.
    vehiculo = Vehiculo(placa="KDT482", color="Gris", modelo=2021, marca="Mazda", tipo="CARRO",
                        fecha_pago=date(2026, 10, 5))
    assert vehiculo.fecha_vencimiento == date(2026, 11, 4)
    assert Vehiculo(placa="KDT483", color="Gris", modelo=2021, marca="Mazda", tipo="CARRO").fecha_vencimiento is None


def test_editar_la_fecha_de_pago_no_borra_los_dias_ya_pagados():
    vehiculo = Vehiculo(fecha_pago=date(2026, 10, 2))   # vence 01/11
    assert vehiculo.aplicar_pago(date(2026, 11, 5)) == date(2026, 12, 1)
    vehiculo.fecha_pago = date(2026, 11, 5)            # p. ej., el formulario reenvía la misma fecha
    assert vehiculo.fecha_vencimiento == date(2026, 12, 1)


def test_aplicar_pago_cuenta_desde_el_corte_y_encadena_pagos():
    vehiculo = Vehiculo()
    assert vehiculo.aplicar_pago(date(2026, 11, 19)) == date(2026, 12, 19)   # primer pago
    assert vehiculo.aplicar_pago(date(2026, 12, 23)) == date(2027, 1, 18)    # tardío: 19/12 + 30
    assert vehiculo.fecha_pago == date(2026, 12, 23)
    assert vehiculo.fecha_vencimiento == date(2027, 1, 18)
    # RF-04: con el nuevo vencimiento la validación de ingreso de la iteración 1 deja entrar.
    estado = evaluar_mensualidad(1, vehiculo.fecha_pago, vehiculo.fecha_vencimiento, date(2027, 1, 2))
    assert estado.estado == "VIGENTE" and estado.permite_ingreso


def test_modelo_pago_y_restricciones():
    pago = Pago(valor=Decimal("120000"), medio="QR")
    assert pago.valor == Decimal("120000") and pago.medio == "QR"
    for valor in (0, -1, Decimal("0.00"), True, 1.5, "120000"):
        with pytest.raises(ValueError):
            Pago(valor=valor)
    with pytest.raises(ValueError):
        Pago(medio="TARJETA")
    tabla = Pago.__table__
    assert {c.name for c in tabla.c if c.nullable} == {"vencimiento_anterior"}
    assert len(tabla.foreign_keys) == 3 and all(fk.ondelete == "RESTRICT" for fk in tabla.foreign_keys)
    checks = {c.name for c in tabla.constraints if isinstance(c, sa.CheckConstraint)}
    assert {"ck_pago_valor_positivo", "ck_pago_medio", "ck_pago_vencimiento_30_dias"} <= checks
    vencimiento = Vehiculo.__table__.c.fecha_vencimiento
    assert vencimiento.computed is None and vencimiento.nullable


def test_alembic_offline_0008():
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "0007b:0008", sql=True)
    sql = output.getvalue()
    assert "ALTER TABLE vehiculo ALTER COLUMN fecha_vencimiento DROP EXPRESSION" in sql
    assert "CHECK ((fecha_pago IS NULL) = (fecha_vencimiento IS NULL))" in sql
    assert "CREATE TABLE pago" in sql
    assert "CHECK (valor > 0)" in sql
    assert "COALESCE(vencimiento_anterior, fecha_pago) + 30" in sql
    assert sql.count("ON DELETE RESTRICT") == 3
    assert "DROP TABLE" not in sql and "DROP COLUMN" not in sql
