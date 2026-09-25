"""Verificacion puntual del guard del downgrade de A1 en una BD desechable.

No forma parte de las 12 suites: solo comprueba que `downgrade` ABORTA (no
corrompe datos) cuando existen usuarios con correo=NULL, que es justo el caso
que hara realidad el modulo de Usuarios (identidad por cedula).
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config

BASE = "postgresql://postgres:admin@localhost:5433/postgres"
DB = "celr_v6_a1_guard_test"
ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")

# Revisiones FIJAS, no relativas. Un `downgrade -1` solo baja UN paso: en
# cuanto se agrega una migracion encima de A1 (A3.1 lo hizo), el guard deja de
# alcanzarse y el test se pone verde sin comprobar nada. Con destino absoluto
# el guard se sigue ejecutando aunque la cadena crezca.
REV_A1 = "d4e5f6a7b8c9"      # la migracion cuyo guard se verifica
REV_PREVIA_A1 = "c3d4e5f6a7b8"  # su revision padre


def run() -> int:
    admin = create_engine(BASE, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {DB}"))
        conn.execute(text(f"CREATE DATABASE {DB}"))
    print(f"[OK] BD desechable creada: {DB}")

    url = f"postgresql://postgres:admin@localhost:5433/{DB}"
    cfg = Config(ALEMBIC_INI)
    # env.py:14 fuerza la URL desde DATABASE_URL: hay que cambiar la variable,
    # no el Config. Se restaura al final para no dejar el proceso contaminado.
    url_previa = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        rc = _ciclo_downgrade(url, cfg, DB, admin)
    finally:
        if url_previa is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = url_previa
    if rc != 0:
        print("\n[GUARD DOWNGRADE FALLO]")
        return rc
    print("\n[GUARD DOWNGRADE OK]")
    return 0


def _ciclo_downgrade(url: str, cfg: Config, DB: str, admin) -> int:
    """Cuerpo del chequeo: corre con DATABASE_URL ya apuntando a la BD desechable."""
    command.upgrade(cfg, "head")
    with create_engine(url).connect() as conn:
        head_esperado = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
    print(f"[OK] upgrade head aplicado (head={head_esperado})")

    eng = create_engine(url)
    # engine.begin(): sin commit explicito el INSERT se pierde al cerrar, y el
    # guard se comprobaria contra una tabla vacia (falso verde).
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO usuarios (correo, contrasena_hash, rol, activo, "
            "debe_cambiar_contrasena) VALUES (NULL, 'x', 'admin', true, true)"
        ))
    with eng.connect() as conn:
        nulos = conn.execute(
            text("SELECT count(*) FROM usuarios WHERE correo IS NULL")
        ).scalar()
    if nulos != 1:
        print(f"[FALLA] el usuario con correo=NULL no quedo persistido (nulos={nulos})")
        return 1
    print(f"[OK] usuario con correo=NULL insertado y confirmado (nulos={nulos})")

    fallo = None
    try:
        # Destino absoluto: baja hasta la revision previa de A1, atravesando
        # cualquier revision que se haya agregado encima.
        command.downgrade(cfg, REV_PREVIA_A1)
    except Exception as e:  # noqa: BLE001 - aqui el fallo es lo esperado
        fallo = e
    if fallo is None:
        print("[FALLA] el downgrade NO abortó: el guard no protege los datos")
        return 1
    primera_linea = str(fallo).strip().splitlines()[0]
    print(f"[OK] el downgrade ABORTÓ: {primera_linea}")
    if "correo NULL" not in str(fallo):
        print("[FALLA] el mensaje del guard no menciona los usuarios con correo NULL")
        return 1
    print("[OK] el mensaje del guard es accionable (menciona correo NULL)")

    with eng.connect() as conn:
        sigue_en_head = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        cedula_existe = conn.execute(text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='usuarios' AND column_name='cedula'"
        )).scalar()
    print(f"[OK] la BD sigue en '{sigue_en_head}' y cedula existe={bool(cedula_existe)}")
    if sigue_en_head != head_esperado or not cedula_existe:
        print("[FALLA] el rollback transaccional no dejó el esquema intacto")
        return 1

    # Con el usuario NULL eliminado, el downgrade debe completar.
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM usuarios WHERE correo IS NULL"))
    command.downgrade(cfg, REV_PREVIA_A1)
    print("[OK] sin usuarios con correo NULL, el downgrade completa")

    with eng.connect() as conn:
        sigue_en_previo = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        correo_not_null = conn.execute(text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='usuarios' AND column_name='correo'"
        )).scalar()
    print(f"[OK] version={sigue_en_previo}, correo is_nullable={correo_not_null}")
    if sigue_en_previo != REV_PREVIA_A1 or correo_not_null != "NO":
        print("[FALLA] el downgrade no restauró el esquema previo")
        return 1

    eng.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {DB}"))
    print(f"[OK] BD desechable destruida: {DB}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
