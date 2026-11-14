"""Crea el primer administrador desde la consola, sin poner contraseñas en el código.

Uso (desde backend/, con el entorno virtual activo y la base migrada):
    python -m app.crear_administrador

Pide los datos y la contraseña (que no se muestra al escribir). Solo funciona si todavía no hay ningún
administrador activo; los siguientes se crean desde la pantalla Usuarios.
"""
import getpass
import sys
from datetime import date

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditoria import registrar
from app.database import get_engine
from app.models import Operador
from app.schemas.cliente import normalizar_documento
from app.schemas.operador import normalizar_telefono
from app.schemas.usuario import normalizar_usuario
from app.seguridad import faltantes_politica, hash_contrasena


def preguntar(texto: str, validar=lambda v: v.strip() or None):
    while True:
        try:
            valor = validar(input(f"{texto}: "))
            if valor:
                return valor
        except (ValueError, ValidationError) as error:
            print(f"  {error}")


def main() -> int:
    with Session(get_engine()) as session, session.begin():
        if session.scalar(select(Operador.id).where(Operador.rol == "ADMINISTRADOR", Operador.estado == "ACTIVO")):
            print("Ya existe un administrador activo. Crea los demás usuarios desde la pantalla Usuarios.")
            return 1
    print("Primer administrador de Autos Colombia")
    usuario = preguntar("Nombre de usuario (ej. admin)", normalizar_usuario)
    nombres = preguntar("Nombres")
    apellidos = preguntar("Apellidos")
    tipo = preguntar("Tipo de documento (CC, CE, TI, PA, NIT)",
                     lambda v: v.strip().upper() if v.strip().upper() in {"CC", "CE", "TI", "PA", "NIT"} else None)
    documento = preguntar("Número de documento", normalizar_documento)
    telefono = preguntar("Teléfono", normalizar_telefono)
    while True:
        clave = getpass.getpass("Contraseña: ")
        faltan = faltantes_politica(clave, usuario)
        if faltan:
            print("  La contraseña debe tener: " + ", ".join(faltan) + ".")
        elif clave != getpass.getpass("Confirmar contraseña: "):
            print("  Las contraseñas no coinciden.")
        else:
            break
    with Session(get_engine()) as session, session.begin():
        if session.scalar(select(Operador.id).where(Operador.usuario == usuario)):
            print("El usuario ya existe.")
            return 1
        admin = Operador(usuario=usuario, nombres=nombres, apellidos=apellidos, nombre=f"{nombres} {apellidos}",
                         tipo_documento=tipo, numero_documento=documento, telefono=telefono, rol="ADMINISTRADOR",
                         estado="ACTIVO", contrasena_hash=hash_contrasena(clave), contrasena_temporal=False,
                         fecha_ingreso=date.today())
        session.add(admin)
        session.flush()
        registrar(session, None, "USUARIO_CREADO", f"Creó el administrador {usuario} desde la consola.",
                  usuario_texto="consola", entidad="usuario", entidad_id=admin.id)
    print(f"Administrador «{usuario}» creado. Ya puede iniciar sesión.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
