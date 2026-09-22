import sys
import os
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.flota import Vehiculo

CLIENT = TestClient(app)
FECHA = "2026-09-17"


def login():
    r = CLIENT.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
    assert r.status_code == 200, f"Login fallido: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def crear_gasto(headers, body):
    r = CLIENT.post("/api/v1/gastos", json=body, headers=headers)
    assert r.status_code in (200, 201), f"POST /gastos fallo: {r.status_code} {r.text}"
    return r.json()


def main():
    print("Test: gasto combustible (campos, consistencia aritmetica, km_actual)")
    db = SessionLocal()
    try:
        veh = db.query(Vehiculo).filter(Vehiculo.estado == "activo").first() or db.query(Vehiculo).first()
        assert veh is not None, "No hay vehiculos en la BD"
        vehiculo_id = veh.id
        km_antes = float(veh.km_actual or 0)
    finally:
        db.close()
    print(f"  usando vehiculo_id={vehiculo_id} km_actual={km_antes}")

    headers = login()
    suf_int = int(uuid.uuid4().hex[:8], 16)

    creados = []

    # 1) Gasto de combustible consistente con km MAYOR -> pendiente y km_actual se actualiza
    km_nuevo = km_antes + 1000.0
    g1_valor = 606000 + (suf_int % 60)
    g1 = crear_gasto(headers, {
        "vehiculo_id": vehiculo_id,
        "categoria": "combustible",
        "fecha_gasto": FECHA,
        "valor_total": g1_valor,
        "cantidad_galones": 50.5,
        "precio_por_galon": 12000.0,
        "km_registro": km_nuevo,
        "ciudad_abastecimiento": "Bogota",
        "asumido_por": "empresa",
        "responsable_pago": "conductor",
        "tiene_num_factura": False,
    })
    creados.append(g1["id"])
    print(f"  G1 consistente -> gasto_id={g1['id']} estado={g1['estado_validacion']}")
    assert float(g1["cantidad_galones"]) == 50.5
    assert g1["ciudad_abastecimiento"] == "Bogota"
    assert g1["estado_validacion"] == "pendiente", f"esperaba pendiente, obtuvo {g1['estado_validacion']}"

    r = CLIENT.get(f"/api/v1/vehiculos/{vehiculo_id}", headers=headers)
    assert r.status_code == 200
    km_despues = float(r.json()["km_actual"])
    print(f"  km_actual tras G1: {km_antes} -> {km_despues}")
    assert abs(km_despues - km_nuevo) < 0.01, f"km_actual no se actualizo: {km_despues} != {km_nuevo}"

    # 2) Inconsistencia aritmetica (10 * 10000 != 50000) -> observado, NO bloquea
    g2_valor = 50000 + ((suf_int // 97) % 60)
    g2 = crear_gasto(headers, {
        "vehiculo_id": vehiculo_id,
        "categoria": "combustible",
        "fecha_gasto": FECHA,
        "valor_total": g2_valor,
        "cantidad_galones": 10.0,
        "precio_por_galon": 10000.0,
        "km_registro": km_despues + 1.0,
        "asumido_por": "empresa",
        "responsable_pago": "conductor",
        "tiene_num_factura": False,
    })
    creados.append(g2["id"])
    print(f"  G2 inconsistencia aritmetica -> gasto_id={g2['id']} estado={g2['estado_validacion']}")
    assert g2["estado_validacion"] == "observado", f"esperaba observado, obtuvo {g2['estado_validacion']}"

    r = CLIENT.get(f"/api/v1/vehiculos/{vehiculo_id}", headers=headers)
    km_tras_g2 = float(r.json()["km_actual"])  # G2 reporto km mayor -> avanza

    # 3) km_registro MENOR que km_actual -> observado y km_actual NO retrocede
    g3 = crear_gasto(headers, {
        "vehiculo_id": vehiculo_id,
        "categoria": "combustible",
        "fecha_gasto": FECHA,
        "valor_total": 20000 + ((suf_int // 13) % 50),
        "cantidad_galones": 1.0,
        "precio_por_galon": 20000.0,
        "km_registro": km_tras_g2 - 5.0,
        "asumido_por": "empresa",
        "responsable_pago": "conductor",
        "tiene_num_factura": False,
    })
    creados.append(g3["id"])
    print(f"  G3 km inferior -> gasto_id={g3['id']} estado={g3['estado_validacion']}")
    assert g3["estado_validacion"] == "observado", f"esperaba observado, obtuvo {g3['estado_validacion']}"

    r = CLIENT.get(f"/api/v1/vehiculos/{vehiculo_id}", headers=headers)
    km_final = float(r.json()["km_actual"])
    assert abs(km_final - km_tras_g2) < 0.01, "km_actual retrocedio con un km_registro menor"

    # 4) PUT convierte G1 en inconsistente -> observado
    r = CLIENT.put(
        f"/api/v1/gastos/{g1['id']}",
        json={"cantidad_galones": 10.0, "precio_por_galon": 10000.0, "valor_total": 50000},
        headers=headers,
    )
    assert r.status_code == 200, f"PUT esperaba 200, obtuvo {r.status_code}: {r.text}"
    print(f"  PUT G1 inconsistente -> estado={r.json()['estado_validacion']}")
    assert r.json()["estado_validacion"] == "observado"

    # Limpieza (soft delete)
    for gid in creados:
        r = CLIENT.delete(f"/api/v1/gastos/{gid}", headers=headers)
        assert r.status_code == 204, f"DELETE {gid} fallo: {r.status_code}"

    print("[OK] Combustible: campos capturados, consistencia marcada y km_actual actualizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())