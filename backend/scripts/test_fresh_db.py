"""Prueba end-to-end de Alembic sobre una base de datos desechable.

La base de la aplicacion nunca se modifica. El test solo crea, migra y destruye
``celr_v6_fresh_test`` usando una conexion administrativa al servidor PostgreSQL.

TM7 compara las FKs por relacion (columnas, tabla referenciada y columnas
referenciadas), no por nombre. El baseline ``a5b6b344c873`` crea FKs con
nombres default (``*_id_fkey``) via ``create_all()`` y ``a1b2c3d4e5f6``
agrega las nombradas (``fk_*``) para la misma relacion. En el primer ciclo
coexisten ambas; en el segundo solo queda la nombrada porque ``create_all()``
es no-op sobre tablas existentes. Es drift cosmetico de nombres: la relacion
referencial es identica.
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CheckConstraint, ForeignKeyConstraint

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base_class import Base  # noqa: E402
import app.models  # noqa: E402,F401

APP_DB_URL_TEXT = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:admin@localhost:5433/celr_v6_db",
)
APP_DB_URL = make_url(APP_DB_URL_TEXT)
FRESH_DB_NAME = "celr_v6_fresh_test"
FRESH_DB_URL = APP_DB_URL.set(database=FRESH_DB_NAME)
ADMIN_DB_URL = APP_DB_URL.set(database="postgres")
FRESH_DB_URL_TEXT = FRESH_DB_URL.render_as_string(hide_password=False)
ADMIN_DB_URL_TEXT = ADMIN_DB_URL.render_as_string(hide_password=False)
HEAD_REVISION = "c3d4e5f6a7b8"
BASELINE_TABLES = [
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
EXPECTED_BASELINE = [7, 9, 7, 6, 24, 37, 8, 6, 0]


class TestFreshDBError(RuntimeError):
    """Error de una comprobacion del test fresh DB."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise TestFreshDBError(message)


def _assert_safe_urls() -> None:
    _check(APP_DB_URL.database == "celr_v6_db", "DATABASE_URL de la app no apunta a celr_v6_db")
    _check(FRESH_DB_NAME in FRESH_DB_URL_TEXT, "URL de fresh DB mal formada")
    _check(FRESH_DB_URL_TEXT != APP_DB_URL_TEXT, "fresh DB no puede ser la app DB")
    _check(APP_DB_URL.database != FRESH_DB_NAME, "fresh DB no puede ser la app DB")


def _alembic_command() -> list[str]:
    executable = BACKEND_DIR / "venv" / "Scripts" / "alembic.exe"
    if executable.exists():
        return [str(executable)]
    return [sys.executable, "-m", "alembic"]


def _run_alembic(*args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = FRESH_DB_URL_TEXT
    env["PYTHONIOENCODING"] = "utf-8"
    env["ENVIRONMENT"] = "development"
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [*_alembic_command(), *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise TestFreshDBError(
            f"alembic {' '.join(args)} fallo ({result.returncode})\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    print(f"    [alembic] {' '.join(args)}: OK")
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip())


def _admin_connect(admin_engine):
    return admin_engine.connect()


def _drop_fresh_database(admin_engine) -> None:
    with _admin_connect(admin_engine) as connection:
        try:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{FRESH_DB_NAME}" WITH (FORCE)')
            )
        except SQLAlchemyError:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :dbname AND pid <> pg_backend_pid()"
                ),
                {"dbname": FRESH_DB_NAME},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{FRESH_DB_NAME}"'))


def _create_fresh_database(admin_engine) -> None:
    with _admin_connect(admin_engine) as connection:
        connection.execute(text(f'CREATE DATABASE "{FRESH_DB_NAME}"'))


def _fresh_database_exists(admin_engine) -> bool:
    with _admin_connect(admin_engine) as connection:
        return connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": FRESH_DB_NAME},
        ).first() is not None


def _read_app_state(engine) -> dict:
    with engine.connect() as connection:
        versions = tuple(
            row[0]
            for row in connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            )
        )
        counts = tuple(
            connection.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            for table in BASELINE_TABLES
        )
    return {"versions": versions, "counts": counts}


