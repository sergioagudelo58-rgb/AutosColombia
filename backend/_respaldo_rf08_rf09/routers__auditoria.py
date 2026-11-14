from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.auditoria import AuditoriaPagina
from app.services import auditoria as service

# Solo consulta: la auditoría no se edita ni se borra (RNF-07). Será exclusiva del administrador (RF-02).
router = APIRouter(prefix="/auditoria", tags=["Auditoría"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("", response_model=AuditoriaPagina)
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    usuario: Annotated[str | None, Query(max_length=100, description="Búsqueda parcial por usuario")] = None,
    desde: Annotated[date | None, Query(description="Fecha inicial (hora de Colombia)")] = None,
    hasta: Annotated[date | None, Query(description="Fecha final, inclusive (hora de Colombia)")] = None,
    accion: Annotated[str | None, Query(max_length=60, description="Por ejemplo INGRESO, SALIDA, CAMBIO_CELDA")] = None,
    placa: Annotated[str | None, Query(max_length=20, description="Búsqueda parcial por placa")] = None,
):
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=422, detail="La fecha inicial no puede ser posterior a la final.")
    return service.listar(session, offset, limit, usuario, desde, hasta, accion, placa)