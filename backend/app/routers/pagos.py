from typing import Annotated

from fastapi import APIRouter, Query

from app.auth import DbSession, SesionActual
from app.schemas.cliente import Documento
from app.schemas.pago import ConsultaPago, PagoCrear, PagoRespuesta
from app.schemas.vehiculo import Placa
from app.services.pago import ServicioPago

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.get("/consulta", response_model=ConsultaPago,
            summary="Buscar cliente y vehículo por cédula y placa y ver hasta cuándo va la mensualidad (RF-01, RF-03)")
def consultar(actor: SesionActual, session: DbSession, cedula: Annotated[Documento, Query()],
              placa: Annotated[Placa, Query()]) -> ConsultaPago:
    return ServicioPago(session).consultar(cedula, placa)


@router.post("", response_model=PagoRespuesta, status_code=201,
             summary="Registrar el pago de la mensualidad; el usuario sale de la sesión (RF-01, RF-03)")
def registrar(data: PagoCrear, actor: SesionActual, session: DbSession) -> PagoRespuesta:
    return ServicioPago(session).registrar(data, actor)
