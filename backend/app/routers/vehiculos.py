from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.auth import Administrador, SesionActual
from app.database import get_session
from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear, VehiculoRespuesta, VehiculosPagina
from app.services import vehiculo as service

router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])
DatabaseSession = Annotated[Session, Depends(get_session)]
VehicleId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=VehiculoRespuesta, status_code=201)
def create(data: VehiculoCrear, actor: SesionActual, session: DatabaseSession):
    return service.create_vehicle(session, data, actor)


@router.get("", response_model=VehiculosPagina)
def list_all(
    actor: SesionActual,
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return service.list_vehicles(session, offset, limit)


@router.get("/{id}", response_model=VehiculoRespuesta)
def get_one(id: VehicleId, actor: SesionActual, session: DatabaseSession):
    return service.get_vehicle(session, id)


@router.patch("/{id}", response_model=VehiculoRespuesta)
def update(id: VehicleId, data: VehiculoActualizar, actor: Administrador, session: DatabaseSession):
    return service.update_vehicle(session, id, data, actor)


@router.delete("/{id}", status_code=204)
def delete(id: VehicleId, actor: Administrador, session: DatabaseSession) -> Response:
    service.delete_vehicle(session, id, actor)
    return Response(status_code=204)
