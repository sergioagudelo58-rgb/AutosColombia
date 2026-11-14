"""Contratos del panel en vivo (RF-08), el reporte de ocupación (RF-10) y el historial (RF-11)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.schemas.estancia import Cupo, MovimientoRespuesta, utc


class OcupacionCelda(BaseModel):
    """Lo que el operario ve al seleccionar una celda ocupada (solo lectura)."""
    estancia_id: int
    numero_recibo: str
    placa: str
    tipo_vehiculo: str
    entrada: datetime
    puerta: str
    operador: str

    _utc = field_validator("entrada")(utc)


class CeldaEstado(BaseModel):
    id: int
    codigo: str
    tipo: Literal["CARRO_CAMIONETA", "MOTO"]
    estado: Literal["DISPONIBLE", "OCUPADA", "INHABILITADA"]
    reciente: bool
    """Asignada en los últimos 60 segundos (azul en el mapa)."""
    ocupacion: OcupacionCelda | None


class Actividad(BaseModel):
    tipo: Literal["ENTRADA", "SALIDA", "NOVEDAD"]
    fecha: datetime
    placa: str
    celda: str
    puerta: str | None
    operador: str
    detalle: str

    _utc = field_validator("fecha")(utc)


class Panel(BaseModel):
    generado_en: datetime
    cupos: list[Cupo]
    celdas: list[CeldaEstado]
    actividad: list[Actividad]

    _utc = field_validator("generado_en")(utc)


class ReporteOcupacion(BaseModel):
    generado_en: datetime
    desde: date
    hasta: date
    clientes_registrados: int
    vehiculos_registrados: int
    vehiculos_por_tipo: dict[str, int]
    vehiculos_adentro: int
    cupos: list[Cupo]
    celdas_total: int
    celdas_ocupadas: int
    celdas_disponibles: int
    porcentaje_ocupacion: float
    entradas: int
    salidas: int
    novedades: int

    _utc = field_validator("generado_en")(utc)


class HistorialPagina(BaseModel):
    items: list[MovimientoRespuesta]
    total: int
    offset: int
    limit: int
