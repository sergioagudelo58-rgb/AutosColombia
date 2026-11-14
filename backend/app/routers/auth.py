from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auditoria import Actor
from app.auth import SesionActual, equipo_de, sesion_con_temporal, sesion_sin_actividad
from app.database import get_session
from app.schemas.auth import AccesoDenegado, CambioContrasena, LoginCrear, LoginRespuesta, PuertaTurno, SesionRespuesta
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["Sesión"])
DbSession = Annotated[Session, Depends(get_session)]
ConTemporal = Annotated[Actor, Depends(sesion_con_temporal)]


@router.post("/login", response_model=LoginRespuesta)
def login(data: LoginCrear, request: Request, session: DbSession) -> dict:
    return service.login(session, data, equipo_de(request))


@router.post("/logout", status_code=204)
def logout(actor: ConTemporal, session: DbSession) -> Response:
    service.logout(session, actor)
    return Response(status_code=204)


@router.get("/sesion", response_model=SesionRespuesta)
def sesion(actor: Annotated[Actor, Depends(sesion_sin_actividad)], session: DbSession) -> dict:
    """Consulta del estado de la sesión: no reinicia el conteo de inactividad."""
    return service.sesion(session, actor)


@router.post("/cambiar-contrasena", response_model=SesionRespuesta)
def cambiar_contrasena(data: CambioContrasena, actor: ConTemporal, session: DbSession) -> dict:
    return service.cambiar_contrasena(session, actor, data)


@router.patch("/sesion", response_model=SesionRespuesta)
def cambiar_puerta(data: PuertaTurno, actor: SesionActual, session: DbSession) -> dict:
    return service.cambiar_puerta(session, actor, data.puerta_id)


@router.post("/acceso-denegado", status_code=204)
def acceso_denegado(data: AccesoDenegado, actor: SesionActual, session: DbSession) -> Response:
    service.acceso_denegado(session, actor, data.ruta)
    return Response(status_code=204)
