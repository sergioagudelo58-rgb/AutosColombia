"""Tarifas de la mensualidad (RN-12): el único lugar donde se definen los valores.

El valor de cada pago debe ser igual a la tarifa del tipo de vehículo. Lo usan los dos sitios donde se
registra un pago: el primer pago al crear el vehículo (services/vehiculo.py) y POST /pagos (services/pago.py).
"""
from decimal import Decimal

CARRO = Decimal("250000")
CAMIONETA = Decimal("250000")
MOTO = Decimal("100000")

TARIFAS: dict[str, Decimal] = {"CARRO": CARRO, "CAMIONETA": CAMIONETA, "MOTO": MOTO}

MENSAJE_CARRO_CAMIONETA = "El valor de la mensualidad para carro y camioneta es $250.000."
MENSAJE_MOTO = "El valor de la mensualidad para moto es $100.000."


def valor_corresponde(tipo: str, valor: Decimal) -> bool:
    """True si el valor es exactamente la tarifa del tipo de vehículo."""
    tarifa = TARIFAS.get(tipo)
    return tarifa is not None and Decimal(valor) == tarifa


def mensaje_tarifa(tipo: str) -> str:
    """Mensaje que se muestra cuando el valor no coincide con la tarifa."""
    return MENSAJE_MOTO if tipo == "MOTO" else MENSAJE_CARRO_CAMIONETA
