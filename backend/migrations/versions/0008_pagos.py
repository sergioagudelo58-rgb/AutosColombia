"""Iteración 3, gestión de pagos: tabla pago y vencimiento como columna normal (RF-01, RF-02).

Revision ID: 0008
Revises: 0007b

- VEHICULO: fecha_vencimiento deja de calcularse como fecha_pago + 30. Con los pagos, la nueva
  mensualidad se cuenta desde la fecha de corte (RN-06, RN-07, RN-09) y no desde la fecha en que el
  cliente pagó, así que la aplicación la guarda. DROP EXPRESSION conserva los vencimientos actuales.
  Una restricción exige que fecha_pago y fecha_vencimiento se informen juntas.
- PAGO: registro inmutable de cada pago con cliente, vehículo, fecha, valor, medio (banco, efectivo
  o QR), corte anterior, vencimiento nuevo y usuario que lo registró (RNF-03, RNF-04).
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE vehiculo ALTER COLUMN fecha_vencimiento DROP EXPRESSION")
    op.create_check_constraint("ck_vehiculo_mensualidad_completa", "vehiculo",
                               "(fecha_pago IS NULL) = (fecha_vencimiento IS NULL)")

    op.create_table(
        "pago",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("vehiculo_id", sa.BigInteger(), nullable=False),
        sa.Column("cliente_id", sa.BigInteger(), nullable=False),
        sa.Column("fecha_pago", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("medio", sa.Text(), nullable=False),
        sa.Column("vencimiento_anterior", sa.Date(), nullable=True),
        sa.Column("vencimiento_nuevo", sa.Date(), nullable=False),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculo.id"], name="fk_pago_vehiculo", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"], name="fk_pago_cliente", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operador_id"], ["operador.id"], name="fk_pago_operador", ondelete="RESTRICT"),
        sa.CheckConstraint("valor > 0", name="ck_pago_valor_positivo"),
        sa.CheckConstraint("medio IN ('BANCO', 'EFECTIVO', 'QR')", name="ck_pago_medio"),
        sa.CheckConstraint("vencimiento_nuevo = COALESCE(vencimiento_anterior, fecha_pago) + 30",
                           name="ck_pago_vencimiento_30_dias"),
    )
    op.create_index("ix_pago_vehiculo", "pago", ["vehiculo_id", "registrado_en"])
    op.create_index("ix_pago_cliente", "pago", ["cliente_id"])


def downgrade() -> None:
    # Reversión deliberada: elimina los pagos y vuelve a calcular el vencimiento como fecha_pago + 30,
    # con lo que se pierden los días que los pagos sumaron desde la fecha de corte.
    op.drop_index("ix_pago_cliente", table_name="pago")
    op.drop_index("ix_pago_vehiculo", table_name="pago")
    op.drop_table("pago")
    op.drop_constraint("ck_vehiculo_mensualidad_completa", "vehiculo", type_="check")
    op.drop_column("vehiculo", "fecha_vencimiento")
    op.add_column("vehiculo", sa.Column("fecha_vencimiento", sa.Date(),
                                        sa.Computed("fecha_pago + 30", persisted=True)))
