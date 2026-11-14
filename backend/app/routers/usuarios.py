from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.auth import Administrador
from app.database import get_session
from app.schemas.usuario import (Retiro, UsuarioActualizar, UsuarioConTemporal, UsuarioCrear, UsuarioRespuesta,
                                 UsuariosPagina)
from app.services import usuario as service

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])
DbSession = Annotated[Session, Depends(get_session)]
UsuarioId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=UsuarioConTemporal, status_code=201)
def crear(data: UsuarioCrear, actor: Administrador, session: DbSession) -> dict:
    return service.crear(session, actor, data)


@router.get("", response_model=UsuariosPagina)
def listar(
    actor: Administrador, session: DbSession,
    estado: Literal["ACTIVO", "RETIRADO"] | None = None,
    rol: Literal["ADMINISTRADOR", "OPERADOR"] | None = None,
    q: Annotated[str | None, Query(max_length=60)] = None,
) -> dict:
    return service.listar(session, estado, rol, q)


@router.get("/{id}", response_model=UsuarioRespuesta)
def obtener(id: UsuarioId, actor: Administrador, session: DbSession) -> dict:
    return service.obtener(session, id)


@router.patch("/{id}", response_model=UsuarioRespuesta)
def actualizar(id: UsuarioId, data: UsuarioActualizar, actor: Administrador, session: DbSession) -> dict:
    return service.actualizar(session, actor, id, data)


@router.post("/{id}/retirar", response_model=UsuarioRespuesta)
def retirar(id: UsuarioId, data: Retiro, actor: Administrador, session: DbSession) -> dict:
    return service.retirar(session, actor, id, data)


@router.post("/{id}/reactivar", response_model=UsuarioConTemporal)
def reactivar(id: UsuarioId, actor: Administrador, session: DbSession) -> dict:
    return service.reactivar(session, actor, id)


@router.post("/{id}/restablecer-contrasena", response_model=UsuarioConTemporal)
def restablecer(id: UsuarioId, actor: Administrador, session: DbSession) -> dict:
    return service.restablecer_contrasena(session, actor, id)


@router.post("/{id}/desbloquear", response_model=UsuarioRespuesta)
def desbloquear(id: UsuarioId, actor: Administrador, session: DbSession) -> dict:
    return service.desbloquear(session, actor, id)


@router.post("/{id}/cerrar-sesion", response_model=UsuarioRespuesta)
def cerrar_sesion(id: UsuarioId, actor: Administrador, session: DbSession) -> dict:
    return service.cerrar_sesion(session, actor, id)
