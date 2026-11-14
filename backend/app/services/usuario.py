"""Usuarios del sistema: crear, consultar, modificar, retirar, reactivar y contraseñas (RF-04 a RF-07)."""
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auditoria import Actor, cambios, registrar
from app.errores import ApiError
from app.models import Operador, Sesion
from app.schemas.usuario import Retiro, UsuarioActualizar, UsuarioCrear
from app.seguridad import INACTIVIDAD, generar_temporal, hash_contrasena

ULTIMO_ADMIN = "No se puede retirar al único administrador activo."
CAMPOS = ("nombres", "apellidos", "telefono", "correo", "rol")


def _abiertas(session: Session, ids: list[int]) -> dict[int, Sesion]:
    if not ids:
        return {}
    limite = datetime.now(timezone.utc) - INACTIVIDAD
    filas = session.scalars(select(Sesion).where(Sesion.operador_id.in_(ids), Sesion.cerrada.is_(None),
                                                 Sesion.ultima_actividad >= limite))
    return {s.operador_id: s for s in filas}


def vista(usuario: Operador, abierta: Sesion | None) -> dict:
    ahora = datetime.now(timezone.utc)
    return {
        "id": usuario.id, "usuario": usuario.usuario, "nombre": usuario.nombre, "nombres": usuario.nombres,
        "apellidos": usuario.apellidos, "tipo_documento": usuario.tipo_documento,
        "numero_documento": usuario.numero_documento, "telefono": usuario.telefono, "correo": usuario.correo,
        "rol": usuario.rol, "estado": usuario.estado, "fecha_ingreso": usuario.fecha_ingreso,
        "fecha_retiro": usuario.fecha_retiro, "motivo_retiro": usuario.motivo_retiro,
        "ultima_conexion": usuario.ultima_conexion, "en_linea": abierta is not None,
        "puerta": abierta.puerta.nombre if abierta and abierta.puerta else None,
        "bloqueado": usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora,
        "contrasena_temporal": usuario.contrasena_temporal, "sin_contrasena": usuario.contrasena_hash is None,
    }


def _vista_de(session: Session, usuario: Operador) -> dict:
    return vista(usuario, _abiertas(session, [usuario.id]).get(usuario.id))


def _buscar(session: Session, usuario_id: int) -> Operador:
    usuario = session.get(Operador, usuario_id, with_for_update=True)
    if usuario is None:
        raise ApiError(404, "Usuario no encontrado.")
    return usuario


def _datos(usuario: Operador) -> dict:
    return {c: getattr(usuario, c) for c in CAMPOS}


def _cerrar_sesion(session: Session, usuario_id: int, motivo: str) -> bool:
    abierta = session.scalar(select(Sesion).where(Sesion.operador_id == usuario_id, Sesion.cerrada.is_(None))
                             .with_for_update())
    if abierta is None:
        return False
    abierta.cerrada, abierta.motivo_cierre = datetime.now(timezone.utc), motivo
    return True


def _duplicado(error: IntegrityError) -> ApiError:
    restriccion = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if restriccion == "uq_operador_usuario":
        return ApiError(409, "El usuario ya existe.")
    if restriccion == "uq_operador_documento":
        return ApiError(409, "Ya existe un usuario con ese número de documento.")
    if restriccion == "uq_operador_telefono":
        return ApiError(409, "Ya existe un usuario con ese teléfono.")
    if restriccion == "tg_operador_ultimo_administrador":
        return ApiError(409, "No se puede dejar el sistema sin un administrador activo.")
    return ApiError(409, "Los datos entran en conflicto con otro usuario.")


