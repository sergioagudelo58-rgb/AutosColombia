from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.seguridad import LONGITUD_MAXIMA

Clave = Annotated[str, StringConstraints(min_length=1, max_length=LONGITUD_MAXIMA)]


class LoginCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=30)]
    contrasena: Clave
    puerta_id: int | None = Field(default=None, ge=1, le=32767)


class CambioContrasena(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actual: Clave
    nueva: Annotated[str, StringConstraints(max_length=LONGITUD_MAXIMA + 1)]
    confirmacion: Annotated[str, StringConstraints(max_length=LONGITUD_MAXIMA + 1)]


class PuertaTurno(BaseModel):
    model_config = ConfigDict(extra="forbid")
    puerta_id: int | None = Field(ge=1, le=32767)


class AccesoDenegado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ruta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SesionRespuesta(BaseModel):
    usuario_id: int
    usuario: str
    nombre: str
    rol: str
    puerta_id: int | None
    puerta: str | None
    contrasena_temporal: bool
    inactividad_segundos: int


class LoginRespuesta(SesionRespuesta):
    token: str
