from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.auth import Administrador, DbSession
from app.schemas.auditoria import AuditoriaPagina
from app.services import auditoria as service

# Solo consulta: la auditoría no se edita ni se borra (RNF-07). Exclusiva del administrador (RF-02, RF-10).
router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


@router.get("", response_model=AuditoriaPagina)
def listar(
    session: DbSession,
    actor: Administrador,
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
