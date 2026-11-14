"""Utilidades comunes: fijar quién hace la operación sin pasar por el inicio de sesión.

Las pruebas de los módulos de entrada, salida, reportes y vehículos verifican reglas del negocio; el
inicio de sesión, los permisos y el cierre por inactividad se prueban por HTTP en test_auth_postgres.py.
"""
from contextlib import contextmanager

import pytest

from app.auditoria import Actor
from app.auth import sesion_actual, sesion_con_temporal, sesion_sin_actividad
from app.main import app

ADMIN_PRUEBA = Actor(id=1, usuario="prueba_admin", nombre="Admin Prueba", rol="ADMINISTRADOR", puerta_id=1,
                     puerta="Puerta 1", sesion_id=None, equipo="pruebas")


def actor_de(operador, puerta=None, rol: str | None = None) -> Actor:
    return Actor(id=operador.id, usuario=operador.usuario, nombre=operador.nombre, rol=rol or operador.rol,
                 puerta_id=puerta.id if puerta is not None else None,
                 puerta=puerta.nombre if puerta is not None else None, sesion_id=None, equipo="pruebas")


@contextmanager
def como(actor: Actor):
    """Las solicitudes dentro del bloque se hacen con la sesión de `actor`."""
    anteriores = {d: app.dependency_overrides.get(d) for d in (sesion_actual, sesion_con_temporal, sesion_sin_actividad)}
    for dependencia in anteriores:
        app.dependency_overrides[dependencia] = lambda: actor
    try:
        yield actor
    finally:
        for dependencia, anterior in anteriores.items():
            if anterior is None:
                app.dependency_overrides.pop(dependencia, None)
            else:
                app.dependency_overrides[dependencia] = anterior


@pytest.fixture
def sesion_admin():
    """Para pruebas de validación sin base de datos: hay sesión de administrador."""
    with como(ADMIN_PRUEBA) as actor:
        yield actor


CABECERA = "X-Prueba-Actor"


def cabecera(operador_id: int, puerta_id: int | None = 1, rol: str = "OPERADOR") -> dict:
    """Cabecera para pruebas: la solicitud se hace como ese usuario, en esa puerta."""
    return {CABECERA: f"{operador_id}:{puerta_id or ''}:{rol}"}


@contextmanager
def actor_por_cabecera():
    """Toma el usuario y la puerta de la cabecera X-Prueba-Actor; sin cabecera, actúa el administrador."""
    from fastapi import Request

    def resolver(request: Request) -> Actor:
        valor = request.headers.get(CABECERA)
        if not valor:
            return ADMIN_PRUEBA
        operador_id, puerta_id, rol = valor.split(":")
        puerta = int(puerta_id) if puerta_id else None
        return Actor(id=int(operador_id), usuario=f"prueba{operador_id}", nombre=f"Prueba {operador_id}", rol=rol,
                     puerta_id=puerta, puerta=f"Puerta {puerta}" if puerta else None, sesion_id=None,
                     equipo="pruebas")

    dependencias = (sesion_actual, sesion_con_temporal, sesion_sin_actividad)
    for dependencia in dependencias:
        app.dependency_overrides[dependencia] = resolver
    try:
        yield
    finally:
        for dependencia in dependencias:
            app.dependency_overrides.pop(dependencia, None)


def borrar_auditoria_de_pruebas(session) -> None:
    """La bitácora es de solo lectura (RNF-07). Solo la limpieza de pruebas desactiva el trigger, dentro de
    su propia transacción, para borrar los registros hechos con equipo «pruebas»."""
    from sqlalchemy import text
    session.execute(text("ALTER TABLE auditoria DISABLE TRIGGER tg_auditoria_solo_lectura"))
    session.execute(text("DELETE FROM auditoria WHERE equipo = 'pruebas'"))
    session.execute(text("ALTER TABLE auditoria ENABLE TRIGGER tg_auditoria_solo_lectura"))
