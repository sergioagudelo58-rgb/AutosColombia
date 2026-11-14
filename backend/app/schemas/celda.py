from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, field_validator

from app.models import required_text

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
Codigo = Annotated[Texto, AfterValidator(str.upper)]
TipoCelda = Literal["CARRO_CAMIONETA", "MOTO"]
# Estado que ve el usuario: DISPONIBLE y OCUPADA se calculan según la estancia abierta (RF-12).
EstadoCelda = Literal["DISPONIBLE", "OCUPADA", "INHABILITADA", "ELIMINADA"]


class CeldaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo
    tipo: TipoCelda


class CeldaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo | None = None
    tipo: TipoCelda | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class CeldaRespuesta(CeldaCrear):
    """Forma reducida que usan estancias, mapa y reportes. No cambia."""
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int


class CeldaDetalle(CeldaRespuesta):
    """Celda con su estado calculado (gestión de celdas)."""
    estado: EstadoCelda
    motivo_estado: str | None = None
    fecha_estado: datetime | None = None


class CambioEstado(BaseModel):
    """Cuerpo de inhabilitar, habilitar y eliminar: el motivo es obligatorio (RNF-11)."""
    model_config = ConfigDict(extra="forbid")
    motivo: Texto


class TotalTipo(BaseModel):
    tipo: TipoCelda
    total: int
    disponibles: int
    ocupadas: int
    inhabilitadas: int


class CeldasPagina(BaseModel):
    items: list[CeldaDetalle]
    total: int
    offset: int
    limit: int
    totales_por_tipo: list[TotalTipo]