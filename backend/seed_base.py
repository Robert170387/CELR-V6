"""Seed base idempotente y no destructivo de CELR v6.

Este entrypoint prepara únicamente datos base:

- catálogo DIVIPOLA de municipios;
- bootstrap opcional de una cuenta administradora, siempre create-only.

La cuenta administradora solo se crea cuando se proporcionan
``CELR_BOOTSTRAP_ADMIN_EMAIL`` y ``CELR_BOOTSTRAP_ADMIN_PASSWORD``. Nunca se
resetea una cuenta existente. Las entidades operacionales y los fixtures de
la demo viven en otros entrypoints.

La transacción es propiedad de ``main``. Las funciones reutilizables no hacen
commit para que ``scripts/seed_municipios.py`` pueda conservar su contrato
histórico haciendo commit desde su propio entrypoint.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

from sqlalchemy import func

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.flota import Usuario
from app.models.ubicacion import Municipio


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "municipios_colombia.json")
BOOTSTRAP_ADMIN_EMAIL_ENV = "CELR_BOOTSTRAP_ADMIN_EMAIL"
BOOTSTRAP_ADMIN_PASSWORD_ENV = "CELR_BOOTSTRAP_ADMIN_PASSWORD"


@dataclass(frozen=True)
class ResultadoBootstrapAdmin:
    estado: str
    correo: str | None = None
    usuario_id: int | None = None


@dataclass(frozen=True)
class ResultadoMunicipios:
    insertados: int
    actualizados: int
    total_fuente: int


@dataclass(frozen=True)
class ResultadoSeedBase:
    admin: ResultadoBootstrapAdmin
    municipios: ResultadoMunicipios


def _configuracion_bootstrap_admin() -> tuple[str, str] | None:
    """Lee y valida las variables de bootstrap sin exponer la contraseña."""
    email = (os.getenv(BOOTSTRAP_ADMIN_EMAIL_ENV) or "").strip().lower()
    password = os.getenv(BOOTSTRAP_ADMIN_PASSWORD_ENV)

    if not email and not password:
        return None
    if not email or not password:
        raise RuntimeError(
            "Configuración incompleta: deben proporcionarse "
            f"{BOOTSTRAP_ADMIN_EMAIL_ENV} y {BOOTSTRAP_ADMIN_PASSWORD_ENV} juntos"
        )
    if not email:
        raise RuntimeError(f"{BOOTSTRAP_ADMIN_EMAIL_ENV} no puede estar vacío")
    return email, password


def asegurar_admin_bootstrap(db) -> ResultadoBootstrapAdmin:
    """Crea el admin inicial solo si no existe; nunca modifica una cuenta."""
    configuracion = _configuracion_bootstrap_admin()
    if configuracion is None:
        return ResultadoBootstrapAdmin(estado="omitido")

    email, password = configuracion
    usuario = (
        db.query(Usuario)
        .filter(func.lower(Usuario.correo) == email)
        .first()
    )
    if usuario is not None:
        if usuario.rol != "admin" or not usuario.activo:
            raise RuntimeError(
                f"El usuario bootstrap {email} existe, pero no es un administrador "
                "activo; no se realizará ninguna modificación automática"
            )
        return ResultadoBootstrapAdmin(
            estado="existente",
            correo=usuario.correo,
            usuario_id=usuario.id,
        )

    usuario = Usuario(
        correo=email,
        contrasena_hash=hash_password(password),
        rol="admin",
        activo=True,
        debe_cambiar_contrasena=True,
        password_version=1,
    )
    db.add(usuario)
    db.flush()
    return ResultadoBootstrapAdmin(
        estado="creado",
        correo=email,
        usuario_id=usuario.id,
    )


def _registros_municipios(data_path: str) -> list[dict[str, str]]:
    with open(data_path, encoding="utf-8") as archivo:
        registros = json.load(archivo)

    if not isinstance(registros, list):
        raise ValueError("El catálogo municipal debe ser una lista JSON")

    normalizados: list[dict[str, str]] = []
    codigos_vistos: set[str] = set()
    for indice, registro in enumerate(registros, start=1):
        try:
            codigo_completo = str(registro["code"]["id"])
            codigo_dane = codigo_completo[2:]
            departamento = str(registro["parent"]["name"]["local"])
            municipio = str(registro["name"]["local"])
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError(
                f"Registro municipal inválido en la posición {indice}"
            ) from exc

        if codigo_dane in codigos_vistos:
            raise ValueError(f"Código DANE duplicado en el catálogo: {codigo_dane}")
        codigos_vistos.add(codigo_dane)
        normalizados.append(
            {
                "codigo_dane": codigo_dane,
                "departamento": departamento,
                "municipio": municipio,
            }
        )

    return normalizados


def sincronizar_municipios(
    db,
    data_path: str = DATA_PATH,
) -> ResultadoMunicipios:
    """Sincroniza el catálogo por código DANE sin hacer commit.

    Las inserciones y actualizaciones quedan dentro de la transacción que
    administra el entrypoint. Las actualizaciones se limitan a los nombres
    canónicos; nunca se eliminan registros.
    """
    registros = _registros_municipios(data_path)
    codigos = [registro["codigo_dane"] for registro in registros]
    existentes = {
        municipio.codigo_dane: municipio
        for municipio in db.query(Municipio)
        .filter(Municipio.codigo_dane.in_(codigos))
        .all()
    }

    insertados = 0
    actualizados = 0
    for registro in registros:
        codigo_dane = registro["codigo_dane"]
        municipio = existentes.get(codigo_dane)
        if municipio is None:
            db.add(Municipio(**registro))
            insertados += 1
            continue

        if (
            municipio.departamento != registro["departamento"]
            or municipio.municipio != registro["municipio"]
        ):
            municipio.departamento = registro["departamento"]
            municipio.municipio = registro["municipio"]
            actualizados += 1

    # Valida la operación dentro de la transacción actual sin apropiarse del commit.
    db.flush()
    return ResultadoMunicipios(
        insertados=insertados,
        actualizados=actualizados,
        total_fuente=len(registros),
    )


def ejecutar_seed_base(db) -> ResultadoSeedBase:
    """Ejecuta el seed base dentro de la transacción recibida."""
    admin = asegurar_admin_bootstrap(db)
    municipios = sincronizar_municipios(db)
    return ResultadoSeedBase(admin=admin, municipios=municipios)


def main() -> int:
    db = SessionLocal()
    try:
        resultado = ejecutar_seed_base(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"ERROR durante el seed base: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    if resultado.admin.estado == "omitido":
        print(
            "[WARN] Bootstrap admin omitido: no se proporcionaron "
            f"{BOOTSTRAP_ADMIN_EMAIL_ENV} y {BOOTSTRAP_ADMIN_PASSWORD_ENV}"
        )
    else:
        print(f"[OK] Bootstrap admin: {resultado.admin.estado}")

    resultado_municipios = resultado.municipios
    print(
        "[OK] Municipios: "
        f"fuente={resultado_municipios.total_fuente} "
        f"insertados={resultado_municipios.insertados} "
        f"actualizados={resultado_municipios.actualizados}"
    )
    print("--- SEED BASE COMPLETADO CON EXITO ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
