"""Vigencia de la mensualidad (iteración 1: RN-06, RN-07, RF-04) y cálculo del nuevo vencimiento al
registrar un pago (iteración 3: RF-02, RN-06 a RN-09). Sin acceso a base de datos."""

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

ZONA_COLOMBIA = ZoneInfo("America/Bogota")
# RN-07: la mensualidad es siempre de 30 días, no de un mes calendario.
DIAS_MENSUALIDAD = 30


def calcular_vencimiento(vencimiento_anterior: date | None, fecha_pago: date) -> date:
    """Nueva fecha de vencimiento al registrar un pago (RF-02).

    - Primer pago, sin fecha de corte anterior (RN-08): fecha de pago + 30 días.
    - Con fecha de corte (RN-06, RN-07, RN-09): corte + 30 días, sin importar si el cliente pagó
      tarde o antes del vencimiento, para que no se pierdan ni se regalen días.
    """
    if not isinstance(fecha_pago, date) or isinstance(fecha_pago, datetime):
        raise ValueError("La fecha de pago debe ser una fecha (sin hora).")
    if vencimiento_anterior is not None and (
        not isinstance(vencimiento_anterior, date) or isinstance(vencimiento_anterior, datetime)
    ):
        raise ValueError("La fecha de corte debe ser una fecha (sin hora).")
    corte = fecha_pago if vencimiento_anterior is None else vencimiento_anterior
    return corte + timedelta(days=DIAS_MENSUALIDAD)

EstadoMensualidad = Literal["VIGENTE", "VENCE_HOY", "VENCIDA", "SIN_PAGO", "SIN_CLIENTE"]


class Mensualidad(BaseModel):
    estado: EstadoMensualidad
    fecha_pago: date | None
    fecha_vencimiento: date | None
    dias: int | None
    """Días que faltan (vigente) o que han pasado desde el vencimiento (vencida)."""
    permite_ingreso: bool
    mensaje: str


def hoy_colombia() -> date:
    """RNF-11: la fecha la decide el servidor en la zona horaria de Colombia."""
    return datetime.now(ZONA_COLOMBIA).date()


def _fecha(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def evaluar_mensualidad(
    cliente_id: int | None, fecha_pago: date | None, fecha_vencimiento: date | None, hoy: date
) -> Mensualidad:
    if cliente_id is None:
        return Mensualidad(
            estado="SIN_CLIENTE", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=None,
            permite_ingreso=False,
            mensaje="El vehículo no está asociado a un cliente. Asócialo antes de registrar el ingreso.",
        )
    if fecha_pago is None or fecha_vencimiento is None:
        return Mensualidad(
            estado="SIN_PAGO", fecha_pago=None, fecha_vencimiento=None, dias=None, permite_ingreso=False,
            mensaje="El vehículo no tiene una mensualidad registrada. Registra la fecha de pago.",
        )
    dias = (fecha_vencimiento - hoy).days
    if dias > 0:
        return Mensualidad(
            estado="VIGENTE", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=dias,
            permite_ingreso=True, mensaje=f"Mensualidad vigente hasta {_fecha(fecha_vencimiento)}.",
        )
    if dias == 0:
        return Mensualidad(
            estado="VENCE_HOY", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=0,
            permite_ingreso=True, mensaje="La mensualidad vence hoy. Recuerda al cliente renovarla.",
        )
    vencidos = -dias
    return Mensualidad(
        estado="VENCIDA", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=vencidos,
        permite_ingreso=False,
        mensaje=f"Mensualidad vencida hace {vencidos} {'día' if vencidos == 1 else 'días'} "
                f"(venció el {_fecha(fecha_vencimiento)}). No se permite el ingreso.",
    )
