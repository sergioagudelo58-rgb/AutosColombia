"""Estado de las celdas, contadores por tipo y actividad reciente de las puertas (RF-08).

Cada consulta se calcula al momento en el servidor; la pantalla la repite cada 2 segundos (RNF-02).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import TIPOS_CELDA, Celda, Estancia, Novedad
from app.schemas.estancia import Cupo
from app.schemas.reporte import Actividad, CeldaEstado, OcupacionCelda, Panel
from app.services.estancia import NOMBRE_CUPO, transaccion

RECIENTE = timedelta(seconds=60)
ACTIVIDAD = 15


def cupos_de(celdas: list[Celda], ocupadas: set[int]) -> list[Cupo]:
    cupos = []
    for tipo in TIPOS_CELDA:
        total = sum(1 for c in celdas if c.tipo == tipo)
        ocupado = sum(1 for c in celdas if c.tipo == tipo and c.id in ocupadas)
        cupos.append(Cupo(tipo_celda=tipo, nombre=NOMBRE_CUPO[tipo], total=total, ocupadas=ocupado,
                          disponibles=total - ocupado))
    return cupos


class ServicioPanel:
    def __init__(self, session: Session) -> None:
        self.session = session

    @transaccion
    def panel(self) -> Panel:
        ahora = datetime.now(timezone.utc)
        celdas = list(self.session.scalars(select(Celda).order_by(Celda.codigo)))
        abiertas = self.session.scalars(
            select(Estancia).options(joinedload(Estancia.vehiculo), joinedload(Estancia.puerta_entrada),
                                     joinedload(Estancia.operador_entrada))
            .where(Estancia.salida.is_(None))
        ).unique().all()
        por_celda = {e.celda_id: e for e in abiertas}
        # Una celda es «recién asignada» si el ingreso o su último cambio de celda ocurrió hace menos de 60 s.
        cambios = dict(self.session.execute(
            select(Novedad.estancia_id, func.max(Novedad.fecha))
            .join(Estancia, Estancia.id == Novedad.estancia_id)
            .where(Estancia.salida.is_(None), Novedad.fecha >= ahora - RECIENTE)
            .group_by(Novedad.estancia_id)
        ).all())

        estados = []
        for celda in celdas:
            estancia = por_celda.get(celda.id)
            ocupacion, reciente = None, False
            if estancia is not None:
                asignada = max(estancia.entrada, cambios.get(estancia.id, estancia.entrada))
                reciente = asignada >= ahora - RECIENTE
                ocupacion = OcupacionCelda(
                    estancia_id=estancia.id, numero_recibo=estancia.numero_recibo, placa=estancia.vehiculo.placa,
                    tipo_vehiculo=estancia.vehiculo.tipo, entrada=estancia.entrada,
                    puerta=estancia.puerta_entrada.nombre, operador=estancia.operador_entrada.nombre,
                )
            estados.append(CeldaEstado(id=celda.id, codigo=celda.codigo, tipo=celda.tipo,
                                       estado="OCUPADA" if estancia else "DISPONIBLE", reciente=reciente,
                                       ocupacion=ocupacion))
        return Panel(generado_en=ahora, cupos=cupos_de(celdas, set(por_celda)), celdas=estados,
                     actividad=self._actividad())

    def _actividad(self) -> list[Actividad]:
        detalle = (joinedload(Estancia.vehiculo), joinedload(Estancia.celda))
        entradas = self.session.scalars(
            select(Estancia).options(*detalle, joinedload(Estancia.puerta_entrada),
                                     joinedload(Estancia.operador_entrada))
            .order_by(Estancia.entrada.desc()).limit(ACTIVIDAD)
        ).unique().all()
        salidas = self.session.scalars(
            select(Estancia).options(*detalle, joinedload(Estancia.puerta_salida),
                                     joinedload(Estancia.operador_salida))
            .where(Estancia.salida.is_not(None)).order_by(Estancia.salida.desc()).limit(ACTIVIDAD)
        ).unique().all()
        novedades = self.session.scalars(
            select(Novedad).options(joinedload(Novedad.estancia).joinedload(Estancia.vehiculo),
                                    joinedload(Novedad.celda_anterior), joinedload(Novedad.celda_nueva),
                                    joinedload(Novedad.operador))
            .order_by(Novedad.fecha.desc()).limit(ACTIVIDAD)
        ).unique().all()

        eventos = [
            Actividad(tipo="ENTRADA", fecha=e.entrada, placa=e.vehiculo.placa, celda=e.celda.codigo,
                      puerta=e.puerta_entrada.nombre, operador=e.operador_entrada.nombre,
                      detalle=f"Ingresó a la celda {e.celda.codigo} · {e.numero_recibo}")
            for e in entradas
        ] + [
            Actividad(tipo="SALIDA", fecha=e.salida, placa=e.vehiculo.placa, celda=e.celda.codigo,
                      puerta=e.puerta_salida.nombre if e.puerta_salida else None,
                      operador=e.operador_salida.nombre if e.operador_salida else "—",
                      detalle=f"Salió y liberó la celda {e.celda.codigo}")
            for e in salidas
        ] + [
            Actividad(tipo="NOVEDAD", fecha=n.fecha, placa=n.estancia.vehiculo.placa, celda=n.celda_nueva.codigo,
                      puerta=None, operador=n.operador.nombre,
                      detalle=f"Celda {n.celda_anterior.codigo} → {n.celda_nueva.codigo}: {n.motivo}")
            for n in novedades
        ]
        eventos.sort(key=lambda a: a.fecha, reverse=True)
        return eventos[:ACTIVIDAD]
