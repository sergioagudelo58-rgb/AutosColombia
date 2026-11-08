"""RF-07 a RF-11 contra PostgreSQL real, con los datos temporales del fixture `datos`.

Requiere RUN_POSTGRES_TESTS=1 y la base autos_colombia en la revisión 0006.
"""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.database import get_engine
from app.main import app
from app.models import Cliente
from app.services.mensualidad import hoy_colombia
from test_estancias_postgres import abiertas, datos, entrada, pytestmark  # noqa: F401  (fixture compartido)


def libres(client, tipo):
    return [c for c in client.get('/panel').json()['celdas'] if c['tipo'] == tipo and c['estado'] == 'DISPONIBLE']


def celda_en_panel(client, celda_id):
    return next(c for c in client.get('/panel').json()['celdas'] if c['id'] == celda_id)


def test_salida_por_recibo_verifica_placa_y_guarda_puerta(datos):
    d = datos
    with TestClient(app) as client:
        carro = client.post('/estancias/entrada', json=entrada(d)).json()
        moto = client.post('/estancias/entrada', json=entrada(d, 'moto')).json()
        abierta = client.get('/estancias/abierta', params={'recibo': carro['numero_recibo'].replace('-', '').lower()})
        assert abierta.status_code == 200 and abierta.json()['placa'] == d['placa']['carro']
        sin_ingreso = client.get('/estancias/abierta', params={'placa': d['placa']['camioneta']})
        assert sin_ingreso.status_code == 409 and 'ingreso abierto' in sin_ingreso.json()['detail']

        # HU-07 criterio 3: el recibo de otro vehículo no cierra nada.
        cruzado = client.post('/estancias/salida', json={'placa': d['placa']['carro'],
                                                         'numero_recibo': moto['numero_recibo'],
                                                         'operador_id': d['o'][0], 'puerta_id': 2})
        assert cruzado.status_code == 409 and 'no corresponde' in cruzado.json()['detail']
        assert abiertas(d) == 2

        salida = client.post('/estancias/salida', json={'numero_recibo': carro['numero_recibo'],
                                                        'operador_id': d['o'][1], 'puerta_id': 2})
        body = salida.json()
        assert salida.status_code == 200 and not body['abierta']
        assert body['puerta_salida']['id'] == 2 and body['operador_salida']['id'] == d['o'][1]
        repetida = client.post('/estancias/salida', json={'numero_recibo': carro['numero_recibo'],
                                                          'operador_id': d['o'][1], 'puerta_id': 2})
        assert repetida.status_code == 409 and 'ingreso abierto' in repetida.json()['detail']
        assert celda_en_panel(client, carro['celda']['id'])['estado'] == 'DISPONIBLE'


def test_cambio_e_intercambio_de_celda(datos):
    d = datos
    with TestClient(app) as client:
        carro = client.post('/estancias/entrada', json=entrada(d)).json()
        camioneta = client.post('/estancias/entrada', json=entrada(d, 'camioneta', o=1)).json()
        assert celda_en_panel(client, carro['celda']['id'])['reciente']
        destino = libres(client, 'CARRO_CAMIONETA')[0]
        url = f"/estancias/{carro['id']}/celda"
        moto = libres(client, 'MOTO')
        if moto:
            otro_tipo = client.post(url, json={'celda_id': moto[0]['id'], 'motivo': 'x', 'operador_id': d['o'][0]})
            assert otro_tipo.status_code == 409 and 'es para motos' in otro_tipo.json()['detail']

        # (a) El conductor parqueó en otra celda libre: cambio simple con novedad.
        motivo = f"El conductor parqueó en la {destino['codigo']}"
        simple = client.post(url, json={'celda_id': destino['id'], 'motivo': motivo, 'operador_id': d['o'][0]})
        assert simple.status_code == 200
        estancia = simple.json()['estancia']
        assert estancia['celda']['id'] == destino['id'] and simple.json()['intercambio'] is None
        nov = estancia['novedades'][-1]
        assert nov['celda_anterior']['id'] == carro['celda']['id'] and nov['motivo'] == motivo
        assert nov['operador']['id'] == d['o'][0]
        assert celda_en_panel(client, carro['celda']['id'])['estado'] == 'DISPONIBLE'
        nueva = celda_en_panel(client, destino['id'])
        assert nueva['estado'] == 'OCUPADA' and nueva['ocupacion']['placa'] == d['placa']['carro']

        # (b) La celda elegida figura ocupada: solo con «Intercambiar celdas».
        url = f"/estancias/{camioneta['id']}/celda"
        cambio = {'celda_id': destino['id'], 'motivo': 'Celda asignada ocupada', 'operador_id': d['o'][1]}
        ocupada = client.post(url, json=cambio)
        assert ocupada.status_code == 409 and 'Intercambiar celdas' in ocupada.json()['detail']
        swap = client.post(url, json={**cambio, 'intercambiar': True})
        assert swap.status_code == 200
        assert swap.json()['estancia']['celda']['id'] == destino['id']
        assert swap.json()['intercambio']['celda']['id'] == camioneta['celda']['id']
        assert abiertas(d) == 2

        historial = client.get('/reportes/historial', params={'placa': d['placa']['carro']}).json()
        assert historial['total'] == 1 and len(historial['items'][0]['novedades']) == 2
        actividad = client.get('/panel').json()['actividad']
        assert any(a['tipo'] == 'NOVEDAD' and a['placa'] == d['placa']['camioneta'] for a in actividad)


def test_reporte_de_ocupacion_e_historial(datos):
    d = datos
    with Session(get_engine()) as s:
        documento = s.get(Cliente, d['cliente']).numero_documento
    with TestClient(app) as client:
        antes = client.get('/reportes/ocupacion').json()
        assert antes['desde'] == antes['hasta'] == hoy_colombia().isoformat()
        assert set(antes['vehiculos_por_tipo']) == {'MOTO', 'CARRO', 'CAMIONETA'}
        client.post('/estancias/entrada', json=entrada(d))
        despues = client.get('/reportes/ocupacion').json()
        assert despues['entradas'] >= antes['entradas'] + 1
        panel = client.get('/panel').json()
        ocupadas = sum(c['estado'] == 'OCUPADA' for c in panel['celdas'])
        # Los totales coinciden con el mapa de celdas (HU-10).
        assert despues['celdas_ocupadas'] == ocupadas == despues['vehiculos_adentro']
        assert despues['celdas_total'] == len(panel['celdas'])
        assert any(a['tipo'] == 'ENTRADA' and a['placa'] == d['placa']['carro'] for a in panel['actividad'])
        assert client.get('/reportes/ocupacion?desde=2026-10-19&hasta=2026-10-18').status_code == 422

        por_cliente = client.get('/reportes/historial', params={'cliente': documento}).json()
        assert por_cliente['total'] == 1 and por_cliente['items'][0]['abierta']
        hoy = hoy_colombia().isoformat()
        por_fecha = client.get('/reportes/historial', params={'placa': d['placa']['carro'], 'desde': hoy,
                                                              'hasta': hoy}).json()
        assert por_fecha['total'] == 1
        fuera = client.get('/reportes/historial', params={'placa': d['placa']['carro'], 'desde': '2020-01-01',
                                                          'hasta': '2020-01-31'}).json()
        assert fuera['total'] == 0 and fuera['items'] == []
