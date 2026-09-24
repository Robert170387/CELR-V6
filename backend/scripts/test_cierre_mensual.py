import sys
import os
from datetime import date
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, Conductor, Usuario as UsuarioModel
from app.models.operaciones import ViajeODT
from app.models.financiero import LiquidacionConductor
from app.services.operaciones import recalcular_viaje
from _test_helpers import capturar_token_ids, limpiar_tokens_nuevos


def seed(db: Session):
    print("\n=== Seed: verificando vehiculo y conductor ===")
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


def crear_viaje(db: Session, veh_id: int, cond_id: int, fecha: date, etiqueta: str) -> ViajeODT:
    viaje = ViajeODT(
        vehiculo_id=veh_id,
        conductor_id=cond_id,
        origen="Bogota",
        destino="Medellin",
        fecha_salida=fecha,
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
    print(f"  Viaje {etiqueta}: id={viaje.id}, fecha={viaje.fecha_salida}, flete_neto={viaje.flete_neto}")
    return viaje


def test_01_crear_cierre_mensual(client, headers, cond_id, viajes_jun):
    print("\n=== Test 1: POST /cierre-mensual (2026-06, 2 viajes) ===")
    r = client.post(
        "/api/v1/liquidaciones/cierre-mensual",
        json={
            "conductor_id": cond_id,
            "periodo_ym": "2026-06",
            "salario_basico": 1300000,
            "auxilio_transporte": 140606,
            "papeleria": 0,
            "descuento_salud_pension": 130000,
            "bonificaciones": 0,
            "viaticos_reconocidos": 0,
            "otros_haberes": 0,
            "anticipos_entregados": 0,
            "gastos_a_cargo_conductor": 0,
            "prestamos": 0,
            "otros_descuentos": 0,
            "observaciones": "Cierre mensual test",
        },
        headers=headers,
    )
    assert r.status_code == 200, f"cierre-mensual fallo: {r.status_code} {r.text}"
    body = r.json()
    print(f"  cierre creado: id={body['id']} periodo_ym={body['periodo_ym']} "
          f"total_viajes={body['total_viajes']} comision_flete={body['comision_flete']} "
          f"saldo_neto={body['saldo_neto']}")
    assert body["es_cierre_mensual"] is True
    assert body["estado"] == "borrador"
    assert body["vehiculo_id"] is None, "el cierre mensual no debe tener vehiculo"
    assert body["periodo_ym"] == "2026-06"
    assert body["viajes_ids"] and set(body["viajes_ids"]) == {v.id for v in viajes_jun}
    # comision_flete = comisiones_total (sumando unico de total_haberes)
    assert Decimal(body["comision_flete"]) == Decimal(body["comisiones_total"])
    # 2 viajes de 850000 flete_neto al 10% -> comisiones_total = 170000
    assert Decimal(body["comisiones_total"]) == Decimal("170000.00"), body["comisiones_total"]
    # los viajes del mes quedaron liquidados
    db_viajes = [v for v in viajes_jun]
    # (se verifican los estados mas abajo con Session)
    return body["id"]


def test_02_duplicado_409(client, headers, cond_id):
    print("\n=== Test 2: cierre-mensual duplicado -> 409 ===")
    r = client.post(
        "/api/v1/liquidaciones/cierre-mensual",
        json={"conductor_id": cond_id, "periodo_ym": "2026-06"},
        headers=headers,
    )
    assert r.status_code == 409, f"esperaba 409 por duplicado, obtuve {r.status_code} {r.text}"
    print(f"  409 obtenido: {r.json()['detail']}")


def test_03_get_cierre_mensual(client, headers, cond_id, liq_id):
    print("\n=== Test 3: GET /cierre-mensual ===")
    r = client.get(
        "/api/v1/liquidaciones/cierre-mensual",
        params={"conductor_id": cond_id, "periodo_ym": "2026-06"},
        headers=headers,
    )
    assert r.status_code == 200, f"GET fallo: {r.status_code} {r.text}"
    assert r.json()["id"] == liq_id
    print(f"  GET OK: estado={r.json()['estado']} total_viajes={r.json()['total_viajes']}")

    r404 = client.get(
        "/api/v1/liquidaciones/cierre-mensual",
        params={"conductor_id": cond_id, "periodo_ym": "2026-05"},
        headers=headers,
    )
    assert r404.status_code == 404, f"esperaba 404 para otro mes, obtuve {r404.status_code}"
    print("  GET otro mes -> 404 OK")


def test_03b_listar_cierres(client, headers, cond_id, liq_id):
    print("\n=== Test 3b: GET /cierres-mensuales (listado) ===")
    r = client.get(
        "/api/v1/liquidaciones/cierres-mensuales",
        params={"conductor_id": cond_id},
        headers=headers,
    )
    assert r.status_code == 200, f"listar fallo: {r.status_code} {r.text}"
    body = r.json()
    assert isinstance(body, list) and len(body) >= 1, f"esperaba al menos 1 cierre, obtuve {body}"
    ids = [c["id"] for c in body]
    assert liq_id in ids, f"el cierre {liq_id} no aparece en el listado: {ids}"
    # más reciente primero: primer elemento debe ser el cierre de 2026-06
    assert body[0]["periodo_ym"] >= body[-1]["periodo_ym"], "orden por periodo descendente roto"
    print(f"  listado OK: {len(body)} cierre(s), primero={body[0]['periodo_ym']}, ids={ids}")


def test_04_cerrar_viaje_bloqueado_409(client, headers, veh_id, viaje_id):
    print("\n=== Test 4: /cerrar/{viaje} de un mes cerrado -> 409 ===")
    r = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje_id}",
        json={
            "conductor_id": 2,
            "vehiculo_id": veh_id,
            "periodo_inicio": "2026-06-01",
            "periodo_fin": "2026-06-30",
            "comision_flete": 85000,
            "porcentaje_comision": 10,
            "viajes_ids": [viaje_id],
            "estado": "borrador",
        },
        headers=headers,
    )
    assert r.status_code == 409, f"esperaba 409 por cierre mensual existente, obtuve {r.status_code} {r.text}"
    print(f"  409 obtenido: {r.json()['detail']}")


