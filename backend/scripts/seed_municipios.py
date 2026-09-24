"""Wrapper compatible del seed idempotente del catálogo DIVIPOLA.

La sincronización canónica vive en ``backend/seed_base.py`` y no hace commit.
Este entrypoint conserva el contrato histórico: al ejecutarse directamente,
la transacción es de este wrapper y se confirma al finalizar.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from seed_base import DATA_PATH, sincronizar_municipios
from app.db.session import SessionLocal


# Se mantiene el nombre público histórico para callers existentes.
def seed_municipios(db, data_path=DATA_PATH) -> tuple:
    resultado = sincronizar_municipios(db, data_path=data_path)
    db.commit()
    return resultado.insertados, resultado.total_fuente


def main() -> int:
    db = SessionLocal()
    try:
        insertados, total_fuente = seed_municipios(db)
        print(f"Municipios en fuente: {total_fuente} | Insertados: {insertados}")
        print("[OK] Seed de municipios finalizado")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR durante el seed de municipios: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
