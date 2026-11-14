from fastapi.testclient import TestClient
import pytest

from app.main import app

pytestmark = pytest.mark.usefixtures('sesion_admin')


def test_openapi_y_salud():
    with TestClient(app) as client:
        schema = client.get('/openapi.json').json()
        for path, method in [('/estancias/entrada', 'post'), ('/estancias/salida', 'post'),
                             ('/estancias/vehiculo/{placa}', 'get'),
                             ('/estancias/recibo/{numero_recibo}', 'get'), ('/clientes', 'post'),
                             ('/clientes', 'get'), ('/clientes/{id}', 'get'), ('/clientes/{id}', 'patch'),
                             ('/puertas', 'get')]:
            assert method in schema['paths'][path]
        assert client.get('/health').json() == {'status': 'ok'}


@pytest.mark.parametrize('payload', [
    {}, {'placa': ' '}, {'placa': None}, {'placa': 'TEST'},
    {'placa': 'ABC123', 'celda_id': 1},
    # RF-08: el usuario y la puerta salen de la sesión; no se aceptan en el cuerpo.
    {'placa': 'ABC123', 'operador_id': 1}, {'placa': 'ABC123', 'puerta_id': 1},
    {'placa': 'ABC123', 'operador_id': 1, 'puerta_id': 1},
    {'placa': 'ABC123', 'entrada': '2026-01-01'},
])
def test_entrada_invalida(payload):
    with TestClient(app) as client:
        assert client.post('/estancias/entrada', json=payload).status_code == 422


def test_salida_no_admite_celda_ni_fecha():
    with TestClient(app) as client:
        for extra in ({'celda_id': 1}, {'salida': '2026-01-01'}, {'id': 1}):
            assert client.post('/estancias/salida', json={'placa': 'ABC123', **extra}).status_code == 422
        assert client.post('/estancias/salida', json={}).status_code == 422
        assert client.post('/estancias/salida', json={'placa': 'ABC123', 'operador_id': 1}).status_code == 422
        # RF-05: la celda no la envía el operario.
        assert client.post('/estancias/entrada', json={'placa': 'ABC123', 'celda_id': 1}).status_code == 422
        assert client.get('/estancias/recibo/ABC').status_code == 422
        assert client.get('/estancias/vehiculo/%20%20').status_code == 422
