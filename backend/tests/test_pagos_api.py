"""RF-01: validación del cuerpo del pago, sin base de datos."""
from fastapi.testclient import TestClient
import pytest

from app.main import app

pytestmark = pytest.mark.usefixtures('sesion_admin')

VALIDO = {'cedula': '1036458221', 'placa': 'KDT482', 'fecha_pago': '2026-11-05', 'valor': '250000',
          'medio': 'EFECTIVO'}


def test_rutas_publicadas():
    with TestClient(app) as client:
        paths = client.get('/openapi.json').json()['paths']
        assert 'post' in paths['/pagos']
        assert 'get' in paths['/pagos/consulta']


@pytest.mark.parametrize('cambio', [
    {'cedula': None}, {'cedula': ' '}, {'cedula': '1.0'},
    {'placa': None}, {'placa': 'TEST'},
    {'fecha_pago': None}, {'fecha_pago': ''}, {'fecha_pago': '2026-11-05T10:00:00'},
    {'valor': None}, {'valor': 0}, {'valor': -5000}, {'valor': '12.345'}, {'valor': '10000000000'},
    {'medio': None}, {'medio': 'TARJETA'}, {'medio': 'pasarela'},
    # RNF-03: el usuario que registra sale de la sesión; no se acepta en el cuerpo.
    {'operador_id': 1}, {'cliente_id': 1}, {'vencimiento_nuevo': '2026-12-31'},
])
def test_pago_invalido(cambio):
    with TestClient(app) as client:
        assert client.post('/pagos', json={**VALIDO, **cambio}).status_code == 422


@pytest.mark.parametrize('campo', ['cedula', 'placa', 'fecha_pago', 'valor', 'medio'])
def test_pago_sin_dato_obligatorio(campo):
    cuerpo = {k: v for k, v in VALIDO.items() if k != campo}
    with TestClient(app) as client:
        assert client.post('/pagos', json=cuerpo).status_code == 422


def test_consulta_exige_cedula_y_placa():
    with TestClient(app) as client:
        assert client.get('/pagos/consulta', params={'placa': 'KDT482'}).status_code == 422
        assert client.get('/pagos/consulta', params={'cedula': '1036458221'}).status_code == 422
        assert client.get('/pagos/consulta', params={'cedula': '1036458221', 'placa': 'X'}).status_code == 422

