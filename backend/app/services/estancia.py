"""Consulta, entrada con celda automática y recibo (RF-03 a RF-05), salida (RF-07) y cambio de celda (RF-09).

Concurrencia (RNF-01): la asignación bloquea la fila de la celda con FOR UPDATE SKIP LOCKED, de modo
que dos puertas que confirman a la vez reciben celdas distintas. Las restricciones de la base
(una estancia abierta por vehículo y por celda) deciden cualquier carrera restante.
"""
from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import exists, func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import TIPOS_CELDA, Celda, Estancia, Novedad, Operador, Puerta, Vehiculo, tipo_celda_para
from app.schemas.celda import CeldaRespuesta
from app.schemas.cliente import ClienteRespuesta
from app.schemas.estancia import (
    CambioCeldaCrear, CambioCeldaRespuesta, ConsultaVehiculo, Cupo, EntradaCrear, MovimientoRespuesta,
    NovedadRespuesta, OperadorResumen, PuertaRespuesta, SalidaCrear,
)
from app.schemas.vehiculo import VehiculoRespuesta
from app.services.mensualidad import evaluar_mensualidad, hoy_colombia

NOMBRE_CUPO = {"CARRO_CAMIONETA": "carros y camionetas", "MOTO": "motos"}


class EstanciaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def transaccion(operation):
    """Una transacción por solicitud; materializa la respuesta antes del commit."""
    @wraps(operation)
    def wrapped(self, *args, **kwargs):
        try:
            with self.session.begin():
                return operation(self, *args, **kwargs)
        except IntegrityError as error:
            self.session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505" and constraint == "uq_estancia_vehiculo_abierta":
                raise EstanciaError(409, "El vehículo ya está dentro.") from None
            if code in {"23505", "23P01"} and constraint in {"uq_estancia_celda_abierta", "ex_estancia_celda_abierta"}:
                raise EstanciaError(409, "La celda está ocupada. Intenta de nuevo.") from None
            if code == "23503":
                raise EstanciaError(404, "Una de las referencias ya no existe. Actualiza los datos.") from None
            if code in {"23502", "23514"}:
                raise EstanciaError(422, "Los datos incumplen las restricciones de la estancia.") from None
            raise EstanciaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError as error:
            self.session.rollback()
            if getattr(getattr(error, "orig", None), "sqlstate", None) in {"40P01", "40001"}:
                raise EstanciaError(409, "Otra puerta modificó las mismas celdas al mismo tiempo. Intenta de nuevo.") from None
            raise EstanciaError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def _abierta():
    return Estancia.salida.is_(None)


def _detalle_query():
    return select(Estancia).options(
        joinedload(Estancia.vehiculo).joinedload(Vehiculo.cliente),
        joinedload(Estancia.celda),
        joinedload(Estancia.puerta_entrada), joinedload(Estancia.puerta_salida),
        joinedload(Estancia.operador_entrada), joinedload(Estancia.operador_salida),
        selectinload(Estancia.novedades).options(
            joinedload(Novedad.celda_anterior), joinedload(Novedad.celda_nueva), joinedload(Novedad.operador),
        ),
    )


def novedad(registro: Novedad) -> NovedadRespuesta:
    return NovedadRespuesta(
        id=registro.id,
        celda_anterior=CeldaRespuesta.model_validate(registro.celda_anterior),
        celda_nueva=CeldaRespuesta.model_validate(registro.celda_nueva),
        motivo=registro.motivo,
        operador=OperadorResumen.model_validate(registro.operador),
        fecha=registro.fecha,
    )


def movimiento(estancia: Estancia) -> MovimientoRespuesta:
    vehiculo = estancia.vehiculo
    cliente = vehiculo.cliente
    return MovimientoRespuesta(
        id=estancia.id,
        numero_recibo=estancia.numero_recibo,
        vehiculo_id=vehiculo.id,
        placa=vehiculo.placa,
        tipo_vehiculo=vehiculo.tipo,
        marca=vehiculo.marca,
        linea=vehiculo.linea,
        color=vehiculo.color,
        cliente=f"{cliente.nombres} {cliente.apellidos}" if cliente else None,
        celda=CeldaRespuesta.model_validate(estancia.celda),
        entrada=estancia.entrada,
        salida=estancia.salida,
        abierta=estancia.salida is None,
        puerta_entrada=PuertaRespuesta.model_validate(estancia.puerta_entrada),
        puerta_salida=PuertaRespuesta.model_validate(estancia.puerta_salida) if estancia.puerta_salida else None,
        operador_entrada=OperadorResumen.model_validate(estancia.operador_entrada),
        operador_salida=(OperadorResumen.model_validate(estancia.operador_salida)
                         if estancia.operador_salida else None),
        cliente_documento=f"{cliente.tipo_documento} {cliente.numero_documento}" if cliente else None,
        novedades=[novedad(n) for n in estancia.novedades],
    )


