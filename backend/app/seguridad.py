"""Contraseñas (RNF-01, RNF-02), tokens de sesión y reglas de bloqueo (RNF-03, RNF-04). Sin base de datos."""

import hashlib
import secrets
import string
from datetime import timedelta

import bcrypt

INACTIVIDAD = timedelta(minutes=15)
"""RNF-04: la sesión se cierra sola tras 15 minutos sin actividad."""
INTENTOS_MAXIMOS = 5
BLOQUEO = timedelta(minutes=15)
"""RNF-03: tras 5 intentos fallidos seguidos, la cuenta se bloquea 15 minutos."""
LONGITUD_MINIMA = 8
LONGITUD_MAXIMA = 64
"""bcrypt solo usa los primeros 72 bytes; con 64 caracteres no se pierde ninguno en la práctica."""

_ALFABETO_TEMPORAL = "".join(c for c in string.ascii_letters + string.digits if c not in "O0Il1")


def hash_contrasena(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_contrasena(contrasena: str, hash_guardado: str | None) -> bool:
    if not hash_guardado:
        # Se calcula igual un hash para no revelar por el tiempo de respuesta si la cuenta tiene clave.
        bcrypt.checkpw(b"x", _HASH_FICTICIO)
        return False
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8")[:72], hash_guardado.encode("ascii"))
    except ValueError:
        return False


_HASH_FICTICIO = bcrypt.hashpw(b"autos-colombia", bcrypt.gensalt())


def generar_temporal() -> str:
    """Contraseña temporal de 10 caracteres que cumple la política (RN-06); se muestra una sola vez."""
    while True:
        clave = "".join(secrets.choice(_ALFABETO_TEMPORAL) for _ in range(10))
        if not faltantes_politica(clave):
            return clave


def faltantes_politica(contrasena: str, usuario: str | None = None) -> list[str]:
    """RNF-02: devuelve lo que le falta a la contraseña; lista vacía si cumple."""
    faltan = []
    if len(contrasena) < LONGITUD_MINIMA:
        faltan.append("mínimo 8 caracteres")
    if len(contrasena) > LONGITUD_MAXIMA:
        faltan.append("máximo 64 caracteres")
    if not any(c.isupper() for c in contrasena):
        faltan.append("una letra mayúscula")
    if not any(c.islower() for c in contrasena):
        faltan.append("una letra minúscula")
    if not any(c.isdigit() for c in contrasena):
        faltan.append("un número")
    if usuario and contrasena.strip().lower() == usuario.lower():
        faltan.append("ser distinta del nombre de usuario")
    return faltan


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """En la base solo se guarda el SHA-256 del token: una copia de la base no permite suplantar sesiones."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
