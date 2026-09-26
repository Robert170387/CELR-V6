"""Verificación read-only de la idempotencia de los seeds base y demo.

El script toma un fingerprint de la BD, ejecuta ``seed_base`` dos veces y
``seed_demo`` dos veces (N=2 para cada entrypoint) y comprueba que:

- la segunda ejecución de cada seed no cambia el estado de su primera;
- no se modifican registros operativos existentes;
- el baseline local siga siendo el esperado;
- ``km_actual`` de SKN756 y ``refresh_tokens`` conserven el estado esperado;
- el guard de producción rechaza la seed demo.

N=2 es suficiente bajo el contrato actual: la idempotencia operativa se
define como ``estado_post-N == estado_post-(N+1)``. Ni ``seed_base.py`` ni
``seed_demo.py`` tienen fuentes de no-determinismo (no usan ``now()``,
aleatoriedad ni orden no estable), por lo que una tercera ejecución de
cada entrypoint es informativamente equivalente a la segunda bajo ese
contrato.

Trigger de N=3: si en el futuro cualquiera de esos seeds incorpora una
operación no determinista, el verificador debe subir a N=3 y comparar
``estado_post-2 == estado_post-3`` para el entrypoint afectado.

No imprime hashes de contraseñas ni tokens: solo guarda sus digest SHA-256
en memoria para compararlos.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

RAIZ_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(RAIZ_BACKEND)

from app.db.session import SessionLocal, engine  # noqa: E402
from seed_base import (  # noqa: E402
    _configuracion_bootstrap_admin,
    ejecutar_seed_base,
)
from seed_demo import (  # noqa: E402
    ALLOW_DEMO_ENV,
    SeedDemoError,
    ejecutar_seed_demo,
    validar_guard_demo,
)


ESPERADO_CONTEO = {
    "usuarios": 7,
    "vehiculos": 9,
    "conductores": 7,
    "proveedores": 6,
    "viajes_odt": 24,
    "gastos": 37,
    "ingresos": 8,
    "liquidaciones_conductores": 6,
    "refresh_tokens": 0,
}
ESPERADO_KM_SKN756 = "125000.00"
ESPERADO_MAX_ODT = "ODT-2026-000030"
TABLAS_CONTEO = (
    *ESPERADO_CONTEO.keys(),
    "municipios",
    "conductor_vehiculo",
    "secuencias_documento",
)


def _normalizar(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, bytes):
        return valor.hex()
    return valor


def _filas(conn, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    return [
        {clave: _normalizar(valor) for clave, valor in dict(fila._mapping).items()}
        for fila in conn.execute(text(sql), params or {})
    ]


def _sha256(valor: Any) -> str:
    if valor is None:
        valor = ""
    return hashlib.sha256(str(valor).encode("utf-8")).hexdigest()


def _filas_con_digest_secretos(
    conn,
    sql: str,
    campo_secreto: str,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    filas = _filas(conn, sql, params)
    for fila in filas:
        if campo_secreto in fila:
            fila[f"{campo_secreto}_sha256"] = _sha256(fila.pop(campo_secreto))
    return filas


def _fingerprint() -> dict[str, Any]:
    with engine.connect() as conn:
        conteos = {
            tabla: conn.execute(text(f"SELECT count(*) FROM {tabla}")).scalar()
            for tabla in TABLAS_CONTEO
        }

        usuarios = _filas_con_digest_secretos(
            conn,
            """
            SELECT correo, rol, activo, debe_cambiar_contrasena,
                   password_version, conductor_id, ultimo_acceso,
                   contrasena_hash
            FROM usuarios
            ORDER BY correo
            """,
            "contrasena_hash",
        )
        vehiculos = _filas(
            conn,
            """
            SELECT id, placa, marca, modelo, anio, tipo_carroceria,
                   capacidad_ton, estado, km_actual, km_inicial_sistema,
                   numero_motor, numero_chasis, propietario_nombre,
                   propietario_nit
            FROM vehiculos
            ORDER BY placa
            """,
        )
        conductores = _filas(
            conn,
            """
            SELECT id, cedula, nombre_completo, telefono, correo, direccion,
                   num_licencia, categoria_licencia, vencimiento_licencia,
                   estado, porcentaje_comision_default
            FROM conductores
            ORDER BY cedula
            """,
        )
        proveedores = _filas(
            conn,
            """
            SELECT id, nit, razon_social, nombre_comercial, tipo, telefono,
                   correo, ciudad, ciudad_municipio_id, banco, tipo_cuenta,
                   numero_cuenta
            FROM proveedores
            ORDER BY nit
            """,
        )
        asignaciones = _filas(
            conn,
            """
            SELECT id, conductor_id, vehiculo_id, fecha_inicio, fecha_fin,
                   es_principal, observaciones
            FROM conductor_vehiculo
            ORDER BY id
            """,
        )
        refresh_tokens = _filas_con_digest_secretos(
            conn,
            """
            SELECT id, usuario_id, token_hash, expira_en, revocado,
                   creado_en, usado_en
            FROM refresh_tokens
            ORDER BY id
            """,
            "token_hash",
        )
        secuencias = _filas(
            conn,
            "SELECT clave, valor FROM secuencias_documento ORDER BY clave",
        )
        municipios = _filas(
            conn,
            """
            SELECT codigo_dane, departamento, municipio
            FROM municipios
            ORDER BY codigo_dane
            """,
        )
        vehiculo_skn756 = next(
            (fila for fila in vehiculos if fila["placa"] == "SKN756"),
            None,
        )
        max_odt = conn.execute(
            text("SELECT max(numero_odt) FROM viajes_odt")
        ).scalar()

    payload_municipios = json.dumps(
        municipios, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "conteos": conteos,
        "usuarios": usuarios,
        "vehiculos": vehiculos,
        "conductores": conductores,
        "proveedores": proveedores,
        "asignaciones": asignaciones,
        "refresh_tokens": refresh_tokens,
        "secuencias": secuencias,
        "municipios": municipios,
        "municipios_sha256": _sha256(payload_municipios),
        "km_actual_skn756": (
            vehiculo_skn756["km_actual"] if vehiculo_skn756 is not None else None
        ),
        "max_odt": max_odt,
    }


def _validar_baseline(fingerprint: dict[str, Any], etiqueta: str) -> list[str]:
    errores: list[str] = []
    for tabla, esperado in ESPERADO_CONTEO.items():
        actual = fingerprint["conteos"].get(tabla)
        if actual != esperado:
            errores.append(
                f"{etiqueta}: {tabla}={actual}, esperado={esperado}"
            )

    if fingerprint["conteos"].get("municipios", 0) < 1000:
        errores.append(
            f"{etiqueta}: municipios={fingerprint['conteos'].get('municipios')}, "
            "se esperaban al menos 1000"
        )
    if fingerprint["km_actual_skn756"] != ESPERADO_KM_SKN756:
        errores.append(
            f"{etiqueta}: km_actual SKN756={fingerprint['km_actual_skn756']}, "
            f"esperado={ESPERADO_KM_SKN756}"
        )
    if fingerprint["max_odt"] != ESPERADO_MAX_ODT:
        errores.append(
            f"{etiqueta}: max ODT={fingerprint['max_odt']}, "
            f"esperado={ESPERADO_MAX_ODT}"
        )
    return errores


def _comparar_operativos(
    antes: dict[str, Any],
    despues: dict[str, Any],
    bootstrap_email: str | None,
) -> list[str]:
    errores: list[str] = []
    for clave in (
        "vehiculos",
        "conductores",
        "proveedores",
        "asignaciones",
        "refresh_tokens",
        "secuencias",
    ):
        if antes[clave] != despues[clave]:
            errores.append(f"los seeds modificaron datos protegidos: {clave}")

    usuarios_antes = {fila["correo"]: fila for fila in antes["usuarios"]}
    usuarios_despues = {fila["correo"]: fila for fila in despues["usuarios"]}
    for correo, fila in usuarios_antes.items():
        if usuarios_despues.get(correo) != fila:
            errores.append(f"los seeds modificaron un usuario existente: {correo}")
    nuevos_usuarios = set(usuarios_despues) - set(usuarios_antes)
    permitidos = {bootstrap_email} if bootstrap_email else set()
    if nuevos_usuarios - permitidos:
        errores.append(
            "los seeds crearon usuarios no previstos: "
            + ", ".join(sorted(nuevos_usuarios - permitidos))
        )

    municipios_antes = {fila["codigo_dane"] for fila in antes["municipios"]}
    municipios_despues = {fila["codigo_dane"] for fila in despues["municipios"]}
    eliminados = municipios_antes - municipios_despues
    if eliminados:
        errores.append(
            "los seeds eliminaron códigos DANE: " + ", ".join(sorted(eliminados))
        )
    return errores


def _fingerprint_sha256(fingerprint: dict[str, Any]) -> str:
    payload = json.dumps(
        fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return _sha256(payload)


def _correr_seed_base():
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


def _correr_seed_demo():
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


def _guard_produccion_rechaza_demo() -> bool:
    try:
        validar_guard_demo(environment="production", allow_value="1")
    except SeedDemoError:
        return True
    return False


def main() -> int:
    if not _guard_produccion_rechaza_demo():
        print(
            "[ERR] El guard de producción no rechazó la seed demo",
            file=sys.stderr,
        )
        print("[VERIFY SEED ERROR]")
        return 1

    try:
        configuracion = _configuracion_bootstrap_admin()
        bootstrap_email = configuracion[0] if configuracion else None
    except Exception as exc:
        print(f"[ERR] Configuración bootstrap: {exc}", file=sys.stderr)
        return 1

    antes = _fingerprint()
    errores = _validar_baseline(antes, "antes")
    if errores:
        for error in errores:
            print(f"[ERR] {error}", file=sys.stderr)
        # El mensaje importa: este script compara contra conteos ABSOLUTOS de una
        # base recien sembrada, asi que cualquier desviacion significa "esta base
        # no cumple el supuesto", no "el seed esta roto". Sin esta frase, las 8
        # lineas de [ERR] se leen como un fallo del seed y se pierde tiempo
        # buscando un bug que no esta.
        print(
            "\n[VERIFY SEED] Que significa esto:\n"
            "  Este verificador solo es valido sobre una base RECIEN SEMBRADA.\n"
            "  Compara conteos absolutos contra los del seed, asi que sobre una base\n"
            "  de desarrollo con datos de uso SIEMPRE falla, y ese fallo no dice\n"
            "  nada sobre el seed.\n"
            "\n  Que hacer:\n"
            "    - Si querias verificar el seed: levantar una base vacia y correrlo\n"
            "      ahi. docker compose down -v && docker compose up -d db\n"
            "    - Si solo querias el estado de esta base: no es la herramienta.\n"
            "      Lee los conteos directo, o usa las suites (que si son delta).\n"
            "\n  Este script NO modifico nada: fallo antes de ejecutar el seed.\n"
            "\n[VERIFY SEED ERROR] base fuera del supuesto de recien sembrada; "
            "no se ejecuto el seed",
            file=sys.stderr,
        )
        return 1

    if bootstrap_email:
        correos_existentes = {
            str(fila["correo"]).lower() for fila in antes["usuarios"]
        }
        if bootstrap_email not in correos_existentes:
            print(
                "[ERR] El email bootstrap todavía no existe; el verificador no crea "
                "cuentas ni ejecutará el seed",
                file=sys.stderr,
            )
            print("[VERIFY SEED ERROR]")
            return 1

    try:
        # El verificador activa el opt-in solo dentro de este proceso y restaura
        # la variable original al terminar; no modifica el entorno persistente.
        validar_guard_demo(allow_value="1")
    except SeedDemoError as exc:
        print(f"[ERR] Guard local de seed demo: {exc}", file=sys.stderr)
        return 1

    print(f"[INFO] Fingerprint antes: {_fingerprint_sha256(antes)}")

    try:
        base_primera = _correr_seed_base()
        despues_base_primera = _fingerprint()
        base_segunda = _correr_seed_base()
        despues_base_segunda = _fingerprint()

        allow_anterior = os.environ.get(ALLOW_DEMO_ENV)
        os.environ[ALLOW_DEMO_ENV] = "1"
        try:
            demo_primera = _correr_seed_demo()
            despues_demo_primera = _fingerprint()
            demo_segunda = _correr_seed_demo()
            despues_demo_segunda = _fingerprint()
        finally:
            if allow_anterior is None:
                os.environ.pop(ALLOW_DEMO_ENV, None)
            else:
                os.environ[ALLOW_DEMO_ENV] = allow_anterior
    except Exception as exc:
        print(f"[ERR] Ejecución de seeds: {exc}", file=sys.stderr)
        print("[VERIFY SEED ERROR]")
        return 1

    if despues_base_primera != despues_base_segunda:
        print(
            "[ERR] La segunda ejecución de seed_base cambió el fingerprint",
            file=sys.stderr,
        )
        print("[VERIFY SEED ERROR] seed base no idempotente")
        return 1

    if despues_demo_primera != despues_demo_segunda:
        print(
            "[ERR] La segunda ejecución de seed_demo cambió el fingerprint",
            file=sys.stderr,
        )
        print("[VERIFY SEED ERROR] seed demo no idempotente")
        return 1

    errores = _comparar_operativos(
        antes, despues_demo_primera, bootstrap_email
    )
    errores.extend(_validar_baseline(despues_demo_segunda, "después"))

    if errores:
        for error in errores:
            print(f"[ERR] {error}", file=sys.stderr)
        print("[VERIFY SEED ERROR]")
        return 1

    print(
        "[OK] Seed base idempotente: "
        f"municipios_fuente={base_primera.municipios.total_fuente} "
        f"insertados={base_primera.municipios.insertados} "
        f"actualizados={base_primera.municipios.actualizados}"
    )
    print(
        "[OK] Seed demo idempotente: "
        f"admin={demo_primera.admin_estado} "
        f"conductor={demo_primera.conductor_estado} "
        f"vehiculo={demo_primera.vehiculo_estado} "
        f"proveedor={demo_primera.proveedor_estado} "
        f"asignacion={demo_primera.asignacion_estado}"
    )
    print("[OK] Guard de producción: seed demo rechazada")
    print("[OK] Protecciones: password/km/refresh_tokens/operativos sin cambios")
    print("[OK] Baseline conservado")
    print("[VERIFY SEED OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
