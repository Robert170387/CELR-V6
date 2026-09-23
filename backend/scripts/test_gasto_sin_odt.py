import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, RefreshToken, Usuario as UsuarioModel
from app.models.operaciones import Gasto

CLIENT = TestClient(app)


def main():
    print("Smoke test: gasto SIN ODT (Gasto Fijo / Mantenimiento)")
    suf = None
    inicio = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        veh = db.query(Vehiculo).first()
        assert veh is not None, "No hay vehiculos en la BD"
        vehiculo_id = veh.id
        print(f"  usando vehiculo_id={vehiculo_id} ({veh.placa})")

        r = CLIENT.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
        assert r.status_code == 200, f"Login fallido: {r.status_code} {r.text}"
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        suf = uuid.uuid4().hex[:8]

        r = CLIENT.post(
            "/api/v1/gastos",
            json={
                "vehiculo_id": vehiculo_id,
                "categoria": "mantenimiento",
                "descripcion": "Gasto fijo / mantenimiento de vehiculo (smoke sin ODT)",
                "fecha_gasto": "2026-09-17",
                "valor_total": 150000,
                "asumido_por": "empresa",
                "responsable_pago": "empresa",
                "tiene_num_factura": True,
                "num_factura": f"SF-{suf}",
            },
            headers=headers,
        )
        print(f"  POST /gastos sin viaje_id -> {r.status_code}")
        if r.status_code not in (200, 201):
            print(f"  FALLO: {r.text}")
            return 1
        data = r.json()
        print(f"  creado gasto_id={data['id']} viaje_id={data['viaje_id']}, categoria={data['categoria']}")
        assert data["viaje_id"] is None, "esperaba viaje_id None"

        mid = data["id"]

        r = CLIENT.put(
            f"/api/v1/gastos/{mid}",
            json={"viaje_id": None, "vehiculo_id": vehiculo_id, "categoria": "mantenimiento", "fecha_gasto": "2026-09-17", "valor_total": 160000},
            headers=headers,
        )
        print(f"  PUT /gastos/{mid} (viaje_id null) -> {r.status_code}")
        assert r.status_code == 200
        assert r.json()["viaje_id"] is None

        r = CLIENT.delete(f"/api/v1/gastos/{mid}", headers=headers)
        print(f"  DELETE /gastos/{mid} -> {r.status_code}")
        assert r.status_code == 204

        r = CLIENT.get(f"/api/v1/gastos/{mid}", headers=headers)
        print(f"  GET /gastos/{mid} post-delete -> {r.status_code}")
        assert r.status_code == 404

        print("[OK] Gasto fijo/mantenimiento sin ODT (crear, editar, eliminar) funciona.")
        return 0
    finally:
        db.close()
        # Limpieza 2.B: el DELETE de la API es soft-delete; aquí se borra físicamente
        # el gasto creado en esta corrida (num_factura SF-<suf>, propio del run) para
        # volver al baseline. Nunca se borra el vehículo del seed.
        if suf:
            db2 = SessionLocal()
            try:
                db2.query(Gasto).filter(Gasto.num_factura == f"SF-{suf}").delete(
                    synchronize_session=False
                )
                admin = db2.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
                if admin:
                    db2.query(RefreshToken).filter(
                        RefreshToken.usuario_id == admin.id,
                        RefreshToken.creado_en >= inicio,
                    ).delete(synchronize_session=False)
                db2.commit()
            except Exception:
                db2.rollback()
            finally:
                db2.close()


if __name__ == "__main__":
    sys.exit(main())