def _guardar(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as error:
        raise _duplicado(error) from None


def crear(session: Session, actor: Actor, data: UsuarioCrear) -> dict:
    temporal = generar_temporal()
    with session.begin():
        if session.scalar(select(Operador.id).where(Operador.usuario == data.usuario)) is not None:
            raise ApiError(409, "El usuario ya existe.")
        usuario = Operador(**data.model_dump(), nombre=f"{data.nombres} {data.apellidos}",
                           contrasena_hash=hash_contrasena(temporal), contrasena_temporal=True, estado="ACTIVO")
        session.add(usuario)
        _guardar(session)
        registrar(session, actor, "USUARIO_CREADO",
                  f"Creó el usuario {usuario.usuario} ({usuario.rol.lower()}).", entidad="usuario",
                  entidad_id=usuario.id, nuevo={**_datos(usuario), "usuario": usuario.usuario,
                                               "numero_documento": usuario.numero_documento})
        return {**vista(usuario, None), "contrasena_generada": temporal}


def listar(session: Session, estado: str | None, rol: str | None, q: str | None) -> dict:
    with session.begin():
        consulta = select(Operador)
        if estado:
            consulta = consulta.where(Operador.estado == estado)
        if rol:
            consulta = consulta.where(Operador.rol == rol)
        if q:
            patron = f"%{q.strip()}%"
            consulta = consulta.where(or_(Operador.usuario.ilike(patron), Operador.nombre.ilike(patron),
                                          Operador.numero_documento.ilike(patron)))
        usuarios = list(session.scalars(consulta.order_by(Operador.estado, Operador.nombre)))
        abiertas = _abiertas(session, [u.id for u in usuarios])
        items = [vista(u, abiertas.get(u.id)) for u in usuarios]
        return {"items": items, "total": len(items), "en_linea": sum(1 for i in items if i["en_linea"])}


def obtener(session: Session, usuario_id: int) -> dict:
    with session.begin():
        usuario = session.get(Operador, usuario_id)
        if usuario is None:
            raise ApiError(404, "Usuario no encontrado.")
        return _vista_de(session, usuario)


def actualizar(session: Session, actor: Actor, usuario_id: int, data: UsuarioActualizar) -> dict:
    with session.begin():
        usuario = _buscar(session, usuario_id)
        antes = _datos(usuario)
        for clave, valor in data.model_dump(exclude_unset=True).items():
            setattr(usuario, clave, valor)
        usuario.nombre = f"{usuario.nombres or ''} {usuario.apellidos or ''}".strip() or usuario.nombre
        anterior, nuevo = cambios(antes, _datos(usuario))
        if not nuevo:
            return _vista_de(session, usuario)
        _guardar(session)
        if "rol" in nuevo:
            # Con otro perfil cambian los permisos: la sesión abierta se cierra para que vuelva a ingresar.
            _cerrar_sesion(session, usuario.id, "CERRADA_ADMIN")
        registrar(session, actor, "USUARIO_MODIFICADO", f"Modificó los datos de {usuario.usuario}.",
                  entidad="usuario", entidad_id=usuario.id, anterior=anterior, nuevo=nuevo)
        return _vista_de(session, usuario)


def retirar(session: Session, actor: Actor, usuario_id: int, data: Retiro) -> dict:
    with session.begin():
        usuario = _buscar(session, usuario_id)
        if usuario.estado == "RETIRADO":
            raise ApiError(409, "El usuario ya está retirado.")
        if usuario.id == actor.id:
            raise ApiError(409, "No puedes retirar tu propio usuario.")
        if usuario.rol == "ADMINISTRADOR" and not session.scalar(
                select(func.count()).select_from(Operador).where(Operador.id != usuario.id,
                                                                  Operador.rol == "ADMINISTRADOR",
                                                                  Operador.estado == "ACTIVO")):
            raise ApiError(409, ULTIMO_ADMIN)
        fecha = data.fecha_retiro or date.today()
        if usuario.fecha_ingreso and fecha < usuario.fecha_ingreso:
            raise ApiError(422, "La fecha de retiro no puede ser anterior a la fecha de ingreso.")
        usuario.estado, usuario.fecha_retiro, usuario.motivo_retiro = "RETIRADO", fecha, data.motivo
        _guardar(session)
        cerro = _cerrar_sesion(session, usuario.id, "RETIRO")
        registrar(session, actor, "USUARIO_RETIRADO",
                  f"Retiró a {usuario.usuario}{' y cerró su sesión abierta' if cerro else ''}.",
                  entidad="usuario", entidad_id=usuario.id, anterior={"estado": "ACTIVO"},
                  nuevo={"estado": "RETIRADO", "fecha_retiro": fecha}, motivo=data.motivo)
        return vista(usuario, None)


def reactivar(session: Session, actor: Actor, usuario_id: int) -> dict:
    temporal = generar_temporal()
    with session.begin():
        usuario = _buscar(session, usuario_id)
        if usuario.estado == "ACTIVO":
            raise ApiError(409, "El usuario ya está activo.")
        usuario.estado, usuario.fecha_retiro, usuario.motivo_retiro = "ACTIVO", None, None
        usuario.contrasena_hash, usuario.contrasena_temporal = hash_contrasena(temporal), True
        usuario.intentos_fallidos, usuario.bloqueado_hasta = 0, None
        _guardar(session)
        registrar(session, actor, "USUARIO_REACTIVADO",
                  f"Reactivó a {usuario.usuario} con una contraseña temporal nueva.", entidad="usuario",
                  entidad_id=usuario.id, anterior={"estado": "RETIRADO"}, nuevo={"estado": "ACTIVO"})
        return {**vista(usuario, None), "contrasena_generada": temporal}


def restablecer_contrasena(session: Session, actor: Actor, usuario_id: int) -> dict:
    temporal = generar_temporal()
    with session.begin():
        usuario = _buscar(session, usuario_id)
        if usuario.estado != "ACTIVO":
            raise ApiError(409, "Reactiva al usuario antes de restablecer su contraseña.")
        usuario.contrasena_hash, usuario.contrasena_temporal = hash_contrasena(temporal), True
        usuario.intentos_fallidos, usuario.bloqueado_hasta = 0, None
        cerro = _cerrar_sesion(session, usuario.id, "CONTRASENA_RESTABLECIDA")
        registrar(session, actor, "CONTRASENA_RESTABLECIDA",
                  f"Restableció la contraseña de {usuario.usuario}{' y cerró su sesión' if cerro else ''}.",
                  entidad="usuario", entidad_id=usuario.id)
        return {**vista(usuario, None), "contrasena_generada": temporal}


def desbloquear(session: Session, actor: Actor, usuario_id: int) -> dict:
    with session.begin():
        usuario = _buscar(session, usuario_id)
        usuario.intentos_fallidos, usuario.bloqueado_hasta = 0, None
        registrar(session, actor, "USUARIO_DESBLOQUEADO", f"Desbloqueó la cuenta de {usuario.usuario}.",
                  entidad="usuario", entidad_id=usuario.id)
        return _vista_de(session, usuario)


def cerrar_sesion(session: Session, actor: Actor, usuario_id: int) -> dict:
    with session.begin():
        usuario = _buscar(session, usuario_id)
        if not _cerrar_sesion(session, usuario.id, "CERRADA_ADMIN"):
            raise ApiError(409, "El usuario no tiene una sesión abierta.")
        registrar(session, actor, "SESION_CERRADA_ADMIN", f"Cerró la sesión de {usuario.usuario}.",
                  entidad="usuario", entidad_id=usuario.id)
        return vista(usuario, None)
