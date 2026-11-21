"""RF-01 y RF-03 en PostgreSQL: registro del pago con cédula y placa, notificaciones, usuario de la sesión,
auditoría y fecha hasta la que va la mensualidad. El cálculo desde el corte (RF-02) se prueba en
test_mensualidad.py; aquí se comprueba que el endpoint lo usa."""
from datetime import timedelta
from decimal import Decimal
import os
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.database import get_engine
from app.main import app
from app.models import Auditoria, Cliente, Estancia, Novedad, Operador, Pago, Vehiculo
from app.services.mensualidad import hoy_colombia
from app.tarifas import MENSAJE_CARRO_CAMIONETA, MENSAJE_MOTO
from conftest import actor_por_cabecera, borrar_auditoria_de_pruebas, cabecera

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requiere PostgreSQL local.')


def placa() -> str:
    return ''.join(chr(65 + int(c, 16) % 26) for c in uuid4().hex[:3]) + '123'


def documento() -> str:
    return str(int(uuid4().hex[:12], 16))[:12]


def telefono() -> str:
    return f'3{int(uuid4().hex[:8], 16) % 10**9:09d}'


def ddmmaaaa(fecha) -> str:
    return fecha.strftime('%d/%m/%Y')


@pytest.fixture
def datos():
    engine = get_engine()
    with engine.connect() as c:
        assert c.scalar(text('SELECT current_database()')) == 'autos_colombia'
        assert c.scalar(text('SELECT version_num FROM alembic_version')) == '0008'
    hoy = hoy_colombia()
    with Session(engine) as s, s.begin():
        clientes = [Cliente(tipo_documento='CC', numero_documento=documento(), nombres=n, apellidos='Prueba',
                            telefono=telefono()) for n in ('Laura', 'Andrés')]
        s.add_all(clientes)
        s.flush()

        def vehiculo(cliente, pago, tipo='CARRO'):
            return Vehiculo(placa=placa(), color='Gris', modelo=2021, marca='Mazda', linea='3', tipo=tipo,
                            cliente_id=cliente.id if cliente else None, fecha_pago=pago)

        vehiculos = {
            # Vencido hace 4 días: el vencimiento es hoy - 4 (fecha de pago hace 34 días).
            'vencido': vehiculo(clientes[0], hoy - timedelta(days=34)),
            # Vigente 10 días más (pago adelantado).
            'vigente': vehiculo(clientes[0], hoy - timedelta(days=20)),
            # Sin pago anterior: el primer pago cuenta desde la fecha de pago.
            'nuevo': vehiculo(clientes[0], None),
            'de_otro': vehiculo(clientes[1], hoy),
            'sin_cliente': vehiculo(None, None),
            # RN-12: una camioneta y una moto del mismo cliente, para probar cada tarifa.
            'camioneta': vehiculo(clientes[0], hoy - timedelta(days=34), 'CAMIONETA'),
            'moto': vehiculo(clientes[0], hoy - timedelta(days=34), 'MOTO'),
        }
        operador = Operador(nombre='Prueba pagos', telefono=telefono(), usuario=f'prueba{uuid4().hex[:10]}')
        s.add_all(list(vehiculos.values()) + [operador])
        s.flush()
        data = {'clientes': [c.id for c in clientes], 'cedula': clientes[0].numero_documento,
                'operador': operador.id, 'id': {k: v.id for k, v in vehiculos.items()},
                'placa': {k: v.placa for k, v in vehiculos.items()},
                'vence': {k: v.fecha_vencimiento for k, v in vehiculos.items()}}
    try:
        with actor_por_cabecera(), TestClient(app) as api:
            data['api'] = api
            data['headers'] = cabecera(data['operador'], 1)
            yield data
    finally:
        ids = list(data['id'].values())
        with Session(engine) as s, s.begin():
            # Los ingresos creados por las pruebas referencian vehículo y operador (RESTRICT): se borran primero.
            estancias = select(Estancia.id).where(Estancia.vehiculo_id.in_(ids))
            s.execute(delete(Novedad).where(Novedad.estancia_id.in_(estancias)))
            s.execute(delete(Estancia).where(Estancia.vehiculo_id.in_(ids)))
            s.execute(delete(Pago).where(Pago.vehiculo_id.in_(ids)))
            s.execute(delete(Vehiculo).where(Vehiculo.id.in_(ids)))
            s.execute(delete(Cliente).where(Cliente.id.in_(data['clientes'])))
            s.execute(delete(Operador).where(Operador.id == data['operador']))
            borrar_auditoria_de_pruebas(s)


