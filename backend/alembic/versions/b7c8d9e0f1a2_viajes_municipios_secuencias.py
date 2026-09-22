"""viajes municipios secuencias

- Tabla municipios (catalogo DIVIPOLA de departamentos/municipios).
- Tabla secuencias_documento (consecutivos atomicos, ej. numero_odt).
- Columnas FK *_municipio_id en viajes_odt, gastos, proveedores y
  flypass_transacciones hacia municipios.id.

Revision ID: b7c8d9e0f1a2
Revises: a5b6b344c873
Create Date: 2026-09-17 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a5b6b344c873'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabla_existe(inspector, nombre: str) -> bool:
    return nombre in inspector.get_table_names()


def _columna_existe(inspector, tabla: str, columna: str) -> bool:
    return columna in [c["name"] for c in inspector.get_columns(tabla)]


def _indice_existe(inspector, tabla: str, indice: str) -> bool:
    return indice in [ix["name"] for ix in inspector.get_indexes(tabla)]


def upgrade() -> None:
    """Upgrade schema.

    Idempotente: el baseline a5b6b344c873 (create_all de los modelos) ya crea
    municipios, secuencias_documento y las columnas FK cuando los modelos los
    incluyen, por lo que en bases nuevas todo esto ya existe. Los guards evitan
    DuplicateTable/duplicate column en bases frescas sin romper bases previas.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _tabla_existe(inspector, "municipios"):
        op.create_table(
            "municipios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("codigo_dane", sa.String(10), nullable=False, unique=True),
            sa.Column("departamento", sa.String(80), nullable=False),
            sa.Column("municipio", sa.String(80), nullable=False),
        )
        op.create_index("ix_municipios_departamento", "municipios", ["departamento"])
        op.create_index("ix_municipios_departamento_municipio", "municipios", ["departamento", "municipio"])

    if not _tabla_existe(inspector, "secuencias_documento"):
        op.create_table(
            "secuencias_documento",
            sa.Column("clave", sa.String(50), primary_key=True),
            sa.Column("valor", sa.Integer(), nullable=False, server_default="0"),
        )

    if not _columna_existe(inspector, "viajes_odt", "origen_municipio_id"):
        op.add_column(
            "viajes_odt",
            sa.Column("origen_municipio_id", sa.Integer(), sa.ForeignKey("municipios.id"), nullable=True),
        )
    if not _columna_existe(inspector, "viajes_odt", "destino_municipio_id"):
        op.add_column(
            "viajes_odt",
            sa.Column("destino_municipio_id", sa.Integer(), sa.ForeignKey("municipios.id"), nullable=True),
        )
    if not _columna_existe(inspector, "gastos", "ciudad_abastecimiento_municipio_id"):
        op.add_column(
            "gastos",
            sa.Column("ciudad_abastecimiento_municipio_id", sa.Integer(), sa.ForeignKey("municipios.id"), nullable=True),
        )
    if not _columna_existe(inspector, "proveedores", "ciudad_municipio_id"):
        op.add_column(
            "proveedores",
            sa.Column("ciudad_municipio_id", sa.Integer(), sa.ForeignKey("municipios.id"), nullable=True),
        )
    if not _columna_existe(inspector, "flypass_transacciones", "ciudad_peaje_municipio_id"):
        op.add_column(
            "flypass_transacciones",
            sa.Column("ciudad_peaje_municipio_id", sa.Integer(), sa.ForeignKey("municipios.id"), nullable=True),
        )

    if not _indice_existe(inspector, "viajes_odt", "ix_viajes_odt_origen_municipio_id"):
        op.create_index("ix_viajes_odt_origen_municipio_id", "viajes_odt", ["origen_municipio_id"])
    if not _indice_existe(inspector, "viajes_odt", "ix_viajes_odt_destino_municipio_id"):
        op.create_index("ix_viajes_odt_destino_municipio_id", "viajes_odt", ["destino_municipio_id"])
    if not _indice_existe(inspector, "gastos", "ix_gastos_ciudad_abastecimiento_municipio_id"):
        op.create_index("ix_gastos_ciudad_abastecimiento_municipio_id", "gastos", ["ciudad_abastecimiento_municipio_id"])
    if not _indice_existe(inspector, "proveedores", "ix_proveedores_ciudad_municipio_id"):
        op.create_index("ix_proveedores_ciudad_municipio_id", "proveedores", ["ciudad_municipio_id"])
    if not _indice_existe(inspector, "flypass_transacciones", "ix_flypass_transacciones_ciudad_peaje_municipio_id"):
        op.create_index("ix_flypass_transacciones_ciudad_peaje_municipio_id", "flypass_transacciones", ["ciudad_peaje_municipio_id"])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _indice_existe(inspector, "flypass_transacciones", "ix_flypass_transacciones_ciudad_peaje_municipio_id"):
        op.drop_index("ix_flypass_transacciones_ciudad_peaje_municipio_id", table_name="flypass_transacciones")
    if _indice_existe(inspector, "proveedores", "ix_proveedores_ciudad_municipio_id"):
        op.drop_index("ix_proveedores_ciudad_municipio_id", table_name="proveedores")
    if _indice_existe(inspector, "gastos", "ix_gastos_ciudad_abastecimiento_municipio_id"):
        op.drop_index("ix_gastos_ciudad_abastecimiento_municipio_id", table_name="gastos")
    if _indice_existe(inspector, "viajes_odt", "ix_viajes_odt_destino_municipio_id"):
        op.drop_index("ix_viajes_odt_destino_municipio_id", table_name="viajes_odt")
    if _indice_existe(inspector, "viajes_odt", "ix_viajes_odt_origen_municipio_id"):
        op.drop_index("ix_viajes_odt_origen_municipio_id", table_name="viajes_odt")

    if _columna_existe(inspector, "flypass_transacciones", "ciudad_peaje_municipio_id"):
        op.drop_column("flypass_transacciones", "ciudad_peaje_municipio_id")
    if _columna_existe(inspector, "proveedores", "ciudad_municipio_id"):
        op.drop_column("proveedores", "ciudad_municipio_id")
    if _columna_existe(inspector, "gastos", "ciudad_abastecimiento_municipio_id"):
        op.drop_column("gastos", "ciudad_abastecimiento_municipio_id")
    if _columna_existe(inspector, "viajes_odt", "destino_municipio_id"):
        op.drop_column("viajes_odt", "destino_municipio_id")
    if _columna_existe(inspector, "viajes_odt", "origen_municipio_id"):
        op.drop_column("viajes_odt", "origen_municipio_id")

    if _tabla_existe(inspector, "secuencias_documento"):
        op.drop_table("secuencias_documento")
    if _tabla_existe(inspector, "municipios"):
        op.drop_table("municipios")