def test_05_cancelar_libera(client, headers, cond_id, liq_id, viajes_jun, db):
    print("\n=== Test 5: cancelar cierre mensual -> libera viajes ===")
    r = client.post(f"/api/v1/liquidaciones/{liq_id}/cancelar", headers=headers)
    assert r.status_code == 200, f"cancelar fallo: {r.status_code} {r.text}"
    assert r.json()["viajes_liberados"] == len(viajes_jun)
    print(f"  cancelar OK: {r.json()['mensaje']}")

    # viajes de nuevo sin liquidar
    for v in viajes_jun:
        db.refresh(v)
        assert v.estado == "en_curso", f"viaje {v.id} no liberado (estado={v.estado})"
    print("  viajes liberados a en_curso: OK")

    # GET ya no encuentra el cierre
    r404 = client.get(
        "/api/v1/liquidaciones/cierre-mensual",
        params={"conductor_id": cond_id, "periodo_ym": "2026-06"},
        headers=headers,
    )
    assert r404.status_code == 404
    print("  GET tras cancelar -> 404 OK")


def test_06_reabrir_solo_aprobado(client, headers, admin2_headers, cond_id, veh_id, viaje_jul):
    print("\n=== Test 6: liquidación individual aprobada + reabrir ===")
    # 1) cerrar individual el viaje de julio (estado aprobado)
    r = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje_jul.id}",
        json={
            "conductor_id": cond_id,
            "vehiculo_id": veh_id,
            "periodo_inicio": "2026-07-01",
            "periodo_fin": "2026-07-31",
            "comision_flete": 85000,
            "porcentaje_comision": 10,
            "viajes_ids": [viaje_jul.id],
            "estado": "aprobado",
        },
        headers=headers,
    )
    assert r.status_code == 200, f"cerrar individual fallo: {r.status_code} {r.text}"
    liq_individual = r.json()["liquidacion_id"]
    print(f"  liquidación individual id={liq_individual}")

    # 2) reabrir la aprobada -> 200, vuelve a borrador con rastro
    r = client.post(f"/api/v1/liquidaciones/{liq_individual}/reabrir", headers=admin2_headers)
    assert r.status_code == 200, f"reabrir fallo: {r.status_code} {r.text}"
    body = r.json()
    assert body["estado"] == "borrador", body
    assert "[reabierto" in body["rastro"]
    print(f"  reabrir aprobada OK -> estado={body['estado']} rastro='{body['rastro']}'")

    # 3) reabrir de nuevo -> 400 (ya no está aprobada)
    r400 = client.post(f"/api/v1/liquidaciones/{liq_individual}/reabrir", headers=admin2_headers)
    assert r400.status_code == 400, f"segundo reabrir debía ser 400, obtuve {r400.status_code}"
    print("  reabrir borrador -> 400 OK")

    # 4) estado en BD: aprobado_por NULL
    with SessionLocal() as s2:
        liq = s2.query(LiquidacionConductor).filter(LiquidacionConductor.id == liq_individual).first()
        assert liq.estado == "borrador" and liq.aprobado_por is None
        print(f"  BD: estado={liq.estado} aprobado_por={liq.aprobado_por}")
    return liq_individual


