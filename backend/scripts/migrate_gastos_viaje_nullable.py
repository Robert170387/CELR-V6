"""Migración: permisos de gastos sin ODT (Fijos / Mantenimiento).

Antes: todo gasto exigía un viaje_id NOT NULL. Con esta migración el vínculo
pasa a ser opcional para soportar "Gastos Fijos / Mantenimiento de Vehículo"
(cambio de aceite, llantas, parqueadero) que no están atados a una ODT.
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import engine


def main():
    print("=== Migracion: gastos.viaje_id pasa a ser opcional ===")

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                select a.attnotnull
                from pg_attribute a
                join pg_class rel on rel.oid = a.attrelid
                where rel.relname = 'gastos' and a.attname = 'viaje_id'
                """
            )
        ).fetchone()

        if row is None:
            print("  tabla 'gastos' sin columna viaje_id - nada que hacer")
            return

        if not row[0]:
            print("  viaje_id ya admite NULL - sin cambios")
            return

        conn.execute(text("ALTER TABLE gastos ALTER COLUMN viaje_id DROP NOT NULL"))
        print("  viaje_id: DROP NOT NULL aplicado")

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                select a.attnotnull
                from pg_attribute a
                join pg_class rel on rel.oid = a.attrelid
                where rel.relname = 'gastos' and a.attname = 'viaje_id'
                """
            )
        ).fetchone()
        print(f"  verificacion: viaje_id nullable={not row[0]}")

    print("[OK] Gasto sin ODT habilitado (gasto fijo / mantenimiento).")


if __name__ == "__main__":
    main()