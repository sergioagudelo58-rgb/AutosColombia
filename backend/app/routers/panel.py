from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auditoria import Actor
from app.auth import sesion_sin_actividad
from app.database import get_session
from app.schemas.reporte import Panel
from app.services.panel import ServicioPanel

router = APIRouter(prefix="/panel", tags=["Panel"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("", response_model=Panel,
            summary="Mapa de celdas, contadores por tipo y actividad reciente de las puertas (RF-08)")
def panel(actor: Annotated[Actor, Depends(sesion_sin_actividad)], session: DatabaseSession) -> Panel:
    """El mapa se actualiza solo cada 2 s: esa consulta no cuenta como actividad del usuario (RNF-04)."""
    return ServicioPanel(session).panel()
