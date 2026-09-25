"""A3.4 — Auditoria de eventos sensibles.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-25

Registro append-only de eventos que afectan credenciales y cuentas: logins,
cambios de contrasena, resets y sus solicitudes.

Decisiones cerradas (A3.4):
* D-Aud-1: se guarda `request.client.host`. OJO — el Dockerfile corre uvicorn
  SIN `--proxy-headers`, asi que detras del proxy de Render esta columna
  guardara la IP DEL PROXY, no la del cliente. Ver deuda IP-real-detras-de-proxy
  antes de sacar conclusiones de este dato.
* D-Aud-2: sin purga. El volumen es nulo y la retencion es decision de negocio.
* Append-only por convencion, no por restriccion de base: hoy nada impide
  UPDATE/DELETE sobre las filas. Ver deuda append-only.
* Solo hacia adelante: no se reconstruye historia previa a esta migracion.

ON DELETE SET NULL en las dos FKs: si se borra un usuario, el rastro se
conserva aunque pierda el actor y el objetivo. Perder el evento seria peor que
perder la referencia.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _tabla_existe(tabla: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return tabla in set(inspector.get_table_names())


def upgrade() -> None:
    if not _tabla_existe("auditoria_evento"):
        op.create_table(
            "auditoria_evento",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("evento", sa.String(length=50), nullable=False),
            sa.Column("usuario_actor_id", sa.Integer(), nullable=True),
            sa.Column("usuario_objetivo_id", sa.Integer(), nullable=True),
            # OJO: en produccion detras de proxy sin --proxy-headers esta
            # columna guarda la IP DEL PROXY. Deuda IP-real-detras-de-proxy.
            sa.Column("ip", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            # Nunca debe contener secretos: tokens, contrasenas ni codigos.
            sa.Column("detalle", JSONB(), nullable=True),
            sa.Column(
                "creado_en",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["usuario_actor_id"], ["usuarios.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["usuario_objetivo_id"], ["usuarios.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    for columna in ("evento", "usuario_actor_id", "usuario_objetivo_id", "creado_en"):
        op.execute(text(
            f"CREATE INDEX IF NOT EXISTS ix_auditoria_evento_{columna} "
            f"ON auditoria_evento ({columna})"
        ))


def downgrade() -> None:
    for columna in ("creado_en", "usuario_objetivo_id", "usuario_actor_id", "evento"):
        op.execute(text(f"DROP INDEX IF EXISTS ix_auditoria_evento_{columna}"))
    if _tabla_existe("auditoria_evento"):
        op.drop_table("auditoria_evento")
