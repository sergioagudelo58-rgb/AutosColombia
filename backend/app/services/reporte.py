"""Reporte de ocupación (RF-10) e historial de movimientos (RF-11). Solo lectura.

Los rangos se interpretan como días calendario de Colombia (RNF-11): del inicio de «desde»
hasta el final de «hasta», en America/Bogota.
"""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.models import TIPOS_VEHICULO, Celda, Cliente, Estancia, Novedad, Vehiculo
from app.schemas.reporte import HistorialPagina, ReporteOcupacion
from app.services.estancia import EstanciaError, _detalle_query, movimiento, transaccion
from app.services.mensualidad import ZONA_COLOMBIA, hoy_colombia
from app.services.panel import cupos_de


def rango_colombia(desde: date, hasta: date) -> tuple[datetime, datetime]:
    if desde > hasta:
        raise EstanciaError(422, "La fecha inicial no puede ser posterior a la fecha final.")
    inicio = datetime.combine(desde, time.min, ZONA_COLOMBIA)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, ZONA_COLOMBIA)
    return inicio, fin


def _en(columna, inicio: datetime, fin: datetime):
    return and_(columna >= inicio, columna < fin)


class ServicioReporte:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _contar(self, tabla, *condiciones) -> int:
        return self.session.scalar(select(func.count()).select_from(tabla).where(*condiciones))

    @transaccion
    def ocupacion(self, desde: date | None, hasta: date | None) -> ReporteOcupacion:
        hoy = hoy_colombia()
        desde, hasta = desde or hasta or hoy, hasta or desde or hoy
        inicio, fin = rango_colombia(desde, hasta)
        por_tipo = dict(self.session.execute(select(Vehiculo.tipo, func.count()).group_by(Vehiculo.tipo)).all())
        celdas = list(self.session.scalars(select(Celda).where(Celda.estado == "ACTIVA")))
        ocupadas = set(self.session.scalars(select(Estancia.celda_id).where(Estancia.salida.is_(None))))
        cupos = cupos_de(celdas, ocupadas)
        total = sum(c.total for c in cupos)
        ocupado = sum(c.ocupadas for c in cupos)
        return ReporteOcupacion(
            generado_en=datetime.now(timezone.utc),
            desde=desde,
            hasta=hasta,
            clientes_registrados=self._contar(Cliente),
            vehiculos_registrados=sum(por_tipo.values()),
            vehiculos_por_tipo={tipo: por_tipo.get(tipo, 0) for tipo in TIPOS_VEHICULO},
            vehiculos_adentro=self._contar(Estancia, Estancia.salida.is_(None)),
            cupos=cupos,
            celdas_total=total,
            celdas_ocupadas=ocupado,
            celdas_disponibles=total - ocupado,
            porcentaje_ocupacion=round(ocupado * 100 / total, 1) if total else 0.0,
            entradas=self._contar(Estancia, _en(Estancia.entrada, inicio, fin)),
            salidas=self._contar(Estancia, _en(Estancia.salida, inicio, fin)),
            novedades=self._contar(Novedad, _en(Novedad.fecha, inicio, fin)),
        )

    @transaccion
    def historial(self, placa: str | None, cliente: str | None, desde: date | None, hasta: date | None,
                  offset: int, limit: int) -> HistorialPagina:
        condiciones = []
        if placa:
            texto = "".join(placa.split()).replace("-", "").upper()
            condiciones.append(func.strpos(Vehiculo.placa, texto) > 0)
        if cliente:
            texto = " ".join(cliente.split())
            nombre = func.lower(Cliente.nombres + " " + Cliente.apellidos)
            condiciones.append(or_(Cliente.numero_documento == texto.replace(" ", "").upper(),
                                   func.strpos(nombre, texto.lower()) > 0))
        if desde or hasta:
            inicio, fin = rango_colombia(desde or date.min, hasta or date.max - timedelta(days=1))
            novedad_en_rango = exists().where(Novedad.estancia_id == Estancia.id, _en(Novedad.fecha, inicio, fin))
            condiciones.append(or_(_en(Estancia.entrada, inicio, fin), _en(Estancia.salida, inicio, fin),
                                   novedad_en_rango))

        def base(consulta):
            return (consulta.join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id)
                    .outerjoin(Cliente, Cliente.id == Vehiculo.cliente_id).where(*condiciones))

        total = self.session.scalar(base(select(func.count()).select_from(Estancia)))
        ids = list(self.session.scalars(
            base(select(Estancia.id)).order_by(Estancia.entrada.desc(), Estancia.id.desc()).offset(offset).limit(limit)
        ))
        estancias = {e.id: e for e in self.session.scalars(_detalle_query().where(Estancia.id.in_(ids))).unique()}
        return HistorialPagina(items=[movimiento(estancias[i]) for i in ids], total=total, offset=offset, limit=limit)
