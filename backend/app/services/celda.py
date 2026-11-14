"""Gestión de celdas: RF-11 (construir), RF-12 (consultar), RF-13 (modificar),
RF-14 (inhabilitar y habilitar) y RF-15 (eliminar con borrado lógico).

Concurrencia: cada cambio bloquea la fila de la celda con FOR UPDATE y después comprueba que no
tenga una estancia abierta. Así una entrada que está tomando esa celda en otra puerta termina primero
(y el cambio se rechaza con 409), o el cambio termina primero (y la entrada la salta o no la ve activa).
"""
from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import TIPOS_CELDA, Celda, Estancia
from app.schemas.celda import CeldaActualizar, CeldaCrear
from app.auditoria import Actor
from app.services.auditoria import registrar as auditar


class CeldaError(Exception):
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
            if code == "23505" and constraint == "uq_celda_codigo":
                raise CeldaError(409, "Ya existe una celda con ese código.") from None
            if code == "23503":
                raise CeldaError(409, "La celda tiene registros relacionados.") from None
            if code in {"23502", "23514"}:
                raise CeldaError(422, "Los datos incumplen las restricciones de la celda.") from None
            raise CeldaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise CeldaError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


# ---------- utilidades ----------

def _ocupada():
    """Subconsulta: la celda tiene una estancia abierta (se correlaciona con Celda)."""
    return exists().where(Estancia.celda_id == Celda.id, Estancia.salida.is_(None))


def estado_visible(celda: Celda, ocupada: bool) -> str:
    if celda.estado == "ELIMINADA":
        return "ELIMINADA"
    if celda.estado == "INHABILITADA":
        return "INHABILITADA"
    return "OCUPADA" if ocupada else "DISPONIBLE"


def detalle(celda: Celda, ocupada: bool) -> dict:
    return {
        "id": celda.id, "codigo": celda.codigo, "tipo": celda.tipo,
        "estado": estado_visible(celda, ocupada),
        "motivo_estado": celda.motivo_estado, "fecha_estado": celda.fecha_estado,
    }


def _esta_ocupada(session: Session, cell_id: int) -> bool:
    return session.scalar(
        select(exists().where(Estancia.celda_id == cell_id, Estancia.salida.is_(None)))
    ) is True


def find_cell(session: Session, cell_id: int, lock: bool = False) -> Celda:
    consulta = select(Celda).where(Celda.id == cell_id)
    cell = session.scalar(consulta.with_for_update() if lock else consulta)
    if cell is None:
        raise CeldaError(404, "Celda no encontrada.")
    return cell


def _celda_modificable(session: Session, cell_id: int, accion: str) -> Celda:
    """Bloquea la celda y exige que exista, no esté eliminada y esté libre."""
    cell = find_cell(session, cell_id, lock=True)
    if cell.estado == "ELIMINADA":
        raise CeldaError(409, f"La celda {cell.codigo} está eliminada y no se puede {accion}.")
    if _esta_ocupada(session, cell.id):
        raise CeldaError(409, f"La celda {cell.codigo} está ocupada: no se puede {accion} mientras tenga un vehículo.")
    return cell


# ---------- RF-11 ----------

@database_operation
def create_cell(session: Session, data: CeldaCrear, actor: Actor) -> dict:
    cell = Celda(**data.model_dump())
    session.add(cell)
    session.flush()
    auditar(session, accion="CELDA_CREADA", entidad="celda", entidad_id=cell.id, actor=actor,
            nuevo={"codigo": cell.codigo, "tipo": cell.tipo})
    session.commit()
    session.refresh(cell)
    return detalle(cell, False)


# ---------- RF-12 ----------

@database_operation
def list_cells(session: Session, offset: int, limit: int, q: str | None = None,
               tipo: str | None = None, estado: str | None = None) -> dict:
    ocupada = _ocupada()
    condiciones = []
    if q:
        condiciones.append(Celda.codigo.icontains(q.strip(), autoescape=True))
    if tipo:
        condiciones.append(Celda.tipo == tipo)
    if estado == "ELIMINADA":
        condiciones.append(Celda.estado == "ELIMINADA")
    elif estado == "INHABILITADA":
        condiciones.append(Celda.estado == "INHABILITADA")
    elif estado == "DISPONIBLE":
        condiciones += [Celda.estado == "ACTIVA", ~ocupada]
    elif estado == "OCUPADA":
        condiciones += [Celda.estado == "ACTIVA", ocupada]
    else:
        # Sin filtro de estado, las eliminadas no se muestran (salen del listado, del mapa y de la asignación).
        condiciones.append(Celda.estado != "ELIMINADA")

    total = session.scalar(select(func.count()).select_from(Celda).where(*condiciones))
    filas = session.execute(
        select(Celda, ocupada.label("ocupada")).where(*condiciones).order_by(Celda.id).offset(offset).limit(limit)
    ).all()
    return {
        "items": [detalle(celda, bool(esta_ocupada)) for celda, esta_ocupada in filas],
        "total": total, "offset": offset, "limit": limit,
        "totales_por_tipo": _totales_por_tipo(session),
    }


