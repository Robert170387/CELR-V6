import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import engine
from app.core.roles import ROLES_VALIDOS, SQL_CHECK_ROL

CONSTRAINT_NAME = "ck_usuarios_rol_valido"
LEGACY_CONSTRAINTS = ("usuarios_rol_check", CONSTRAINT_NAME)


def main():
    print("=== Migracion: constraint de roles en tabla 'usuarios' ===")
    print(f"Roles objetivo: {ROLES_VALIDOS}")

    with engine.begin() as conn:
        legacy = [
            row[0]
            for row in conn.execute(
                text(
                    """
                    select con.conname
                    from pg_constraint con
                    join pg_class rel on rel.oid = con.conrelid
                    where rel.relname = 'usuarios' and con.contype = 'c'
                      and con.conname in ('usuarios_rol_check', 'ck_usuarios_rol_valido')
                    """
                )
            ).fetchall()
        ]

        for name in legacy:
            conn.execute(text(f'ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS "{name}"'))
            print(f"  constraint eliminado: {name}")

        conn.execute(
            text(f'ALTER TABLE usuarios ADD CONSTRAINT "{CONSTRAINT_NAME}" CHECK ({SQL_CHECK_ROL})')
        )
        print(f"  constraint creado: {CONSTRAINT_NAME} -> {SQL_CHECK_ROL}")

        rows = conn.execute(
            text(
                """
                select pg_get_constraintdef(con.oid)
                from pg_constraint con
                join pg_class rel on rel.oid = con.conrelid
                where rel.relname = 'usuarios' and con.contype = 'c'
                """
            )
        ).fetchall()
        for r in rows:
            print(f"  verificacion: {r[0]}")

    print("[OK] Constraint de roles migrado.")


if __name__ == "__main__":
    main()
