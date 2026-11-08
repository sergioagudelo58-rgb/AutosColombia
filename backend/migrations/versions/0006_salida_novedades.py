"""Salida con puerta, novedades de celda y restricción diferible por celda: RF-07 a RF-09.

Revision ID: 0006
Revises: 0005

- ESTANCIA: la puerta de salida se informa junto con la salida (RF-07). Las estancias ya
  cerradas antes de esta revisión no la guardaban; se asignan a Puerta 1, igual que hizo 0005
  con la puerta de entrada.
- ESTANCIA: el índice único parcial uq_estancia_celda_abierta se reemplaza por la restricción
  de exclusión ex_estancia_celda_abierta (misma regla: una estancia abierta por celda), que es
  DEFERRABLE INITIALLY IMMEDIATE. Se comprueba al instante salvo en el intercambio de celdas,
  que la difiere hasta el commit para mover dos registros a la vez (RF-09).
- NOVEDAD: registro inmutable de cada cambio de celda (RN-12, RNF-07).
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE estancia SET puerta_salida_id = (SELECT id FROM puerta WHERE nombre = 'Puerta 1') "
        "WHERE salida IS NOT NULL AND puerta_salida_id IS NULL"
    )
    op.create_check_constraint("ck_estancia_puerta_salida", "estancia",
                               "(salida IS NULL) = (puerta_salida_id IS NULL)")

    op.drop_index("uq_estancia_celda_abierta", table_name="estancia")
    op.execute(
        "ALTER TABLE estancia ADD CONSTRAINT ex_estancia_celda_abierta "
        "EXCLUDE USING btree (celda_id WITH =) WHERE (salida IS NULL) DEFERRABLE INITIALLY IMMEDIATE"
    )

    op.create_table(
        "novedad",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("estancia_id", sa.BigInteger(), nullable=False),
        sa.Column("celda_anterior_id", sa.BigInteger(), nullable=False),
        sa.Column("celda_nueva_id", sa.BigInteger(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["estancia_id"], ["estancia.id"], name="fk_novedad_estancia", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["celda_anterior_id"], ["celda.id"], name="fk_novedad_celda_anterior",
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["celda_nueva_id"], ["celda.id"], name="fk_novedad_celda_nueva",
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operador_id"], ["operador.id"], name="fk_novedad_operador", ondelete="RESTRICT"),
        sa.CheckConstraint("celda_anterior_id <> celda_nueva_id", name="ck_novedad_celdas_distintas"),
        sa.CheckConstraint("motivo ~ '[^[:space:]]'", name="ck_novedad_motivo_no_vacio"),
    )
    op.create_index("ix_novedad_estancia", "novedad", ["estancia_id"])
    op.create_index("ix_novedad_fecha", "novedad", ["fecha"])


def downgrade() -> None:
    # Reversión deliberada: elimina las novedades registradas.
    op.drop_index("ix_novedad_fecha", table_name="novedad")
    op.drop_index("ix_novedad_estancia", table_name="novedad")
    op.drop_table("novedad")
    op.execute("ALTER TABLE estancia DROP CONSTRAINT ex_estancia_celda_abierta")
    op.create_index("uq_estancia_celda_abierta", "estancia", ["celda_id"], unique=True,
                    postgresql_where=sa.text("salida IS NULL"))
    op.drop_constraint("ck_estancia_puerta_salida", "estancia", type_="check")