def pagar(d, clave='vencido', **cambios):
    cuerpo = {'cedula': d['cedula'], 'placa': d['placa'][clave], 'fecha_pago': hoy_colombia().isoformat(),
              'valor': '250000', 'medio': 'EFECTIVO', **cambios}
    return d['api'].post('/pagos', json=cuerpo, headers=d['headers'])


def consultar(d, clave='vencido', cedula=None):
    return d['api'].get('/pagos/consulta', params={'cedula': cedula or d['cedula'], 'placa': d['placa'][clave]},
                        headers=d['headers'])


# ---------- RF-01: notificaciones ----------

@pytest.mark.parametrize('accion', [consultar, pagar])
def test_cliente_no_registrado(datos, accion):
    if accion is consultar:
        r = consultar(datos, cedula='999999999999999')
    else:
        r = pagar(datos, cedula='999999999999999')
    assert r.status_code == 404
    assert r.json()['detail'] == 'El cliente no está registrado.'


@pytest.mark.parametrize('accion', ['consulta', 'pago'])
def test_vehiculo_no_registrado(datos, accion):
    if accion == 'consulta':
        r = datos['api'].get('/pagos/consulta', params={'cedula': datos['cedula'], 'placa': 'ZZZ999'},
                             headers=datos['headers'])
    else:
        r = pagar(datos, placa='ZZZ999')
    assert r.status_code == 404
    assert r.json()['detail'] == 'El vehículo no está registrado.'


@pytest.mark.parametrize('clave', ['de_otro', 'sin_cliente'])
def test_vehiculo_de_otro_cliente(datos, clave):
    for r in (consultar(datos, clave), pagar(datos, clave)):
        assert r.status_code == 409
        assert r.json()['detail'] == 'El vehículo no pertenece a este cliente.'
    with Session(get_engine()) as s:
        assert s.scalar(select(Pago).where(Pago.vehiculo_id == datos['id'][clave])) is None


def test_no_acepta_fecha_futura(datos):
    r = pagar(datos, fecha_pago=(hoy_colombia() + timedelta(days=1)).isoformat())
    assert r.status_code == 422
    assert r.json()['detail'] == 'La fecha de pago no puede ser posterior a hoy.'


# ---------- RF-03: hasta cuándo va la mensualidad al buscar ----------

def test_consulta_muestra_hasta_cuando(datos):
    r = consultar(datos, 'vigente')
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo['cliente']['numero_documento'] == datos['cedula']
    assert cuerpo['vehiculo']['placa'] == datos['placa']['vigente']
    assert cuerpo['mensualidad']['estado'] == 'VIGENTE'
    assert cuerpo['mensualidad']['mensaje'] == f"Mensualidad vigente hasta {ddmmaaaa(datos['vence']['vigente'])}."


# ---------- RF-01 + RF-02 + RF-03: registrar y mostrar el nuevo vencimiento ----------

def test_pago_tardio_cuenta_desde_el_corte(datos):
    corte = datos['vence']['vencido']
    r = pagar(datos, 'vencido')
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    nuevo = corte + timedelta(days=30)
    assert cuerpo['vencimiento_anterior'] == corte.isoformat()
    assert cuerpo['vencimiento_nuevo'] == nuevo.isoformat()
    assert cuerpo['mensualidad']['mensaje'] == f'Mensualidad vigente hasta {ddmmaaaa(nuevo)}.'
    assert cuerpo['cedula'] == datos['cedula']
    assert cuerpo['medio'] == 'EFECTIVO'


def test_pago_adelantado_cuenta_desde_el_corte(datos):
    corte = datos['vence']['vigente']
    r = pagar(datos, 'vigente', fecha_pago=hoy_colombia().isoformat(), medio='QR')
    assert r.status_code == 201, r.text
    assert r.json()['vencimiento_nuevo'] == (corte + timedelta(days=30)).isoformat()


