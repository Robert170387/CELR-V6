"""R1-pre-1 — Índice en flypass_transacciones(viaje_id).

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-25

La tabla `flypass_transacciones` NO tenía índice sobre `viaje_id`, mientras
`gastos` (`ix_gastos_viaje_id`) e `ingresos` (`ix_ingresos_viaje_id`) sí lo
tienen. La incoherencia es invisible hasta que alguien consulta peajes por
viaje: es la tercera lista 1:N del resumen de viaje (R1) y sin índice cada
llamada es un seq scan sobre la tabla completa.

No cambia el modelo ni los datos: es puramente un índice. Es idempotente por
guard, como toda migración del proyecto — la baseline ejecuta `create_all`
con los modelos vigentes, así que una BD "vacía" y una ya migrada arrancan en
estados distintos y la misma migración puede fallar en una y no en la otra.
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

INDICE = "ix_flypass_transacciones_viaje_id"
TABLA = "flypass_transacciones"
COLUMNA = "viaje_id"


def _indice_existe(tabla: str, indice: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return indice in [item["name"] for item in inspector.get_indexes(tabla)]


def _columna_existe(tabla: str, columna: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return columna in [item["name"] for item in inspector.get_columns(tabla)]


def upgrade() -> None:
    # Guarda también por columna: si alguien aplicó el índice a mano con otro
    # nombre, esta migración no debe reventar ni duplicar el trabajo.
    if not _columna_existe(TABLA, COLUMNA):
        return
    if _indice_existe(TABLA, INDICE):
        return
    op.create_index(INDICE, TABLA, [COLUMNA], unique=False)


def downgrade() -> None:
    if _indice_existe(TABLA, INDICE):
        op.drop_index(INDICE, table_name=TABLA)
