"""Iteración 2 contra PostgreSQL real, por HTTP y con tokens de sesión reales (RF-01 a RF-07).

Todo ocurre dentro de una transacción que se revierte al final: no quedan usuarios, sesiones ni
registros de auditoría en la base local.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.database import get_engine, get_session
from app.main import app
from app.models import Auditoria, Operador, Sesion
from app.seguridad import hash_contrasena

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")
CLAVE = "Portero2026"


def unico() -> str:
    return uuid4().hex[:8]


def telefono() -> str:
    return f"3{int(uuid4().hex[:8], 16) % 10**9:09d}"


class Api:
    def __init__(self, client: TestClient, session: Session) -> None:
        self.client, self.session = client, session

    def usuario(self, rol="OPERADOR", clave=CLAVE, temporal=False, **extra) -> Operador:
        nombre = f"u{unico()}"
        usuario = Operador(usuario=nombre, nombre=f"Prueba {nombre}", nombres="Prueba", apellidos=nombre,
                           telefono=telefono(), numero_documento=str(int(uuid4().hex[:10], 16))[:10],
                           tipo_documento="CC", rol=rol, estado="ACTIVO", contrasena_hash=hash_contrasena(clave),
                           contrasena_temporal=temporal, **extra)
        self.session.add(usuario)
        self.session.commit()
        # Desligado de la sesión: sus datos siguen disponibles aunque una solicitud revierta su transacción.
        self.session.expunge(usuario)
        return usuario

    def login(self, usuario: str, clave=CLAVE, puerta_id: int | None = 1):
        return self.client.post("/auth/login", json={"usuario": usuario, "contrasena": clave, "puerta_id": puerta_id})

    def token(self, usuario: str, clave=CLAVE, puerta_id: int | None = 1) -> dict:
        respuesta = self.login(usuario, clave, puerta_id)
        assert respuesta.status_code == 200, respuesta.text
        return {"Authorization": f"Bearer {respuesta.json()['token']}"}

    def auditoria(self, accion: str, usuario: str | None = None) -> list[Auditoria]:
        consulta = select(Auditoria).where(Auditoria.accion == accion)
        if usuario:
            consulta = consulta.where(Auditoria.usuario == usuario)
        filas = list(self.session.scalars(consulta.order_by(Auditoria.id)))
        self.session.commit()
        return filas


@pytest.fixture
def api():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0007b"
            with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as session:
                def override():
                    yield session
                    # Cada solicitud real usa su propia sesión; aquí se cierra la lectura pendiente.
                    if session.in_transaction():
                        session.commit()
                app.dependency_overrides[get_session] = override
                try:
                    with TestClient(app) as client:
                        yield Api(client, session)
                finally:
                    app.dependency_overrides.pop(get_session, None)
        finally:
            transaction.rollback()


def test_login_correcto_muestra_usuario_rol_y_puerta(api):
    """RF-01 caso 1: el ingreso queda a nombre del usuario, con su puerta."""
    operador = api.usuario()
    respuesta = api.login(operador.usuario.upper(), puerta_id=2)
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["usuario"] == operador.usuario and body["rol"] == "OPERADOR" and body["puerta"] == "Puerta 2"
    assert len(body["token"]) >= 40 and body["inactividad_segundos"] == 900
    guardada = api.session.scalar(select(Sesion).where(Sesion.operador_id == operador.id))
    api.session.commit()
    # RNF-01: en la base solo queda el hash del token, nunca el token.
    assert guardada.token_hash != body["token"] and len(guardada.token_hash) == 64
    sesion = api.client.get("/auth/sesion", headers={"Authorization": f"Bearer {body['token']}"}).json()
    assert sesion["puerta"] == "Puerta 2" and sesion["nombre"] == operador.nombre
    assert api.auditoria("LOGIN", operador.usuario)[0].puerta == "Puerta 2"


def test_error_generico_y_bloqueo_tras_cinco_intentos(api):
    """RF-01 caso 2 y RNF-03: mismo mensaje para usuario o clave errados; 5 fallos bloquean 15 minutos."""
    operador = api.usuario()
    inexistente = api.login("no_existe_" + unico())
    assert inexistente.status_code == 401 and inexistente.json()["detail"] == "Usuario o contraseña incorrectos."
    for intento in range(4):
        fallo = api.login(operador.usuario, "Equivocada1")
        assert fallo.status_code == 401 and fallo.json()["detail"] == "Usuario o contraseña incorrectos."
    quinto = api.login(operador.usuario, "Equivocada1")
    assert quinto.status_code == 423 and quinto.json()["detail"] == "Cuenta bloqueada por 15 minutos."
    # Bloqueada, ni siquiera la contraseña correcta entra.
    assert api.login(operador.usuario).status_code == 423
    assert len(api.auditoria("CUENTA_BLOQUEADA", operador.usuario)) == 1
    assert len(api.auditoria("LOGIN_FALLIDO", operador.usuario)) == 4


def test_operador_debe_elegir_puerta(api):
    operador = api.usuario()
    sin_puerta = api.login(operador.usuario, puerta_id=None)
    assert sin_puerta.status_code == 422 and "puerta" in sin_puerta.json()["detail"]
    admin = api.usuario("ADMINISTRADOR")
    assert api.login(admin.usuario, puerta_id=None).status_code == 200


def test_una_sesion_por_usuario_y_sesiones_simultaneas(api):
    """RF-03: dos operadores y el administrador a la vez; el mismo usuario no abre una segunda sesión."""
    uno, dos, admin = api.usuario(), api.usuario(), api.usuario("ADMINISTRADOR")
    cabeceras = [api.token(uno.usuario, puerta_id=1), api.token(dos.usuario, puerta_id=2),
                 api.token(admin.usuario, puerta_id=None)]
    assert all(api.client.get("/panel", headers=h).status_code == 200 for h in cabeceras)
    repetida = api.login(uno.usuario, puerta_id=2)
    assert repetida.status_code == 409 and "Puerta 1" in repetida.json()["detail"]
    # Al cerrar la sesión puede volver a ingresar, y el token anterior ya no sirve.
    assert api.client.post("/auth/logout", headers=cabeceras[0]).status_code == 204
    cerrado = api.client.get("/panel", headers=cabeceras[0])
    assert cerrado.status_code == 401 and cerrado.headers["X-Motivo-Sesion"] == "LOGOUT"
    assert api.login(uno.usuario, puerta_id=2).status_code == 200


def test_sesion_vence_tras_15_minutos_sin_actividad(api):
    """RNF-04: la consulta de estado no cuenta como actividad; tras 15 minutos la sesión se cierra."""
    operador = api.usuario()
    cabecera = api.token(operador.usuario)
    api.session.execute(update(Sesion).where(Sesion.operador_id == operador.id)
                        .values(ultima_actividad=datetime.now(timezone.utc) - timedelta(minutes=16)))
    api.session.commit()
    vencida = api.client.get("/panel", headers=cabecera)
    assert vencida.status_code == 401 and vencida.headers["X-Motivo-Sesion"] == "INACTIVIDAD"
    assert "15 minutos" in vencida.json()["detail"]
    assert len(api.auditoria("SESION_VENCIDA", operador.usuario)) == 1
    # Una sesión abandonada no impide volver a ingresar desde otro equipo.
    assert api.login(operador.usuario).status_code == 200


def test_permisos_por_perfil_se_validan_en_el_servidor(api):
    """RF-02 y RNF-05: el operador no accede a funciones de administrador y el intento queda auditado."""
    operador = api.usuario()
    cabecera = api.token(operador.usuario)
    for metodo, ruta in (("GET", "/usuarios"), ("GET", "/celdas"), ("GET", "/reportes/ocupacion"),
                         ("POST", "/celdas"), ("POST", "/usuarios")):
        respuesta = api.client.request(metodo, ruta, headers=cabecera, json={})
        assert respuesta.status_code == 403 and respuesta.json()["detail"] == "No tiene permiso para esta acción."
    assert len(api.auditoria("ACCESO_DENEGADO", operador.usuario)) == 5
    for ruta in ("/panel", "/clientes", "/vehiculos"):
        assert api.client.get(ruta, headers=cabecera).status_code == 200
    # Sin sesión no se accede a nada, salvo el inicio de sesión, las puertas y la salud del servicio.
    assert api.client.get("/panel").status_code == 401
    assert api.client.get("/puertas").status_code == 200


def test_contrasena_temporal_obliga_a_cambiarla(api):
    """RF-05 y RNF-02: con contraseña temporal solo se puede cambiarla; la nueva cumple la política."""
    operador = api.usuario(temporal=True, clave="Temporal99")
    cabecera = api.token(operador.usuario, "Temporal99")
    bloqueado = api.client.get("/panel", headers=cabecera)
    assert bloqueado.status_code == 403 and bloqueado.headers["X-Motivo-Sesion"] == "CONTRASENA_TEMPORAL"
    url = "/auth/cambiar-contrasena"
    debil = api.client.post(url, headers=cabecera, json={"actual": "Temporal99", "nueva": "corta",
                                                         "confirmacion": "corta"})
    assert debil.status_code == 422
    assert all(t in debil.json()["detail"] for t in ("mínimo 8 caracteres", "una letra mayúscula", "un número"))
    distinta = api.client.post(url, headers=cabecera, json={"actual": "Temporal99", "nueva": "Nueva2026x",
                                                            "confirmacion": "Nueva2026y"})
    assert distinta.status_code == 422 and "confirmación" in distinta.json()["detail"]
    errada = api.client.post(url, headers=cabecera, json={"actual": "Otra12345", "nueva": "Nueva2026x",
                                                          "confirmacion": "Nueva2026x"})
    assert errada.status_code == 422
    ok = api.client.post(url, headers=cabecera, json={"actual": "Temporal99", "nueva": "Nueva2026x",
                                                      "confirmacion": "Nueva2026x"})
    assert ok.status_code == 200 and ok.json()["contrasena_temporal"] is False
    assert api.client.get("/panel", headers=cabecera).status_code == 200
    guardada = api.session.get(Operador, operador.id)
    api.session.commit()
    assert guardada.contrasena_hash.startswith("$2") and "Nueva2026x" not in guardada.contrasena_hash


def test_administrador_gestiona_usuarios(api):
    """RF-04, RF-05, RF-06 y RF-07 de punta a punta."""
    admin = api.usuario("ADMINISTRADOR")
    h = api.token(admin.usuario, puerta_id=None)
    nombre = f"drios{unico()}"
    datos = {"tipo_documento": "CC", "numero_documento": str(int(uuid4().hex[:10], 16))[:10],
             "nombres": "Diana", "apellidos": "Ríos", "telefono": telefono(), "correo": "diana@correo.com",
             "usuario": nombre, "rol": "OPERADOR", "fecha_ingreso": "2026-11-01"}
    creado = api.client.post("/usuarios", headers=h, json=datos)
    assert creado.status_code == 201, creado.text
    nuevo = creado.json()
    temporal = nuevo["contrasena_generada"]
    assert nuevo["estado"] == "ACTIVO" and nuevo["contrasena_temporal"] and len(temporal) == 10
    duplicado = api.client.post("/usuarios", headers=h, json={**datos, "numero_documento": "99887766"})
    assert duplicado.status_code == 409 and duplicado.json()["detail"] == "El usuario ya existe."
    doc_repetido = api.client.post("/usuarios", headers=h, json={**datos, "usuario": f"otro{unico()}",
                                                                     "telefono": telefono()})
    assert doc_repetido.status_code == 409 and "documento" in doc_repetido.json()["detail"]
    # La contraseña temporal no se vuelve a mostrar.
    assert "contrasena_generada" not in api.client.get(f"/usuarios/{nuevo['id']}", headers=h).json()

    # RF-06: lista con «en línea»; el usuario no se cambia; la modificación guarda anterior y nuevo.
    hu = api.token(nombre, temporal, puerta_id=2)
    lista = api.client.get("/usuarios", headers=h, params={"q": nombre}).json()
    assert lista["items"][0]["en_linea"] and lista["items"][0]["puerta"] == "Puerta 2"
    assert api.client.patch(f"/usuarios/{nuevo['id']}", headers=h, json={"usuario": "otro"}).status_code == 422
    cambio = api.client.patch(f"/usuarios/{nuevo['id']}", headers=h, json={"correo": "diana.rios@correo.com"})
    assert cambio.status_code == 200 and cambio.json()["correo"] == "diana.rios@correo.com"
    registro = api.auditoria("USUARIO_MODIFICADO")[-1]
    assert registro.valor_anterior == {"correo": "diana@correo.com"}
    assert registro.valor_nuevo == {"correo": "diana.rios@correo.com"}

    # RF-05: restablecer genera otra temporal y cierra la sesión abierta del empleado.
    restablecida = api.client.post(f"/usuarios/{nuevo['id']}/restablecer-contrasena", headers=h).json()
    assert restablecida["contrasena_generada"] != temporal
    cerrada = api.client.get("/auth/sesion", headers=hu)
    assert cerrada.status_code == 401 and cerrada.headers["X-Motivo-Sesion"] == "CONTRASENA_RESTABLECIDA"
    hu = api.token(nombre, restablecida["contrasena_generada"], puerta_id=2)

    # RF-07: retirar exige motivo, cierra la sesión y bloquea el ingreso; reactivar da otra temporal.
    assert api.client.post(f"/usuarios/{nuevo['id']}/retirar", headers=h, json={"motivo": " "}).status_code == 422
    retiro = api.client.post(f"/usuarios/{nuevo['id']}/retirar", headers=h,
                             json={"motivo": "Terminó su contrato", "fecha_retiro": "2026-11-30"})
    assert retiro.status_code == 200 and retiro.json()["estado"] == "RETIRADO"
    expulsado = api.client.get("/panel", headers=hu)
    assert expulsado.status_code == 401 and expulsado.json()["detail"] == "Usuario inactivo. Comuníquese con el administrador."
    retirado = api.login(nombre, restablecida["contrasena_generada"], 2)
    assert retirado.status_code == 403 and retirado.json()["detail"] == "Usuario inactivo. Comuníquese con el administrador."
    reactivado = api.client.post(f"/usuarios/{nuevo['id']}/reactivar", headers=h).json()
    assert reactivado["estado"] == "ACTIVO" and reactivado["contrasena_temporal"]
    assert api.login(nombre, reactivado["contrasena_generada"], 2).status_code == 200


def test_no_se_retira_al_unico_administrador(api):
    """RF-07 y RNF-08: además de la validación del servicio, un trigger lo impide en la base."""
    admin, otro = api.usuario("ADMINISTRADOR"), api.usuario("ADMINISTRADOR")
    # Dentro de la transacción de prueba (se revierte), solo quedan estos dos administradores activos.
    api.session.execute(update(Operador).where(Operador.rol == "ADMINISTRADOR",
                                               Operador.id.not_in([admin.id, otro.id])).values(rol="OPERADOR"))
    api.session.commit()
    h = api.token(admin.usuario, puerta_id=None)
    assert api.client.post(f"/usuarios/{admin.id}/retirar", headers=h, json={"motivo": "x"}).status_code == 409
    assert api.client.post(f"/usuarios/{otro.id}/retirar", headers=h, json={"motivo": "Se fue"}).status_code == 200
    ultimo = api.client.patch(f"/usuarios/{admin.id}", headers=h, json={"rol": "OPERADOR"})
    assert ultimo.status_code == 409 and "administrador activo" in ultimo.json()["detail"]



def test_auditoria_de_usuarios_es_de_solo_lectura(api):
    """RNF-07: los eventos de sesión y de usuarios quedan en una bitácora que nadie modifica."""
    admin = api.usuario("ADMINISTRADOR")
    api.token(admin.usuario, puerta_id=None)
    registro = api.auditoria("LOGIN", admin.usuario)[0]
    assert registro.rol == "ADMINISTRADOR" and registro.equipo
    with pytest.raises(Exception, match="solo lectura"):
        api.session.execute(text("UPDATE auditoria SET detalle = 'x' WHERE id = :id"), {"id": registro.id})
    api.session.rollback()
