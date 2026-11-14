from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.auth import solo_admin
from app.database import get_session
from app.schemas.celda import (
    CambioEstado, CeldaActualizar, CeldaCrear, CeldaDetalle, CeldasPagina, EstadoCelda, TipoCelda,
)
from app.services import celda as service

# RF-02: la administración de celdas es solo del administrador.
router = APIRouter(prefix="/celdas", tags=["Celdas"], dependencies=[Depends(solo_admin)])
DatabaseSession = Annotated[Session, Depends(get_session)]
CellId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=CeldaDetalle, status_code=201)
def create(data: CeldaCrear, session: DatabaseSession):
    return service.create_cell(session, data)


@router.get("", response_model=CeldasPagina)
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=50, description="Búsqueda parcial por código")] = None,
    tipo: TipoCelda | None = None,
    estado: EstadoCelda | None = None,
):
    return service.list_cells(session, offset, limit, q, tipo, estado)


@router.get("/{id}", response_model=CeldaDetalle)
def get_one(id: CellId, session: DatabaseSession):
    return service.get_cell(session, id)


@router.patch("/{id}", response_model=CeldaDetalle)
def update(id: CellId, data: CeldaActualizar, session: DatabaseSession):
    return service.update_cell(session, id, data)


@router.post("/{id}/inhabilitar", response_model=CeldaDetalle)
def disable(id: CellId, data: CambioEstado, session: DatabaseSession):
    return service.disable_cell(session, id, data.motivo)


@router.post("/{id}/habilitar", response_model=CeldaDetalle)
def enable(id: CellId, data: CambioEstado, session: DatabaseSession):
    return service.enable_cell(session, id, data.motivo)


@router.post("/{id}/eliminar", response_model=CeldaDetalle)
def delete(id: CellId, data: CambioEstado, session: DatabaseSession):
    """Borrado lógico (RF-15): no existe DELETE porque la celda y su historial se conservan."""
    return service.delete_cell(session, id, data.motivo)