class ServicioEstancia:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---------- utilidades ----------

    def _operador(self, operador_id: int) -> Operador:
        operador = self.session.get(Operador, operador_id)
        if operador is None:
            raise EstanciaError(404, "Operador no encontrado.")
        return operador

    def _puerta(self, puerta_id: int) -> Puerta:
        puerta = self.session.get(Puerta, puerta_id)
        if puerta is None:
            raise EstanciaError(404, "Puerta no encontrada.")
        return puerta

    def _detalle(self, estancia_id: int) -> MovimientoRespuesta:
        self.session.expire_all()
        estancia = self.session.scalars(_detalle_query().where(Estancia.id == estancia_id)).unique().one()
        return movimiento(estancia)

    def _cupos(self) -> list[Cupo]:
        totales = dict(self.session.execute(select(Celda.tipo, func.count()).group_by(Celda.tipo)).all())
        ocupadas = dict(self.session.execute(
            select(Celda.tipo, func.count()).join(Estancia, Estancia.celda_id == Celda.id)
            .where(_abierta()).group_by(Celda.tipo)
        ).all())
        cupos = []
        for tipo in TIPOS_CELDA:
            total, ocupado = totales.get(tipo, 0), ocupadas.get(tipo, 0)
            cupos.append(Cupo(tipo_celda=tipo, nombre=NOMBRE_CUPO[tipo], total=total, ocupadas=ocupado,
                              disponibles=max(total - ocupado, 0)))
        return cupos

    def _cupo(self, tipo_celda: str) -> Cupo:
        return next(c for c in self._cupos() if c.tipo_celda == tipo_celda)

    def _celda_libre(self, tipo_celda: str) -> Celda | None:
        """RN-08: cualquier celda libre de su tipo. Se bloquea antes de confirmar que sigue libre."""
        descartadas: list[int] = []
        while True:
            ocupada = exists().where(Estancia.celda_id == Celda.id, _abierta())
            consulta = (select(Celda).where(Celda.tipo == tipo_celda, ~ocupada)
                        .order_by(Celda.codigo).limit(1).with_for_update(skip_locked=True))
            if descartadas:
                consulta = consulta.where(Celda.id.not_in(descartadas))
            celda = self.session.scalar(consulta)
            if celda is None:
                return None
            # Con la fila bloqueada, una consulta nueva ve cualquier ocupación ya confirmada.
            if self.session.scalar(select(Estancia.id).where(Estancia.celda_id == celda.id, _abierta())) is None:
                return celda
            descartadas.append(celda.id)

    # ---------- RF-03 / RF-04 ----------

    @transaccion
    def consultar(self, placa: str) -> ConsultaVehiculo:
        vehiculo = self.session.scalar(
            select(Vehiculo).options(joinedload(Vehiculo.cliente)).where(Vehiculo.placa == placa)
        )
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no registrado. Registra el cliente y el vehículo para continuar.")
        mensualidad = evaluar_mensualidad(vehiculo.cliente_id, vehiculo.fecha_pago, vehiculo.fecha_vencimiento,
                                          hoy_colombia())
        estancia = self.session.scalars(
            _detalle_query().where(Estancia.vehiculo_id == vehiculo.id, _abierta())
        ).unique().one_or_none()
        cupo = self._cupo(tipo_celda_para(vehiculo.tipo))
        motivo = None
        if estancia is not None:
            motivo = f"El vehículo ya se encuentra en la celda {estancia.celda.codigo}."
        elif not mensualidad.permite_ingreso:
            motivo = mensualidad.mensaje
        elif cupo.disponibles == 0:
            motivo = f"No hay celdas disponibles para {cupo.nombre} ({cupo.ocupadas}/{cupo.total})."
        return ConsultaVehiculo(
            vehiculo=VehiculoRespuesta.model_validate(vehiculo),
            cliente=ClienteRespuesta.model_validate(vehiculo.cliente) if vehiculo.cliente else None,
            mensualidad=mensualidad,
            esta_dentro=estancia is not None,
            estancia=movimiento(estancia) if estancia else None,
            cupo=cupo,
            puede_ingresar=motivo is None,
            motivo=motivo,
        )

    # ---------- RF-05 (con el cupo por tipo que necesita la asignación) ----------

    @transaccion
    def entrada(self, data: EntradaCrear) -> MovimientoRespuesta:
        # Bloquear el vehículo serializa dos confirmaciones del mismo vehículo en ambas puertas.
        vehiculo = self.session.scalar(select(Vehiculo).where(Vehiculo.placa == data.placa).with_for_update())
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no registrado. Registra el cliente y el vehículo para continuar.")
        operador = self._operador(data.operador_id)
        puerta = self._puerta(data.puerta_id)
        abierta = self.session.scalar(select(Estancia).where(Estancia.vehiculo_id == vehiculo.id, _abierta()))
        if abierta is not None:
            raise EstanciaError(409, f"El vehículo ya se encuentra en la celda {abierta.celda.codigo}.")
        mensualidad = evaluar_mensualidad(vehiculo.cliente_id, vehiculo.fecha_pago, vehiculo.fecha_vencimiento,
                                          hoy_colombia())
        if not mensualidad.permite_ingreso:
            raise EstanciaError(409, mensualidad.mensaje)
        tipo_celda = tipo_celda_para(vehiculo.tipo)
        celda = self._celda_libre(tipo_celda)
        if celda is None:
            cupo = self._cupo(tipo_celda)
            raise EstanciaError(
                409, f"No hay celdas disponibles para {cupo.nombre} ({cupo.ocupadas}/{cupo.total})."
            )
        estancia = Estancia(vehiculo_id=vehiculo.id, celda_id=celda.id, operador_entrada_id=operador.id,
                            puerta_entrada_id=puerta.id, entrada=datetime.now(timezone.utc))
        self.session.add(estancia)
        self.session.flush()
        return self._detalle(estancia.id)

    # ---------- RF-07 ----------

    def _abierta_para(self, placa: str | None, numero_recibo: str | None, bloquear: bool = False) -> Estancia:
        """Ingreso abierto buscado por placa, por recibo o por ambos (que deben coincidir)."""
        vehiculo = None
        if placa is not None:
            vehiculo = self.session.scalar(select(Vehiculo).where(Vehiculo.placa == placa))
            if vehiculo is None:
                raise EstanciaError(404, "Vehículo no registrado.")
        if numero_recibo is not None:
            consulta = select(Estancia).where(Estancia.numero_recibo == numero_recibo)
            estancia = self.session.scalar(consulta.with_for_update() if bloquear else consulta)
            if estancia is None:
                raise EstanciaError(404, f"No existe el recibo {numero_recibo}.")
            if vehiculo is not None and estancia.vehiculo_id != vehiculo.id:
                raise EstanciaError(
                    409, f"El recibo {numero_recibo} no corresponde a la placa {placa}. Verifica el recibo."
                )
            if not estancia.esta_abierta():
                raise EstanciaError(
                    409, f"Este vehículo no tiene un ingreso abierto: el recibo {numero_recibo} ya tiene salida."
                )
            return estancia
        # PostgreSQL vuelve a evaluar salida IS NULL tras esperar el bloqueo.
        consulta = select(Estancia).where(Estancia.vehiculo_id == vehiculo.id, _abierta())
        estancia = self.session.scalar(consulta.with_for_update() if bloquear else consulta)
        if estancia is None:
            raise EstanciaError(409, "Este vehículo no tiene un ingreso abierto.")
        return estancia

    @transaccion
    def abierta(self, placa: str | None, numero_recibo: str | None) -> MovimientoRespuesta:
        if placa is None and numero_recibo is None:
            raise EstanciaError(422, "Digita la placa o el número del recibo.")
        return self._detalle(self._abierta_para(placa, numero_recibo).id)

    @transaccion
    def salida(self, data: SalidaCrear) -> MovimientoRespuesta:
        estancia = self._abierta_para(data.placa, data.numero_recibo, bloquear=True)
        operador = self._operador(data.operador_id)
        puerta = self._puerta(data.puerta_id)
        try:
            estancia.cerrar(datetime.now(timezone.utc), operador, puerta)
        except ValueError:
            raise EstanciaError(409, "No se puede cerrar la estancia con su estado o fecha actuales.") from None
        self.session.flush()
        return self._detalle(estancia.id)

    # ---------- RF-09 ----------

    @transaccion
    def cambiar_celda(self, estancia_id: int, data: CambioCeldaCrear) -> CambioCeldaRespuesta:
        operador = self._operador(data.operador_id)
        estancia = self.session.scalar(select(Estancia).where(Estancia.id == estancia_id).with_for_update())
        if estancia is None:
            raise EstanciaError(404, "Registro de ingreso no encontrado.")
        if not estancia.esta_abierta():
            raise EstanciaError(409, "Solo se puede cambiar la celda de un ingreso abierto.")
        if data.celda_id == estancia.celda_id:
            raise EstanciaError(409, "El vehículo ya está registrado en esa celda. Elige otra.")
        # Bloquear ambas celdas en orden de id evita interbloqueos con la otra puerta.
        celdas = {c.id: c for c in self.session.scalars(
            select(Celda).where(Celda.id.in_([estancia.celda_id, data.celda_id]))
            .order_by(Celda.id).with_for_update()
        )}
        nueva = celdas.get(data.celda_id)
        if nueva is None:
            raise EstanciaError(404, "Celda no encontrada.")
        anterior = celdas[estancia.celda_id]
        vehiculo = self.session.get(Vehiculo, estancia.vehiculo_id)
        requerido = tipo_celda_para(vehiculo.tipo)
        if nueva.tipo != requerido:
            raise EstanciaError(
                409, f"La celda {nueva.codigo} es para {NOMBRE_CUPO[nueva.tipo]}; "
                     f"{vehiculo.placa} necesita una celda para {NOMBRE_CUPO[requerido]}."
            )
        otra = self.session.scalar(
            select(Estancia).where(Estancia.celda_id == nueva.id, _abierta()).with_for_update()
        )
        if otra is None:
            estancia.celda_id = nueva.id
            self.session.add(Novedad(estancia_id=estancia.id, celda_anterior_id=anterior.id,
                                     celda_nueva_id=nueva.id, motivo=data.motivo, operador_id=operador.id))
        else:
            placa_otra = self.session.get(Vehiculo, otra.vehiculo_id).placa
            if not data.intercambiar:
                raise EstanciaError(
                    409, f"La celda {nueva.codigo} está ocupada por {placa_otra}. Si ese vehículo está en "
                         f"realidad en la celda {anterior.codigo}, elige «Intercambiar celdas»."
                )
            # Los dos registros se mueven a la vez; la regla de una estancia por celda se verifica al confirmar.
            self.session.execute(text("SET CONSTRAINTS ex_estancia_celda_abierta DEFERRED"))
            estancia.celda_id, otra.celda_id = nueva.id, anterior.id
            self.session.add_all([
                Novedad(estancia_id=estancia.id, celda_anterior_id=anterior.id, celda_nueva_id=nueva.id,
                        motivo=f"{data.motivo} (intercambio con {placa_otra})", operador_id=operador.id),
                Novedad(estancia_id=otra.id, celda_anterior_id=nueva.id, celda_nueva_id=anterior.id,
                        motivo=f"{data.motivo} (intercambio con {vehiculo.placa})", operador_id=operador.id),
            ])
        self.session.flush()
        return CambioCeldaRespuesta(
            estancia=self._detalle(estancia.id),
            intercambio=self._detalle(otra.id) if otra is not None else None,
        )

    @transaccion
    def recibo(self, numero_recibo: str) -> MovimientoRespuesta:
        estancia = self.session.scalars(
            _detalle_query().where(Estancia.numero_recibo == numero_recibo)
        ).unique().one_or_none()
        if estancia is None:
            raise EstanciaError(404, f"No existe el recibo {numero_recibo}.")
        return movimiento(estancia)
