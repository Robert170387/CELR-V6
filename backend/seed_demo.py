"""Seed demo local, opt-in y no destructivo de CELR v6.

Este entrypoint crea fixtures de desarrollo únicamente cuando se cumplen las
condiciones locales:

- ``ENVIRONMENT`` no es ``production``;
- ``CELR_ALLOW_DEMO_SEED=1`` está definido.

La política predeterminada es ``create-if-missing``. No se sobrescriben
passwords, odómetros, estados, contactos ni atributos existentes. No hay
``--reset`` en esta fase: cualquier reseteo requiere una operación posterior
explícita y separada.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from sqlalchemy import func

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.flota import Conductor, ConductorVehiculo, Usuario, Vehiculo
from app.models.operaciones import Proveedor


ADMIN_EMAIL = "test@celr.com"
ADMIN_PASSWORD = "admin123"
CONDUCTOR_CEDULA = "1234567890"
LEGACY_CONDUCTOR_CEDULA = "12345678"
PLACA_PRINCIPAL = "SKN756"
PROVEEDOR_NIT = "900123456"
ALLOW_DEMO_ENV = "CELR_ALLOW_DEMO_SEED"


class SeedDemoError(RuntimeError):
    """Error de guard o de datos de la seed demo."""


@dataclass(frozen=True)
class ResultadoDemo:
    admin_estado: str
    conductor_estado: str
    conductor_id: int
    vehiculo_estado: str
    vehiculo_id: int
    proveedor_estado: str
    proveedor_id: int
    asignacion_estado: str


def _es_produccion(environment: str | None = None) -> bool:
    entorno = settings.ENVIRONMENT if environment is None else environment
    return entorno.strip().lower() == "production"


def demo_habilitado(allow_value: str | None = None) -> bool:
    allow = os.getenv(ALLOW_DEMO_ENV) if allow_value is None else allow_value
    return not _es_produccion() and allow == "1"


def validar_guard_demo(
    environment: str | None = None,
    allow_value: str | None = None,
) -> None:
    """Valida el guard doble antes de abrir una sesión o escribir datos."""
    allow = os.getenv(ALLOW_DEMO_ENV) if allow_value is None else allow_value
    if _es_produccion(environment):
        raise SeedDemoError(
            "Seed demo bloqueado: no se permite ejecutar con ENVIRONMENT=production"
        )
    if allow != "1":
        raise SeedDemoError(
            f"Seed demo bloqueado: se requiere {ALLOW_DEMO_ENV}=1"
        )


def _obtener_admin(db) -> tuple[str, int]:
    usuario = (
        db.query(Usuario)
        .filter(func.lower(Usuario.correo) == ADMIN_EMAIL)
        .first()
    )
    if usuario is not None:
        return "existente", usuario.id

    usuario = Usuario(
        correo=ADMIN_EMAIL,
        contrasena_hash=hash_password(ADMIN_PASSWORD),
        rol="admin",
        activo=True,
        debe_cambiar_contrasena=True,
        password_version=1,
    )
    db.add(usuario)
    db.flush()
    return "creado", usuario.id


def _obtener_conductor(db) -> tuple[str, Conductor]:
    conductor = (
        db.query(Conductor)
        .filter(Conductor.cedula == CONDUCTOR_CEDULA)
        .first()
    )
    if conductor is not None:
        return "existente", conductor

    # No se migra una cédula legacy en esta fase: usarla es no destructivo y
    # evita crear un segundo conductor cuando la base ya tiene el registro viejo.
    conductor_legacy = (
        db.query(Conductor)
        .filter(Conductor.cedula == LEGACY_CONDUCTOR_CEDULA)
        .first()
    )
    if conductor_legacy is not None:
        return "legacy", conductor_legacy

    conductor = Conductor(
        nombre_completo="Juan Perez",
        cedula=CONDUCTOR_CEDULA,
        telefono="3001234567",
        correo="juan.perez@celr.com",
        estado="activo",
    )
    db.add(conductor)
    db.flush()
    return "creado", conductor


def _obtener_vehiculo(db) -> tuple[str, Vehiculo]:
    vehiculo = db.query(Vehiculo).filter(Vehiculo.placa == PLACA_PRINCIPAL).first()
    if vehiculo is not None:
        return "existente", vehiculo

    vehiculo = Vehiculo(
        placa=PLACA_PRINCIPAL,
        marca="Kenworth",
        modelo="2020",
        anio=2020,
        tipo_carroceria="Plataforma",
        capacidad_ton=30,
        estado="activo",
        km_actual=125000,
        km_inicial_sistema=125000,
    )
    db.add(vehiculo)
    db.flush()
    return "creado", vehiculo


def _obtener_proveedor(db) -> tuple[str, Proveedor]:
    proveedor = db.query(Proveedor).filter(Proveedor.nit == PROVEEDOR_NIT).first()
    if proveedor is not None:
        return "existente", proveedor

    proveedor = Proveedor(
        nit=PROVEEDOR_NIT,
        razon_social="Terpel Colombia S.A.",
        nombre_comercial="Terpel",
        tipo="combustible",
        ciudad="Bogota",
    )
    db.add(proveedor)
    db.flush()
    return "creado", proveedor


def _obtener_asignacion(db, conductor_id: int, vehiculo_id: int) -> str:
    asignacion = (
        db.query(ConductorVehiculo)
        .filter(
            ConductorVehiculo.conductor_id == conductor_id,
            ConductorVehiculo.vehiculo_id == vehiculo_id,
            ConductorVehiculo.fecha_fin.is_(None),
        )
        .first()
    )
    if asignacion is not None:
        return "existente"

    db.add(
        ConductorVehiculo(
            conductor_id=conductor_id,
            vehiculo_id=vehiculo_id,
            es_principal=True,
            observaciones="Asignacion principal inicial",
        )
    )
    db.flush()
    return "creada"


def ejecutar_seed_demo(db) -> ResultadoDemo:
    """Ejecuta fixtures demo dentro de la transacción recibida."""
    validar_guard_demo()
    admin_estado, _admin_id = _obtener_admin(db)
    conductor_estado, conductor = _obtener_conductor(db)
    vehiculo_estado, vehiculo = _obtener_vehiculo(db)
    proveedor_estado, proveedor = _obtener_proveedor(db)
    asignacion_estado = _obtener_asignacion(
        db, conductor.id, vehiculo.id
    )
    return ResultadoDemo(
        admin_estado=admin_estado,
        conductor_estado=conductor_estado,
        conductor_id=conductor.id,
        vehiculo_estado=vehiculo_estado,
        vehiculo_id=vehiculo.id,
        proveedor_estado=proveedor_estado,
        proveedor_id=proveedor.id,
        asignacion_estado=asignacion_estado,
    )


def main() -> int:
    try:
        validar_guard_demo()
        db = SessionLocal()
        try:
            resultado = ejecutar_seed_demo(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as exc:
        print(f"ERROR durante el seed demo: {exc}", file=sys.stderr)
        return 1

    print(
        "[OK] Seed demo: "
        f"admin={resultado.admin_estado} "
        f"conductor={resultado.conductor_estado} "
        f"vehiculo={resultado.vehiculo_estado} "
        f"proveedor={resultado.proveedor_estado} "
        f"asignacion={resultado.asignacion_estado}"
    )
    print("--- SEED DEMO COMPLETADO CON EXITO ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
