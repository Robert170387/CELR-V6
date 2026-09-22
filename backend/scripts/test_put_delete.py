import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.flota import Usuario as UsuarioModel, Vehiculo, Conductor
from app.models.operaciones import ViajeODT, Gasto, Proveedor
from app.models.financiero import Ingreso
from app.core.security import hash_password

CLIENT = TestClient(app)


def login(correo="test@celr.com", contrasena="admin123"):
    r = CLIENT.post("/api/v1/auth/login", json={"correo": correo, "contrasena": contrasena})
    assert r.status_code == 200, f"Login fallido para {correo}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def post(url, body, headers):
    r = CLIENT.post(url, json=body, headers=headers)
    assert r.status_code in (200, 201), f"POST {url} fallo: {r.status_code} {r.text}"
    return r.json()


def put(url, body, headers, esperado=200):
    r = CLIENT.put(url, json=body, headers=headers)
    if r.status_code != esperado:
        raise AssertionError(f"PUT {url} esperaba {esperado}, obtuvo {r.status_code}: {r.text}")
    return r


def delete(url, headers, esperado=204):
    r = CLIENT.delete(url, headers=headers)
    if r.status_code != esperado:
        raise AssertionError(f"DELETE {url} esperaba {esperado}, obtuvo {r.status_code}: {r.text}")
    return r


