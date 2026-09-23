import sys
import os
from datetime import datetime, date
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, Conductor, Usuario as UsuarioModel
from app.models.operaciones import ViajeODT, Gasto
from app.models.financiero import Ingreso, LiquidacionConductor
from app.schemas.liquidacion import LiquidacionCreate
from app.services.operaciones import recalcular_viaje


def seed(db: Session):
    print("\n=== Seed: Verificando vehiculo y conductor ===")
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


def create_test_viaje(db: Session, veh_id: int, cond_id: int):
    print("\n=== Crear viaje de prueba (numero_odt autogenerado) ===")
    viaje = ViajeODT(
        vehiculo_id=veh_id,
        conductor_id=cond_id,
        origen="Bogota",
        destino="Medellin",
        fecha_salida=date(2026, 9, 16),
        valor_flete_manifiesto=Decimal("1000000.00"),
        # FASE A2: el cliente envia los PORCENTAJES; los valores los deriva el servidor (10% y 5%)
        retefuente_porcentaje=Decimal("10.00"),
        reteica_porcentaje=Decimal("5.00"),
        estado="en_curso",
    )
    db.add(viaje)
    db.flush()
    recalcular_viaje(db, viaje)
    db.commit()
    db.refresh(viaje)
    print(f"Viaje creado: id={viaje.id}, numero_odt={viaje.numero_odt}, flete_neto={viaje.flete_neto}")
    return viaje


def create_test_gastos(db: Session, viaje_id: int, veh_id: int, cond_id: int):
    print("\n=== Crear 2 gastos de prueba ===")
    h1 = f"hash-liq-{datetime.utcnow().strftime('%H%M%S%f')}-1"
    h2 = f"hash-liq-{datetime.utcnow().strftime('%H%M%S%f')}-2"

    gasto1 = Gasto(
        viaje_id=viaje_id, vehiculo_id=veh_id, proveedor_id=None,
        categoria="combustible", fecha_gasto=date(2026, 9, 16),
        valor_total=Decimal("300000.00"), km_registro=Decimal("500.00"),
        responsable_pago="conductor", asumido_por="empresa",
        hash_comprobante=h1,
    )
    gasto2 = Gasto(
        viaje_id=viaje_id, vehiculo_id=veh_id, proveedor_id=None,
        categoria="peaje", fecha_gasto=date(2026, 9, 16),
        valor_total=Decimal("50000.00"), km_registro=Decimal("600.00"),
        responsable_pago="conductor", asumido_por="empresa",
        hash_comprobante=h2,
    )
    db.add(gasto1)
    db.add(gasto2)
    db.commit()
    db.refresh(gasto1)
    db.refresh(gasto2)
    print(f"Gasto 1: id={gasto1.id}, valor={gasto1.valor_total}, asumido_por={gasto1.asumido_por}")
    print(f"Gasto 2: id={gasto2.id}, valor={gasto2.valor_total}, asumido_por={gasto2.asumido_por}")
    return gasto1, gasto2


def create_test_ingreso(db: Session, viaje_id: int, veh_id: int):
    print("\n=== Crear anticipo de prueba ===")
    ing = Ingreso(
        viaje_id=viaje_id, vehiculo_id=veh_id, tipo_ingreso="anticipo_manifiesto",
        fecha_ingreso=date(2026, 9, 16), valor=Decimal("100000.00"),
        descripcion="Anticipo de flete", estado_pago="recibido",
    )
    db.add(ing)
    db.commit()
    db.refresh(ing)
    print(f"Ingreso creado: id={ing.id}, valor={ing.valor}, tipo={ing.tipo_ingreso}")
    return ing


