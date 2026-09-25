import sys
import os
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, Conductor, RefreshToken, Usuario as UsuarioModel
from app.models.operaciones import ViajeODT, Gasto
from app.models.financiero import FlypassTransaccion, Ingreso, LiquidacionConductor
from app.schemas.liquidacion import LiquidacionCreate
from app.services.operaciones import recalcular_viaje
from _test_helpers import capturar_token_ids, limpiar_tokens_nuevos


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


def crear_peaje_legalizado(db: Session, viaje: ViajeODT) -> Gasto:
    """Crea un gasto peaje que legaliza la transacción Flypass."""
    gasto = Gasto(
        viaje_id=viaje.id,
        vehiculo_id=viaje.vehiculo_id,
        categoria="peaje",
        fecha_gasto=viaje.fecha_salida,
        valor_total=Decimal("50000.00"),
        responsable_pago="empresa",
        asumido_por="empresa",
        metodo_pago="tarjeta",
        estado_pago="legalizado",
        hash_comprobante=f"hash-flypass-legal-{uuid.uuid4().hex}",
    )
    db.add(gasto)
    db.flush()
    recalcular_viaje(db, viaje)
    db.commit()
    db.refresh(gasto)
    return gasto


def crear_flypass(
    db: Session,
    viaje: ViajeODT,
    gasto_id: int | None = None,
) -> FlypassTransaccion:
    """Crea una transacción Flypass de prueba, pendiente si no tiene gasto."""
    transaccion = FlypassTransaccion(
        vehiculo_id=viaje.vehiculo_id,
        fecha_transaccion=datetime(
            viaje.fecha_salida.year,
            viaje.fecha_salida.month,
            viaje.fecha_salida.day,
            tzinfo=timezone.utc,
        ),
        nombre_peaje="Peaje de prueba",
        ciudad_peaje="Bogota",
        valor=Decimal("50000.00"),
        num_transaccion_flypass=f"TEST-FLYPASS-{uuid.uuid4().hex}",
        viaje_id=viaje.id,
        gasto_id=gasto_id,
    )
    db.add(transaccion)
    db.commit()
    db.refresh(transaccion)
    return transaccion


def payload_cierre_individual(
    viaje_id: int,
    conductor_id: int,
    vehiculo_id: int,
    periodo_inicio: str,
    periodo_fin: str,
) -> dict:
    return {
        "conductor_id": conductor_id,
        "vehiculo_id": vehiculo_id,
        "periodo_inicio": periodo_inicio,
        "periodo_fin": periodo_fin,
        "comision_flete": 85000,
        "porcentaje_comision": 10,
        "anticipos_entregados": 0,
        "gastos_a_cargo_conductor": 0,
        "viajes_ids": [viaje_id],
        "estado": "borrador",
    }


def payload_cierre_mensual(conductor_id: int, periodo_ym: str) -> dict:
    return {
        "conductor_id": conductor_id,
        "periodo_ym": periodo_ym,
        "salario_basico": 0,
        "auxilio_transporte": 0,
        "papeleria": 0,
        "descuento_salud_pension": 0,
        "bonificaciones": 0,
        "viaticos_reconocidos": 0,
        "otros_haberes": 0,
        "anticipos_entregados": 0,
        "gastos_a_cargo_conductor": 0,
        "prestamos": 0,
        "otros_descuentos": 0,
    }


def cliente_autenticado():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"correo": "test@celr.com", "contrasena": "admin123"},
    )
    assert login.status_code == 200, f"Login falló: {login.status_code} {login.text}"
    return client, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_flypass_bloquea_cierre_individual(
    db: Session,
    viaje: ViajeODT,
    flypass_creados: list,
    client,
    headers: dict,
) -> None:
    print("\n=== T1: ODT con Flypass pendiente -> 409 ===")
    flypass = crear_flypass(db, viaje)
    flypass_creados.append(flypass)
    response = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje.id}",
        json=payload_cierre_individual(
            viaje.id, viaje.conductor_id, viaje.vehiculo_id, "2026-10-01", "2026-10-31"
        ),
        headers=headers,
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["cercable"] is False
    assert any(
        "Flypass" in mensaje
        for item in detail["bloqueos"]
        for mensaje in item["bloqueos"]
    )
    db.refresh(viaje)
    assert viaje.estado == "en_curso"
    assert not db.query(LiquidacionConductor).filter(
        LiquidacionConductor.viajes_ids.contains([viaje.id])
    ).first()
    print("  409 con bloqueo Flypass y ODT sin mutaciones: OK")


def test_flypass_legalizado_cierra_individual(
    db: Session,
    viaje: ViajeODT,
    flypass_creados: list,
    client,
    headers: dict,
) -> None:
    print("\n=== T2: ODT con Flypass legalizado -> cierre normal ===")
    gasto = crear_peaje_legalizado(db, viaje)
    flypass = crear_flypass(db, viaje, gasto_id=gasto.id)
    flypass_creados.append(flypass)
    response = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje.id}",
        json=payload_cierre_individual(
            viaje.id, viaje.conductor_id, viaje.vehiculo_id, "2026-10-01", "2026-10-31"
        ),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    print("  cierre con Flypass legalizado: OK")