def test_primer_pago_cuenta_desde_la_fecha_de_pago(datos):
    fecha = hoy_colombia() - timedelta(days=2)
    r = pagar(datos, 'nuevo', fecha_pago=fecha.isoformat(), medio='BANCO')
    assert r.status_code == 201, r.text
    assert r.json()['vencimiento_anterior'] is None
    assert r.json()['vencimiento_nuevo'] == (fecha + timedelta(days=30)).isoformat()


def test_pago_queda_con_usuario_de_la_sesion_y_en_auditoria(datos):
    r = pagar(datos, 'vencido', medio='BANCO')
    assert r.status_code == 201, r.text
    pago_id = r.json()['id']
    assert r.json()['registrado_por'] == f"prueba{datos['operador']}"
    with Session(get_engine()) as s:
        pago = s.get(Pago, pago_id)
        assert pago.operador_id == datos['operador']
        assert pago.cliente_id == datos['clientes'][0]
        assert pago.valor == Decimal('250000')
        vehiculo = s.get(Vehiculo, datos['id']['vencido'])
        assert vehiculo.fecha_vencimiento == pago.vencimiento_nuevo
        assert vehiculo.fecha_pago == pago.fecha_pago
        evento = s.scalar(select(Auditoria).where(Auditoria.accion == 'PAGO_REGISTRADO',
                                                  Auditoria.entidad_id == str(pago_id)))
        assert evento is not None
        assert evento.usuario_id == datos['operador']
        assert evento.placa == datos['placa']['vencido']


def test_dos_pagos_seguidos_suman_30_dias_cada_uno(datos):
    corte = datos['vence']['vencido']
    assert pagar(datos, 'vencido').status_code == 201
    r = pagar(datos, 'vencido')
    assert r.status_code == 201
    assert r.json()['vencimiento_nuevo'] == (corte + timedelta(days=60)).isoformat()


# ---------- RF-04: el pago habilita el ingreso ----------

def test_vehiculo_vencido_entra_despues_de_pagar(datos):
    api, headers, placa_vencida = datos['api'], datos['headers'], datos['placa']['vencido']
    antes = api.post('/estancias/entrada', json={'placa': placa_vencida}, headers=headers)
    assert antes.status_code == 409
    assert 'Mensualidad vencida' in antes.json()['detail']

    pago = pagar(datos, 'vencido')
    assert pago.status_code == 201, pago.text
    assert pago.json()['mensualidad']['estado'] == 'VIGENTE'

    consulta = api.get(f'/estancias/vehiculo/{placa_vencida}', headers=headers).json()
    assert consulta['mensualidad']['estado'] == 'VIGENTE' and consulta['puede_ingresar']

    despues = api.post('/estancias/entrada', json={'placa': placa_vencida}, headers=headers)
    assert despues.status_code == 201, despues.text
    assert despues.json()['placa'] == placa_vencida and despues.json()['abierta']


# ---------- RN-12: el valor del pago es la tarifa del tipo de vehículo ----------

@pytest.mark.parametrize('clave, valor', [('vencido', '250000'), ('camioneta', '250000'), ('moto', '100000')])
def test_pago_con_la_tarifa_se_acepta(datos, clave, valor):
    r = pagar(datos, clave, valor=valor)
    assert r.status_code == 201, r.text
    assert Decimal(r.json()['valor']) == Decimal(valor)


@pytest.mark.parametrize('clave, valor, mensaje', [
    ('vencido', '100000', MENSAJE_CARRO_CAMIONETA),      # carro con la tarifa de moto
    ('camioneta', '100000', MENSAJE_CARRO_CAMIONETA),    # camioneta con la tarifa de moto
    ('moto', '250000', MENSAJE_MOTO),                    # moto con la tarifa de carro
    ('vencido', '249999.99', MENSAJE_CARRO_CAMIONETA),   # cualquier valor distinto de la tarifa
    ('moto', '100000.50', MENSAJE_MOTO),
])
def test_pago_con_valor_distinto_a_la_tarifa_se_rechaza(datos, clave, valor, mensaje):
    r = pagar(datos, clave, valor=valor)
    assert r.status_code == 422
    assert r.json()['detail'] == mensaje
    with Session(get_engine()) as s:
        assert s.scalar(select(Pago).where(Pago.vehiculo_id == datos['id'][clave])) is None
        assert s.get(Vehiculo, datos['id'][clave]).fecha_vencimiento == datos['vence'][clave]
