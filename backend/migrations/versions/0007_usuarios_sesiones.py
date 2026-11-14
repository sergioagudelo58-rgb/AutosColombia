"""Iteración 2: usuarios, sesiones y permisos por perfil (RF-01 a RF-07).

Revision ID: 0007
Revises: 0006

- OPERADOR pasa a ser la cuenta de usuario (Administrador u Operador): usuario único, documento
  único, hash bcrypt, rol, estado, bloqueo por intentos y datos de retiro. Los operadores que ya
  existían reciben un usuario «operador<id>», quedan Activos y sin contraseña: no pueden ingresar
  hasta que el administrador les restablezca la contraseña. El primer administrador se crea con
  «python -m app.crear_administrador».
- SESION: una sesión abierta por usuario (RN-03), con su puerta y su última actividad (RNF-04).
- AUDITORIA: bitácora de solo lectura para los eventos de sesión y de usuarios que piden RF-01,
  RF-02, RF-04 y RF-06 (bloqueo, acceso denegado, creación y modificación con valor anterior y
  nuevo). Un trigger rechaza UPDATE, DELETE y TRUNCATE (RNF-07).
- Un trigger impide retirar o cambiar de perfil al último administrador activo (RF-07).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007b"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------- OPERADOR como cuenta de usuario
    for nombre, tipo in [
        ("usuario", sa.Text()), ("tipo_documento", sa.Text()), ("numero_documento", sa.Text()),
        ("nombres", sa.Text()), ("apellidos", sa.Text()), ("correo", sa.Text()), ("contrasena_hash", sa.Text()),
        ("bloqueado_hasta", sa.DateTime(timezone=True)), ("ultima_conexion", sa.DateTime(timezone=True)),
        ("fecha_ingreso", sa.Date()), ("fecha_retiro", sa.Date()), ("motivo_retiro", sa.Text()),
    ]:
        op.add_column("operador", sa.Column(nombre, tipo, nullable=True))
    op.add_column("operador", sa.Column("rol", sa.Text(), server_default="OPERADOR", nullable=False))
    op.add_column("operador", sa.Column("estado", sa.Text(), server_default="ACTIVO", nullable=False))
    op.add_column("operador", sa.Column("contrasena_temporal", sa.Boolean(), server_default=sa.text("true"),
                                        nullable=False))
    op.add_column("operador", sa.Column("intentos_fallidos", sa.Integer(), server_default="0", nullable=False))
    op.add_column("operador", sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(),
                                        nullable=False))
    op.execute("UPDATE operador SET usuario = 'operador' || id WHERE usuario IS NULL")
    op.alter_column("operador", "usuario", nullable=False)
    op.create_unique_constraint("uq_operador_usuario", "operador", ["usuario"])
    op.create_unique_constraint("uq_operador_documento", "operador", ["numero_documento"])
    op.create_check_constraint("ck_operador_usuario_formato", "operador", "usuario ~ '^[a-z][a-z0-9._]{2,29}$'")
    op.create_check_constraint("ck_operador_rol", "operador", "rol IN ('ADMINISTRADOR', 'OPERADOR')")
    op.create_check_constraint("ck_operador_estado", "operador", "estado IN ('ACTIVO', 'RETIRADO')")
    op.create_check_constraint("ck_operador_tipo_documento", "operador",
                               "tipo_documento IS NULL OR tipo_documento IN ('CC', 'CE', 'TI', 'PA', 'NIT')")
    op.create_check_constraint("ck_operador_intentos", "operador", "intentos_fallidos >= 0")
    op.create_check_constraint("ck_operador_retiro_completo", "operador",
                               "(estado = 'RETIRADO') = (fecha_retiro IS NOT NULL)")
    op.execute("""
        CREATE FUNCTION operador_conserva_administrador() RETURNS trigger AS $$
        BEGIN
            IF OLD.rol = 'ADMINISTRADOR' AND OLD.estado = 'ACTIVO'
               AND (TG_OP = 'DELETE' OR NEW.rol <> 'ADMINISTRADOR' OR NEW.estado <> 'ACTIVO')
               AND NOT EXISTS (SELECT 1 FROM operador
                               WHERE id <> OLD.id AND rol = 'ADMINISTRADOR' AND estado = 'ACTIVO') THEN
                RAISE EXCEPTION 'No se puede dejar el sistema sin un administrador activo.'
                    USING ERRCODE = '23514', CONSTRAINT = 'tg_operador_ultimo_administrador';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER tg_operador_ultimo_administrador BEFORE UPDATE OR DELETE ON operador
        FOR EACH ROW EXECUTE FUNCTION operador_conserva_administrador()
    """)

    # ---------------- SESION
    op.create_table(
        "sesion",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("puerta_id", sa.SmallInteger(), nullable=True),
        sa.Column("equipo", sa.Text(), nullable=True),
        sa.Column("iniciada", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ultima_actividad", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("cerrada", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_cierre", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["operador_id"], ["operador.id"], name="fk_sesion_operador", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["puerta_id"], ["puerta.id"], name="fk_sesion_puerta", ondelete="RESTRICT"),
        sa.UniqueConstraint("token_hash", name="uq_sesion_token"),
        sa.CheckConstraint("(cerrada IS NULL) = (motivo_cierre IS NULL)", name="ck_sesion_cierre_completo"),
    )
    op.create_index("uq_sesion_abierta", "sesion", ["operador_id"], unique=True,
                    postgresql_where=sa.text("cerrada IS NULL"))

    # ---------------- AUDITORIA
    op.create_table(
        "auditoria",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=True),
        sa.Column("usuario", sa.Text(), nullable=True),
        sa.Column("rol", sa.Text(), nullable=True),
        sa.Column("puerta", sa.Text(), nullable=True),
        sa.Column("equipo", sa.Text(), nullable=True),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("entidad", sa.Text(), nullable=True),
        sa.Column("entidad_id", sa.Text(), nullable=True),
        sa.Column("placa", sa.Text(), nullable=True),
        sa.Column("detalle", sa.Text(), nullable=False),
        sa.Column("valor_anterior", postgresql.JSONB(), nullable=True),
        sa.Column("valor_nuevo", postgresql.JSONB(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.CheckConstraint("accion ~ '^[A-Z_]+$'", name="ck_auditoria_accion"),
    )
    op.create_index("ix_auditoria_fecha", "auditoria", ["fecha"])
    op.create_index("ix_auditoria_usuario", "auditoria", ["usuario_id", "fecha"])
    op.create_index("ix_auditoria_accion", "auditoria", ["accion"])
    op.create_index("ix_auditoria_placa", "auditoria", ["placa"])
    op.execute("""
        CREATE FUNCTION auditoria_solo_lectura() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'La auditoría es de solo lectura.' USING ERRCODE = '42501';
        END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER tg_auditoria_solo_lectura BEFORE UPDATE OR DELETE ON auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_solo_lectura()
    """)
    op.execute("""
        CREATE TRIGGER tg_auditoria_sin_truncate BEFORE TRUNCATE ON auditoria
        FOR EACH STATEMENT EXECUTE FUNCTION auditoria_solo_lectura()
    """)


def downgrade() -> None:
    # Reversión deliberada: elimina sesiones, auditoría y los datos de las cuentas.
    op.execute("DROP TRIGGER tg_auditoria_sin_truncate ON auditoria")
    op.execute("DROP TRIGGER tg_auditoria_solo_lectura ON auditoria")
    op.execute("DROP FUNCTION auditoria_solo_lectura()")
    op.drop_table("auditoria")
    op.drop_index("uq_sesion_abierta", table_name="sesion")
    op.drop_table("sesion")
    op.execute("DROP TRIGGER tg_operador_ultimo_administrador ON operador")
    op.execute("DROP FUNCTION operador_conserva_administrador()")
    for nombre in ("ck_operador_retiro_completo", "ck_operador_intentos", "ck_operador_tipo_documento",
                   "ck_operador_estado", "ck_operador_rol", "ck_operador_usuario_formato"):
        op.drop_constraint(nombre, "operador", type_="check")
    op.drop_constraint("uq_operador_documento", "operador", type_="unique")
    op.drop_constraint("uq_operador_usuario", "operador", type_="unique")
    for nombre in ("creado_en", "intentos_fallidos", "contrasena_temporal", "estado", "rol", "motivo_retiro",
                   "fecha_retiro", "fecha_ingreso", "ultima_conexion", "bloqueado_hasta", "contrasena_hash",
                   "correo", "apellidos", "nombres", "numero_documento", "tipo_documento", "usuario"):
        op.drop_column("operador", nombre)
