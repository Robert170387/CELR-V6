"""Reset seguro de datos transaccionales de CELR v6.

El script conserva los catálogos maestros, la versión de Alembic y las
secuencias de documentos. Solo trunca las tablas de actividad indicadas por
la operación de reset autorizada.

Uso desde ``backend/``:

    python scripts/db_reset.py
    python scripts/db_reset.py --dry-run
    python scripts/db_reset.py --execute --yes

Sin ``--execute`` el modo por defecto es ``--dry-run``.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


RAIZ_BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ_BACKEND / ".env")

# El orden está explícito para que el flujo sea auditable. CASCADE cubre las
# dependencias residuales, pero las siete tablas se operan una por una.
TABLAS_ACTIVIDAD = [
    "flypass_transacciones",
    "movimientos_bancarios",
    "liquidaciones_conductores",
    "ingresos",
    "gastos",
    "viajes_odt",
    "refresh_tokens",
]

TABLAS_MAESTRAS = [
    "usuarios",
    "vehiculos",
    "conductores",
    "proveedores",
    "municipios",
]

TABLAS_CONTROL = [
    "secuencias_documento",
    "alembic_version",
]

TABLAS_PRESERVADAS = TABLAS_MAESTRAS + TABLAS_CONTROL

TODAS_LAS_TABLAS = TABLAS_ACTIVIDAD + TABLAS_PRESERVADAS


class ResetError(RuntimeError):
    """Error de validación previo o durante el reset."""


def _normalizar_url(valor: str) -> str:
    """Normaliza el alias legado de PostgreSQL usado por Aiven."""
    if valor.startswith("postgres://"):
        return "postgresql://" + valor[len("postgres://") :]
    return valor


def _obtener_url() -> Any:
    valor = os.getenv("DATABASE_URL", "").strip()
    if not valor:
        raise ResetError(
            "Falta DATABASE_URL. Configura postgresql://postgres:admin@localhost:5433/celr_v6_db"
        )

    url = make_url(_normalizar_url(valor))
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ResetError(
            f"Reset bloqueado: el host debe ser localhost/127.0.0.1, recibido {url.host!r}"
        )
    if url.port != 5433:
        raise ResetError(
            f"Reset bloqueado: el puerto debe ser 5433, recibido {url.port!r}"
        )
    if url.database != "celr_v6_db":
        raise ResetError(
            f"Reset bloqueado: la base debe ser celr_v6_db, recibido {url.database!r}"
        )
    return url


def _validar_entorno() -> None:
    entorno = os.getenv("ENVIRONMENT", "development").strip().lower()
    if entorno == "production":
        raise ResetError("Reset bloqueado: ENVIRONMENT=production")


def _verificar_conexion(engine: Any, url: Any) -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            base = conn.execute(text("SELECT current_database()" )).scalar()
            if base != url.database:
                raise ResetError(
                    f"La conexión apunta a {base!r}, pero se esperaba {url.database!r}"
                )
    except ResetError:
        raise
    except Exception as exc:  # pragma: no cover - mensaje de CLI
        raise ResetError(f"No se pudo conectar a PostgreSQL local: {exc}") from exc


def _verificar_tablas(conn: Any) -> None:
    faltantes: list[str] = []
    for tabla in TODAS_LAS_TABLAS:
        existe = conn.execute(
            text("SELECT to_regclass(:nombre)"),
            {"nombre": f"public.{tabla}"},
        ).scalar()
        if existe is None:
            faltantes.append(tabla)
    if faltantes:
        raise ResetError(
            "Faltan tablas requeridas en public: " + ", ".join(faltantes)
        )


def _conteo(conn: Any, tabla: str) -> int:
    return int(conn.execute(text(f'SELECT COUNT(*) FROM "{tabla}"')).scalar())


def _conteos(conn: Any, tablas: list[str]) -> dict[str, int]:
    return {tabla: _conteo(conn, tabla) for tabla in tablas}


def _secuencias(conn: Any) -> list[tuple[str, int]]:
    return [
        (str(row["clave"]), int(row["valor"]))
        for row in conn.execute(
            text("SELECT clave, valor FROM secuencias_documento ORDER BY clave")
        ).mappings()
    ]


def _alembic(conn: Any) -> list[str]:
    return [
        str(row["version_num"])
        for row in conn.execute(text("SELECT version_num FROM alembic_version")).mappings()
    ]


def _imprimir_plan(conteos: dict[str, int], modo: str) -> None:
    etiqueta_modo = "DRY-RUN" if modo == "dry-run" else "EJECUCIÓN"
    print(f"[{etiqueta_modo}] Operaciones planificadas:")
    for tabla in TABLAS_ACTIVIDAD:
        print(f"  TRUNCATE {tabla:<28} ({conteos[tabla]} filas)")
    print("Preservadas (sin cambios):")
    for tabla in TABLAS_PRESERVADAS:
        conteo = conteos.get(tabla)
        if conteo is None:
            print(f"  {tabla}")
        else:
            print(f"  {tabla:<28} ({conteo} filas)")


def _pedir_confirmacion() -> bool:
    try:
        respuesta = input("Escriba SI para ejecutar el reset: ").strip().upper()
    except EOFError:
        print("ABORTADO: no hay consola interactiva.")
        return False
    if respuesta != "SI":
        print("ABORTADO: confirmación diferente de SI.")
        return False
    return True


def _ejecutar_reset(engine: Any) -> dict[str, Any]:
    """Trunca en una transacción y devuelve conteos/snapshots posteriores."""
    with engine.begin() as conn:
        _verificar_tablas(conn)

        conteos_pre = _conteos(conn, TABLAS_ACTIVIDAD)
        preservados_pre = _conteos(conn, TABLAS_MAESTRAS)
        secuencias_pre = _secuencias(conn)
        alembic_pre = _alembic(conn)

        for tabla in TABLAS_ACTIVIDAD:
            conn.execute(text(f'TRUNCATE TABLE "{tabla}" RESTART IDENTITY CASCADE'))

        # CASCADE no debe tocar catálogos maestros, secuencias ni Alembic.
        conteos_post = _conteos(conn, TABLAS_ACTIVIDAD)
        preservados_post = _conteos(conn, TABLAS_MAESTRAS)
        secuencias_post = _secuencias(conn)
        alembic_post = _alembic(conn)

        if any(conteos_post.values()):
            raise ResetError(
                "La operación terminó con filas en tablas de actividad; se revierte."
            )
        if preservados_pre != preservados_post:
            raise ResetError(
                "Una tabla preservada cambió durante el reset; se revierte la transacción."
            )
        if secuencias_pre != secuencias_post:
            raise ResetError(
                "secuencias_documento cambió durante el reset; se revierte la transacción."
            )
        if alembic_pre != alembic_post:
            raise ResetError(
                "alembic_version cambió durante el reset; se revierte la transacción."
            )

    return {
        "conteos_pre": conteos_pre,
        "conteos_post": conteos_post,
        "preservados_post": preservados_post,
        "secuencias_post": secuencias_post,
        "alembic_post": alembic_post,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset transaccional de CELR v6 (dry-run por defecto)."
    )
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el plan sin ejecutar (modo por defecto).",
    )
    modo.add_argument(
        "--execute",
        action="store_true",
        help="Ejecuta el reset; requiere --yes o confirmación SI.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma automáticamente el modo --execute.",
    )
    args = parser.parse_args()
    if args.yes and not args.execute:
        parser.error("--yes solo es válido junto con --execute")
    return args


def main() -> int:
    args = _parse_args()
    try:
        _validar_entorno()
        url = _obtener_url()
        engine = create_engine(
            url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        try:
            _verificar_conexion(engine, url)
            with engine.connect() as conn:
                _verificar_tablas(conn)
                conteos = _conteos(conn, TODAS_LAS_TABLAS)

            modo = "execute" if args.execute else "dry-run"
            _imprimir_plan(conteos, modo)

            if not args.execute:
                print("Para ejecutar: python scripts/db_reset.py --execute --yes")
                return 0

            if not args.yes and not _pedir_confirmacion():
                return 2

            resultado = _ejecutar_reset(engine)
            print("[OK] Reset transaccional completado.")
            print("Conteos post-reset:")
            for tabla in TABLAS_ACTIVIDAD:
                print(f"  {tabla:<28} {resultado['conteos_post'][tabla]}")
            print("Preservadas verificadas:")
            for tabla, conteo in resultado["preservados_post"].items():
                print(f"  {tabla:<28} {conteo}")
            print("secuencias_documento:")
            for clave, valor in resultado["secuencias_post"]:
                print(f"  {clave:<28} {valor}")
            print("alembic_version:")
            for version in resultado["alembic_post"]:
                print(f"  {version}")
            return 0
        finally:
            engine.dispose()
    except ResetError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - mensaje de CLI
        print(f"[ERROR] Fallo inesperado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
