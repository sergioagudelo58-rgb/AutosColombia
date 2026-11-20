"""Contratos de la gestión de pagos (iteración 3: RF-01 y RF-03)."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.cliente import ClienteRespuesta, Documento
from app.schemas.vehiculo import Placa, VehiculoRespuesta
from app.services.mensualidad import Mensualidad

MedioPago = Literal["BANCO", "EFECTIVO", "QR"]
# Igual que la columna pago.valor: NUMERIC(12, 2), mayor que cero (RNF-04).
ValorPago = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class PagoCrear(BaseModel):
    """RF-01: lo que digita el operario. El usuario que registra sale de la sesión, no del cuerpo."""
    model_config = ConfigDict(extra="forbid")
    cedula: Documento
    placa: Placa
    fecha_pago: date
    valor: ValorPago
    medio: MedioPago

    @field_validator("cedula", "placa", "fecha_pago", "valor", "medio", mode="before")
    @classmethod
    def obligatorio(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("Este dato es obligatorio.")
        return value


class ConsultaPago(BaseModel):
    """RF-01 y RF-03: cliente, vehículo y hasta cuándo va la mensualidad, antes de registrar el pago."""
    cliente: ClienteRespuesta
    vehiculo: VehiculoRespuesta
    mensualidad: Mensualidad


class PagoRespuesta(BaseModel):
    """RF-03: el pago guardado y la fecha hasta la que va la mensualidad, para decírsela al cliente."""
    id: int
    cedula: str
    cliente: str
    placa: str
    fecha_pago: date
    valor: Decimal
    medio: MedioPago
    vencimiento_anterior: date | None
    vencimiento_nuevo: date
    registrado_por: str
    registrado_en: datetime
    mensualidad: Mensualidad

    @field_validator("registrado_en")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)