def test_07_d5_odts_ya_liquidadas(client, headers, cond_id, veh_id, viaje_ago):
    print("\n=== Test 7: D5-c — cierre del mes con ODT ya liquidada -> 409 ===")
    # cerrar individualmente primero el viaje de agosto
    r = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje_ago.id}",
        json={
            "conductor_id": cond_id,
            "vehiculo_id": veh_id,
            "periodo_inicio": "2026-08-01",
            "periodo_fin": "2026-08-31",
            "comision_flete": 85000,
            "porcentaje_comision": 10,
            "viajes_ids": [viaje_ago.id],
            "estado": "aprobado",
        },
        headers=headers,
    )
    assert r.status_code == 200, f"cerrar individual ago fallo: {r.status_code} {r.text}"

    r2 = client.post(
        "/api/v1/liquidaciones/cierre-mensual",
        json={"conductor_id": cond_id, "periodo_ym": "2026-08"},
        headers=headers,
    )
    assert r2.status_code == 409, f"esperaba 409 D5-c, obtuve {r2.status_code} {r2.text}"
    msg = r2.json()["detail"]
    assert "ya liquidados" in msg
    print(f"  409 D5-c obtenido: {msg}")


def test_08_recrear_tras_cancelar(client, headers, cond_id, viajes_jun):
    print("\n=== Test 8: el periodo cancelado vuelve a poder cerrarse ===")
    r = client.post(
        "/api/v1/liquidaciones/cierre-mensual",
        json={"conductor_id": cond_id, "periodo_ym": "2026-06"},
        headers=headers,
    )
    assert r.status_code == 200, f"recrear cierre 2026-06 fallo: {r.status_code} {r.text}"
    print(f"  recreado: id={r.json()['id']} estado={r.json()['estado']}")
    return r.json()["id"]


