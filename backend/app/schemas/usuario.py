import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models import USUARIO_FORMATO, required_text
from app.schemas.cliente import Correo, Documento, TipoDocumento
from app.schemas.operador import Telefono, Texto

Rol = Literal["ADMINISTRADOR", "OPERADOR"]
Motivo = Annotated[str, BeforeValidator(lambda v: required_text(v, "El motivo")), Field(max_length=300)]


def normalizar_usuario(value: str) -> str:
    usuario = required_text(value, "El nombre de usuario").lower()
    if not re.fullmatch(USUARIO_FORMATO, usuario):
        raise ValueError("El usuario debe tener de 3 a 30 caracteres: letras minúsculas, números, punto o guion "
                         "bajo, y empezar por una letra.")
    return usuario


NombreUsuario = Annotated[str, BeforeValidator(normalizar_usuario)]


class UsuarioCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo_documento: TipoDocumento
    numero_documento: Documento
    nombres: Texto
    apellidos: Texto
    telefono: Telefono
    correo: Correo = None
    usuario: NombreUsuario
    rol: Rol
    fecha_ingreso: date


class UsuarioActualizar(BaseModel):
    """El nombre de usuario no se modifica una vez creado (RF-06)."""
    model_config = ConfigDict(extra="forbid")
    nombres: Texto | None = None
    apellidos: Texto | None = None
    telefono: Telefono | None = None
    correo: Correo = None
    rol: Rol | None = None

    @field_validator("nombres", "apellidos", "telefono", "rol", mode="before")
    @classmethod
    def sin_nulos(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class Retiro(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha_retiro: date | None = None
    motivo: Motivo


class UsuarioRespuesta(BaseModel):
    id: int
    usuario: str
    nombre: str
    nombres: str | None
    apellidos: str | None
    tipo_documento: str | None
    numero_documento: str | None
    telefono: str
    correo: str | None
    rol: str
    estado: str
    fecha_ingreso: date | None
    fecha_retiro: date | None
    motivo_retiro: str | None
    ultima_conexion: datetime | None
    en_linea: bool
    puerta: str | None
    bloqueado: bool
    contrasena_temporal: bool
    sin_contrasena: bool


class UsuarioConTemporal(UsuarioRespuesta):
    """La contraseña temporal se devuelve una sola vez, en la respuesta de la operación (RN-06)."""
    contrasena_generada: str


class UsuariosPagina(BaseModel):
    items: list[UsuarioRespuesta]
    total: int
    en_linea: int
