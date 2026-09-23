"""B2 — Cierre mensual COMPENSADO_RC en liquidaciones_conductores.

Revision ID: f2e1d0c9b8a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-23

Cambios de esquema (todo en espanol):
* liquidaciones_conductores:
  - es_cierre_mensual BOOLEAN (B2): distingue el corte mensual consolidado de
    la liquidacion individual por ODT.
  - periodo_ym VARCHAR(7): clave de periodo normalizada 'YYYY-MM', COLUMNA
    GENERADA persisted = to_char(periodo_inicio, 'YYYY-MM') -> sin backfill
    manual, sin server_default '' ni CHECK de formato (PG la deriva siempre).
  - vehiculo_id pasa a NULLABLE: en el cierre mensual el vehiculo vive en cada
    ODT; la liquidacion del mes no necesita uno propio.
  - UNIQUE parcial: ux_liquidaciones_mes_cierre sobre (conductor_id, periodo_ym)
    WHERE es_cierre_mensual AND eliminado_en IS NULL -> un solo cierre mensual
    por conductor+mes (NULLs y borrados no colisionan).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "f2e1d0c9b8a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # B2: bandera de corte mensual (default falso -> no altera liquidaciones previas)
    op.add_column("liquidaciones_conductores",
                  sa.Column("es_cierre_mensual", sa.Boolean(),
                            nullable=False, server_default="false"))
    # B2: clave de periodo normalizada derivada (persisted), sin backfill manual.
    # Ojo: la expresion debe ser INMUTABLE (PG lo exige en GENERATED ... STORED);
    # to_char() es estable (depende del locale), asi que se usa EXTRACT+LPAD.
    expr_ym = ("lpad(extract(year from periodo_inicio)::int::text, 4, '0')"
               " || '-' || lpad(extract(month from periodo_inicio)::int::text, 2, '0')")
    op.add_column("liquidaciones_conductores",
                  sa.Column("periodo_ym", sa.String(7),
                            sa.Computed(expr_ym, persisted=True)))
    # B2: el cierre mensual no esta atado a un vehiculo (vive en cada ODT)
    op.alter_column("liquidaciones_conductores", "vehiculo_id",
                    existing_type=sa.Integer(), nullable=True)

    # B2: un solo cierre mensual por conductor+mes (NULLs y borrados no colisionan)
    op.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_liquidaciones_mes_cierre
        ON liquidaciones_conductores (conductor_id, periodo_ym)
        WHERE es_cierre_mensual AND eliminado_en IS NULL
    """))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ux_liquidaciones_mes_cierre"))
    # NOTA: el DROP NOT NULL de vehiculo_id solo restaura si no existen cierres
    # mensuales con vehiculo_id NULL (esa condicion la garantiza el negocio).
    op.alter_column("liquidaciones_conductores", "vehiculo_id",
                    existing_type=sa.Integer(), nullable=False)
    op.drop_column("liquidaciones_conductores", "periodo_ym")
    op.drop_column("liquidaciones_conductores", "es_cierre_mensual")