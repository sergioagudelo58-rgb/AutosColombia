"""Contratos HTTP de RF-07 a RF-11 sin PostgreSQL: la validación ocurre antes de usar la sesión.

El flujo con datos reales está en test_reportes_postgres.py.
"""
from fastapi.testclient import TestClient
import pytest

from app.database import get_session
from app.main import app


class SesionNoUsada:
    """Falla si un endpoint intenta consultar la base cuando debía rechazar la solicitud antes."""
    def __getattr__(self, name):
        raise AssertionError(f"La solicitud no debía llegar a la base de datos ({name}).")


@pytest.fixture
def client():
    def override():
        yield SesionNoUsada()
    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_openapi_publica_rutas_de_la_iteracion(client):
    paths = client.get('/openapi.json').json()['paths']
    for path, method in [('/estancias/abierta', 'get'), ('/estancias/salida', 'post'),
                         ('/estancias/{id}/celda', 'post'), ('/panel', 'get'),
                         ('/reportes/ocupacion', 'get'), ('/reportes/historial', 'get')]:
        assert method in paths[path]
    assert client.get('/health').json() == {'status': 'ok'}


@pytest.mark.parametrize('payload', [
    {'operador_id': 1, 'puerta_id': 1},                                   # sin placa ni recibo
    {'placa': 'ABC123', 'operador_id': 1},                                # sin puerta (RF-07)
    {'placa': 'ABC123', 'operador_id': 1, 'puerta_id': 0},
    {'numero_recibo': 'XYZ', 'operador_id': 1, 'puerta_id': 1},
    {'placa': 'ABC123', 'operador_id': 1, 'puerta_id': 1, 'salida': '2026-01-01'},
])
def test_salida_invalida(client, payload):
    response = client.post('/estancias/salida', json=payload)
    assert response.status_code == 422


def test_salida_sin_placa_ni_recibo_explica_que_hacer(client):
    detail = client.post('/estancias/salida', json={'operador_id': 1, 'puerta_id': 1}).json()['detail']
    assert 'placa o el número del recibo' in detail[0]['msg']


@pytest.mark.parametrize('query', ['placa=%20', 'placa=12', 'recibo=ABC'])
def test_abierta_valida_placa_y_recibo(client, query):
    assert client.get('/estancias/abierta?' + query).status_code == 422


@pytest.mark.parametrize('payload', [
    {'celda_id': 30, 'operador_id': 1},                                   # motivo obligatorio (HU-09)
    {'celda_id': 30, 'operador_id': 1, 'motivo': '   '},
    {'celda_id': 30, 'operador_id': 1, 'motivo': 'x' * 301},
    {'celda_id': 0, 'operador_id': 1, 'motivo': 'Parqueó en la 30'},
    {'celda_id': 30, 'motivo': 'Parqueó en la 30'},
    {'celda_id': 30, 'operador_id': 1, 'motivo': 'ok', 'celda_anterior_id': 25},
])
def test_cambio_de_celda_invalido(client, payload):
    assert client.post('/estancias/5/celda', json=payload).status_code == 422


def test_cambio_de_celda_valida_id_de_estancia(client):
    assert client.post('/estancias/0/celda', json={'celda_id': 1, 'operador_id': 1,
                                                   'motivo': 'x'}).status_code == 422


@pytest.mark.parametrize('path', [
    '/reportes/ocupacion?desde=18-10-2026',
    '/reportes/historial?desde=ayer',
    '/reportes/historial?limit=0',
    '/reportes/historial?limit=101',
    '/reportes/historial?offset=-1',
    '/reportes/historial?placa=' + 'A' * 11,
])
def test_reportes_validan_parametros(client, path):
    assert client.get(path).status_code == 422
