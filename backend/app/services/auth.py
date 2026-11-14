"""Inicio y cierre de sesión, contraseña propia y puerta del turno (RF-01, RF-03, RF-05)."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auditoria import Actor, registrar
from app.errores import ApiError
from app.models import Operador, Puerta, Sesion
from app.schemas.auth import CambioContrasena, LoginCrear
from app.seguridad import (BLOQUEO, INACTIVIDAD, INTENTOS_MAXIMOS, faltantes_politica, hash_contrasena,
                           hash_token, nuevo_token, verificar_contrasena)

CREDENCIALES = "Usuario o contraseña incorrectos."
BLOQUEADA = "Cuenta bloqueada por 15 minutos."
INACTIVO = "Usuario inactivo. Comuníquese con el administrador."


def respuesta(usuario: Operador, sesion: Sesion, puerta: Puerta | None, token: str | None = None) -> dict:
    datos = {
        "usuario_id": usuario.id, "usuario": usuario.usuario, "nombre": usuario.nombre, "rol": usuario.rol,
        "puerta_id": puerta.id if puerta else None, "puerta": puerta.nombre if puerta else None,
        "contrasena_temporal": usuario.contrasena_temporal,
        "inactividad_segundos": int(INACTIVIDAD.total_seconds()),
    }
    if token:
        datos["token"] = token
    return datos


def _actor(usuario: Operador, sesion: Sesion | None, puerta: Puerta | None, equipo: str | None) -> Actor:
    return Actor(id=usuario.id, usuario=usuario.usuario, nombre=usuario.nombre, rol=usuario.rol,
                 puerta_id=puerta.id if puerta else None, puerta=puerta.nombre if puerta else None,
                 sesion_id=sesion.id if sesion else None, equipo=equipo)


def _vence_si_inactiva(session: Session, usuario: Operador, ahora: datetime, equipo: str) -> Sesion | None:
    """Devuelve la sesión abierta vigente del usuario; si venció por inactividad, la cierra."""
    abierta = session.scalar(select(Sesion).where(Sesion.operador_id == usuario.id, Sesion.cerrada.is_(None))
                             .with_for_update())
    if abierta is not None and ahora - abierta.ultima_actividad > INACTIVIDAD:
        abierta.cerrada, abierta.motivo_cierre = ahora, "INACTIVIDAD"
        registrar(session, _actor(usuario, abierta, abierta.puerta, abierta.equipo), "SESION_VENCIDA",
                  "Sesión cerrada por 15 minutos sin actividad.", entidad="sesion", entidad_id=abierta.id)
        session.flush()
        return None
    return abierta


def login(session: Session, data: LoginCrear, equipo: str) -> dict:
    error: ApiError | None = None
    resultado: dict | None = None
    with session.begin():
        ahora = datetime.now(timezone.utc)
        usuario = session.scalar(select(Operador).where(Operador.usuario == data.usuario).with_for_update())
        if usuario is None:
            verificar_contrasena(data.contrasena, None)
            registrar(session, None, "LOGIN_FALLIDO", "Intento de ingreso con un usuario que no existe.",
                      usuario_texto=data.usuario[:30], equipo=equipo)
            error = ApiError(401, CREDENCIALES)
        elif usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora:
            error = ApiError(423, BLOQUEADA)
        elif not verificar_contrasena(data.contrasena, usuario.contrasena_hash):
            usuario.intentos_fallidos += 1
            actor = _actor(usuario, None, None, equipo)
            if usuario.intentos_fallidos >= INTENTOS_MAXIMOS:
                usuario.intentos_fallidos = 0
                usuario.bloqueado_hasta = ahora + BLOQUEO
                registrar(session, actor, "CUENTA_BLOQUEADA",
                          f"Cuenta bloqueada 15 minutos tras {INTENTOS_MAXIMOS} intentos fallidos.",
                          entidad="usuario", entidad_id=usuario.id)
                error = ApiError(423, BLOQUEADA)
            else:
                registrar(session, actor, "LOGIN_FALLIDO",
                          f"Contraseña incorrecta (intento {usuario.intentos_fallidos} de {INTENTOS_MAXIMOS}).",
                          entidad="usuario", entidad_id=usuario.id)
                error = ApiError(401, CREDENCIALES)
        elif usuario.estado != "ACTIVO":
            registrar(session, _actor(usuario, None, None, equipo), "LOGIN_FALLIDO",
                      "Intento de ingreso de un usuario retirado.", entidad="usuario", entidad_id=usuario.id)
            error = ApiError(403, INACTIVO)
        else:
            puerta = session.get(Puerta, data.puerta_id) if data.puerta_id is not None else None
            if data.puerta_id is not None and puerta is None:
                error = ApiError(422, "La puerta seleccionada no existe.")
            elif usuario.rol == "OPERADOR" and puerta is None:
                error = ApiError(422, "Selecciona la puerta en la que vas a trabajar.")
            elif (abierta := _vence_si_inactiva(session, usuario, ahora, equipo)) is not None:
                donde = abierta.puerta.nombre if abierta.puerta else "otro equipo"
                error = ApiError(409, f"Este usuario ya tiene una sesión abierta en {donde}. "
                                      "Ciérrela allí o pida al administrador que la cierre.")
            else:
                usuario.intentos_fallidos = 0
                usuario.bloqueado_hasta = None
                usuario.ultima_conexion = ahora
                token = nuevo_token()
                sesion = Sesion(token_hash=hash_token(token), operador_id=usuario.id,
                                puerta_id=puerta.id if puerta else None, equipo=equipo,
                                iniciada=ahora, ultima_actividad=ahora)
                session.add(sesion)
                try:
                    session.flush()
                except IntegrityError:
                    # Dos ingresos simultáneos del mismo usuario: el índice único deja pasar solo uno (RN-03).
                    raise ApiError(409, "Este usuario ya tiene una sesión abierta.") from None
                registrar(session, _actor(usuario, sesion, puerta, equipo), "LOGIN",
                          f"Inicio de sesión{' en ' + puerta.nombre if puerta else ''}.",
                          entidad="sesion", entidad_id=sesion.id)
                resultado = respuesta(usuario, sesion, puerta, token)
    if error is not None:
        raise error
    return resultado


def logout(session: Session, actor: Actor) -> None:
    with session.begin():
        sesion = session.get(Sesion, actor.sesion_id, with_for_update=True)
        if sesion is not None and sesion.cerrada is None:
            sesion.cerrada, sesion.motivo_cierre = datetime.now(timezone.utc), "LOGOUT"
            registrar(session, actor, "LOGOUT", "Cierre de sesión.", entidad="sesion", entidad_id=sesion.id)


def sesion(session: Session, actor: Actor) -> dict:
    with session.begin():
        usuario = session.get(Operador, actor.id)
        abierta = session.get(Sesion, actor.sesion_id)
        return respuesta(usuario, abierta, abierta.puerta)


def cambiar_contrasena(session: Session, actor: Actor, data: CambioContrasena) -> dict:
    error: ApiError | None = None
    with session.begin():
        usuario = session.get(Operador, actor.id, with_for_update=True)
        if not verificar_contrasena(data.actual, usuario.contrasena_hash):
            registrar(session, actor, "CAMBIO_CONTRASENA_FALLIDO", "La contraseña actual no coincide.",
                      entidad="usuario", entidad_id=usuario.id)
            error = ApiError(422, "La contraseña actual no es correcta.")
        elif data.nueva != data.confirmacion:
            error = ApiError(422, "La confirmación no coincide con la nueva contraseña.")
        elif faltan := faltantes_politica(data.nueva, usuario.usuario):
            error = ApiError(422, "La contraseña debe tener: " + ", ".join(faltan) + ".")
        elif verificar_contrasena(data.nueva, usuario.contrasena_hash):
            error = ApiError(422, "La nueva contraseña debe ser distinta de la actual.")
        else:
            usuario.contrasena_hash = hash_contrasena(data.nueva)
            usuario.contrasena_temporal = False
            registrar(session, actor, "CAMBIO_CONTRASENA", "El usuario cambió su contraseña.",
                      entidad="usuario", entidad_id=usuario.id)
            abierta = session.get(Sesion, actor.sesion_id)
            resultado = respuesta(usuario, abierta, abierta.puerta)
    if error is not None:
        raise error
    return resultado


def cambiar_puerta(session: Session, actor: Actor, puerta_id: int | None) -> dict:
    """El administrador elige la puerta en la que cubre el turno; el operador la fija al ingresar."""
    if not actor.es_admin:
        raise ApiError(403, "La puerta del operador se elige al iniciar sesión.")
    with session.begin():
        puerta = session.get(Puerta, puerta_id) if puerta_id is not None else None
        if puerta_id is not None and puerta is None:
            raise ApiError(422, "La puerta seleccionada no existe.")
        abierta = session.get(Sesion, actor.sesion_id, with_for_update=True)
        abierta.puerta_id = puerta.id if puerta else None
        registrar(session, actor, "CAMBIO_PUERTA",
                  f"Cubre turno en {puerta.nombre}." if puerta else "Deja de cubrir turno en puerta.",
                  entidad="sesion", entidad_id=abierta.id)
        session.flush()
        return respuesta(session.get(Operador, actor.id), abierta, puerta)


def acceso_denegado(session: Session, actor: Actor, ruta: str) -> None:
    with session.begin():
        registrar(session, actor, "ACCESO_DENEGADO", f"Intentó abrir {ruta} sin permiso.",
                  entidad="ruta", entidad_id=ruta)
