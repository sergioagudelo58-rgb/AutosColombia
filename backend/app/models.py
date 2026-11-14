"""Modelos iniciales. Importar este módulo no crea tablas ni abre conexiones."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, Identity, Index, Integer,
    SmallInteger, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates

TIPOS_VEHICULO = ("MOTO", "CARRO", "CAMIONETA")
TIPOS_CELDA = ("CARRO_CAMIONETA", "MOTO")
TIPOS_DOCUMENTO = ("CC", "CE", "TI", "PA", "NIT")
DIAS_MENSUALIDAD = 30
TELEFONO_COLOMBIANO = "^(3[0-9]{9}|60[1-8][0-9]{7})$"
ROLES = ("ADMINISTRADOR", "OPERADOR")
ESTADOS_USUARIO = ("ACTIVO", "RETIRADO")
USUARIO_FORMATO = "^[a-z][a-z0-9._]{2,29}$"


def tipo_celda_para(tipo_vehiculo: str) -> str:
    """RN-05: las motos usan celdas de moto; carros y camionetas comparten las demás."""
    return "MOTO" if tipo_vehiculo == "MOTO" else "CARRO_CAMIONETA"


class Base(DeclarativeBase):
    pass


def required_text(value: str, attribute: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute} debe ser texto no vacío.")
    return value.strip()


class Cliente(Base):
    """Persona dueña de uno o varios vehículos (RN-03)."""
    __tablename__ = "cliente"
    __table_args__ = (
        UniqueConstraint("numero_documento", name="uq_cliente_documento"),
        CheckConstraint("tipo_documento IN ('CC', 'CE', 'TI', 'PA', 'NIT')", name="ck_cliente_tipo_documento"),
        CheckConstraint("numero_documento ~ '^[0-9A-Z]{3,20}$'", name="ck_cliente_documento_formato"),
        CheckConstraint("nombres ~ '[^[:space:]]'", name="ck_cliente_nombres_no_vacios"),
        CheckConstraint("apellidos ~ '[^[:space:]]'", name="ck_cliente_apellidos_no_vacios"),
        CheckConstraint(f"telefono ~ '{TELEFONO_COLOMBIANO}'", name="ck_cliente_telefono_colombiano"),
        CheckConstraint("correo IS NULL OR correo ~ '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
                        name="ck_cliente_correo_formato"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tipo_documento: Mapped[str] = mapped_column(Text, nullable=False)
    numero_documento: Mapped[str] = mapped_column(Text, nullable=False)
    nombres: Mapped[str] = mapped_column(Text, nullable=False)
    apellidos: Mapped[str] = mapped_column(Text, nullable=False)
    telefono: Mapped[str] = mapped_column(Text, nullable=False)
    correo: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    vehiculos: Mapped[list["Vehiculo"]] = relationship(back_populates="cliente", order_by="Vehiculo.placa")


class Puerta(Base):
    """Puertas de acceso del parqueadero (RN-10)."""
    __tablename__ = "puerta"
    __table_args__ = (UniqueConstraint("nombre", name="uq_puerta_nombre"),)

    id: Mapped[int] = mapped_column(SmallInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)


class Vehiculo(Base):
    __tablename__ = "vehiculo"
    __table_args__ = (
        UniqueConstraint("placa", name="uq_vehiculo_placa"),
        CheckConstraint("placa ~ '[^[:space:]]'", name="ck_vehiculo_placa_no_vacia"),
        CheckConstraint("placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_vehiculo_placa_normalizada"),
        CheckConstraint("placa ~ '^[A-Z]{3}[0-9]{2}[0-9A-Z]$'", name="ck_vehiculo_placa_colombiana"),
        CheckConstraint("color ~ '[^[:space:]]'", name="ck_vehiculo_color_no_vacio"),
        CheckConstraint("marca ~ '[^[:space:]]'", name="ck_vehiculo_marca_no_vacia"),
        CheckConstraint("modelo BETWEEN 1 AND 9999", name="ck_vehiculo_modelo_anio"),
        CheckConstraint("tipo IN ('MOTO', 'CARRO', 'CAMIONETA')", name="ck_vehiculo_tipo"),
        CheckConstraint("linea IS NULL OR linea ~ '[^[:space:]]'", name="ck_vehiculo_linea_no_vacia"),
        Index("ix_vehiculo_cliente", "cliente_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    placa: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[int] = mapped_column(Integer, nullable=False)
    marca: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    # Nulos solo para vehículos anteriores a la revisión 0005: sin cliente o sin pago no pueden ingresar (RF-04).
    cliente_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cliente.id", name="fk_vehiculo_cliente", ondelete="RESTRICT"), nullable=True
    )
    linea: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_pago: Mapped[date | None] = mapped_column(Date, nullable=True)
    # RN-06: vencimiento = fecha de pago + 30 días; lo calcula PostgreSQL.
    fecha_vencimiento: Mapped[date | None] = mapped_column(
        Date, Computed(f"fecha_pago + {DIAS_MENSUALIDAD}", persisted=True)
    )

    cliente: Mapped[Cliente | None] = relationship(back_populates="vehiculos")

    @validates("placa", "color", "marca", "tipo")
    def validate_text(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if key == "placa":
            return value.upper()
        if key == "tipo" and value not in TIPOS_VEHICULO:
            raise ValueError("tipo debe ser MOTO, CARRO o CAMIONETA.")
        return value

    @validates("modelo")
    def validate_modelo(self, key: str, value: int) -> int:
        if type(value) is not int or not 1 <= value <= 9999:
            raise ValueError("modelo debe ser un año entero entre 1 y 9999.")
        return value


class Celda(Base):
    __tablename__ = "celda"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_celda_codigo"),
        CheckConstraint("codigo ~ '[^[:space:]]'", name="ck_celda_codigo_no_vacio"),
        CheckConstraint("codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name="ck_celda_codigo_normalizado"),
        CheckConstraint("tipo IN ('CARRO_CAMIONETA', 'MOTO')", name="ck_celda_tipo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)

    @validates("codigo", "tipo")
    def validate_text(self, key: str, value: str) -> str:
        value = required_text(value, key)
        if key == "tipo" and value not in TIPOS_CELDA:
            raise ValueError("tipo debe ser CARRO_CAMIONETA o MOTO.")
        return value.upper() if key == "codigo" else value


class Operador(Base):
    """Usuario del sistema (empleado): Administrador u Operador (RN-01). Nunca se borra; se retira (RN-05).

    La tabla conserva su nombre de la iteración 1 porque los ingresos, salidas y novedades la referencian.
    Los usuarios creados antes de la revisión 0007 no tienen documento ni contraseña: el administrador
    debe restablecerla para que puedan ingresar.
    """
    __tablename__ = "operador"
    __table_args__ = (
        CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_operador_nombre_no_vacio"),
        CheckConstraint("telefono ~ '[^[:space:]]'", name="ck_operador_telefono_no_vacio"),
        UniqueConstraint("telefono", name="uq_operador_telefono"),
        CheckConstraint("telefono ~ '^(3[0-9]{9}|60[1-8][0-9]{7})$'", name="ck_operador_telefono_colombiano"),
        UniqueConstraint("usuario", name="uq_operador_usuario"),
        UniqueConstraint("numero_documento", name="uq_operador_documento"),
        CheckConstraint(f"usuario ~ '{USUARIO_FORMATO}'", name="ck_operador_usuario_formato"),
        CheckConstraint("rol IN ('ADMINISTRADOR', 'OPERADOR')", name="ck_operador_rol"),
        CheckConstraint("estado IN ('ACTIVO', 'RETIRADO')", name="ck_operador_estado"),
        CheckConstraint("tipo_documento IS NULL OR tipo_documento IN ('CC', 'CE', 'TI', 'PA', 'NIT')",
                        name="ck_operador_tipo_documento"),
        CheckConstraint("intentos_fallidos >= 0", name="ck_operador_intentos"),
        CheckConstraint("(estado = 'RETIRADO') = (fecha_retiro IS NOT NULL)", name="ck_operador_retiro_completo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    telefono: Mapped[str] = mapped_column(Text, nullable=False)
    usuario: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_documento: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_documento: Mapped[str | None] = mapped_column(Text, nullable=True)
    nombres: Mapped[str | None] = mapped_column(Text, nullable=True)
    apellidos: Mapped[str | None] = mapped_column(Text, nullable=True)
    correo: Mapped[str | None] = mapped_column(Text, nullable=True)
    rol: Mapped[str] = mapped_column(Text, nullable=False, server_default="OPERADOR", default="OPERADOR")
    estado: Mapped[str] = mapped_column(Text, nullable=False, server_default="ACTIVO", default="ACTIVO")
    # RNF-01: solo el hash bcrypt; nunca la contraseña.
    contrasena_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_temporal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"),
                                                      default=True)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultima_conexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_ingreso: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_retiro: Mapped[date | None] = mapped_column(Date, nullable=True)
    motivo_retiro: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @validates("nombre", "telefono")
    def validate_text(self, key: str, value: str) -> str:
        return required_text(value, key)


class Estancia(Base):
    __tablename__ = "estancia"
    __table_args__ = (
        CheckConstraint("salida >= entrada", name="ck_estancia_orden_fechas"),
        CheckConstraint(
            "(salida IS NULL) = (operador_salida_id IS NULL)",
            name="ck_estancia_cierre_completo",
        ),
        # RF-07: la puerta de salida se informa junto con la salida.
        CheckConstraint(
            "(salida IS NULL) = (puerta_salida_id IS NULL)",
            name="ck_estancia_puerta_salida",
        ),
        UniqueConstraint("numero_recibo", name="uq_estancia_numero_recibo"),
        Index("uq_estancia_vehiculo_abierta", "vehiculo_id", unique=True,
              postgresql_where=text("salida IS NULL")),
        # Una estancia abierta por celda. Es diferible para que el intercambio de celdas (RF-09)
        # pueda mover dos registros en la misma transacción; fuera de él se comprueba al instante.
        ExcludeConstraint(("celda_id", "="), name="ex_estancia_celda_abierta", using="btree",
                          where=text("salida IS NULL"), deferrable=True, initially="IMMEDIATE"),
        Index("ix_estancia_vehiculo_entrada", "vehiculo_id", "entrada"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehiculo.id", name="fk_estancia_vehiculo", ondelete="RESTRICT"), nullable=False
    )
    celda_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_estancia_celda", ondelete="RESTRICT"), nullable=False
    )
    entrada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operador_entrada_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_estancia_operador_entrada", ondelete="RESTRICT"), nullable=False
    )
    operador_salida_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_estancia_operador_salida", ondelete="RESTRICT"), nullable=True
    )
    puerta_entrada_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("puerta.id", name="fk_estancia_puerta_entrada", ondelete="RESTRICT"), nullable=False
    )
    puerta_salida_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("puerta.id", name="fk_estancia_puerta_salida", ondelete="RESTRICT"), nullable=True
    )
    # Recibo de ingreso E-000245 (RF-05), derivado del id para que nunca se repita.
    numero_recibo: Mapped[str] = mapped_column(
        Text, Computed("'E-' || lpad(id::text, 6, '0')", persisted=True)
    )

    vehiculo: Mapped[Vehiculo] = relationship()
    celda: Mapped[Celda] = relationship()
    operador_entrada: Mapped[Operador] = relationship(foreign_keys=[operador_entrada_id])
    operador_salida: Mapped[Operador | None] = relationship(foreign_keys=[operador_salida_id])
    puerta_entrada: Mapped[Puerta] = relationship(foreign_keys=[puerta_entrada_id])
    puerta_salida: Mapped[Puerta | None] = relationship(foreign_keys=[puerta_salida_id])
    novedades: Mapped[list["Novedad"]] = relationship(
        back_populates="estancia", order_by="Novedad.fecha", foreign_keys="Novedad.estancia_id"
    )

    def esta_abierta(self) -> bool:
        return self.salida is None

    def cerrar(self, fecha_salida: datetime, operador: Operador, puerta: Puerta) -> None:
        """Valida y asigna el cierre; el servicio debe gestionar flush y commit."""
        if not self.esta_abierta():
            raise ValueError("La estancia ya está cerrada.")
        if not isinstance(fecha_salida, datetime) or fecha_salida.utcoffset() is None:
            raise ValueError("La fecha de salida debe tener zona horaria.")
        if not isinstance(self.entrada, datetime) or self.entrada.utcoffset() is None:
            raise ValueError("La entrada debe estar cargada y tener zona horaria antes de cerrar.")
        if fecha_salida.astimezone(timezone.utc) < self.entrada.astimezone(timezone.utc):
            raise ValueError("La salida no puede ser anterior a la entrada.")
        if not isinstance(operador, Operador) or operador.id is None:
            raise ValueError("El operador de salida debe tener un id asignado.")
        if not isinstance(puerta, Puerta) or puerta.id is None:
            raise ValueError("La puerta de salida debe tener un id asignado.")
        self.salida = fecha_salida
        self.operador_salida = operador
        self.operador_salida_id = operador.id
        self.puerta_salida = puerta
        self.puerta_salida_id = puerta.id


class Novedad(Base):
    """Cambio de celda de un registro abierto (RN-12, RF-09). Nunca se edita ni se borra (RNF-07)."""
    __tablename__ = "novedad"
    __table_args__ = (
        CheckConstraint("celda_anterior_id <> celda_nueva_id", name="ck_novedad_celdas_distintas"),
        CheckConstraint("motivo ~ '[^[:space:]]'", name="ck_novedad_motivo_no_vacio"),
        Index("ix_novedad_estancia", "estancia_id"),
        Index("ix_novedad_fecha", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estancia_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("estancia.id", name="fk_novedad_estancia", ondelete="RESTRICT"), nullable=False
    )
    celda_anterior_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_novedad_celda_anterior", ondelete="RESTRICT"), nullable=False
    )
    celda_nueva_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("celda.id", name="fk_novedad_celda_nueva", ondelete="RESTRICT"), nullable=False
    )
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    operador_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_novedad_operador", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    estancia: Mapped[Estancia] = relationship(back_populates="novedades", foreign_keys=[estancia_id])
    celda_anterior: Mapped[Celda] = relationship(foreign_keys=[celda_anterior_id])
    celda_nueva: Mapped[Celda] = relationship(foreign_keys=[celda_nueva_id])
    operador: Mapped[Operador] = relationship()

    @validates("motivo")
    def validate_motivo(self, key: str, value: str) -> str:
        return required_text(value, "El motivo")


class Sesion(Base):
    """Sesión abierta en un equipo (RF-03). Se guarda solo el hash del token."""
    __tablename__ = "sesion"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sesion_token"),
        # RN-03: un mismo usuario solo puede tener una sesión abierta a la vez.
        Index("uq_sesion_abierta", "operador_id", unique=True, postgresql_where=text("cerrada IS NULL")),
        CheckConstraint("(cerrada IS NULL) = (motivo_cierre IS NULL)", name="ck_sesion_cierre_completo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    operador_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operador.id", name="fk_sesion_operador", ondelete="RESTRICT"), nullable=False
    )
    puerta_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("puerta.id", name="fk_sesion_puerta", ondelete="RESTRICT"), nullable=True
    )
    equipo: Mapped[str | None] = mapped_column(Text, nullable=True)
    iniciada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ultima_actividad: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                       nullable=False)
    cerrada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_cierre: Mapped[str | None] = mapped_column(Text, nullable=True)

    operador: Mapped[Operador] = relationship()
    puerta: Mapped[Puerta | None] = relationship()


class Auditoria(Base):
    """Bitácora de solo lectura (RF-01, RF-02, RF-04, RF-06; RNF-07). Un trigger impide modificar o borrar filas.

    usuario_id no es llave foránea: también se registran intentos de usuarios inexistentes, y el
    nombre de usuario se copia para que la fila se entienda aunque el usuario cambie.
    """
    __tablename__ = "auditoria"
    __table_args__ = (
        CheckConstraint("accion ~ '^[A-Z_]+$'", name="ck_auditoria_accion"),
        Index("ix_auditoria_fecha", "fecha"),
        Index("ix_auditoria_usuario", "usuario_id", "fecha"),
        Index("ix_auditoria_accion", "accion"),
        Index("ix_auditoria_placa", "placa"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    usuario: Mapped[str | None] = mapped_column(Text, nullable=True)
    rol: Mapped[str | None] = mapped_column(Text, nullable=True)
    puerta: Mapped[str | None] = mapped_column(Text, nullable=True)
    equipo: Mapped[str | None] = mapped_column(Text, nullable=True)
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    entidad: Mapped[str | None] = mapped_column(Text, nullable=True)
    entidad_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    placa: Mapped[str | None] = mapped_column(Text, nullable=True)
    detalle: Mapped[str] = mapped_column(Text, nullable=False)
    valor_anterior: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    valor_nuevo: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
