"""Registro de pagos de la mensualidad (iteración 3: RF-01 y RF-03).

El pago se registra solo en la plataforma, sin pasarela (RN-01). El operario digita la cédula del cliente,
la placa, la fecha de pago, el valor y el medio; el nuevo vencimiento lo calcula Vehiculo.aplicar_pago
desde la fecha de corte (RF-02). El usuario que registra sale de la sesión (RNF-03).
"""
from functools import wraps

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auditoria import Actor
from app.errores import ApiError
from app.models import Cliente, Pago, Vehiculo
from app.schemas.cliente import ClienteRespuesta
from app.schemas.pago import ConsultaPago, PagoCrear, PagoRespuesta
from app.schemas.vehiculo import VehiculoRespuesta
from app.services.auditoria import registrar as auditar
from app.services.mensualidad import evaluar_mensualidad, hoy_colombia
from app.tarifas import mensaje_tarifa, valor_corresponde

# Notificaciones del documento (RF-01, HU-01).
CLIENTE_NO_REGISTRADO = "El cliente no está registrado."
VEHICULO_NO_REGISTRADO = "El vehículo no está registrado."
VEHICULO_DE_OTRO_CLIENTE = "El vehículo no pertenece a este cliente."
FECHA_FUTURA = "La fecha de pago no puede ser posterior a hoy."


def _transaccion(operation):
    """Una transacción por solicitud; los errores de la base de datos salen como mensajes públicos."""
    @wraps(operation)
    def wrapped(self, *args, **kwargs):
        try:
            with self.session.begin():
                return operation(self, *args, **kwargs)
        except IntegrityError as error:
            self.session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            if code == "23503":
                raise ApiError(404, "Una de las referencias ya no existe. Actualiza los datos.") from None
            raise ApiError(422, "Los datos del pago no cumplen las reglas de la mensualidad.") from None
        except SQLAlchemyError:
            self.session.rollback()
            raise ApiError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


class ServicioPago:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _cliente_y_vehiculo(self, cedula: str, placa: str, bloquear: bool) -> tuple[Cliente, Vehiculo]:
        """Valida que la cédula y la placa estén registradas y que el vehículo sea de ese cliente (RN-05)."""
        cliente = self.session.scalar(select(Cliente).where(Cliente.numero_documento == cedula))
        if cliente is None:
            raise ApiError(404, CLIENTE_NO_REGISTRADO)
        consulta = select(Vehiculo).where(Vehiculo.placa == placa)
        if bloquear:
            # Dos pagos del mismo vehículo al mismo tiempo calculan el vencimiento uno después del otro.
            consulta = consulta.with_for_update()
        vehiculo = self.session.scalar(consulta)
        if vehiculo is None:
            raise ApiError(404, VEHICULO_NO_REGISTRADO)
        if vehiculo.cliente_id != cliente.id:
            raise ApiError(409, VEHICULO_DE_OTRO_CLIENTE)
        return cliente, vehiculo

    @_transaccion
    def consultar(self, cedula: str, placa: str) -> ConsultaPago:
        """RF-03: al buscar, muestra hasta cuándo va la mensualidad."""
        cliente, vehiculo = self._cliente_y_vehiculo(cedula, placa, bloquear=False)
        return ConsultaPago(
            cliente=ClienteRespuesta.model_validate(cliente),
            vehiculo=VehiculoRespuesta.model_validate(vehiculo),
            mensualidad=evaluar_mensualidad(vehiculo.cliente_id, vehiculo.fecha_pago, vehiculo.fecha_vencimiento,
                                            hoy_colombia()),
        )

    @_transaccion
    def registrar(self, data: PagoCrear, actor: Actor) -> PagoRespuesta:
        """RF-01: guarda el pago con el usuario de la sesión y lo deja en la auditoría."""
        if data.fecha_pago > hoy_colombia():
            raise ApiError(422, FECHA_FUTURA)
        cliente, vehiculo = self._cliente_y_vehiculo(data.cedula, data.placa, bloquear=True)
        # RN-12: el valor debe ser la tarifa del tipo de vehículo; si no coincide, no se guarda nada.
        if not valor_corresponde(vehiculo.tipo, data.valor):
            raise ApiError(422, mensaje_tarifa(vehiculo.tipo))

        vencimiento_anterior = vehiculo.fecha_vencimiento
        vencimiento_nuevo = vehiculo.aplicar_pago(data.fecha_pago)  # RF-02 (Sergio): 30 días desde el corte.
        pago = Pago(
            vehiculo_id=vehiculo.id,
            cliente_id=cliente.id,
            fecha_pago=data.fecha_pago,
            valor=data.valor,
            medio=data.medio,
            vencimiento_anterior=vencimiento_anterior,
            vencimiento_nuevo=vencimiento_nuevo,
            operador_id=actor.id,
        )
        self.session.add(pago)
        self.session.flush()

        auditar(self.session, accion="PAGO_REGISTRADO", entidad="pago", entidad_id=pago.id, placa=vehiculo.placa,
                actor=actor,
                anterior={"fecha_vencimiento": vencimiento_anterior} if vencimiento_anterior else None,
                nuevo={"fecha_pago": data.fecha_pago, "valor": str(data.valor), "medio": data.medio,
                       "fecha_vencimiento": vencimiento_nuevo, "cedula": cliente.numero_documento},
                detalle=f"Registró el pago de {vehiculo.placa} (cédula {cliente.numero_documento}); "
                        f"mensualidad hasta {vencimiento_nuevo.strftime('%d/%m/%Y')}.")
        self.session.flush()
        self.session.refresh(pago)

        return PagoRespuesta(
            id=pago.id,
            cedula=cliente.numero_documento,
            cliente=f"{cliente.nombres} {cliente.apellidos}",
            placa=vehiculo.placa,
            fecha_pago=pago.fecha_pago,
            valor=pago.valor,
            medio=pago.medio,
            vencimiento_anterior=pago.vencimiento_anterior,
            vencimiento_nuevo=pago.vencimiento_nuevo,
            registrado_por=actor.usuario,
            registrado_en=pago.registrado_en,
            mensualidad=evaluar_mensualidad(vehiculo.cliente_id, vehiculo.fecha_pago, vehiculo.fecha_vencimiento,
                                            hoy_colombia()),
        )
