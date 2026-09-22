"""baseline v6

Crea todo el esquema a partir de los modelos (app/models).
- En una base vacía (deploy nuevo) construye todas las tablas.
- En la base existente es no-op: create_all no altera lo que ya existe;
  previamente docker-compose corria init_db.py + scripts/migrate_v6_hardening.py,
  por lo que el estado real de la base es la fuente de verdad hasta aqui.
Siguientes cambios de esquema se hacen con migraciones normales.

Revision ID: a5b6b344c873
Revises: 
Create Date: 2026-09-17 02:44:49.756114

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a5b6b344c873'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from app.db.base_class import Base
    import app.models  # noqa: F401  (asegura que todos los modelos esten registrados)

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Downgrade schema."""
    pass