def test_calcular_liquidacion(db: Session, viaje_id: int):
    print("\n=== Test 1: GET /api/v1/liquidaciones/calcular/{viaje_id} ===")
    from app.api.v1.endpoints.liquidaciones import calcular_liquidacion
    result = calcular_liquidacion(viaje_id, db)
    print(f"  flete_neto = {result.flete_neto}")
    print(f"  total_gastos_empresa = {result.total_gastos_empresa}")
    print(f"  total_anticipos = {result.total_anticipos}")
    print(f"  comision_flete = {result.comision_flete}")
    print(f"  saldo_neto = {result.saldo_neto}")

    # Validacion matematica: saldo_neto = flete_neto - gastos_empresa - anticipos - comision
    expected = result.flete_neto - result.total_gastos_empresa - result.total_anticipos - result.comision_flete
    assert abs(float(result.saldo_neto) - float(expected)) < 0.01, f"Saldo neto incorrecto: {result.saldo_neto} vs esperado {expected}"
    print(f"  Validacion matematica PASADA: saldo_neto={result.saldo_neto} == esperado={expected}")
    return result


def test_cerrar_liquidacion(db: Session, viaje_id: int, cond_id: int, veh_id: int, current_user: UsuarioModel):
    print("\n=== Test 2: POST /api/v1/liquidaciones/cerrar/{viaje_id} ===")
    from app.api.v1.endpoints.liquidaciones import cerrar_liquidacion
    from app.models.financiero import LiquidacionConductor

    liq_data = LiquidacionCreate(
        conductor_id=cond_id,
        vehiculo_id=veh_id,
        periodo_inicio=date(2026, 9, 1),
        periodo_fin=date(2026, 9, 16),
        comision_flete=Decimal("85000.00"),
        porcentaje_comision=Decimal("10.00"),
        bonificaciones=Decimal("0.00"),
        viaticos_reconocidos=Decimal("0.00"),
        otros_haberes=Decimal("0.00"),
        anticipos_entregados=Decimal("100000.00"),
        gastos_a_cargo_conductor=Decimal("0.00"),
        prestamos=Decimal("0.00"),
        otros_descuentos=Decimal("0.00"),
        viajes_ids=[viaje_id],
        estado="aprobado",
    )
    from fastapi import Request
    result = cerrar_liquidacion(viaje_id, liq_data, db, current_user)
    print(f"  Resultado: {result}")

    # Verificar que el viaje esta liquidado
    viaje = db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
    assert viaje.estado == "liquidado", f"Estado viaje incorrecto: {viaje.estado}"
    print(f"  Estado viaje confirmado: {viaje.estado}")

    # Verificar que liquidacion_conductores tiene el registro
    liq = db.query(LiquidacionConductor).filter(LiquidacionConductor.viajes_ids.contains([viaje_id])).first()
    assert liq is not None, "LiquidacionConductor no encontrada"
    print(f"  LiquidacionConductor creada: id={liq.id}, saldo_neto={liq.saldo_neto}")
    print(f"  [OK] Test cerrar_liquidacion PASADO")