def _generated_columns(connection) -> set[tuple[str, str]]:
    return {
        (row[0], row[1])
        for row in connection.execute(
            text(
                "SELECT table_name, column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND is_generated = 'ALWAYS'"
            )
        )
    }


def _fk_signature(fk: dict) -> tuple:
    """Firma semantica de una FK, sin depender del nombre de la constraint."""
    return (
        tuple(sorted(fk.get("constrained_columns") or [])),
        fk.get("referred_table"),
        tuple(sorted(fk.get("referred_columns") or [])),
    )


def _schema_snapshot(engine) -> dict:
    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = sorted(
            table for table in inspector.get_table_names() if table != "alembic_version"
        )
        columns = {
            table: tuple(
                sorted(column["name"] for column in inspector.get_columns(table))
            )
            for table in tables
        }
        checks = {
            table: tuple(
                sorted(
                    constraint["name"]
                    for constraint in inspector.get_check_constraints(table)
                    if constraint.get("name")
                )
            )
            for table in tables
        }
        foreign_keys = {
            table: {
                _fk_signature(fk)
                for fk in inspector.get_foreign_keys(table)
            }
            for table in tables
        }
        generated = tuple(
            sorted(
                item
                for item in _generated_columns(connection)
                if item[0] in tables
            )
        )
        views = tuple(
            sorted(
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT viewname FROM pg_views "
                        "WHERE schemaname = 'public'"
                    )
                )
            )
        )
    return {
        "tables": tuple(tables),
        "columns": columns,
        "checks": checks,
        "foreign_keys": foreign_keys,
        "generated": generated,
        "views": views,
    }


def _expected_metadata() -> tuple[set[str], dict[str, set[str]], dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    tables = set(Base.metadata.tables)
    columns = {
        name: set(table.columns.keys())
        for name, table in Base.metadata.tables.items()
    }
    checks = {}
    foreign_keys = {}
    generated = {}
    for table_name, table in Base.metadata.tables.items():
        checks[table_name] = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint) and constraint.name
        }
        foreign_keys[table_name] = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint) and constraint.name
        }
        generated[table_name] = {
            column.name
            for column in table.columns
            if column.computed is not None
        }
    return tables, columns, checks, foreign_keys, generated


def _verify_schema(engine, snapshot_label: str) -> dict:
    expected_tables, expected_columns, expected_checks, expected_fks, expected_generated = _expected_metadata()
    with engine.connect() as connection:
        inspector = inspect(connection)
        actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
        missing_tables = expected_tables - actual_tables
        _check(
            not missing_tables,
            f"TM2 {snapshot_label}: tablas faltantes={sorted(missing_tables)}",
        )
        print(f"[OK] TM2 {snapshot_label}: todas las tablas de Base.metadata existen")

        missing_columns = {}
        for table, expected in expected_columns.items():
            actual = {column["name"] for column in inspector.get_columns(table)}
            difference = expected - actual
            if difference:
                missing_columns[table] = sorted(difference)
        _check(
            not missing_columns,
            f"TM3 {snapshot_label}: columnas faltantes={missing_columns}",
        )
        print(f"[OK] TM3 {snapshot_label}: todas las columnas de Base.metadata existen")

        actual_generated = _generated_columns(connection)
        missing_checks = {}
        missing_fks = {}
        missing_generated = {}
        for table in expected_tables:
            actual_checks = {
                item["name"]
                for item in inspector.get_check_constraints(table)
                if item.get("name")
            }
            difference = expected_checks[table] - actual_checks
            if difference:
                missing_checks[table] = sorted(difference)

            actual_fks = {
                item["name"]
                for item in inspector.get_foreign_keys(table)
                if item.get("name")
            }
            difference = expected_fks[table] - actual_fks
            if difference:
                missing_fks[table] = sorted(difference)

            difference = expected_generated.get(table, set()) - {
                column for table_name, column in actual_generated if table_name == table
            }
            if difference:
                missing_generated[table] = sorted(difference)

        _check(
            not missing_checks,
            f"TM4 {snapshot_label}: checks faltantes={missing_checks}",
        )
        _check(
            not missing_fks,
            f"TM4 {snapshot_label}: FKs faltantes={missing_fks}",
        )
        _check(
            not missing_generated,
            f"TM4 {snapshot_label}: generadas faltantes={missing_generated}",
        )
        view_exists = connection.execute(
            text(
                "SELECT 1 FROM pg_views "
                "WHERE schemaname = 'public' AND viewname = 'v_odt_resumen'"
            )
        ).first() is not None
        _check(view_exists, f"TM4 {snapshot_label}: falta v_odt_resumen")
        print(f"[OK] TM4 {snapshot_label}: checks, FKs, generadas y vista existen")

    return _schema_snapshot(engine)


