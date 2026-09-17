"""Migración: permite borradores de gasto con valor_total = 0.

El OCR crea gastos en estado 'pendiente' cuando no logra leer el monto; hasta que
el usuario complete la captura manual el valor es 0. El constraint original
`gastos_valor_total_check` exigía `> 0` y rompía ese flujo.
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import engine

CONSTRAINT_NAME = "ck_gastos_valor_total_no_negativo"
CHECK_SQL = "valor_total >= 0"
LEGACY_CONSTRAINTS = ("gastos_valor_total_check", CONSTRAINT_NAME)


def main():
    print("=== Migracion: constraint de valor_total en tabla 'gastos' ===")
    print(f"Regla objetivo: {CHECK_SQL}")

    with engine.begin() as conn:
        legacy = [
            row[0]
            for row in conn.execute(
                text(
                    """
                    select con.conname
                    from pg_constraint con
                    join pg_class rel on rel.oid = con.conrelid
                    where rel.relname = 'gastos' and con.contype = 'c'
                      and con.conname in ('gastos_valor_total_check', 'ck_gastos_valor_total_no_negativo')
                    """
                )
            ).fetchall()
        ]

        for name in legacy:
            conn.execute(text(f'ALTER TABLE gastos DROP CONSTRAINT IF EXISTS "{name}"'))
            print(f"  constraint eliminado: {name}")

        conn.execute(
            text(f'ALTER TABLE gastos ADD CONSTRAINT "{CONSTRAINT_NAME}" CHECK ({CHECK_SQL})')
        )
        print(f"  constraint creado: {CONSTRAINT_NAME} -> {CHECK_SQL}")

        rows = conn.execute(
            text(
                """
                select con.conname, pg_get_constraintdef(con.oid)
                from pg_constraint con
                join pg_class rel on rel.oid = con.conrelid
                where rel.relname = 'gastos' and con.contype = 'c'
                order by con.conname
                """
            )
        ).fetchall()
        for name, definition in rows:
            print(f"  verificacion: {name}: {definition}")

    print("[OK] Constraint de valor_total migrado.")


if __name__ == "__main__":
    main()
