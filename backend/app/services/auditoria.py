"""Auditoría (RF-08) y su consulta (RF-10).

registrar() solo agrega la fila a la sesión: se guarda en la misma transacción que la acción auditada,
así que no hay una acción sin su registro ni un registro de una acción que se revirtió.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auditoria import Actor, _json
from app.models import Auditoria

BOGOTA = ZoneInfo("America/Bogota")


def actor_sin_sesion() -> dict[str, str]:
    """Solo para procesos sin usuario (consola). Las acciones web pasan el actor de la sesión."""
    return {"usuario": "Sin sesión", "perfil": "ADMINISTRADOR"}


def _detalle(accion: str, entidad: str, entidad_id, placa: str | None) -> str:
    partes = [accion.replace("_", " ").capitalize(),
              f"{entidad} {entidad_id}" if entidad_id is not None else entidad]
    if placa:
        partes.append(placa)
    return " · ".join(partes)


def registrar(session: Session, *, accion: str, entidad: str, actor: Actor | None = None,
              usuario: str | None = None, perfil: str | None = None, entidad_id=None,
              placa: str | None = None, puerta: str | None = None, anterior: dict | None = None,
              nuevo: dict | None = None, motivo: str | None = None, detalle: str | None = None) -> None:
    session.add(Auditoria(
        usuario_id=actor.id if actor else None,
        usuario=actor.usuario if actor else usuario,
        rol=actor.rol if actor else perfil,
        puerta=(actor.puerta if actor and actor.puerta else puerta),
        equipo=actor.equipo if actor else None,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id is not None else None,
        placa=placa,
        detalle=detalle or _detalle(accion, entidad, entidad_id, placa),
        valor_anterior=_json(anterior) if anterior else None,
        valor_nuevo=_json(nuevo) if nuevo else None,
        motivo=motivo,
    ))


def listar(session: Session, offset: int, limit: int, usuario: str | None, desde: date | None,
           hasta: date | None, accion: str | None, placa: str | None) -> dict:
    condiciones = []
    if usuario and usuario.strip():
        condiciones.append(Auditoria.usuario.icontains(usuario.strip(), autoescape=True))
    if accion and accion.strip():
        condiciones.append(Auditoria.accion == accion.strip().upper())
    if placa and placa.strip():
        condiciones.append(Auditoria.placa.icontains(placa.strip().upper(), autoescape=True))
    if desde:
        condiciones.append(Auditoria.fecha >= datetime.combine(desde, time.min, tzinfo=BOGOTA))
    if hasta:
        condiciones.append(Auditoria.fecha < datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=BOGOTA))
    try:
        total = session.scalar(select(func.count()).select_from(Auditoria).where(*condiciones))
        items = list(session.scalars(
            select(Auditoria).where(*condiciones)
            .order_by(Auditoria.fecha.desc(), Auditoria.id.desc()).offset(offset).limit(limit)
        ))
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(status_code=503, detail="No se pudo consultar la auditoría.") from None
    return {"items": items, "total": total, "offset": offset, "limit": limit}
