from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: datetime
    usuario: str
    perfil: str
    accion: str
    entidad: str
    entidad_id: int | None = None
    placa: str | None = None
    puerta: str | None = None
    valor_anterior: dict | None = None
    valor_nuevo: dict | None = None
    motivo: str | None = None


class AuditoriaPagina(BaseModel):
    items: list[AuditoriaRespuesta]
    total: int
    offset: int
    limit: int