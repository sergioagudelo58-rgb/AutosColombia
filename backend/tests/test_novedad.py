"""Modelo Novedad y revisión 0006 sin conectar a PostgreSQL (RF-07, RF-09)."""
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ExcludeConstraint

from app.models import Estancia, Novedad


def test_novedad_exige_motivo_y_conserva_historial():
    assert Novedad(motivo="  El conductor parqueó en la 30 ").motivo == "El conductor parqueó en la 30"
    with pytest.raises(ValueError, match="motivo"):
        Novedad(motivo="   ")
    table = Novedad.__table__
    assert not {c.name for c in table.c if c.nullable}
    assert len(table.foreign_keys) == 4 and all(fk.ondelete == "RESTRICT" for fk in table.foreign_keys)
    checks = {c.name for c in table.constraints if isinstance(c, sa.CheckConstraint)}
    assert {"ck_novedad_celdas_distintas", "ck_novedad_motivo_no_vacio"} <= checks
    assert not sa.inspect(Estancia).relationships.novedades.cascade.delete


def test_una_estancia_abierta_por_celda_es_diferible():
    exclusion = next(c for c in Estancia.__table__.constraints if isinstance(c, ExcludeConstraint))
    assert exclusion.name == "ex_estancia_celda_abierta"
    assert exclusion.deferrable and exclusion.initially == "IMMEDIATE"
    assert "uq_estancia_celda_abierta" not in {i.name for i in Estancia.__table__.indexes}


def test_alembic_offline_0006():
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "0005:0006", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE novedad" in sql
    assert "CHECK ((salida IS NULL) = (puerta_salida_id IS NULL))" in sql
    assert "DROP INDEX uq_estancia_celda_abierta" in sql
    assert ("EXCLUDE USING btree (celda_id WITH =) WHERE (salida IS NULL) DEFERRABLE INITIALLY IMMEDIATE"
            in sql)
    assert sql.count("ON DELETE RESTRICT") == 4
    assert "DROP TABLE" not in sql
