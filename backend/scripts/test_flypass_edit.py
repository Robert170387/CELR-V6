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
        marca="Flypass Edit Test",
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
        nombre_completo=f"Conductor Edit {sufijo[:6]}",
        cedula=f"7{sufijo[:9]}",
        estado="activo",
    )
    db.add(conductor)
    db.commit()
    db.refresh(conductor)
    return conductor


def crear_viaje(
    db: Session,
    vehiculo_id: int,
    conductor_id: int,
    fecha_salida: date,
    fecha_llegada: date,
) -> ViajeODT:
    viaje = ViajeODT(
        vehiculo_id=vehiculo_id,
        conductor_id=conductor_id,
        origen="Bogota",
        destino="Medellin",
        fecha_salida=fecha_salida,
        fecha_llegada=fecha_llegada,
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


def crear_gasto(
    db: Session,
    vehiculo_id: int,
    sufijo: str,
) -> Gasto:
    gasto = Gasto(
        viaje_id=None,
        vehiculo_id=vehiculo_id,
        categoria="peajes",
        descripcion="Gasto para prueba de edición Flypass",
        fecha_gasto=date(2026, 10, 1),
        valor_total=Decimal("1000.00"),
        responsable_pago="empresa",
        asumido_por="empresa",
        metodo_pago="tag",
        estado_pago="pendiente_por_pagar",
        tiene_num_factura=False,
        hash_comprobante=f"flypass-edit-{sufijo}",
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto


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
        nombre_peaje=f"Peaje Edit {numero}",
        ciudad_peaje=None,
        ciudad_peaje_municipio_id=None,
        valor=Decimal(monto),
        num_transaccion_flypass=f"FLY-EDIT-{sufijo}-{numero}",
        viaje_id=viaje_id,
        gasto_id=gasto_id,
        raw_data={"fixture": sufijo, "numero": numero},
        estado="importado",
        importado_en=datetime.now(timezone.utc),
    )
    db.add(transaccion)
    db.commit()
    db.refresh(transaccion)
    return transaccion


def leer_transaccion(db: Session, flypass_id: int) -> FlypassTransaccion:
    return (
        db.query(FlypassTransaccion)
        .populate_existing()
        .filter(FlypassTransaccion.id == flypass_id)
        .one()
    )


def editar(
    client: TestClient,
    headers: dict,
    flypass_id: int,
    body: dict,
    esperado: int = 200,
):
    respuesta = client.patch(
        f"/api/v1/flypass/{flypass_id}",
        json=body,
        headers=headers,
    )
    assert respuesta.status_code == esperado, (
        f"PATCH esperaba {esperado}, obtuvo {respuesta.status_code}: {respuesta.text}"
    )
    return respuesta


def main() -> int:
    print("Iniciando pruebas de edición Flypass CELR v6...")
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

        vehiculo_a = crear_vehiculo(db, f"E{sufijo[:8]}")
        vehiculo_b = crear_vehiculo(db, f"F{sufijo[:8]}")
        vehiculo_ids.extend([vehiculo_a.id, vehiculo_b.id])
        conductor = crear_conductor(db, sufijo)
        conductor_id = conductor.id
        viaje_a = crear_viaje(
            db, vehiculo_a.id, conductor.id, date(2026, 10, 1), date(2026, 10, 5)
        )
        viaje_b = crear_viaje(
            db, vehiculo_b.id, conductor.id, date(2026, 10, 1), date(2026, 10, 5)
        )
        viaje_ids.extend([viaje_a.id, viaje_b.id])
        gasto = crear_gasto(db, vehiculo_a.id, sufijo)
        gasto_ids.append(gasto.id)

        # TP1, TP3, TP4, TP5, TP6 y TP8 parten sin viaje.
        # TP2, TP9 y TP10 parten con viaje para probar los estados parciales.
        registros = [
            crear_transaccion(db, sufijo, 1, vehiculo_a.id, date(2026, 10, 2), "1001.00", gasto.id, None),
            crear_transaccion(db, sufijo, 2, vehiculo_a.id, date(2026, 10, 2), "1002.00", None, viaje_a.id),
            crear_transaccion(db, sufijo, 3, vehiculo_a.id, date(2026, 10, 2), "1003.00", None, None),
            crear_transaccion(db, sufijo, 4, vehiculo_a.id, date(2026, 10, 2), "1004.00", None, None),
            crear_transaccion(db, sufijo, 5, vehiculo_a.id, date(2026, 10, 2), "1005.00", None, None),
            crear_transaccion(db, sufijo, 6, vehiculo_a.id, date(2026, 10, 2), "1006.00", None, None),
            crear_transaccion(db, sufijo, 7, vehiculo_a.id, date(2026, 10, 2), "1007.00", None, None),
            crear_transaccion(db, sufijo, 8, vehiculo_a.id, date(2026, 10, 2), "1008.00", None, None),
            crear_transaccion(db, sufijo, 9, vehiculo_a.id, date(2026, 10, 2), "1009.00", None, viaje_a.id),
            crear_transaccion(db, sufijo, 10, vehiculo_a.id, date(2026, 10, 2), "1010.00", None, viaje_a.id),
        ]
        flypass_ids.extend(registro.id for registro in registros)
        (
            tp1,
            tp2,
            tp3,
            tp4,
            tp5,
            tp6,
            _tp7,
            tp8,
            tp9,
            tp10,
        ) = registros

        client = TestClient(app)
        login = client.post(
            "/api/v1/auth/login",
            json={"correo": "test@celr.com", "contrasena": "admin123"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        print("\n=== TP1: asignar viaje del mismo vehículo ===")
        respuesta = editar(client, headers, tp1.id, {"viaje_id": viaje_a.id})
        body = respuesta.json()
        assert body["viaje_id"] == viaje_a.id, body
        assert body["estado"] == "asignado_a_viaje", body
        assert body["placa"] == vehiculo_a.placa, body
        assert body["gasto_id"] == gasto.id, body
        fila = leer_transaccion(db, tp1.id)
        assert fila.viaje_id == viaje_a.id, fila.estado
        assert fila.estado == "asignado_a_viaje", fila.estado
        assert fila.gasto_id == gasto.id, fila.gasto_id
        print("  TP1 OK")

        print("\n=== TP2: limpiar viaje con null explícito ===")
        respuesta = editar(client, headers, tp2.id, {"viaje_id": None})
        body = respuesta.json()
        assert body["viaje_id"] is None, body
        assert body["estado"] == "sin_viaje", body
        fila = leer_transaccion(db, tp2.id)
        assert fila.viaje_id is None, fila.viaje_id
        assert fila.estado == "sin_viaje", fila.estado
        print("  TP2 OK")

        print("\n=== TP3: viaje de otro vehículo rechazado ===")
        antes = leer_transaccion(db, tp3.id)
        estado_antes = (antes.viaje_id, antes.estado)
        respuesta = editar(
            client, headers, tp3.id, {"viaje_id": viaje_b.id}, esperado=409
        )
        assert respuesta.json()["detail"] == "El viaje pertenece a otro vehiculo"
        despues = leer_transaccion(db, tp3.id)
        assert (despues.viaje_id, despues.estado) == estado_antes
        print("  TP3 OK")

        print("\n=== TP4: viaje inexistente rechazado ===")
        antes = leer_transaccion(db, tp4.id)
        estado_antes = (antes.viaje_id, antes.estado)
        respuesta = editar(
            client, headers, tp4.id, {"viaje_id": 999999999}, esperado=404
        )
        assert respuesta.json()["detail"] == "Viaje no encontrado"
        despues = leer_transaccion(db, tp4.id)
        assert (despues.viaje_id, despues.estado) == estado_antes
        print("  TP4 OK")

        print("\n=== TP5: estado inválido rechazado por Pydantic ===")
        antes = leer_transaccion(db, tp5.id)
        estado_antes = (antes.viaje_id, antes.estado)
        respuesta = editar(
            client, headers, tp5.id, {"estado": "banana"}, esperado=422
        )
        assert respuesta.json()["detail"], respuesta.text
        despues = leer_transaccion(db, tp5.id)
        assert (despues.viaje_id, despues.estado) == estado_antes
        print("  TP5 OK")

        print("\n=== TP6: estado explícito prevalece sobre auto-coherencia ===")
        respuesta = editar(
            client,
            headers,
            tp6.id,
            {"viaje_id": viaje_a.id, "estado": "ignorar"},
        )
        body = respuesta.json()
        assert body["viaje_id"] == viaje_a.id, body
        assert body["estado"] == "ignorar", body
        fila = leer_transaccion(db, tp6.id)
        assert fila.viaje_id == viaje_a.id, fila.viaje_id
        assert fila.estado == "ignorar", fila.estado
        print("  TP6 OK")

        print("\n=== TP7: Flypass inexistente ===")
        respuesta = editar(
            client,
            headers,
            999999999,
            {"estado": "ignorar"},
            esperado=404,
        )
        assert respuesta.json()["detail"] == "Flypass transaccion no encontrada"
        print("  TP7 OK")

        print("\n=== TP8: body vacío rechazado ===")
        antes = leer_transaccion(db, tp8.id)
        estado_antes = (antes.viaje_id, antes.estado)
        respuesta = editar(client, headers, tp8.id, {}, esperado=422)
        assert respuesta.json()["detail"] == "Debe proveer al menos viaje_id o estado"
        despues = leer_transaccion(db, tp8.id)
        assert (despues.viaje_id, despues.estado) == estado_antes
        print("  TP8 OK")

        print("\n=== TP9: estado solo no toca viaje existente ===")
        respuesta = editar(client, headers, tp9.id, {"estado": "ignorar"})
        body = respuesta.json()
        assert body["viaje_id"] == viaje_a.id, body
        assert body["estado"] == "ignorar", body
        fila = leer_transaccion(db, tp9.id)
        assert fila.viaje_id == viaje_a.id, fila.viaje_id
        assert fila.estado == "ignorar", fila.estado
        print("  TP9 OK")

        print("\n=== TP10: omitir viaje_id no limpia asociación existente ===")
        respuesta = editar(client, headers, tp10.id, {"estado": "importado"})
        body = respuesta.json()
        assert body["viaje_id"] == viaje_a.id, body
        assert body["estado"] == "importado", body
        fila = leer_transaccion(db, tp10.id)
        assert fila.viaje_id == viaje_a.id, fila.viaje_id
        assert fila.estado == "importado", fila.estado
        print("  TP10 OK")

        print("\n[TODOS LOS TESTS FLYPASS EDIT PASARON]")
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