def test_sin_flypass_cierra_individual(
    db: Session,
    viaje: ViajeODT,
    client,
    headers: dict,
) -> None:
    print("\n=== T3: ODT sin Flypass -> cierre normal ===")
    response = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje.id}",
        json=payload_cierre_individual(
            viaje.id, viaje.conductor_id, viaje.vehiculo_id, "2026-10-01", "2026-10-31"
        ),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    print("  cierre sin Flypass: OK")


def test_cierre_mensual_bloqueado_por_flypass(
    db: Session,
    viaje: ViajeODT,
    flypass_creados: list,
    client,
    headers: dict,
) -> None:
    print("\n=== T4: cierre mensual con ODT bloqueada -> 409 ===")
    flypass = crear_flypass(db, viaje)
    flypass_creados.append(flypass)
    response = client.post(
        "/api/v1/liquidaciones/cierre-mensual",
        json=payload_cierre_mensual(viaje.conductor_id, "2026-11"),
        headers=headers,
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["cercable"] is False
    assert any(
        "Flypass" in mensaje
        for item in detail["bloqueos"]
        for mensaje in item["bloqueos"]
    )
    db.refresh(viaje)
    assert viaje.estado == "en_curso"
    assert not db.query(LiquidacionConductor).filter(
        LiquidacionConductor.es_cierre_mensual.is_(True),
        LiquidacionConductor.periodo_ym == "2026-11",
        LiquidacionConductor.eliminado_en.is_(None),
    ).first()
    print("  409 mensual y ninguna ODT marcada: OK")


def test_cierre_mensual_limpio(
    db: Session,
    viaje: ViajeODT,
    client,
    headers: dict,
) -> None:
    print("\n=== T5: cierre mensual limpio -> normal ===")
    response = client.post(
        "/api/v1/liquidaciones/cierre-mensual",
        json=payload_cierre_mensual(viaje.conductor_id, "2026-12"),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    print("  cierre mensual limpio: OK")



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


def test_comision_override_calcular_servidor(
    db: Session,
    veh_id: int,
    cond_id: int,
    viajes_creados: list,
) -> None:
    """TL-OV1..TL-OV5: la liquidación respeta la precedencia de comisión de la ODT."""
    from app.api.v1.endpoints.liquidaciones import _calcular_servidor

    conductor = db.query(Conductor).filter(Conductor.id == cond_id).first()
    assert conductor is not None
    default_original = conductor.porcentaje_comision_default

    def crear_odt(porcentaje: Decimal | None) -> ViajeODT:
        viaje = ViajeODT(
            vehiculo_id=veh_id,
            conductor_id=cond_id,
            origen="Bogota",
            destino="Cali",
            fecha_salida=date(2026, 9, 18),
            valor_flete_manifiesto=Decimal("1000000.00"),
            retefuente_porcentaje=Decimal("10.00"),
            reteica_porcentaje=Decimal("5.00"),
            porcentaje_comision=porcentaje,
            estado="en_curso",
        )
        db.add(viaje)
        db.flush()
        recalcular_viaje(db, viaje)
        db.commit()
        db.refresh(viaje)
        viajes_creados.append(viaje)
        return viaje

    def verificar(etiqueta: str, porcentaje_odt: Decimal | None, default_conductor: Decimal | None, esperado_pct: Decimal) -> None:
        conductor.porcentaje_comision_default = default_conductor
        db.commit()
        viaje = crear_odt(porcentaje_odt)
        resultado = _calcular_servidor(db, viaje)
        esperado_comision = (Decimal("850000.00") * esperado_pct / Decimal("100")).quantize(Decimal("0.01"))
        assert resultado["porcentaje_comision"] == esperado_pct, (
            f"{etiqueta}: porcentaje inesperado {resultado['porcentaje_comision']} != {esperado_pct}"
        )
        assert resultado["comision_flete"] == esperado_comision, (
            f"{etiqueta}: comisión inesperada {resultado['comision_flete']} != {esperado_comision}"
        )
        print(f"  [OK] {etiqueta}: pct={resultado['porcentaje_comision']} comision={resultado['comision_flete']}")

    try:
        verificar("TL-OV1", Decimal("15.00"), Decimal("10.00"), Decimal("15.00"))
        verificar("TL-OV2", None, Decimal("10.00"), Decimal("10.00"))
        verificar("TL-OV3", Decimal("0.00"), Decimal("10.00"), Decimal("0.00"))
        verificar("TL-OV4", Decimal("15.00"), None, Decimal("15.00"))
        verificar("TL-OV5", None, None, Decimal("10.00"))
    finally:
        conductor.porcentaje_comision_default = default_original
        db.commit()


def main():
    print("Iniciando prueba de liquidaciones CELR v6...")
    db = SessionLocal()
    tokens_antes_test = capturar_token_ids(db, "test@celr.com")
    tokens_antes_admin2 = capturar_token_ids(db, "admin2@celr.com")
    viajes_creados = []
    flypass_creados = []
    try:
        admin = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
        assert admin is not None, "Se requiere el usuario admin test@celr.com (ejecuta test_auth.py o seed.py)"
        admin2 = seed_admin2(db)
        veh_id, cond_id = seed(db)
        viaje = create_test_viaje(db, veh_id, cond_id)
        viajes_creados.append(viaje)
        create_test_gastos(db, viaje.id, veh_id, cond_id)
        create_test_ingreso(db, viaje.id, veh_id)
        test_calcular_liquidacion(db, viaje.id)
        test_comision_override_calcular_servidor(db, veh_id, cond_id, viajes_creados)
        viaje2 = create_test_viaje_extra(db, veh_id, cond_id)
        viajes_creados.append(viaje2)
        test_cerrar_comision_incorrecta(db, viaje2, cond_id, veh_id, admin)
        viaje3 = create_test_viaje_extra(db, veh_id, cond_id)
        viajes_creados.append(viaje3)
        test_aprobar_liquidacion(db, viaje3, cond_id, veh_id, admin, admin2)
        test_cerrar_liquidacion(db, viaje.id, cond_id, veh_id, admin)

        client, headers = cliente_autenticado()
        viaje_t1 = create_test_viaje_extra(db, veh_id, cond_id, date(2026, 10, 5))
        viajes_creados.append(viaje_t1)
        test_flypass_bloquea_cierre_individual(
            db, viaje_t1, flypass_creados, client, headers
        )

        viaje_t2 = create_test_viaje_extra(db, veh_id, cond_id, date(2026, 10, 10))
        viajes_creados.append(viaje_t2)
        test_flypass_legalizado_cierra_individual(
            db, viaje_t2, flypass_creados, client, headers
        )

        viaje_t3 = create_test_viaje_extra(db, veh_id, cond_id, date(2026, 10, 15))
        viajes_creados.append(viaje_t3)
        test_sin_flypass_cierra_individual(db, viaje_t3, client, headers)

        viaje_t4 = create_test_viaje_extra(db, veh_id, cond_id, date(2026, 11, 5))
        viajes_creados.append(viaje_t4)
        test_cierre_mensual_bloqueado_por_flypass(
            db, viaje_t4, flypass_creados, client, headers
        )

        viaje_t5 = create_test_viaje_extra(db, veh_id, cond_id, date(2026, 12, 5))
        viajes_creados.append(viaje_t5)
        test_cierre_mensual_limpio(db, viaje_t5, client, headers)
        print("\n[TODOS LOS TESTS DE LIQUIDACIONES PASARON]")
    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpieza 2.B: DELETE real en orden inverso de FK, solo lo creado por esta
        # corrida. Nunca borra el seed (test@celr.com, SKN756, conductor legacy 12345678).
        try:
            for v in viajes_creados:
                db.query(LiquidacionConductor).filter(
                    LiquidacionConductor.viajes_ids.contains([v.id])
                ).delete(synchronize_session=False)
            via_ids = [v.id for v in viajes_creados]
            if flypass_creados:
                db.query(FlypassTransaccion).filter(
                    FlypassTransaccion.id.in_([f.id for f in flypass_creados])
                ).delete(synchronize_session=False)
            if via_ids:
                db.query(Ingreso).filter(Ingreso.viaje_id.in_(via_ids)).delete(synchronize_session=False)
                db.query(Gasto).filter(Gasto.viaje_id.in_(via_ids)).delete(synchronize_session=False)
                db.query(ViajeODT).filter(ViajeODT.id.in_(via_ids)).delete(synchronize_session=False)
            limpiar_tokens_nuevos(db, "admin2@celr.com", tokens_antes_admin2)
            admin2 = db.query(UsuarioModel).filter(UsuarioModel.correo == "admin2@celr.com").first()
            if admin2:
                # El usuario temporal se elimina; también se limpian tokens viejos
                # de una corrida anterior que pudieran haber quedado.
                db.query(RefreshToken).filter(RefreshToken.usuario_id == admin2.id).delete(
                    synchronize_session=False
                )
                # Liquidaciones de corridas antiguas/interrumpidas que referencian a
                # admin2 (creado_por/aprobado_por) — sin esto el DELETE de admin2 rompe por FK.
                db.query(LiquidacionConductor).filter(
                    or_(
                        LiquidacionConductor.creado_por == admin2.id,
                        LiquidacionConductor.aprobado_por == admin2.id,
                    )
                ).delete(synchronize_session=False)
                db.delete(admin2)
            limpiar_tokens_nuevos(db, "test@celr.com", tokens_antes_test)
            db.commit()
        except Exception as e:
            print(f"\n[CLEANUP ERROR]: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            raise
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


def create_test_viaje_extra(
    db: Session,
    veh_id: int,
    cond_id: int,
    fecha_salida: date = date(2026, 9, 17),
) -> ViajeODT:
    viaje = ViajeODT(
        vehiculo_id=veh_id,
        conductor_id=cond_id,
        origen="Bogota",
        destino="Cali",
        fecha_salida=fecha_salida,
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
