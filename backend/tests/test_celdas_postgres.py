"""Integración optativa sin DDL; todos los datos nuevos se revierten."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_engine, get_session
from app.main import app
from conftest import ADMIN_PRUEBA, como

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


@pytest.fixture
def connection():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT current_database()")) == "autos_colombia"
            yield connection
        finally:
            transaction.rollback()


def test_celda_schema_and_constraints(connection):
    inspector = inspect(connection)
    columns = {c['name']: c for c in inspector.get_columns('celda')}
    # RF-14 / RF-15: estado guardado (ACTIVA, INHABILITADA o ELIMINADA) con su motivo y fecha.
    assert set(columns) == {'id', 'codigo', 'tipo', 'estado', 'motivo_estado', 'fecha_estado'}
    assert str(columns['id']['type']) == 'BIGINT'
    assert columns['id']['identity']['always']
    assert {n for n, c in columns.items() if c['nullable']} == {'motivo_estado', 'fecha_estado'}
    assert inspector.get_pk_constraint('celda')['constrained_columns'] == ['id']
    assert any(c['column_names'] == ['codigo'] for c in inspector.get_unique_constraints('celda'))
    code = 'SCHEMA-' + uuid4().hex.upper()
    connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code,'type':'MOTO'})
    assert connection.scalar(text('SELECT estado FROM celda WHERE codigo = :code'), {'code': code}) == 'ACTIVA'
    for estado, motivo in [('BORRADA', 'x'), ('INHABILITADA', None), ('ELIMINADA', ' 	')]:
        with pytest.raises(IntegrityError) as error:
            with connection.begin_nested():
                connection.execute(text('INSERT INTO celda(codigo,tipo,estado,motivo_estado) VALUES (:c,:t,:e,:m)'),
                                   {'c': code + 'E', 't': 'MOTO', 'e': estado, 'm': motivo})
        assert error.value.orig.sqlstate == '23514'
    for code_value, kind, state in [(code,'MOTO','23505'), (' lowercase ','MOTO','23514'),
                                    (' \t','MOTO','23514'), (code+'X',' \t','23514'),
                                    (code+'Z','Libre','23514'),
                                    (None,'MOTO','23502'), (code+'Y',None,'23502')]:
        with pytest.raises(IntegrityError) as error:
            with connection.begin_nested():
                connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code_value,'type':kind})
        assert error.value.orig.sqlstate == state


def test_crud_celdas(connection):
    with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
        def override():
            yield session
        app.dependency_overrides[get_session] = override
        try:
            # RF-02: la administración de celdas es del administrador.
            with como(ADMIN_PRUEBA), TestClient(app) as client:
                code = 'CELL-' + uuid4().hex.upper()
                payload = {'codigo': f' {code.lower()} ', 'tipo': 'MOTO'}
                result = client.post('/celdas', json=payload)
                assert result.status_code == 201
                item = result.json()
                assert item['codigo'] == code and item['tipo'] == 'MOTO'
                path = f"/celdas/{item['id']}"
                assert client.get(path).json() == item
                assert client.post('/celdas', json=payload).status_code == 409
                page = client.get('/celdas?offset=0&limit=1')
                assert page.status_code == 200 and len(page.json()['items']) == 1
                assert client.get('/celdas?limit=0').status_code == 422
                for invalid in ({'id':1}, {'codigo':None}, {'tipo':' \t'}, {'tipo':None}, {'tipo':'Libre'}):
                    assert client.patch(path, json=invalid).status_code == 422
                assert client.post('/celdas', json={}).status_code == 422
                changed = client.patch(path, json={'tipo':'CARRO_CAMIONETA'})
                assert changed.status_code == 200 and changed.json()['tipo'] == 'CARRO_CAMIONETA'
                assert changed.json()['estado'] == 'DISPONIBLE'
                # RF-14: inhabilitar y habilitar exigen motivo.
                assert client.post(path + '/inhabilitar', json={}).status_code == 422
                assert client.post(path + '/inhabilitar', json={'motivo': ' '}).status_code == 422
                off = client.post(path + '/inhabilitar', json={'motivo': 'Mantenimiento'})
                assert off.status_code == 200 and off.json()['estado'] == 'INHABILITADA'
                assert off.json()['motivo_estado'] == 'Mantenimiento' and off.json()['fecha_estado']
                assert client.post(path + '/inhabilitar', json={'motivo': 'otra vez'}).status_code == 409
                on = client.post(path + '/habilitar', json={'motivo': 'Reparada'})
                assert on.status_code == 200 and on.json()['estado'] == 'DISPONIBLE'
                # RF-15: no hay DELETE; el borrado es lógico y conserva la celda.
                assert client.delete(path).status_code == 405
                deleted = client.post(path + '/eliminar', json={'motivo': 'Se demolió'})
                assert deleted.status_code == 200 and deleted.json()['estado'] == 'ELIMINADA'
                assert client.get(path).json()['estado'] == 'ELIMINADA'
                assert client.patch(path, json={'tipo':'MOTO'}).status_code == 409
                assert client.post(path + '/eliminar', json={'motivo': 'x'}).status_code == 409
                assert client.post(path + '/habilitar', json={'motivo': 'x'}).status_code == 409
                visibles = client.get(f'/celdas?q={code}').json()
                assert visibles['total'] == 0
                assert client.get(f'/celdas?q={code}&estado=ELIMINADA').json()['total'] == 1
                assert client.post('/celdas/9223372036854775807/eliminar', json={'motivo': 'x'}).status_code == 404
                assert client.get('/health').json() == {'status':'ok'}
        finally:
            app.dependency_overrides.pop(get_session, None)
