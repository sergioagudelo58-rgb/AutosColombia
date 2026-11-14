"""Bitácora de los eventos de sesión y de usuarios (RF-01, RF-02, RF-04, RF-06). Se agrega a la misma transacción."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Auditoria


@dataclass(frozen=True)
class Actor:
    """Quién hace la operación. Sale siempre de la sesión, nunca de lo que digita el usuario (RF-01)."""
    id: int
    usuario: str
    nombre: str
    rol: str
    puerta_id: int | None
    puerta: str | None
    sesion_id: int | None
    equipo: str | None

    @property
    def es_admin(self) -> bool:
        return self.rol == "ADMINISTRADOR"


def _json(valor: Any) -> Any:
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: _json(v) for k, v in valor.items()}
    return valor


def registrar(session: Session, actor: Actor | None, accion: str, detalle: str, *, entidad: str | None = None,
              entidad_id: Any = None, placa: str | None = None, anterior: dict | None = None,
              nuevo: dict | None = None, motivo: str | None = None, usuario_texto: str | None = None,
              usuario_id: int | None = None, rol: str | None = None, equipo: str | None = None) -> None:
    session.add(Auditoria(
        usuario_id=actor.id if actor else usuario_id,
        usuario=actor.usuario if actor else usuario_texto,
        rol=actor.rol if actor else rol,
        puerta=actor.puerta if actor else None,
        equipo=actor.equipo if actor else equipo,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id is not None else None,
        placa=placa,
        detalle=detalle,
        valor_anterior=_json(anterior) if anterior else None,
        valor_nuevo=_json(nuevo) if nuevo else None,
        motivo=motivo,
    ))


def cambios(antes: dict, despues: dict) -> tuple[dict, dict]:
    """Solo los campos que cambiaron, para guardar valor anterior y nuevo."""
    claves = [k for k in despues if antes.get(k) != despues.get(k)]
    return {k: antes.get(k) for k in claves}, {k: despues.get(k) for k in claves}
