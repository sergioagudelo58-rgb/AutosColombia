"""Estado de la celda: inhabilitar, habilitar y eliminar con borrado lógico (RF-14, RF-15).

Revision ID: 0007
Revises: 0006

- CELDA: agrega estado (ACTIVA, INHABILITADA o ELIMINADA), motivo del último cambio de estado
  y fecha de ese cambio. Las celdas existentes quedan ACTIVA. "Ocupada" no se guarda: se deduce
  de que la celda tenga una estancia abierta.
- Una celda que no está ACTIVA siempre guarda el motivo (RNF-11).
- El código sigue siendo único: una celda eliminada conserva el suyo para no confundir el historial.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("celda", sa.Column("estado", sa.Text(), server_default=sa.text("'ACTIVA'"), nullable=False))
    op.add_column("celda", sa.Column("motivo_estado", sa.Text(), nullable=True))
    op.add_column("celda", sa.Column("fecha_estado", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_celda_estado", "celda", "estado IN ('ACTIVA', 'INHABILITADA', 'ELIMINADA')")
    op.create_check_constraint("ck_celda_motivo_no_vacio", "celda",
                               "motivo_estado IS NULL OR motivo_estado ~ '[^[:space:]]'")
    op.create_check_constraint("ck_celda_motivo_requerido", "celda",
                               "estado = 'ACTIVA' OR motivo_estado IS NOT NULL")


def downgrade() -> None:
    # Reversión deliberada: se pierde el estado; las celdas eliminadas lógicamente reaparecerían como activas.
    op.drop_constraint("ck_celda_motivo_requerido", "celda", type_="check")
    op.drop_constraint("ck_celda_motivo_no_vacio", "celda", type_="check")
    op.drop_constraint("ck_celda_estado", "celda", type_="check")
    op.drop_column("celda", "fecha_estado")
    op.drop_column("celda", "motivo_estado")
    op.drop_column("celda", "estado")