def main():
    print("Iniciando prueba de liquidaciones CELR v6...")
    db = SessionLocal()
    try:
        admin = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
        assert admin is not None, "Se requiere el usuario admin test@celr.com (ejecuta test_auth.py o seed.py)"
        admin2 = seed_admin2(db)
        veh_id, cond_id = seed(db)
        viaje = create_test_viaje(db, veh_id, cond_id)
        create_test_gastos(db, viaje.id, veh_id, cond_id)
        create_test_ingreso(db, viaje.id, veh_id)
        test_calcular_liquidacion(db, viaje.id)
        viaje2 = create_test_viaje_extra(db, veh_id, cond_id)
        test_cerrar_comision_incorrecta(db, viaje2, cond_id, veh_id, admin)
        viaje3 = create_test_viaje_extra(db, veh_id, cond_id)
        test_aprobar_liquidacion(db, viaje3, cond_id, veh_id, admin, admin2)
        test_cerrar_liquidacion(db, viaje.id, cond_id, veh_id, admin)
        print("\n[TODOS LOS TESTS DE LIQUIDACIONES PASARON]")
    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def seed_admin2(db: Session) -> UsuarioModel:
    from app.core.security import hash_password
    u = db.query(UsuarioModel).filter(UsuarioModel.correo == "admin2@celr.com").first()
    if not u:
        u = UsuarioModel(
            correo="admin2@celr.com",
            contrasena_hash=hash_password("admin123"),
            rol="admin",
            activo=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        print(f"Admin2 creado: id={u.id}")
    return u


def create_test_viaje_extra(db: Session, veh_id: int, cond_id: int) -> ViajeODT:
    from datetime import date
    viaje = ViajeODT(
        vehiculo_id=veh_id,
        conductor_id=cond_id,
        origen="Bogota",
        destino="Cali",
        fecha_salida=date(2026, 9, 17),
        valor_flete_manifiesto=Decimal("1000000.00"),
        retefuente_porcentaje=Decimal("10.00"),
        reteica_porcentaje=Decimal("5.00"),
        estado="en_curso",
    )
    db.add(viaje)
    db.flush()
    recalcular_viaje(db, viaje)
    db.commit()
    db.refresh(viaje)
    return viaje


def test_cerrar_comision_incorrecta(db: Session, viaje: ViajeODT, cond_id: int, veh_id: int, current_user: UsuarioModel):
    print("\n=== Test 3: cerrar con comisión alterada -> 409 ===")
    from fastapi import HTTPException
    from app.api.v1.endpoints.liquidaciones import cerrar_liquidacion

    liq_data = LiquidacionCreate(
        conductor_id=cond_id,
        vehiculo_id=veh_id,
        periodo_inicio=date(2026, 9, 1),
        periodo_fin=date(2026, 9, 17),
        comision_flete=Decimal("99999.00"),
        porcentaje_comision=Decimal("10.00"),
        anticipos_entregados=Decimal("0.00"),
        gastos_a_cargo_conductor=Decimal("0.00"),
        viajes_ids=[viaje.id],
        estado="borrador",
    )
    try:
        cerrar_liquidacion(viaje.id, liq_data, db, current_user)
    except HTTPException as e:
        assert e.status_code == 409, f"esperaba 409, obtuve {e.status_code}"
        print(f"  409 obtenido: {e.detail}")
        db.rollback()
        return
    raise AssertionError("Deberia haber lanzado 409 por comision incorrecta")


def test_aprobar_liquidacion(db: Session, viaje: ViajeODT, cond_id: int, veh_id: int, admin: UsuarioModel, admin2: UsuarioModel):
    print("\n=== Test 4: aprobar liquidación (403 self / 200 otro admin) ===")
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje.id}",
        json={
            "conductor_id": cond_id,
            "vehiculo_id": veh_id,
            "periodo_inicio": "2026-09-01",
            "periodo_fin": "2026-09-17",
            "comision_flete": 85000,
            "porcentaje_comision": 10,
            "anticipos_entregados": 0,
            "gastos_a_cargo_conductor": 0,
            "viajes_ids": [viaje.id],
            "estado": "borrador",
        },
        headers=headers,
    )
    assert r.status_code == 200, f"cerrar fallo: {r.status_code} {r.text}"
    liq_id = r.json()["liquidacion_id"]
    print(f"  liquidación creada id={liq_id}")

    r = client.post(f"/api/v1/liquidaciones/{liq_id}/aprobar", headers=headers)
    assert r.status_code == 403, f"auto-aprobación deberia ser 403: {r.status_code} {r.text}"
    print(f"  aprobar por quien creó -> 403: {r.json()['detail']}")

    r = client.post("/api/v1/auth/login", json={"correo": "admin2@celr.com", "contrasena": "admin123"})
    headers2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post(f"/api/v1/liquidaciones/{liq_id}/aprobar", headers=headers2)
    assert r.status_code == 200, f"aprobar con otro admin fallo: {r.status_code} {r.text}"
    assert r.json()["aprobado_por"] == admin2.id
    print(f"  aprobar por otro admin -> 200, aprobado_por={r.json()['aprobado_por']}")

    r = client.post(f"/api/v1/liquidaciones/{liq_id}/aprobar", headers=headers2)
    assert r.status_code == 400, f"aprobar dos veces deberia ser 400: {r.status_code}"
    print(f"  aprobar dos veces -> 400: {r.json()['detail']}")

    r = client.post("/api/v1/liquidaciones/999999/aprobar", headers=headers2)
    assert r.status_code == 404, f"aprobar inexistente deberia ser 404: {r.status_code}"
    print(f"  aprobar inexistente -> 404: PASADO")


if __name__ == "__main__":
    main()
