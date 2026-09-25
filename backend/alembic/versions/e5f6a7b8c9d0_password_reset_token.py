"""A3.1 — Tokens de reset de contrasena (enlace y codigo offline).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-25

Una sola tabla para los dos modos de entrega:
* 'enlace' — secreto de 64 bytes, se manda por email, TTL en horas.
* 'codigo' — 6 digitos leidos en voz alta (offline), TTL corto y con limite
  de intentos porque el espacio de busqueda es bruteforceable (10^6).

Se dimensiona asi desde el arranque para que el flujo de codigo (A3.3) no
requiera una migracion posterior sobre una tabla ya creada.

Patron de copia: refresh_tokens (usuarios de la sesion) — token_hash SHA-256,
expira_en, revocado, usado_en. La diferencia es `tipo`, `intentos` e
`intentos_max`, que son los que hacen falta para el modo 'codigo'.

La FK a usuarios es ON DELETE CASCADE: los tokens de reset no sobreviven a la
cuenta que los genero.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def _tabla_existe(tabla: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return tabla in set(inspector.get_table_names())


def upgrade() -> None:
    # Guard obligatorio: el baseline a5b6b344c873 es dinamico (create_all sobre
    # los modelos actuales), asi que en una BD limpia esta tabla YA existe y el
    # create_table debe saltarsela.
    if not _tabla_existe("password_reset_token"):
        op.create_table(
            "password_reset_token",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("tipo", sa.String(length=20), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
            sa.Column("usado_en", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revocado", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("intentos_max", sa.Integer(), nullable=False, server_default="5"),
            sa.Column(
                "creado_en",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "tipo IN ('enlace', 'codigo')", name="ck_password_reset_tipo_valido"
            ),
            sa.CheckConstraint(
                "intentos >= 0", name="ck_password_reset_intentos_no_negativo"
            ),
            sa.ForeignKeyConstraint(
                ["usuario_id"], ["usuarios.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    # Los indices se crean aparte (y no via unique/index en create_table) para
    # que queden con el MISMO nombre que genera el modelo, igual que
    # ix_usuarios_correo: un UNIQUE index, no una constraint.
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_password_reset_token_usuario_id
        ON password_reset_token (usuario_id)
    """))
    op.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_token_token_hash
        ON password_reset_token (token_hash)
    """))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_password_reset_token_token_hash"))
    op.execute(text("DROP INDEX IF EXISTS ix_password_reset_token_usuario_id"))
    if _tabla_existe("password_reset_token"):
        op.drop_table("password_reset_token")