def main():
    suf = datetime.now().strftime("%H%M%S%f")
    print("Iniciando prueba CRUD PUT/DELETE CELR v6...")

    headers = login()
    creados = {"vehi": [], "cond": [], "prov": [], "viaje": [], "gasto": [], "ingreso": []}
    db = SessionLocal()

    try:
        # --- Preparacion ---
        print("\n=== Preparacion: crear registros base ===")
        veh = post("/api/v1/vehiculos", {"placa": f"PUT{suf[-5:]}", "marca": "Kenworth", "modelo": "T680", "anio": 2021, "km_actual": 100}, headers)
        creados["vehi"].append(veh["id"])
        cond = post("/api/v1/conductores", {"nombre_completo": f"Conductor {suf}", "cedula": f"CC-{suf}", "telefono": "3000000000", "estado": "activo"}, headers)
        creados["cond"].append(cond["id"])
        prov = post("/api/v1/proveedores", {"razon_social": f"Proveedor {suf}", "nit": f"9.{suf}.5", "tipo": "combustible", "ciudad": "Bogota"}, headers)
        creados["prov"].append(prov["id"])
        viaje = post("/api/v1/viajes", {"vehiculo_id": veh["id"], "conductor_id": cond["id"], "origen": "Bogota", "destino": "Medellin", "fecha_salida": "2026-09-16", "estado": "en_curso"}, headers)
        creados["viaje"].append(viaje["id"])
        assert viaje["numero_odt"], "numero_odt debe ser autogenerado por el servidor"
        creados["viaje"].append(viaje["id"])
        gasto = post("/api/v1/gastos", {"viaje_id": viaje["id"], "vehiculo_id": veh["id"], "categoria": "combustible", "fecha_gasto": "2026-09-16", "valor_total": 200000}, headers)
        creados["gasto"].append(gasto["id"])
        ingreso = post("/api/v1/ingresos", {"viaje_id": viaje["id"], "vehiculo_id": veh["id"], "tipo_ingreso": "anticipo", "fecha_ingreso": "2026-09-16", "valor": 100000}, headers)
        creados["ingreso"].append(ingreso["id"])
        print(f"  vehiculo={veh['id']}, conductor={cond['id']}, proveedor={prov['id']}, viaje={viaje['id']}, gasto={gasto['id']}, ingreso={ingreso['id']}")

        # --- PUT ---
        print("\n=== Test 1: PUT vehiculos / conductores / proveedores ===")
        r = put(f"/api/v1/vehiculos/{veh['id']}", {"marca": "Kenworth X"}, headers)
        assert r.json()["marca"] == "Kenworth X"
        r = put(f"/api/v1/conductores/{cond['id']}", {"telefono": "3100000000"}, headers)
        assert r.json()["telefono"] == "3100000000"
        r = put(f"/api/v1/proveedores/{prov['id']}", {"ciudad": "Cali"}, headers)
        assert r.json()["ciudad"] == "Cali"
        print("  [OK ] UPDATE sobre maestras con campos parciales")

        print("\n=== Test 2: PUT viajes ===")
        r = put(f"/api/v1/viajes/{viaje['id']}", {"destino": "Cartagena", "valor_flete_manifiesto": 1200000}, headers)
        assert r.json()["destino"] == "Cartagena"
        print("  [OK ] UPDATE viaje parcial")

        print("\n=== Test 3: PUT gastos e ingresos ===")
        r = put(f"/api/v1/gastos/{gasto['id']}", {"valor_total": 250000}, headers)
        assert r.json()["valor_total"] == 250000 or float(r.json()["valor_total"]) == 250000.0
        r = put(f"/api/v1/ingresos/{ingreso['id']}", {"valor": 150000}, headers)
        assert r.json()["valor"] == 150000 or float(r.json()["valor"]) == 150000.0
        print("  [OK ] UPDATE gasto e ingreso")

        print("\n=== Test 4: PUT no encontrado / FK invalido / duplicado / validacion ===")
        put("/api/v1/vehiculos/999999", {"marca": "X"}, headers, esperado=404)
        put(f"/api/v1/viajes/{viaje['id']}", {"vehiculo_id": 999999}, headers, esperado=404)
        put(f"/api/v1/gastos/{gasto['id']}", {"viaje_id": 999999}, headers, esperado=404)
        veh2 = post("/api/v1/vehiculos", {"placa": f"PUT{suf[-5:]}X", "marca": "Freightliner"}, headers)
        creados["vehi"].append(veh2["id"])
        put(f"/api/v1/vehiculos/{veh['id']}", {"placa": veh2["placa"]}, headers, esperado=409)
        put(f"/api/v1/gastos/{gasto['id']}", {"valor_total": -5}, headers, esperado=422)
        print("  [OK ] 404 inexistente, 404 FK invalido, 409 duplicado, 422 valor negativo")

        # --- RBAC ---
        print("\n=== Test 5: RBAC (cliente no puede editar/eliminar) ===")
        correo_cliente = f"cli-{suf}@celr.com"
        db.add(UsuarioModel(correo=correo_cliente, contrasena_hash=hash_password("clave12345"), rol="cliente", activo=True))
        db.commit()
        headers_cliente = login(correo_cliente, "clave12345")
        put(f"/api/v1/viajes/{viaje['id']}", {"destino": "X"}, headers_cliente, esperado=403)
        delete(f"/api/v1/gastos/{gasto['id']}", headers_cliente, esperado=403)
        print("  [OK ] 403 para rol no autorizado en viajes/gastos (liquidaciones)")

        # --- DELETE ---
        print("\n=== Test 6: DELETE ok (ingreso, gasto, viaje) ===")
        delete(f"/api/v1/ingresos/{ingreso['id']}", headers)
        creados["ingreso"].remove(ingreso["id"])
        delete(f"/api/v1/gastos/{gasto['id']}", headers)
        creados["gasto"].remove(gasto["id"])
        delete(f"/api/v1/viajes/{viaje['id']}", headers)
        creados["viaje"].remove(viaje["id"])
        print("  [OK ] DELETE de ingreso, gasto y viaje")

        print("\n=== Test 7: DELETE rechazado por FK / inexistente ===")
        viaje2 = post("/api/v1/viajes", {"vehiculo_id": veh["id"], "conductor_id": cond["id"], "origen": "Bogota", "destino": "Pasto", "fecha_salida": "2026-09-16", "estado": "en_curso"}, headers)
        creados["viaje"].append(viaje2["id"])
        gasto2 = post("/api/v1/gastos", {"viaje_id": viaje2["id"], "vehiculo_id": veh["id"], "categoria": "peaje", "fecha_gasto": "2026-09-16", "valor_total": 50000}, headers)
        creados["gasto"].append(gasto2["id"])
        # Soft delete: el viaje con gastos asociados YA se elimina (borrado lógico).
        delete(f"/api/v1/viajes/{viaje2['id']}", headers, esperado=204)
        print("  [OK ] DELETE viaje con gasto asociado -> 204 (soft delete)")
        delete(f"/api/v1/vehiculos/{veh['id']}", headers, esperado=409)
        delete(f"/api/v1/conductores/{cond['id']}", headers, esperado=409)
        delete("/api/v1/proveedores/999999", headers, esperado=404)
        delete("/api/v1/vehiculos/999999", headers, esperado=404)
        delete("/api/v1/ingresos/999999", headers, esperado=404)
        print("  [OK ] 409 por asociaciones (maestras), 404 inexistente")

        # --- Conductor rol (escapar a escrito? solo lectura) ---
        print("\n=== Test 8: RBAC conductor no puede escribir maestras ===")
        correo_cond = f"cond-{suf}@celr.com"
        db.add(UsuarioModel(correo=correo_cond, contrasena_hash=hash_password("clave12345"), rol="conductor", activo=True))
        db.commit()
        headers_cond = login(correo_cond, "clave12345")
        post_res = CLIENT.post("/api/v1/vehiculos", json={"placa": f"P{suf[-5:]}", "marca": "X"}, headers=headers_cond)
        assert post_res.status_code == 403, f"POST vehiculo como conductor esperaba 403, obtuvo {post_res.status_code}"
        delete(f"/api/v1/gastos/{gasto2['id']}", headers_cond, esperado=403)
        print("  [OK ] 403 para POST maestra y DELETE gasto como conductor")

        print("\n[TODOS LOS TESTS PUT/DELETE PASARON]")

    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
    finally:
        # Limpieza ORM
        try:
            for via_id in creados["viaje"]:
                db.query(Gasto).filter(Gasto.viaje_id == via_id).delete()
            db.query(Ingreso).filter(Ingreso.viaje_id.in_(creados["viaje"])).delete(synchronize_session=False)
            db.query(ViajeODT).filter(ViajeODT.id.in_(creados["viaje"])).delete(synchronize_session=False)
            db.query(Gasto).filter(Gasto.id.in_(creados["gasto"])).delete(synchronize_session=False)
            db.query(Vehiculo).filter(Vehiculo.id.in_(creados["vehi"])).delete(synchronize_session=False)
            db.query(Conductor).filter(Conductor.id.in_(creados["cond"])).delete(synchronize_session=False)
            db.query(Proveedor).filter(Proveedor.id.in_(creados["prov"])).delete(synchronize_session=False)
            db.query(UsuarioModel).filter(
                UsuarioModel.correo.in_(f"cli-{suf}@celr.com", f"cond-{suf}@celr.com")
            ).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


if __name__ == "__main__":
    main()