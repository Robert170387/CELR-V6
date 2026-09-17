import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db.session import SessionLocal
from app.main import app
from app.models.flota import Usuario as UsuarioModel, Vehiculo
from app.models.operaciones import ViajeODT
from app.core.security import hash_password, create_access_token
from app.schemas.usuario import UsuarioCreate

client = TestClient(app)

SUF = str(int(time.time()))


def seed_usuario(db, correo: str, rol: str) -> UsuarioModel:
    usuario = db.query(UsuarioModel).filter(UsuarioModel.correo == correo).first()
    if not usuario:
        usuario = UsuarioModel(
            correo=correo,
            contrasena_hash=hash_password("admin123"),
            rol=rol,
            activo=True,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
    else:
        usuario.rol = rol
        usuario.activo = True
        db.commit()
        db.refresh(usuario)
    return usuario


def token_for(usuario: UsuarioModel) -> dict:
    tok = create_access_token({"usuario_id": usuario.id, "correo": usuario.correo})
    return {"Authorization": f"Bearer {tok}"}


def check(label: str, expected, actual):
    ok = actual == expected
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}: esperado={expected} obtenido={actual}")
    assert ok, label


def main():
    db = SessionLocal()
    try:
        print("=== Test 0: schema de roles alineado al enum de la DB ===")
        for rol in ["admin", "operador", "contador", "supervisor", "cliente", "conductor"]:
            UsuarioCreate(correo="x@celr.com", contrasena="123456", rol=rol)
        print("  [OK ] los 6 roles validos son aceptados")
        try:
            UsuarioCreate(correo="x@celr.com", contrasena="123456", rol="visualizador")
            raise AssertionError("rol 'visualizador' no deberia ser valido")
        except ValidationError:
            print("  [OK ] rol 'visualizador' rechazado por el schema")

        admin = seed_usuario(db, "test@celr.com", "admin")
        operador = seed_usuario(db, f"rbac_operador_{SUF}@celr.com", "operador")
        conductor = seed_usuario(db, f"rbac_conductor_{SUF}@celr.com", "conductor")
        cliente = seed_usuario(db, f"rbac_cliente_{SUF}@celr.com", "cliente")

        h_admin, h_oper, h_cond, h_cli = (
            token_for(admin), token_for(operador), token_for(conductor), token_for(cliente),
        )
        viaje = db.query(ViajeODT).first()
        vehiculo = db.query(Vehiculo).first()
        if viaje is None or vehiculo is None:
            print("  [!] No hay viaje/vehiculo en la DB; se omiten pruebas que dependen de datos.")
            return
        viaje_id = viaje.id
        vehiculo_id = vehiculo.id

        print("\n=== Test 1: maestros - GET abierto, escritura bloqueada para conductor ===")
        check("GET /vehiculos (conductor)", 200, client.get("/api/v1/vehiculos", headers=h_cond).status_code)

        body_veh = {"placa": f"RB{SUF[-5:]}", "marca": "TEST", "km_actual": 0}
        check("POST /vehiculos (conductor)", 403,
              client.post("/api/v1/vehiculos", json=body_veh, headers=h_cond).status_code)
        check("POST /conductores (conductor)", 403,
              client.post("/api/v1/conductores",
                          json={"nombre_completo": "X", "cedula": f"RB{SUF[-6:]}"},
                          headers=h_cond).status_code)
        check("POST /proveedores (conductor)", 403,
              client.post("/api/v1/proveedores",
                          json={"razon_social": "X", "tipo": "otro"},
                          headers=h_cond).status_code)

        print("\n=== Test 2: liquidaciones - bloqueado para conductor y cliente ===")
        check("GET /liquidaciones/calcular (conductor)", 403,
              client.get(f"/api/v1/liquidaciones/calcular/{viaje_id}", headers=h_cond).status_code)
        check("GET /liquidaciones/calcular (cliente)", 403,
              client.get(f"/api/v1/liquidaciones/calcular/{viaje_id}", headers=h_cli).status_code)
        check("GET /liquidaciones/calcular (operador)", 200,
              client.get(f"/api/v1/liquidaciones/calcular/{viaje_id}", headers=h_oper).status_code)
        check("GET /liquidaciones/calcular (admin)", 200,
              client.get(f"/api/v1/liquidaciones/calcular/{viaje_id}", headers=h_admin).status_code)

        print("\n=== Test 3: ingresos - bloqueado para conductor y cliente ===")
        body_ing = {
            "viaje_id": viaje_id,
            "vehiculo_id": vehiculo_id,
            "tipo_ingreso": "otro",
            "fecha_ingreso": "2026-01-01",
            "valor": 1000,
        }
        check("POST /ingresos (conductor)", 403,
              client.post("/api/v1/ingresos", json=body_ing, headers=h_cond).status_code)
        check("POST /ingresos (cliente)", 403,
              client.post("/api/v1/ingresos", json=body_ing, headers=h_cli).status_code)

        print("\n=== Test 4: rol autorizado si puede escribir maestros ===")
        r = client.post("/api/v1/vehiculos", json=body_veh, headers=h_oper)
        check("POST /vehiculos (operador)", 201, r.status_code)
        if r.status_code == 201:
            db.query(Vehiculo).filter(Vehiculo.placa == body_veh["placa"]).delete(synchronize_session=False)
            db.commit()

        print("\n[OK] TODOS LOS TESTS DE RBAC PASARON")
    finally:
        db.rollback()
        db.query(UsuarioModel).filter(UsuarioModel.correo.like(f"rbac_%_{SUF}@celr.com")).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
