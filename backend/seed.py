"""Wrapper local de seeds de CELR v6.

Ejecuta el seed base y, únicamente con opt-in local explícito, el seed demo.
No contiene lógica de upsert propia. En producción se debe usar directamente
``python seed_base.py``.
"""
from __future__ import annotations

import sys

from app.core.config import settings
from app.db.session import SessionLocal
from seed_base import ejecutar_seed_base
from seed_demo import (
    ALLOW_DEMO_ENV,
    SeedDemoError,
    demo_habilitado,
    ejecutar_seed_demo,
)


def _correr_base():
    db = SessionLocal()
    try:
        resultado = ejecutar_seed_base(db)
        db.commit()
        return resultado
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _correr_demo():
    db = SessionLocal()
    try:
        resultado = ejecutar_seed_demo(db)
        db.commit()
        return resultado
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    try:
        base = _correr_base()
    except Exception as exc:
        print(f"ERROR durante el seed base: {exc}", file=sys.stderr)
        return 1

    if base.admin.estado == "omitido":
        print(
            "[WARN] Bootstrap admin omitido: no se proporcionaron "
            "CELR_BOOTSTRAP_ADMIN_EMAIL y CELR_BOOTSTRAP_ADMIN_PASSWORD"
        )
    else:
        print(f"[OK] Bootstrap admin: {base.admin.estado}")
    print(
        "[OK] Municipios: "
        f"fuente={base.municipios.total_fuente} "
        f"insertados={base.municipios.insertados} "
        f"actualizados={base.municipios.actualizados}"
    )

    if settings.ENVIRONMENT.strip().lower() == "production":
        print(
            "[ERROR] Seed demo bloqueado: ENVIRONMENT=production; "
            "para producción usa directamente seed_base.py",
            file=sys.stderr,
        )
        return 1

    if not demo_habilitado():
        print(
            f"[WARN] Seed demo omitido: se requiere {ALLOW_DEMO_ENV}=1 "
            "para habilitar fixtures locales"
        )
        print("--- SEED BASE COMPLETADO CON EXITO ---")
        return 0

    try:
        demo = _correr_demo()
    except SeedDemoError as exc:
        print(f"ERROR durante el seed demo: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR durante el seed demo: {exc}", file=sys.stderr)
        return 1

    print(
        "[OK] Seed demo: "
        f"admin={demo.admin_estado} "
        f"conductor={demo.conductor_estado} "
        f"vehiculo={demo.vehiculo_estado} "
        f"proveedor={demo.proveedor_estado} "
        f"asignacion={demo.asignacion_estado}"
    )
    print("--- SEED LOCAL COMPLETADO CON EXITO ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
