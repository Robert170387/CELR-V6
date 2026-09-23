"""Prueba de humo CELR v6 - verifica en segundos que el stack esta operativo.

Read-only: NO crea registros persistentes. El unico efecto es un login de prueba
(test@celr.com) que genera un par de tokens de sesion; el refresh token creado se
elimina al final y `ultimo_acceso` del admin se restaura a su valor previo, de modo
que la BD queda exactamente igual antes/despues (patron de limpieza de 2.B).

Verifica:
  1. Conexion a PostgreSQL.
  2. Migraciones aplicadas == head (sin pendientes).
  3. Seed clave presente: admin, vehiculo SKN756, conductor seed, proveedor 900123456,
     catalogo DIVIPOLA >= 1000 municipios.
  4. Login 200 (test@celr.com / admin123) y estado de cambio de contrasena forzado.
  5. Conteos baseline de las tablas operativas (referencia post-migracion).

Uso (desde backend/, con PYTHONPATH=. y DATABASE_URL apuntando al stack 5433):
    venv\\Scripts\\python.exe scripts\\smoke.py

Salida: [SMOKE OK] / [SMOKE ERROR] y exit 0 / 1.
"""
import os
import sys
import traceback
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import settings
from app.db.session import engine, SessionLocal
from app.models.flota import Usuario as UsuarioModel, RefreshToken

TABLAS_BASELINE = [
    "usuarios",
    "vehiculos",
    "conductores",
    "proveedores",
    "viajes_odt",
    "gastos",
    "ingresos",
    "liquidaciones_conductores",
    "refresh_tokens",
]


def _alembic_cfg() -> Config:
    """Config de Alembic con rutas absolutas (independiente del CWD)."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = Config(os.path.join(raiz, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(raiz, "alembic"))
    return cfg


def smoke() -> int:
    errores: list[str] = []
    advertencias: list[str] = []
    print("=== SMOKE CELR v6 ===")
    print(f"URL resuelta: {settings.DATABASE_URL}")
    if "localhost:5432" in settings.DATABASE_URL:
        advertencias.append(
            "DATABASE_URL apunta a localhost:5432 (puerto de celr_app_v2). "
            "Ojo: backend/.env trae esa URL por defecto; usar la variable de entorno "
            "con el stack propio :5433."
        )
        print("[WRN] DATABASE_URL resuelve a :5432 - revísalo (ver backend/.env)")

    # 1) Conexion a PostgreSQL
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK ] 1. Conexion a PostgreSQL")
    except Exception as e:
        errores.append(f"conexion BD: {e}")
        print(f"[ERR] 1. Conexion a PostgreSQL: {e}")

    # 2) Migraciones: aplicadas == head (sin pendientes)
    try:
        script = ScriptDirectory.from_config(_alembic_cfg())
        heads = set(script.get_heads())
        with engine.connect() as conn:
            aplicadas = set(
                row[0] for row in conn.execute(text("SELECT version_num FROM alembic_version"))
            )
        if aplicadas == heads:
            print(f"[OK ] 2. Migraciones en head: {sorted(aplicadas)}")
        else:
            faltan = sorted(heads - aplicadas)
            sobra = sorted(aplicadas - heads)
            detalle = f"aplicadas={sorted(aplicadas)} head={sorted(heads)}"
            if faltan:
                detalle += f" PENDIENTES={faltan}"
            if sobra:
                detalle += f" revisiones-no-conocidas={sobra}"
            errores.append(f"migraciones: {detalle}")
            print(f"[ERR] 2. Migraciones: {detalle}")
    except Exception as e:
        errores.append(f"migraciones: {e}")
        print(f"[ERR] 2. Migraciones: {e}")

    # 3) Seed clave presente
    try:
        with engine.connect() as conn:
            chequeos = [
                ("admin test@celr.com (rol admin)", "SELECT count(*) FROM usuarios WHERE correo='test@celr.com' AND rol='admin'", 1),
                ("vehiculo SKN756", "SELECT count(*) FROM vehiculos WHERE placa='SKN756'", 1),
                ("conductor seed", "SELECT count(*) FROM conductores WHERE cedula IN ('12345678','1234567890')", 1),
                ("proveedor NIT 900123456", "SELECT count(*) FROM proveedores WHERE nit='900123456'", 1),
                ("municipios DIVIPOLA", "SELECT count(*) FROM municipios", 1000),
            ]
            for nombre, sql, minimo in chequeos:
                n = conn.execute(text(sql)).scalar()
                ok = n >= minimo
                print(f"[{'OK ' if ok else 'ERR'}] 3. Seed: {nombre} -> {n}")
                if not ok:
                    errores.append(f"seed {nombre} ({n} < {minimo})")
            flag = conn.execute(text(
                "SELECT debe_cambiar_contrasena FROM usuarios WHERE correo='test@celr.com'"
            )).scalar()
            if flag:
                advertencias.append(
                    "test@celr.com tiene debe_cambiar_contrasena=True (el primer login forzara "
                    "el cambio de clave; el login de todos modos responde 200)"
                )
                print("[WRN] 3. test@celr.com debe_cambiar_contrasena = True")
            else:
                print("[OK ] 3. test@celr.com sin cambio de contrasena forzado")
    except Exception as e:
        errores.append(f"seed: {e}")
        print(f"[ERR] 3. Seed: {e}")

    # 4) Login 200 + limpieza del token creado y restauracion de ultimo_acceso
    try:
        db = SessionLocal()
        try:
            admin = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
            ultimo_antes = admin.ultimo_acceso if admin else None
            inicio = datetime.now(timezone.utc)

            from fastapi.testclient import TestClient
            from app.main import app

            r = TestClient(app).post(
                "/api/v1/auth/login",
                json={"correo": "test@celr.com", "contrasena": "admin123"},
            )
            ok_login = r.status_code == 200
            if ok_login:
                print("[OK ] 4. Login test@celr.com -> 200 (access+refresh)")
            else:
                errores.append(f"login HTTP {r.status_code}")
                print(f"[ERR] 4. Login -> {r.status_code}")

            # Dejar la BD igual que antes: borrar el refresh token creado por el login
            # y restaurar ultimo_acceso (patron de limpieza 2.B).
            if admin:
                db.query(RefreshToken).filter(
                    RefreshToken.usuario_id == admin.id,
                    RefreshToken.creado_en >= inicio,
                ).delete(synchronize_session=False)
                admin.ultimo_acceso = ultimo_antes
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        errores.append(f"login: {e}")
        print(f"[ERR] 4. Login: {e}")

    # 5) Conteos baseline
    try:
        with engine.connect() as conn:
            for t in TABLAS_BASELINE:
                n = conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                print(f"      baseline {t}: {n}")
        print("[OK ] 5. Conteos baseline")
    except Exception as e:
        errores.append(f"counts: {e}")
        print(f"[ERR] 5. Conteos baseline: {e}")

    for w in advertencias:
        print(f"[WRN] {w}")

    if errores:
        print("[SMOKE ERROR]")
        for e in errores:
            print(f"  - {e}")
        return 1
    print("[SMOKE OK]")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(smoke())
    except Exception:
        traceback.print_exc()
        print("[SMOKE ERROR] excepcion no controlada")
        sys.exit(1)