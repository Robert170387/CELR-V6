from app.db.session import SessionLocal
from app.models.flota import Usuario, Vehiculo, Conductor, ConductorVehiculo
from app.models.operaciones import Proveedor
from app.core.security import hash_password, verify_password

ADMIN_EMAIL = "test@celr.com"
ADMIN_PASSWORD = "admin123"
CONDUCTOR_CEDULA = "1234567890"
LEGACY_CONDUCTOR_CEDULA = "12345678"
PLACA_PRINCIPAL = "SKN756"
PROVEEDOR_NIT = "900123456"


def _password_matches(password: str, stored_hash: str) -> bool:
    try:
        return verify_password(password, stored_hash)
    except Exception:
        return False


def upsert_usuario(db) -> Usuario:
    usuario = db.query(Usuario).filter_by(correo=ADMIN_EMAIL).first()
    if not usuario:
        usuario = Usuario(
            correo=ADMIN_EMAIL,
            contrasena_hash=hash_password(ADMIN_PASSWORD),
            rol="admin",
            activo=True,
        )
        db.add(usuario)
    else:
        if not _password_matches(ADMIN_PASSWORD, usuario.contrasena_hash):
            usuario.contrasena_hash = hash_password(ADMIN_PASSWORD)
        if usuario.rol != "admin":
            usuario.rol = "admin"
        if not usuario.activo:
            usuario.activo = True
    return usuario


def upsert_conductor(db) -> Conductor:
    conductor = db.query(Conductor).filter_by(cedula=CONDUCTOR_CEDULA).first()
    if conductor:
        conductor.nombre_completo = "Juan Perez"
        conductor.telefono = "3001234567"
        conductor.correo = "juan.perez@celr.com"
        conductor.estado = "activo"
        return conductor

    legacy = db.query(Conductor).filter_by(cedula=LEGACY_CONDUCTOR_CEDULA).first()
    if legacy:
        legacy.cedula = CONDUCTOR_CEDULA
        legacy.nombre_completo = "Juan Perez"
        legacy.telefono = "3001234567"
        legacy.correo = "juan.perez@celr.com"
        legacy.estado = "activo"
        return legacy

    conductor = Conductor(
        nombre_completo="Juan Perez",
        cedula=CONDUCTOR_CEDULA,
        telefono="3001234567",
        correo="juan.perez@celr.com",
        estado="activo",
    )
    db.add(conductor)
    return conductor


def upsert_vehiculo(db) -> Vehiculo:
    vehiculo = db.query(Vehiculo).filter_by(placa=PLACA_PRINCIPAL).first()
    if not vehiculo:
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
    else:
        vehiculo.marca = "Kenworth"
        vehiculo.modelo = "2020"
        vehiculo.anio = 2020
        vehiculo.tipo_carroceria = vehiculo.tipo_carroceria or "Plataforma"
        vehiculo.capacidad_ton = vehiculo.capacidad_ton or 30
        vehiculo.estado = "activo"
        vehiculo.km_actual = 125000
        vehiculo.km_inicial_sistema = vehiculo.km_inicial_sistema or 125000
    return vehiculo


def upsert_proveedor(db) -> Proveedor:
    proveedor = db.query(Proveedor).filter_by(nit=PROVEEDOR_NIT).first()
    if not proveedor:
        proveedor = Proveedor(
            nit=PROVEEDOR_NIT,
            razon_social="Terpel Colombia S.A.",
            nombre_comercial="Terpel",
            tipo="combustible",
            ciudad="Bogota",
        )
        db.add(proveedor)
    return proveedor


def main():
    db = SessionLocal()
    try:
        upsert_usuario(db)
        upsert_conductor(db)
        upsert_vehiculo(db)
        upsert_proveedor(db)
        db.flush()

        conductor = db.query(Conductor).filter_by(cedula=CONDUCTOR_CEDULA).first()
        vehiculo = db.query(Vehiculo).filter_by(placa=PLACA_PRINCIPAL).first()
        if conductor and vehiculo:
            asignacion = db.query(ConductorVehiculo).filter_by(
                conductor_id=conductor.id,
                vehiculo_id=vehiculo.id,
                fecha_fin=None,
            ).first()
            if not asignacion:
                db.add(ConductorVehiculo(
                    conductor_id=conductor.id,
                    vehiculo_id=vehiculo.id,
                    es_principal=True,
                    observaciones="Asignacion principal inicial",
                ))

        db.commit()
        print("--- SEED COMPLETADO CON EXITO ---")
    except Exception as e:
        db.rollback()
        print(f"ERROR durante el seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()