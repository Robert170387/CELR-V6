"""A1 — Identidad canonica en usuarios: cedula, correo nullable y 1:1 conductor.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-25

Decisiones cerradas (A0.1, cf55684):
* No hay personas juridicas -> no se agrega identificador_fiscal.
* No todos los usuarios son conductores -> la cedula vive en usuarios, no se
  deduce de la tabla conductores.
* Una persona = una cuenta -> unicidad real, no "un conductor puede tener
  varias cuentas".

Cambios de esquema (todo en espanol, guards idempotentes):
* usuarios.cedula VARCHAR(20) NULL + UNIQUE parcial ux_usuarios_cedula
  (cedula IS NOT NULL): la identidad es canonica y no todas las cuentas la
  tienen todavia (sin backfill).
* usuarios.correo -> DROP NOT NULL: la cedula es la identidad primaria en el
  modelo; el correo pasa a ser atributo opcional. El UNIQUE parcial existente
  (ix_usuarios_correo) ya admite varios NULL.
* usuarios.conductor_id: se reemplaza el indice normal ix_usuarios_conductor_id
  (redundante, solo aided lookups) por UNIQUE parcial ux_usuarios_conductor_id
  (conductor_id IS NOT NULL): un conductor no puede quedar ligado a dos cuentas.

El downgrade protege el retorno de correo a NOT NULL: si existen usuarios con
correo NULL, aborta en vez de perder datos.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def _columna_existe(tabla: str, columna: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return columna in {item["name"] for item in inspector.get_columns(tabla)}


def _columna_es_nullable(tabla: str, columna: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    for item in inspector.get_columns(tabla):
        if item["name"] == columna:
            return item["nullable"]
    return False


def _indice_existe(tabla: str, indice: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return indice in {item["name"] for item in inspector.get_indexes(tabla)}


def upgrade() -> None:
    # 1. Identidad canonica opcional (sin backfill: los usuarios actuales quedan en NULL).
    if not _columna_existe("usuarios", "cedula"):
        op.add_column("usuarios",
                      sa.Column("cedula", sa.String(20), nullable=True))

    # 2. Unicidad de la cedula entre las cuentas que si la tienen.
    op.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_cedula
        ON usuarios (cedula) WHERE cedula IS NOT NULL
    """))

    # 3. El correo deja de ser obligatorio (la cedula es la identidad primaria).
    if not _columna_es_nullable("usuarios", "correo"):
        op.alter_column("usuarios", "correo",
                        existing_type=sa.String(100), nullable=True)

    # 4. Un conductor no puede quedar ligado a dos cuentas.
    if _indice_existe("usuarios", "ix_usuarios_conductor_id"):
        op.drop_index("ix_usuarios_conductor_id", table_name="usuarios")
    op.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_conductor_id
        ON usuarios (conductor_id) WHERE conductor_id IS NOT NULL
    """))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ux_usuarios_conductor_id"))
    if not _indice_existe("usuarios", "ix_usuarios_conductor_id"):
        op.create_index("ix_usuarios_conductor_id", "usuarios", ["conductor_id"])

    # Guard de seguridad: volver correo a NOT NULL perderia datos si hay cuentas
    # sin correo (identificadas solo por cedula). Se aborta con un mensaje claro.
    nulos = op.get_bind().execute(
        text("SELECT count(*) FROM usuarios WHERE correo IS NULL")
    ).scalar() or 0
    if nulos > 0:
        raise RuntimeError(
            f"No se puede revertir: {nulos} usuario(s) con correo NULL. "
            f"Complete el correo antes de hacer downgrade."
        )
    if _columna_es_nullable("usuarios", "correo"):
        op.alter_column("usuarios", "correo",
                        existing_type=sa.String(100), nullable=False)

    op.execute(text("DROP INDEX IF EXISTS ux_usuarios_cedula"))
    if _columna_existe("usuarios", "cedula"):
        op.drop_column("usuarios", "cedula")
