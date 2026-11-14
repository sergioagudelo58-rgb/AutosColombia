from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import solo_admin
from app.database import get_session
from app.schemas.reporte import HistorialPagina, ReporteOcupacion
from app.services.reporte import ServicioReporte

router = APIRouter(prefix="/reportes", tags=["Reportes"], dependencies=[Depends(solo_admin)])
DatabaseSession = Annotated[Session, Depends(get_session)]
Fecha = Annotated[date | None, Query(description="Día calendario de Colombia (AAAA-MM-DD)")]


@router.get("/ocupacion", response_model=ReporteOcupacion,
            summary="Reporte de ocupación; el rango por defecto es el día actual (RF-10)")
def ocupacion(session: DatabaseSession, desde: Fecha = None, hasta: Fecha = None) -> ReporteOcupacion:
    return ServicioReporte(session).ocupacion(desde, hasta)


@router.get("/historial", response_model=HistorialPagina,
            summary="Historial de ingresos, salidas y novedades por placa, cliente o fechas (RF-11)")
def historial(
    session: DatabaseSession,
    placa: Annotated[str | None, Query(max_length=10)] = None,
    cliente: Annotated[str | None, Query(max_length=100, description="Documento o nombre")] = None,
    desde: Fecha = None,
    hasta: Fecha = None,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> HistorialPagina:
    return ServicioReporte(session).historial(placa, cliente, desde, hasta, offset, limit)
