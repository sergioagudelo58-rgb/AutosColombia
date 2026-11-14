from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.estancia import utc


class AuditoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: datetime
    usuario: str | None = None
    rol: str | None = None
    puerta: str | None = None
    equipo: str | None = None
    accion: str
    entidad: str | None = None
    entidad_id: str | None = None
    placa: str | None = None
    detalle: str
    valor_anterior: dict | None = None
    valor_nuevo: dict | None = None
    motivo: str | None = None

    _utc = field_validator("fecha")(utc)


class AuditoriaPagina(BaseModel):
    items: list[AuditoriaRespuesta]
    total: int
    offset: int
    limit: int
