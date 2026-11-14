"""RF-09: corregir un ingreso o una salida (solo administrador, con motivo)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.estancia import Motivo


class CorreccionCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: Motivo
    entrada: datetime | None = None
    salida: datetime | None = None
    anular_salida: bool = False

    @model_validator(mode="after")
    def validar(self) -> "CorreccionCrear":
        if self.entrada is None and self.salida is None and not self.anular_salida:
            raise ValueError("Indica qué corregir: la entrada, la salida o anular la salida.")
        if self.anular_salida and self.salida is not None:
            raise ValueError("No se puede corregir y anular la salida a la vez.")
        for fecha in (self.entrada, self.salida):
            if fecha is not None and fecha.utcoffset() is None:
                raise ValueError("Las fechas deben incluir la zona horaria.")
        return self
