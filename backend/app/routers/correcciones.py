from typing import Annotated

from fastapi import APIRouter, Path

from app.auth import Administrador, DbSession
from app.schemas.correccion import CorreccionCrear
from app.schemas.estancia import MovimientoRespuesta
from app.services.correccion import ServicioCorreccion

router = APIRouter(prefix="/estancias", tags=["Correcciones"])
EstanciaId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("/{id}/corregir", response_model=MovimientoRespuesta,
             summary="Corregir o anular la salida de un registro; solo administrador, con motivo (RF-09)")
def corregir(id: EstanciaId, data: CorreccionCrear, actor: Administrador,
             session: DbSession) -> MovimientoRespuesta:
    return ServicioCorreccion(session).corregir(id, data, actor)
