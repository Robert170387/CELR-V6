import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, Conductor
from app.models.operaciones import ViajeODT, Gasto


def seed(db: Session):
    print("\n=== Seed: Creando vehiculo y conductor ===")
    veh = db.query(Vehiculo).filter(Vehiculo.placa == "SKN756").first()
    if not veh:
        veh = Vehiculo(placa="SKN756", marca="Chevrolet", modelo="Express", anio=2020, estado="activo")
        db.add(veh)
    cond = db.query(Conductor).filter(Conductor.cedula == "12345678").first()
    if not cond:
        cond = Conductor(nombre_completo="Juan Perez", cedula="12345678", estado="activo")
        db.add(cond)
    db.commit()
    db.refresh(veh)
    db.refresh(cond)
    print(f"Vehiculo: id={veh.id}, placa={veh.placa}")
    print(f"Conductor: id={cond.id}, cedula={cond.cedula}")
    return veh.id, cond.id


def test_create_viaje(db: Session, veh_id: int, cond_id: int):
    print("\n=== Test 1: Crear viaje de prueba (numero_odt autogenerado) ===")
    viaje = ViajeODT(
        vehiculo_id=veh_id,
        conductor_id=cond_id,
        origen="Bogota",
        destino="Medellin",
        fecha_salida="2026-09-16",
        estado="en_curso",
    )
    db.add(viaje)
    db.commit()
    db.refresh(viaje)
    print(f"Viaje creado: id={viaje.id}, numero_odt={viaje.numero_odt}")
    assert viaje.numero_odt and viaje.numero_odt.startswith("ODT-"), "numero_odt no autogenerado"
    return viaje


def test_duplicate_gasto(db: Session, viaje_id: int, veh_id: int):
    print("\n=== Test 2: Registrar gasto con hash unico ===")
    h1 = f"hash-{datetime.utcnow().strftime('%H%M%S%f')}-1"
    gasto1 = Gasto(
        viaje_id=viaje_id,
        vehiculo_id=veh_id,
        categoria="combustible",
        fecha_gasto="2026-09-16",
        valor_total=50000,
        hash_comprobante=h1,
    )
    db.add(gasto1)
    db.commit()
    db.refresh(gasto1)
    print(f"Gasto creado: id={gasto1.id}, hash_comprobante={gasto1.hash_comprobante}")

    print("\n=== Test 3: Intentar registrar gasto con hash duplicado ===")
    gasto2 = Gasto(
        viaje_id=viaje_id,
        vehiculo_id=veh_id,
        categoria="peaje",
        fecha_gasto="2026-09-16",
        valor_total=25000,
        hash_comprobante=h1,
    )
    db.add(gasto2)
    try:
        db.commit()
        print("ERROR: Se esperaba una excepcion de constraint unico")
    except Exception as e:
        db.rollback()
        print(f"Excepcion capturada como se esperaba: {type(e).__name__}")
        print("OK: Constraint unico detectado - el endpoint retornaria HTTP 400 'Gasto duplicado detectado'")


def test_listar_gastos_viaje(db: Session, viaje_id: int):
    print("\n=== Test 4: Listar gastos del viaje ===")
    gastos = db.query(Gasto).filter(Gasto.viaje_id == viaje_id).all()
    print(f"Gastos encontrados para viaje {viaje_id}: {len(gastos)}")


def test_listar_viajes(db: Session):
    print("\n=== Test 5: Listar viajes activos ===")
    viajes = db.query(ViajeODT).filter(ViajeODT.estado == "en_curso").all()
    print(f"Viajes activos: {len(viajes)}")
    for v in viajes:
        print(f" - id={v.id}, numero_odt={v.numero_odt}, estado={v.estado}")


def main():
    print("Iniciando prueba de endpoints CELR v6...")
    db = SessionLocal()
    viaje = None
    try:
        veh_id, cond_id = seed(db)
        viaje = test_create_viaje(db, veh_id, cond_id)
        test_duplicate_gasto(db, viaje.id, veh_id)
        test_listar_gastos_viaje(db, viaje.id)
        test_listar_viajes(db)
        print("\n[TODOS LOS TESTS PASARON]")
    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpieza 2.B: DELETE real del viaje y sus gastos creados por esta corrida.
        # El vehículo/conductor (SKN756 / cédula 12345678) se reutilizan del seed,
        # NO se borran.
        try:
            if viaje is not None:
                db.query(Gasto).filter(Gasto.viaje_id == viaje.id).delete(synchronize_session=False)
                db.query(ViajeODT).filter(ViajeODT.id == viaje.id).delete(synchronize_session=False)
                db.commit()
        except Exception:
            db.rollback()
        db.close()


if __name__ == "__main__":
    main()