def test_09_cancelar_aprobado_400(client, headers, cond_id, veh_id, viaje_id):
    print("\n=== Test 9: cancelar liquidación aprobada -> 400 ===")
    r = client.post(
        f"/api/v1/liquidaciones/cerrar/{viaje_id}",
        json={
            "conductor_id": cond_id,
            "vehiculo_id": veh_id,
            "periodo_inicio": "2026-06-01",
            "periodo_fin": "2026-06-30",
            "comision_flete": 85000,
            "porcentaje_comision": 10,
            "viajes_ids": [viaje_id],
            "estado": "aprobado",
        },
        headers=headers,
    )
    assert r.status_code == 200, f"cerrar individual fallo: {r.status_code} {r.text}"
    liq_id = r.json()["liquidacion_id"]
    print(f"  liquidación aprobada creada: id={liq_id}")

    r400 = client.post(f"/api/v1/liquidaciones/{liq_id}/cancelar", headers=headers)
    assert r400.status_code == 400, f"cancelar aprobada debía ser 400, obtuve {r400.status_code} {r400.text}"
    assert "borrador" in r400.json()["detail"]
    print(f"  cancelar aprobada -> 400 OK: {r400.json()['detail']}")

    # limpieza propia: reabrir a borrador y cancelar (libera el viaje a en_curso)
    rr = client.post(f"/api/v1/liquidaciones/{liq_id}/reabrir", headers=headers)
    assert rr.status_code == 200, f"reabrir fallo: {rr.status_code} {rr.text}"
    rc = client.post(f"/api/v1/liquidaciones/{liq_id}/cancelar", headers=headers)
    assert rc.status_code == 200, f"cancelar borrador fallo: {rc.status_code} {rc.text}"
    print("  limpieza propia OK (reabrir + cancelar)")


def test_10_cancelar_no_toca_odt_no_liquidada(client, headers, cond_id, viajes_jun, db):
    print("\n=== Test 10: cancelar revalida ODTs (solo toca las 'liquidado') ===")
    r = client.post(
        "/api/v1/liquidaciones/cierre-mensual",
        json={"conductor_id": cond_id, "periodo_ym": "2026-06"},
        headers=headers,
    )
    assert r.status_code == 200, f"cierre-mensual fallo: {r.status_code} {r.text}"
    liq_id = r.json()["id"]

    db.refresh(viajes_jun[0])
    db.refresh(viajes_jun[1])
    assert viajes_jun[0].estado == "liquidado" and viajes_jun[1].estado == "liquidado"
    print(f"  cierre creado id={liq_id}; ODTs {viajes_jun[0].id}, {viajes_jun[1].id} -> liquidado")

    # drift: mientras existe el cierre, una ODT deja de estar 'liquidado' (p. ej. cancelada)
    viajes_jun[1].estado = "cancelado"
    db.commit()
    db.refresh(viajes_jun[1])
    print(f"  drift simulado: ODT {viajes_jun[1].id} -> {viajes_jun[1].estado}")

    # cancelar: el update filtra estado='liquidado' -> libera solo la que sigue así
    rc = client.post(f"/api/v1/liquidaciones/{liq_id}/cancelar", headers=headers)
    assert rc.status_code == 200, f"cancelar fallo: {rc.status_code} {rc.text}"

    db.refresh(viajes_jun[0])
    db.refresh(viajes_jun[1])
    assert viajes_jun[0].estado == "en_curso", \
        f"ODT liquidada debía liberarse a en_curso, quedó {viajes_jun[0].estado}"
    assert viajes_jun[1].estado == "cancelado", \
        f"ODT no liquidada no debe ser tocada, quedó {viajes_jun[1].estado}"
    print(f"  ODTs finales: {viajes_jun[0].id}={viajes_jun[0].estado}, "
          f"{viajes_jun[1].id}={viajes_jun[1].estado} — revalidación OK")


