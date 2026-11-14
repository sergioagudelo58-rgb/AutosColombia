"""Sesión actual y permisos por perfil, validados en el servidor en cada operación (RF-02, RNF-05)."""
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auditoria import Actor, registrar
from app.database import get_session
from app.models import Sesion
from app.seguridad import INACTIVIDAD, hash_token

MENSAJES_CIERRE = {
    "LOGOUT": "Cerraste la sesión. Ingresa de nuevo para continuar.",
    "INACTIVIDAD": "Tu sesión se cerró tras 15 minutos sin actividad. Ingresa de nuevo.",
    "RETIRO": "Usuario inactivo. Comuníquese con el administrador.",
    "CERRADA_ADMIN": "El administrador cerró tu sesión. Ingresa de nuevo.",
    "CONTRASENA_RESTABLECIDA": "Tu contraseña fue restablecida. Ingresa con la contraseña temporal.",
}
SIN_PERMISO = "No tiene permiso para esta acción."
CAMBIA_TEMPORAL = "Debes cambiar tu contraseña temporal antes de continuar."
TOQUE = timedelta(seconds=5)
"""La última actividad se actualiza como mucho cada 5 s para no escribir en cada consulta del mapa."""


def equipo_de(request: Request) -> str:
    ip = request.client.host if request.client else "desconocido"
    agente = (request.headers.get("user-agent") or "")[:80]
    return f"{ip} · {agente}" if agente else ip


def _no_autorizado(detalle: str, codigo: str = "SIN_SESION") -> HTTPException:
    return HTTPException(401, detail=detalle, headers={"WWW-Authenticate": "Bearer", "X-Motivo-Sesion": codigo})


def cerrar(session: Session, sesion: Sesion, motivo: str, ahora: datetime) -> None:
    sesion.cerrada = ahora
    sesion.motivo_cierre = motivo


def _cargar(request: Request, session: Session, tocar: bool, permitir_temporal: bool) -> Actor:
    cabecera = request.headers.get("authorization", "")
    tipo, _, token = cabecera.partition(" ")
    if tipo.lower() != "bearer" or not token.strip():
        raise _no_autorizado("Inicia sesión para continuar.")
    error: HTTPException | None = None
    actor: Actor | None = None
    temporal = False
    with session.begin():
        sesion = session.scalar(
            select(Sesion).options(joinedload(Sesion.operador), joinedload(Sesion.puerta))
            .where(Sesion.token_hash == hash_token(token.strip()))
        )
        ahora = datetime.now(timezone.utc)
        if sesion is None:
            error = _no_autorizado("Inicia sesión para continuar.")
        elif sesion.cerrada is not None:
            motivo = sesion.motivo_cierre or "LOGOUT"
            error = _no_autorizado(MENSAJES_CIERRE.get(motivo, MENSAJES_CIERRE["LOGOUT"]), motivo)
        else:
            usuario = sesion.operador
            actor = Actor(id=usuario.id, usuario=usuario.usuario, nombre=usuario.nombre, rol=usuario.rol,
                          puerta_id=sesion.puerta_id, puerta=sesion.puerta.nombre if sesion.puerta else None,
                          sesion_id=sesion.id, equipo=sesion.equipo)
            if usuario.estado != "ACTIVO":
                cerrar(session, sesion, "RETIRO", ahora)
                error = _no_autorizado(MENSAJES_CIERRE["RETIRO"], "RETIRO")
            elif ahora - sesion.ultima_actividad > INACTIVIDAD:
                cerrar(session, sesion, "INACTIVIDAD", ahora)
                registrar(session, actor, "SESION_VENCIDA", "Sesión cerrada por 15 minutos sin actividad.",
                          entidad="sesion", entidad_id=sesion.id)
                error = _no_autorizado(MENSAJES_CIERRE["INACTIVIDAD"], "INACTIVIDAD")
            else:
                temporal = usuario.contrasena_temporal
                if tocar and ahora - sesion.ultima_actividad > TOQUE:
                    sesion.ultima_actividad = ahora
    if error is not None:
        raise error
    if temporal and not permitir_temporal:
        raise HTTPException(403, detail=CAMBIA_TEMPORAL, headers={"X-Motivo-Sesion": "CONTRASENA_TEMPORAL"})
    return actor


DbSession = Annotated[Session, Depends(get_session)]


def sesion_actual(request: Request, session: DbSession) -> Actor:
    """Cualquier usuario con sesión abierta y contraseña definitiva."""
    return _cargar(request, session, tocar=True, permitir_temporal=False)


def sesion_con_temporal(request: Request, session: DbSession) -> Actor:
    """Permite usuarios con contraseña temporal: cambiar contraseña, cerrar sesión."""
    return _cargar(request, session, tocar=True, permitir_temporal=True)


def sesion_sin_actividad(request: Request, session: DbSession) -> Actor:
    """Consultas automáticas (estado de la sesión, mapa cada 2 s): no cuentan como actividad (RNF-04).
    El estado de la sesión se puede consultar con contraseña temporal; el mapa no."""
    return _cargar(request, session, tocar=False, permitir_temporal=request.url.path.startswith("/auth/"))


def solo_admin(request: Request, session: DbSession, actor: Annotated[Actor, Depends(sesion_actual)]) -> Actor:
    """RNF-05: una acción de administrador hecha por un operador se rechaza y queda en la auditoría."""
    if not actor.es_admin:
        registrar(session, actor, "ACCESO_DENEGADO",
                  f"Intentó {request.method} {request.url.path} sin permiso de administrador.",
                  entidad="ruta", entidad_id=request.url.path)
        session.commit()
        raise HTTPException(403, detail=SIN_PERMISO)
    return actor


SesionActual = Annotated[Actor, Depends(sesion_actual)]
Administrador = Annotated[Actor, Depends(solo_admin)]