def main() -> int:
    exit_code = 0
    app_engine = None
    admin_engine = None
    fresh_engine = None
    pre_state = None

    try:
        _assert_safe_urls()
        print("[OK] Guardas de seguridad: app DB y fresh DB son distintas")

        app_engine = create_engine(
            APP_DB_URL_TEXT,
            pool_pre_ping=True,
        )
        pre_state = _read_app_state(app_engine)
        _check(
            pre_state["versions"] == (HEAD_REVISION,),
            f"Precondición fallida: alembic_version={pre_state['versions']}",
        )
        _check(
            list(pre_state["counts"]) == EXPECTED_BASELINE,
            f"Precondición fallida: baseline={pre_state['counts']}",
        )
        print("[OK] Precondición: celr_v6_db está en head y baseline 7/9/7/6/24/37/8/6/0")

        admin_engine = create_engine(
            ADMIN_DB_URL_TEXT,
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        _drop_fresh_database(admin_engine)
        _create_fresh_database(admin_engine)
        print(f"[OK] Base desechable creada: {FRESH_DB_NAME}")

        _run_alembic("upgrade", "head")
        print("[OK] TM1: upgrade head desde cero no falla")

        fresh_engine = create_engine(
            FRESH_DB_URL_TEXT,
            pool_pre_ping=True,
        )
        snapshot_first = _verify_schema(fresh_engine, "primer ciclo")
        print("[OK] TM2-TM4: schema valida en el primer ciclo")
        fresh_engine.dispose()
        fresh_engine = None

        _run_alembic("downgrade", "base")
        print("[OK] TM5: downgrade base no falla")

        _run_alembic("upgrade", "head")
        print("[OK] TM6: upgrade head posterior a downgrade no falla")

        fresh_engine = create_engine(
            FRESH_DB_URL_TEXT,
            pool_pre_ping=True,
        )
        snapshot_second = _verify_schema(fresh_engine, "segundo ciclo")
        _check(
            snapshot_first == snapshot_second,
            "TM7: el schema del segundo ciclo difiere del primero",
        )
        print("[OK] TM7: schema identico entre ambos ciclos")

        post_state = _read_app_state(app_engine)
        _check(
            post_state == pre_state,
            f"TM8: celr_v6_db cambio: antes={pre_state} despues={post_state}",
        )
        print("[OK] TM8: celr_v6_db intacta")

    except Exception as exc:
        exit_code = 1
        print(f"[FAIL] {exc}")
        traceback.print_exc()
    finally:
        if fresh_engine is not None:
            fresh_engine.dispose()
        cleanup_ok = False
        if admin_engine is not None:
            try:
                _drop_fresh_database(admin_engine)
                cleanup_ok = not _fresh_database_exists(admin_engine)
            except Exception as exc:
                exit_code = 1
                print(f"[FAIL] TM9: no se pudo destruir {FRESH_DB_NAME}: {exc}")
            finally:
                admin_engine.dispose()
        else:
            exit_code = 1
            print("[FAIL] TM9: no se pudo crear el engine administrativo")
        if admin_engine is not None and cleanup_ok:
            print(f"[OK] TM9: {FRESH_DB_NAME} destruida")
        if app_engine is not None:
            app_engine.dispose()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
