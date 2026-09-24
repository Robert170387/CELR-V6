"""FASE 2 — Preserva la fila original del Excel de Flypass.

Revision ID: c3d4e5f6a7b8
Revises: f2e1d0c9b8a7
Create Date: 2026-09-23

Añade una columna JSONB nullable para conservar la fila original importada,
sin backfill ni cambios en los registros existentes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "f2e1d0c9b8a7"
branch_labels = None
depends_on = None


def _columna_existe(tabla: str, columna: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return columna in [item["name"] for item in inspector.get_columns(tabla)]


def upgrade() -> None:
    if not _columna_existe("flypass_transacciones", "raw_data"):
        op.add_column(
            "flypass_transacciones",
            sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        )


def downgrade() -> None:
    if _columna_existe("flypass_transacciones", "raw_data"):
        op.drop_column("flypass_transacciones", "raw_data")
