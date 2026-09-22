"""Migración consolidada del endurecimiento v6 (idempotente).

Agrupa los cambios de esquema de los bloques de endurecimiento:
  - Bloque 2  : tabla refresh_tokens + usuarios.debe_cambiar_contrasena
  - Bloque 4  : conductores.porcentaje_comision_default
  - Bloque 5  : soft delete contable (eliminado_en / eliminado_por)
  - Bloque 8  : liquidaciones.fecha_aprobacion / aprobado_por (si aplica)

Se puede ejecutar varias veces: cada sección comprueba existencia previa.
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import engine


def _columna_existe(conn, tabla: str, columna: str) -> bool:
    row = conn.execute(
        text(
            """
            select a.attname
            from pg_attribute a
            join pg_class rel on rel.oid = a.attrelid
            where rel.relname = :tabla and a.attname = :columna
            """
        ),
        {"tabla": tabla, "columna": columna},
    ).fetchone()
    return row is not None


def _tabla_existe(conn, tabla: str) -> bool:
    row = conn.execute(
        text(
            "select to_regclass(:tabla) "
        ),
        {"tabla": tabla},
    ).fetchone()
    return row is not None and row[0] is not None


def _bloque_refresh_tokens(conn):
    print("=== Bloque 2: refresh_tokens + debe_cambiar_contrasena ===")
    with conn.begin():
        if not _tabla_existe(conn, "refresh_tokens"):
            conn.execute(
                text(
                    """
                    CREATE TABLE refresh_tokens (
                        id          SERIAL PRIMARY KEY,
                        usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
                        token_hash  VARCHAR(64) NOT NULL UNIQUE,
                        expira_en   TIMESTAMPTZ NOT NULL,
                        revocado    BOOLEAN NOT NULL DEFAULT FALSE,
                        creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
                        usado_en    TIMESTAMPTZ
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_refresh_tokens_usuario_id ON refresh_tokens(usuario_id)"))
            print("  refresh_tokens creada")
        else:
            print("  refresh_tokens ya existe")

        if not _columna_existe(conn, "usuarios", "debe_cambiar_contrasena"):
            conn.execute(
                text(
                    "ALTER TABLE usuarios ADD COLUMN debe_cambiar_contrasena BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            print("  usuarios.debe_cambiar_contrasena añadida")
        else:
            print("  usuarios.debe_cambiar_contrasena ya existe")


def _bloque_comision_default(conn):
    print("=== Bloque 4: conductores.porcentaje_comision_default ===")
    with conn.begin():
        if not _columna_existe(conn, "conductores", "porcentaje_comision_default"):
            conn.execute(
                text(
                    "ALTER TABLE conductores ADD COLUMN porcentaje_comision_default NUMERIC(5,2)"
                )
            )
            print("  conductores.porcentaje_comision_default añadida")
        else:
            print("  conductores.porcentaje_comision_default ya existe")


def _bloque_soft_delete(conn):
    print("=== Bloque 5: soft delete contable ===")
    tabla_soft = {
        "gastos": "gastos",
        "ingresos": "ingresos",
        "viajes_odt": "viajes_odt",
        "liquidaciones_conductores": "liquidaciones_conductores",
    }
    with conn.begin():
        for tabla in tabla_soft:
            if not _columna_existe(conn, tabla, "eliminado_en"):
                conn.execute(
                    text(
                        f"ALTER TABLE {tabla} ADD COLUMN eliminado_en TIMESTAMPTZ"
                    )
                )
                print(f"  {tabla}.eliminado_en añadida")
            if not _columna_existe(conn, tabla, "eliminado_por"):
                conn.execute(
                    text(
                        f"ALTER TABLE {tabla} ADD COLUMN eliminado_por INTEGER REFERENCES usuarios(id)"
                    )
                )
                print(f"  {tabla}.eliminado_por añadida")


def main():
    with engine.connect() as conn:
        _bloque_refresh_tokens(conn)
        _bloque_comision_default(conn)
        _bloque_soft_delete(conn)
    print("[OK] Migración de endurecimiento v6 completada.")


if __name__ == "__main__":
    main()