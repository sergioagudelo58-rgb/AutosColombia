"""Contratos de la gestión de pagos (iteración 3: RF-01 y RF-03)."""
from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.cliente import ClienteRespuesta, Documento
# MedioPago y ValorPago viven en schemas.vehiculo: el vehículo nuevo guarda su primer pago (RF-04).
from app.schemas.vehiculo import MedioPago, Placa, ValorPago, VehiculoRespuesta
from app.services.mensualidad import Mensualidad


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
