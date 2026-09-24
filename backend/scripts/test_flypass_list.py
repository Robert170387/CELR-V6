import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.financiero import FlypassTransaccion
from app.models.flota import Conductor, Usuario as UsuarioModel, Vehiculo
from app.models.operaciones import Gasto, ViajeODT
from app.services.operaciones import recalcular_viaje
from _test_helpers import capturar_token_ids, limpiar_tokens_nuevos


def crear_vehiculo(db: Session, placa: str) -> Vehiculo:
    vehiculo = Vehiculo(
        placa=placa,
        marca="Flypass List Test",
        modelo="Utilitario",
        anio=2026,
        estado="activo",
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)
    return vehiculo


def crear_conductor(db: Session, sufijo: str) -> Conductor:
    conductor = Conductor(
        nombre_completo=f"Conductor List {sufijo[:6]}",
        cedula=f"8{sufijo[:9]}",
        estado="activo",
    )
    db.add(conductor)
    db.commit()
    db.refresh(conductor)
    return conductor


def crear_gasto(
    db: Session,
    vehiculo_id: int,
    fecha: date,
    monto: str,
    sufijo: str,
    numero: int,
) -> Gasto:
    gasto = Gasto(
        viaje_id=None,
        vehiculo_id=vehiculo_id,
        categoria="peajes",
        descripcion=f"Gasto para listado Flypass {numero}",
        fecha_gasto=fecha,
        valor_total=Decimal(monto),
        responsable_pago="empresa",
        asumido_por="empresa",
        metodo_pago="tag",
        estado_pago="pendiente_por_pagar",
        tiene_num_factura=False,
        hash_comprobante=f"flypass-list-{sufijo}-{numero}",
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto


def crear_odt(db: Session, vehiculo_id: int, conductor_id: int) -> ViajeODT:
    viaje = ViajeODT(
        vehiculo_id=vehiculo_id,
        conductor_id=conductor_id,
        origen="Bogota",
        destino="Medellin",
        fecha_salida=date(2026, 9, 1),
        fecha_llegada=date(2026, 9, 5),
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


def crear_transaccion(
    db: Session,
    sufijo: str,
    numero: int,
    vehiculo_id: int,
    fecha: date,
    monto: str,
    gasto_id: int | None,
    viaje_id: int | None,
) -> FlypassTransaccion:
    transaccion = FlypassTransaccion(
        vehiculo_id=vehiculo_id,
        fecha_transaccion=datetime.combine(
            fecha, datetime.min.time()
        ).replace(tzinfo=timezone.utc),
        nombre_peaje=f"Peaje List {numero}",
        ciudad_peaje=None,
        ciudad_peaje_municipio_id=None,
        valor=Decimal(monto),
        num_transaccion_flypass=f"FLY-LIST-{sufijo}-{numero}",
        viaje_id=viaje_id,
        gasto_id=gasto_id,
        raw_data={"fixture": numero},
        estado="importado",
        importado_en=datetime.now(timezone.utc),
    )
    db.add(transaccion)
    db.commit()
    db.refresh(transaccion)
    return transaccion


def listar(client: TestClient, headers: dict, params: dict | None = None):
    respuesta = client.get(
        "/api/v1/flypass",
        params=params or {},
        headers=headers,
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def ids(respuesta: dict) -> list[str]:
    return [item["num_transaccion_flypass"] for item in respuesta["data"]]


def main() -> int:
    print("Iniciando pruebas del listado Flypass CELR v6...")
    db = SessionLocal()
    tokens_antes_test = capturar_token_ids(db, "test@celr.com")
    sufijo = uuid.uuid4().hex
    flypass_ids: list[int] = []
    gasto_ids: list[int] = []
    viaje_ids: list[int] = []
    vehiculo_ids: list[int] = []
    conductor_id: int | None = None

    try:
        admin = (
            db.query(UsuarioModel)
            .filter(UsuarioModel.correo == "test@celr.com")
            .first()
        )
        assert admin is not None, "Se requiere admin test@celr.com"

        vehiculo_a = crear_vehiculo(db, f"L{sufijo[:8]}")
        vehiculo_b = crear_vehiculo(db, f"M{sufijo[:8]}")
        vehiculo_ids.extend([vehiculo_a.id, vehiculo_b.id])
        conductor = crear_conductor(db, sufijo)
        conductor_id = conductor.id
        viaje = crear_odt(db, vehiculo_a.id, conductor.id)
        viaje_ids.append(viaje.id)
        gasto_a = crear_gasto(db, vehiculo_a.id, date(2026, 9, 1), "10000.00", sufijo, 1)
        gasto_b = crear_gasto(db, vehiculo_a.id, date(2026, 9, 2), "20000.00", sufijo, 2)
        gasto_ids.extend([gasto_a.id, gasto_b.id])

        transaccion_a = crear_transaccion(
            db, sufijo, 1, vehiculo_a.id, date(2026, 9, 1), "10000.00", gasto_a.id, None
        )
        transaccion_b = crear_transaccion(
            db, sufijo, 2, vehiculo_a.id, date(2026, 9, 2), "20000.00", gasto_b.id, viaje.id
        )
        transaccion_c = crear_transaccion(
            db, sufijo, 3, vehiculo_b.id, date(2026, 9, 3), "30000.00", None, None
        )
        flypass_ids.extend([transaccion_a.id, transaccion_b.id, transaccion_c.id])

        client = TestClient(app)
        login = client.post(
            "/api/v1/auth/login",
            json={"correo": "test@celr.com", "contrasena": "admin123"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        print("\n=== TL1: listado sin filtros y orden ===")
        body = listar(client, headers)
        assert body["total"] == 3, body
        assert ids(body) == [
            f"FLY-LIST-{sufijo}-3",
            f"FLY-LIST-{sufijo}-2",
            f"FLY-LIST-{sufijo}-1",
        ], body
        assert "raw_data" not in body["data"][0], body
        assert body["data"][0]["placa"] == vehiculo_b.placa, body
        print("  TL1 OK")

        print("\n=== TL2: filtro fecha_desde ===")
        body = listar(client, headers, {"fecha_desde": "2026-09-02"})
        assert body["total"] == 2, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-3", f"FLY-LIST-{sufijo}-2"], body
        print("  TL2 OK")

        print("\n=== TL3: filtro fecha_hasta ===")
        body = listar(client, headers, {"fecha_hasta": "2026-09-02"})
        assert body["total"] == 2, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-2", f"FLY-LIST-{sufijo}-1"], body
        print("  TL3 OK")

        print("\n=== TL4: filtro placa ===")
        body = listar(client, headers, {"placa": vehiculo_a.placa})
        assert body["total"] == 2, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-2", f"FLY-LIST-{sufijo}-1"], body
        print("  TL4 OK")

        print("\n=== TL5: filtro sin_odt ===")
        body = listar(client, headers, {"sin_odt": "true"})
        assert body["total"] == 2, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-3", f"FLY-LIST-{sufijo}-1"], body
        body = listar(client, headers, {"sin_odt": "false"})
        assert body["total"] == 1, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-2"], body
        print("  TL5 OK")

        print("\n=== TL6: filtro sin_gasto ===")
        body = listar(client, headers, {"sin_gasto": "true"})
        assert body["total"] == 1, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-3"], body
        body = listar(client, headers, {"sin_gasto": "false"})
        assert body["total"] == 2, body
        print("  TL6 OK")

        print("\n=== TL7: paginación ===")
        body = listar(client, headers, {"skip": 1, "limit": 1})
        assert body["total"] == 3, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-2"], body
        print("  TL7 OK")

        print("\n=== TL8: límite máximo ===")
        response = client.get(
            "/api/v1/flypass?limit=500",
            headers=headers,
        )
        assert response.status_code == 422, response.text
        print("  TL8 OK")

        print("\n=== TL9: combinación de filtros ===")
        body = listar(
            client,
            headers,
            {"placa": vehiculo_a.placa, "sin_odt": "true"},
        )
        assert body["total"] == 1, body
        assert ids(body) == [f"FLY-LIST-{sufijo}-1"], body
        print("  TL9 OK")

        print("\n[TODOS LOS TESTS FLYPASS LIST PASARON]")
        return 0
    finally:
        db.close()
        cleanup = SessionLocal()
        try:
            if flypass_ids:
                cleanup.query(FlypassTransaccion).filter(
                    FlypassTransaccion.id.in_(flypass_ids)
                ).delete(synchronize_session=False)
            if gasto_ids:
                cleanup.query(Gasto).filter(Gasto.id.in_(gasto_ids)).delete(
                    synchronize_session=False
                )
            if viaje_ids:
                cleanup.query(ViajeODT).filter(ViajeODT.id.in_(viaje_ids)).delete(
                    synchronize_session=False
                )
            if conductor_id is not None:
                cleanup.query(Conductor).filter(Conductor.id == conductor_id).delete(
                    synchronize_session=False
                )
            if vehiculo_ids:
                cleanup.query(Vehiculo).filter(Vehiculo.id.in_(vehiculo_ids)).delete(
                    synchronize_session=False
                )
            limpiar_tokens_nuevos(cleanup, "test@celr.com", tokens_antes_test)
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cleanup.close()


if __name__ == "__main__":
    sys.exit(main())
