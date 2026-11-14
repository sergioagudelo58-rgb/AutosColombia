"""Contraseñas y tokens (RNF-01, RNF-02) sin base de datos."""
import pytest
from pydantic import ValidationError

from app.schemas.usuario import UsuarioCrear
from app.seguridad import (faltantes_politica, generar_temporal, hash_contrasena, hash_token, nuevo_token,
                           verificar_contrasena)


def test_hash_bcrypt_y_verificacion():
    guardado = hash_contrasena("Portero2026")
    assert guardado.startswith("$2") and "Portero2026" not in guardado
    assert verificar_contrasena("Portero2026", guardado)
    assert not verificar_contrasena("portero2026", guardado)
    assert not verificar_contrasena("Portero2026", None)


@pytest.mark.parametrize("clave, falta", [
    ("Corta1", "mínimo 8 caracteres"), ("sinmayuscula1", "una letra mayúscula"),
    ("SINMINUSCULA1", "una letra minúscula"), ("SinNumeros", "un número"), ("A1" + "b" * 63, "máximo 64 caracteres"),
])
def test_politica_de_contrasena(clave, falta):
    assert falta in faltantes_politica(clave)


def test_contrasena_distinta_del_usuario_y_temporal_valida():
    assert "ser distinta del nombre de usuario" in faltantes_politica("Drios2026", "drios2026")
    assert faltantes_politica("Portero2026", "drios") == []
    temporales = {generar_temporal() for _ in range(20)}
    assert len(temporales) == 20 and all(len(t) == 10 and not faltantes_politica(t) for t in temporales)


def test_token_se_guarda_como_hash():
    token = nuevo_token()
    assert len(token) >= 40 and hash_token(token) == hash_token(token) and hash_token(token) != token


def test_crear_usuario_valida_formato():
    datos = {"tipo_documento": "CC", "numero_documento": "1.036.458.221", "nombres": "Diana", "apellidos": "Ríos",
             "telefono": "3001234567", "usuario": " DRios ", "rol": "OPERADOR", "fecha_ingreso": "2026-11-01"}
    usuario = UsuarioCrear(**datos)
    assert usuario.usuario == "drios" and usuario.numero_documento == "1036458221"
    for malo in ("1abc", "ab", "con espacio", "ñandu"):
        with pytest.raises(ValidationError):
            UsuarioCrear(**{**datos, "usuario": malo})
    with pytest.raises(ValidationError):
        UsuarioCrear(**{**datos, "rol": "SUPERVISOR"})

