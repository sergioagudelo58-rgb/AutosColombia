from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auditoria import Actor
from app.models import Pago, Vehiculo
from app.services.auditoria import registrar as auditar
from app.services.mensualidad import hoy_colombia
from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear
from app.tarifas import mensaje_tarifa, valor_corresponde

FECHA_FUTURA = "La fecha de pago no puede ser posterior a hoy."


class VehiculoError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def database_operation(operation):
    """Centraliza rollback y mensajes públicos sin detalles del driver."""
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505" and constraint == "uq_vehiculo_placa":
                raise VehiculoError(409, "Ya existe un vehículo con esa placa.") from None
            if code == "23503" and constraint == "fk_vehiculo_cliente":
                raise VehiculoError(404, "Cliente no encontrado.") from None
            if code == "23503":
                raise VehiculoError(409, "El vehículo tiene registros relacionados y no se puede eliminar.") from None
            if code in {"23502", "23514"}:
                raise VehiculoError(422, "Los datos incumplen las restricciones del vehículo.") from None
            raise VehiculoError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise VehiculoError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_vehicle(session: Session, vehicle_id: int) -> Vehiculo:
    vehicle = session.get(Vehiculo, vehicle_id)
    if vehicle is None:
        raise VehiculoError(404, "Vehículo no encontrado.")
    return vehicle


@database_operation
def create_vehicle(session: Session, data: VehiculoCrear, actor: Actor) -> Vehiculo:
    """Registra el vehículo y su primer pago en una sola transacción (RF-04, RN-08)."""
    if data.fecha_pago > hoy_colombia():
        raise VehiculoError(422, FECHA_FUTURA)
    # RN-12: el primer pago debe valer la tarifa del tipo de vehículo; si no coincide, no se guarda nada.
    if not valor_corresponde(data.tipo, data.valor):
        raise VehiculoError(422, mensaje_tarifa(data.tipo))
    datos_vehiculo = data.model_dump(exclude={"valor", "medio"})
    vehicle = Vehiculo(**datos_vehiculo)
    session.add(vehicle)
    session.flush()
    auditar(session, accion="VEHICULO_CREADO", entidad="vehiculo", entidad_id=vehicle.id, placa=vehicle.placa,
            actor=actor, nuevo=datos_vehiculo)
    # El modelo ya calculó el vencimiento (fecha de pago + 30 días, sin corte anterior): el primer pago lo guarda.
    pago = Pago(vehiculo_id=vehicle.id, cliente_id=vehicle.cliente_id, fecha_pago=data.fecha_pago,
                valor=data.valor, medio=data.medio, vencimiento_anterior=None,
                vencimiento_nuevo=vehicle.fecha_vencimiento, operador_id=actor.id)
    session.add(pago)
    session.flush()
    auditar(session, accion="PAGO_REGISTRADO", entidad="pago", entidad_id=pago.id, placa=vehicle.placa,
            actor=actor,
            nuevo={"fecha_pago": data.fecha_pago, "valor": str(data.valor), "medio": data.medio,
                   "fecha_vencimiento": vehicle.fecha_vencimiento},
            detalle=f"Primer pago de {vehicle.placa} al registrar el vehículo; "
                    f"mensualidad hasta {vehicle.fecha_vencimiento.strftime('%d/%m/%Y')}.")
    session.commit()
    session.refresh(vehicle)
    return vehicle


@database_operation
def list_vehicles(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Vehiculo))
    items = list(session.scalars(select(Vehiculo).order_by(Vehiculo.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_vehicle(session: Session, vehicle_id: int) -> Vehiculo:
    return find_vehicle(session, vehicle_id)


@database_operation
def update_vehicle(session: Session, vehicle_id: int, data: VehiculoActualizar, actor: Actor) -> Vehiculo:
    vehicle = find_vehicle(session, vehicle_id)
    cambios_dict = data.model_dump(exclude_unset=True)
    anterior = {k: getattr(vehicle, k) for k, v in cambios_dict.items() if getattr(vehicle, k) != v}
    if anterior:
        auditar(session, accion="VEHICULO_MODIFICADO", entidad="vehiculo", entidad_id=vehicle.id,
                placa=vehicle.placa, actor=actor, anterior=anterior,
                nuevo={k: cambios_dict[k] for k in anterior})
    for key, value in cambios_dict.items():
        setattr(vehicle, key, value)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@database_operation
def delete_vehicle(session: Session, vehicle_id: int, actor: Actor) -> None:
    vehicle = find_vehicle(session, vehicle_id)
    auditar(session, accion="VEHICULO_ELIMINADO", entidad="vehiculo", entidad_id=vehicle.id, placa=vehicle.placa,
            actor=actor, anterior={"placa": vehicle.placa, "tipo": vehicle.tipo})
    session.delete(vehicle)
    session.commit()
