from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.estancia import (
    CambioCeldaCrear, CambioCeldaRespuesta, ConsultaVehiculo, EntradaCrear, MovimientoRespuesta, Recibo, SalidaCrear,
)
from app.schemas.vehiculo import Placa
from app.services.estancia import ServicioEstancia

router = APIRouter(prefix="/estancias", tags=["Estancias"])
DatabaseSession = Annotated[Session, Depends(get_session)]
EstanciaId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("/entrada", response_model=MovimientoRespuesta, status_code=201,
             summary="Registrar entrada con asignación automática de celda y recibo (RF-05)")
def entrada(data: EntradaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).entrada(data)


@router.get("/abierta", response_model=MovimientoRespuesta,
            summary="Ingreso abierto por placa o número de recibo, antes de confirmar la salida (RF-07)")
def abierta(session: DatabaseSession, placa: Annotated[Placa | None, Query()] = None,
            recibo: Annotated[Recibo | None, Query()] = None) -> MovimientoRespuesta:
    return ServicioEstancia(session).abierta(placa, recibo)


@router.post("/salida", response_model=MovimientoRespuesta,
             summary="Registrar salida por placa o recibo, con operador y puerta (RF-07)")
def salida(data: SalidaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).salida(data)


@router.post("/{id}/celda", response_model=CambioCeldaRespuesta,
             summary="Cambiar o intercambiar la celda de un ingreso abierto (RF-09)")
def cambiar_celda(id: EstanciaId, data: CambioCeldaCrear, session: DatabaseSession) -> CambioCeldaRespuesta:
    return ServicioEstancia(session).cambiar_celda(id, data)


@router.get("/vehiculo/{placa}", response_model=ConsultaVehiculo,
            summary="Consultar vehículo y validar mensualidad (RF-03, RF-04)")
def consultar(placa: Placa, session: DatabaseSession) -> ConsultaVehiculo:
    return ServicioEstancia(session).consultar(placa)


@router.get("/recibo/{numero_recibo}", response_model=MovimientoRespuesta, summary="Recibo de ingreso (RF-05)")
def recibo(numero_recibo: Recibo, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).recibo(numero_recibo)
