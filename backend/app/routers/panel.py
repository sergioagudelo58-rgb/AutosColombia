from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.reporte import Panel
from app.services.panel import ServicioPanel

router = APIRouter(prefix="/panel", tags=["Panel"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("", response_model=Panel,
            summary="Mapa de celdas, contadores por tipo y actividad reciente de las puertas (RF-08)")
def panel(session: DatabaseSession) -> Panel:
    return ServicioPanel(session).panel()