def main():
    print("Iniciando prueba de cierre mensual B2 (CELR v6)...")
    db = SessionLocal()
    viajes_creados = []
    tokens_antes_test = capturar_token_ids(db, "test@celr.com")
    tokens_antes_admin2 = capturar_token_ids(db, "admin2@celr.com")
    admin = None
    try:
        admin = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
        assert admin is not None, "Se requiere admin test@celr.com (ejecuta seed.py)"
        veh_id, cond_id = seed(db)

        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r2 = client.post("/api/v1/auth/login", json={"correo": "admin2@celr.com", "contrasena": "admin123"})
        if r2.status_code != 200:
            # crear admin2 temporal (igual que test_liquidaciones)
            from app.core.security import hash_password
            u2 = UsuarioModel(correo="admin2@celr.com", contrasena_hash=hash_password("admin123"), rol="admin", activo=True)
            db.add(u2)
            db.commit()
            db.refresh(u2)
            r2 = client.post("/api/v1/auth/login", json={"correo": "admin2@celr.com", "contrasena": "admin123"})
        admin2_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

        # Viajes de prueba en meses limpios
        v1 = crear_viaje(db, veh_id, cond_id, date(2026, 6, 10), "jun-1")
        v2 = crear_viaje(db, veh_id, cond_id, date(2026, 6, 15), "jun-2")
        viajes_creados.extend([v1, v2])
        v3 = crear_viaje(db, veh_id, cond_id, date(2026, 7, 5), "jul")
        viajes_creados.append(v3)
        v4 = crear_viaje(db, veh_id, cond_id, date(2026, 8, 3), "ago")
        viajes_creados.append(v4)

        liq_id = test_01_crear_cierre_mensual(client, headers, cond_id, [v1, v2])
        test_02_duplicado_409(client, headers, cond_id)
        test_03_get_cierre_mensual(client, headers, cond_id, liq_id)
        test_03b_listar_cierres(client, headers, cond_id, liq_id)

        # los viajes del mes quedaron liquidados
        db.refresh(v1)
        db.refresh(v2)
        assert v1.estado == "liquidado" and v2.estado == "liquidado"
        print("  viajes del mes estado=liquidado: OK")

        test_04_cerrar_viaje_bloqueado_409(client, headers, veh_id, v1.id)
        test_05_cancelar_libera(client, headers, cond_id, liq_id, [v1, v2], db)
        liq_ind = test_06_reabrir_solo_aprobado(client, headers, admin2_headers, cond_id, veh_id, v3)
        test_07_d5_odts_ya_liquidadas(client, headers, cond_id, veh_id, v4)
        liq_id2 = test_08_recrear_tras_cancelar(client, headers, cond_id, [v1, v2])
        test_05_cancelar_libera(client, headers, cond_id, liq_id2, [v1, v2], db)

        test_09_cancelar_aprobado_400(client, headers, cond_id, veh_id, v2.id)
        test_10_cancelar_no_toca_odt_no_liquidada(client, headers, cond_id, [v1, v2], db)

        print("\n[TODOS LOS TESTS DE CIERRE MENSUAL PASARON]")
    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            from app.models.flota import RefreshToken

            for v in viajes_creados:
                db.query(LiquidacionConductor).filter(
                    LiquidacionConductor.viajes_ids.contains([v.id])
                ).delete(synchronize_session=False)
            via_ids = [v.id for v in viajes_creados]
            if via_ids:
                db.query(ViajeODT).filter(ViajeODT.id.in_(via_ids)).delete(synchronize_session=False)
            if admin is not None:
                limpiar_tokens_nuevos(db, "test@celr.com", tokens_antes_test)
            limpiar_tokens_nuevos(db, "admin2@celr.com", tokens_antes_admin2)
            admin2 = db.query(UsuarioModel).filter(UsuarioModel.correo == "admin2@celr.com").first()
            if admin2:
                # El usuario temporal se elimina; también se limpian tokens viejos
                # de una corrida anterior que pudieran haber quedado.
                db.query(RefreshToken).filter(RefreshToken.usuario_id == admin2.id).delete(synchronize_session=False)
                db.query(LiquidacionConductor).filter(
                    (LiquidacionConductor.creado_por == admin2.id) |
                    (LiquidacionConductor.aprobado_por == admin2.id)
                ).delete(synchronize_session=False)
                db.delete(admin2)
            db.commit()
        except Exception as e2:
            print(f"\n[CLEANUP ERROR]: {e2}")
            import traceback
            traceback.print_exc()
            db.rollback()
            raise
        db.close()


if __name__ == "__main__":
    main()