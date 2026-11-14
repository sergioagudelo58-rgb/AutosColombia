"""Corrección de ingresos y salidas (RF-09). Solo administrador, con motivo; guarda el valor anterior y el nuevo."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditoria import Actor, cambios
from app.models import Celda, Estancia, Vehiculo
from app.schemas.correccion import CorreccionCrear
from app.schemas.estancia import MovimientoRespuesta
from app.services.auditoria import registrar as auditar
from app.services.estancia import EstanciaError, _detalle_query, movimiento, transaccion


def _iso(valor: datetime | None) -> str | None:
    return valor.astimezone(timezone.utc).isoformat() if valor is not None else None


class ServicioCorreccion:
    def __init__(self, session: Session) -> None:
        self.session = session

    @transaccion
    def corregir(self, estancia_id: int, data: CorreccionCrear, actor: Actor) -> MovimientoRespuesta:
        estancia = self.session.scalar(select(Estancia).where(Estancia.id == estancia_id).with_for_update())
        if estancia is None:
            raise EstanciaError(404, "Registro de ingreso no encontrado.")
        vehiculo = self.session.get(Vehiculo, estancia.vehiculo_id)
        ahora = datetime.now(timezone.utc)
        entrada = data.entrada or estancia.entrada

        if data.anular_salida:
            if estancia.salida is None:
                raise EstanciaError(409, "Este ingreso no tiene una salida que anular.")
            otro = self.session.scalar(select(Estancia.id).where(
                Estancia.vehiculo_id == estancia.vehiculo_id, Estancia.salida.is_(None)))
            if otro is not None:
                raise EstanciaError(409, "El vehículo ya tiene otro ingreso abierto; no se puede reabrir este.")
            celda = self.session.scalar(select(Celda).where(Celda.id == estancia.celda_id).with_for_update())
            if celda.estado != "ACTIVA":
                raise EstanciaError(409, f"La celda {celda.codigo} ya no está activa; no se puede reabrir el ingreso.")
            ocupante = self.session.scalar(select(Estancia.id).where(
                Estancia.celda_id == celda.id, Estancia.salida.is_(None)))
            if ocupante is not None:
                raise EstanciaError(409, f"La celda {celda.codigo} la ocupa otro vehículo; no se puede reabrir el ingreso.")
            salida = None
        elif data.salida is not None:
            if estancia.salida is None:
                raise EstanciaError(409, "El ingreso sigue abierto: la salida se registra desde Salida, no se corrige.")
            salida = data.salida
        else:
            salida = estancia.salida

        if entrada > ahora or (salida is not None and salida > ahora):
            raise EstanciaError(422, "Las fechas corregidas no pueden estar en el futuro.")
        if salida is not None and salida < entrada:
            raise EstanciaError(422, "La salida no puede ser anterior a la entrada.")

        antes = {"entrada": _iso(estancia.entrada), "salida": _iso(estancia.salida)}
        despues = {"entrada": _iso(entrada), "salida": _iso(salida)}
        anterior, nuevo = cambios(antes, despues)
        if not nuevo:
            raise EstanciaError(409, "La corrección no cambia ningún dato.")

        estancia.entrada = entrada
        if data.anular_salida:
            estancia.salida = None
            estancia.operador_salida_id = None
            estancia.puerta_salida_id = None
        else:
            estancia.salida = salida
        accion = "CORRECCION_ANULA_SALIDA" if data.anular_salida else "CORRECCION_REGISTRO"
        auditar(self.session, accion=accion, entidad="estancia", entidad_id=estancia.id, placa=vehiculo.placa,
                actor=actor, anterior=anterior, nuevo=nuevo, motivo=data.motivo,
                detalle=f"{'Anuló la salida' if data.anular_salida else 'Corrigió el registro'} "
                        f"del recibo {estancia.numero_recibo}.")
        self.session.flush()
        self.session.expire_all()
        detalle = self.session.scalars(_detalle_query().where(Estancia.id == estancia_id)).unique().one()
        return movimiento(detalle)
