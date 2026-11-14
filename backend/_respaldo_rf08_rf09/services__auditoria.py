"""Auditoría (RF-08) y su consulta (RF-10).

registrar() solo agrega la fila a la sesión: se guarda en la misma transacción que la acción auditada,
así que no puede haber una acción sin su registro ni un registro de una acción que se revirtió.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Auditoria

BOGOTA = ZoneInfo("America/Bogota")


def actor_sin_sesion() -> dict[str, str]:
    """Quien actúa cuando la acción no trae operador. Reemplazar por el usuario autenticado cuando exista el login (RF-01)."""
    return {"usuario": "Sin sesión", "perfil": "ADMINISTRADOR"}


def registrar(session: Session, *, accion: str, entidad: str, usuario: str, perfil: str,
              entidad_id: int | None = None, placa: str | None = None, puerta: str | None = None,
              anterior: dict | None = None, nuevo: dict | None = None, motivo: str | None = None) -> None:
    session.add(Auditoria(
        accion=accion, entidad=entidad, entidad_id=entidad_id, usuario=usuario, perfil=perfil,
        placa=placa, puerta=puerta, valor_anterior=anterior, valor_nuevo=nuevo, motivo=motivo,
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