def _totales_por_tipo(session: Session) -> list[dict]:
    """Totales de celdas no eliminadas por tipo, sin importar los filtros del listado."""
    con_vehiculo = Estancia.id.is_not(None)
    filas = session.execute(
        select(Celda.tipo, Celda.estado, con_vehiculo, func.count())
        .select_from(Celda)
        .outerjoin(Estancia, (Estancia.celda_id == Celda.id) & Estancia.salida.is_(None))
        .where(Celda.estado != "ELIMINADA")
        .group_by(Celda.tipo, Celda.estado, con_vehiculo)
    ).all()
    totales = {t: {"tipo": t, "total": 0, "disponibles": 0, "ocupadas": 0, "inhabilitadas": 0} for t in TIPOS_CELDA}
    for tipo, estado, esta_ocupada, cantidad in filas:
        fila = totales[tipo]
        fila["total"] += cantidad
        if estado == "INHABILITADA":
            fila["inhabilitadas"] += cantidad
        elif esta_ocupada:
            fila["ocupadas"] += cantidad
        else:
            fila["disponibles"] += cantidad
    return [totales[t] for t in TIPOS_CELDA]


@database_operation
def get_cell(session: Session, cell_id: int) -> dict:
    cell = find_cell(session, cell_id)
    return detalle(cell, _esta_ocupada(session, cell.id))


# ---------- RF-13 ----------

@database_operation
def update_cell(session: Session, cell_id: int, data: CeldaActualizar, actor: Actor) -> dict:
    cambios = data.model_dump(exclude_unset=True)
    cell = find_cell(session, cell_id, lock=True)
    if cell.estado == "ELIMINADA":
        raise CeldaError(409, f"La celda {cell.codigo} está eliminada y no se puede modificar.")
    cambios = {k: v for k, v in cambios.items() if getattr(cell, k) != v}
    if cambios and _esta_ocupada(session, cell.id):
        raise CeldaError(409, f"La celda {cell.codigo} está ocupada: solo se puede modificar cuando esté libre.")
    anterior = {"codigo": cell.codigo, "tipo": cell.tipo}
    for key, value in cambios.items():
        setattr(cell, key, value)
    if cambios:
        auditar(session, accion="CELDA_MODIFICADA", entidad="celda", entidad_id=cell.id, actor=actor,
                anterior=anterior, nuevo={"codigo": cell.codigo, "tipo": cell.tipo})
    session.commit()
    session.refresh(cell)
    return detalle(cell, _esta_ocupada(session, cell.id))


# ---------- RF-14 ----------

def _cambiar_estado(session: Session, cell: Celda, estado: str, motivo: str, actor: Actor) -> dict:
    anterior = {"celda": cell.codigo, "estado": cell.estado, "motivo": cell.motivo_estado}
    cell.estado = estado
    cell.motivo_estado = motivo
    cell.fecha_estado = datetime.now(timezone.utc)
    accion = {"INHABILITADA": "CELDA_INHABILITADA", "ACTIVA": "CELDA_HABILITADA", "ELIMINADA": "CELDA_ELIMINADA"}[estado]
    auditar(session, accion=accion, entidad="celda", entidad_id=cell.id, actor=actor,
            anterior=anterior, nuevo={"celda": cell.codigo, "estado": estado, "motivo": motivo}, motivo=motivo)
    session.commit()
    session.refresh(cell)
    return detalle(cell, False)


@database_operation
def disable_cell(session: Session, cell_id: int, motivo: str, actor: Actor) -> dict:
    cell = _celda_modificable(session, cell_id, "inhabilitar")
    if cell.estado == "INHABILITADA":
        raise CeldaError(409, f"La celda {cell.codigo} ya está inhabilitada.")
    return _cambiar_estado(session, cell, "INHABILITADA", motivo, actor)


@database_operation
def enable_cell(session: Session, cell_id: int, motivo: str, actor: Actor) -> dict:
    cell = find_cell(session, cell_id, lock=True)
    if cell.estado == "ELIMINADA":
        raise CeldaError(409, f"La celda {cell.codigo} está eliminada y no se puede habilitar.")
    if cell.estado == "ACTIVA":
        raise CeldaError(409, f"La celda {cell.codigo} ya está habilitada.")
    return _cambiar_estado(session, cell, "ACTIVA", motivo, actor)


# ---------- RF-15 ----------

@database_operation
def delete_cell(session: Session, cell_id: int, motivo: str, actor: Actor) -> dict:
    """Borrado lógico: la celda queda ELIMINADA y se conserva todo su historial."""
    cell = _celda_modificable(session, cell_id, "eliminar")
    return _cambiar_estado(session, cell, "ELIMINADA", motivo, actor)