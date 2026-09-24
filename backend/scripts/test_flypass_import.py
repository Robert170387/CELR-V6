import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.financiero import FlypassTransaccion
from app.models.flota import Conductor, RefreshToken, Usuario as UsuarioModel, Vehiculo
from app.models.operaciones import Gasto, Proveedor, ViajeODT
from app.services.operaciones import recalcular_viaje

HEADERS = [
    "TRANSACCION",
    "PLACA",
    "FECHA_MVTO",
    "MONTO",
    "PUNTO ATENCION",
    "EMPRESA",
    "SENTIDO",
    "SALDO",
    "DOCUMENTO CONTABLE",
    "FECHA_INGRESO",
    "FECHA_APLICACION",
    "TIPO",
    "ESTADO",
    "OBSERVACION",
]


def fila_excel(
    transaccion: str,
    placa: str,
    fecha: date,
    monto: str,
    punto: str = "Peaje Test",
) -> list:
    return [
        transaccion,
        placa,
        fecha,
        float(Decimal(monto)),
        punto,
        "Flypass Colombia",
        "DEBITO",
        "ABIERTA",
        "",
        fecha,
        fecha,
        "TAG",
        "PENDIENTE",
        "fixture importador",
    ]


def workbook_bytes(filas: list[list], headers: list[str] | None = None) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Flypass"
    hoja.append(headers or HEADERS)
    for fila in filas:
        hoja.append(fila)
    salida = BytesIO()
    libro.save(salida)
    libro.close()
    return salida.getvalue()


def crear_vehiculo(db: Session, sufijo: str) -> Vehiculo:
    vehiculo = Vehiculo(
        placa=f"F{sufijo[:8]}",
        marca="Flypass Test",
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
        nombre_completo=f"Conductor Flypass {sufijo[:6]}",
        cedula=f"9{sufijo[:9]}",
        estado="activo",
    )
    db.add(conductor)
    db.commit()
    db.refresh(conductor)
    return conductor


def crear_gasto_candidato(
    db: Session,
    vehiculo_id: int,
    proveedor_id: int | None,
    fecha: date,
    monto: str,
    sufijo: str,
    numero: int,
) -> Gasto:
    gasto = Gasto(
        viaje_id=None,
        vehiculo_id=vehiculo_id,
        proveedor_id=proveedor_id,
        categoria="peajes",
        descripcion=f"Gasto peaje fixture {numero}",
        fecha_gasto=fecha,
        valor_total=Decimal(monto),
        responsable_pago="empresa",
        asumido_por="empresa",
        metodo_pago="tag",
        estado_pago="pendiente_por_pagar",
        tiene_num_factura=False,
        hash_comprobante=f"flypass-fixture-{sufijo}-{numero}",
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto


def crear_odt(
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


def importar(
    client: TestClient,
    headers: dict,
    contenido: bytes,
    nombre: str = "flypass.xlsx",
):
    respuesta = client.post(
        "/api/v1/flypass/import",
        files={
            "file": (
                nombre,
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def main() -> int:
    print("Iniciando pruebas del importador Flypass CELR v6...")
    db = SessionLocal()
    inicio = datetime.now(timezone.utc)
    sufijo = uuid.uuid4().hex
    flypass_ids: list[int] = []
    gasto_ids: list[int] = []
    viaje_ids: list[int] = []
    proveedor_preexistente = (
        db.query(Proveedor).filter(Proveedor.razon_social == "Flypass").first()
    )
    proveedor_preexistente_id = proveedor_preexistente.id if proveedor_preexistente else None
    proveedor_id_test = proveedor_preexistente_id
    proveedor_creado_id = None
    vehiculo = None
    conductor = None
    vehiculo_id_test = None
    conductor_id_test = None

    try:
        admin = (
            db.query(UsuarioModel)
            .filter(UsuarioModel.correo == "test@celr.com")
            .first()
        )
        assert admin is not None, "Se requiere admin test@celr.com"

        vehiculo = crear_vehiculo(db, sufijo)
        conductor = crear_conductor(db, sufijo)
        vehiculo_id_test = vehiculo.id
        conductor_id_test = conductor.id
        client = TestClient(app)
        login = client.post(
            "/api/v1/auth/login",
            json={"correo": "test@celr.com", "contrasena": "admin123"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        print("\n=== TF1: dos filas nuevas ===")
        contenido_dos = workbook_bytes(
            [
                fila_excel(f"FLYTEST-{sufijo}-1", vehiculo.placa, date(2026, 9, 20), "12345.67"),
                fila_excel(f"FLYTEST-{sufijo}-2", vehiculo.placa, date(2026, 9, 21), "23456.78"),
            ]
        )
        reporte = importar(client, headers, contenido_dos)
        assert reporte["insertados"] == 2, reporte
        assert reporte["duplicados"] == 0, reporte
        assert reporte["creados_gastos"] == 2, reporte
        assert reporte["matcheados_gastos"] == 0, reporte
        assert reporte["sin_odt"] == 2, reporte
        assert reporte["errores"] == [], reporte
        importadas = (
            db.query(FlypassTransaccion)
            .filter(FlypassTransaccion.num_transaccion_flypass.like(f"FLYTEST-{sufijo}-%"))
            .all()
        )
        assert len(importadas) == 2
        flypass_ids.extend(fila.id for fila in importadas)
        gasto_ids.extend(fila.gasto_id for fila in importadas if fila.gasto_id)
        assert db.query(Gasto).filter(Gasto.id.in_(gasto_ids)).count() == 2
        gastos_importados = db.query(Gasto).filter(Gasto.id.in_(gasto_ids)).all()
        assert all(g.estado_pago == "pendiente_por_pagar" for g in gastos_importados)
        assert all(g.metodo_pago == "tag" for g in gastos_importados)
        assert all(g.proveedor_id is not None for g in gastos_importados)
        if proveedor_creado_id is None:
            proveedor_actual = db.query(Proveedor).filter(
                Proveedor.razon_social == "Flypass"
            ).first()
            if proveedor_actual:
                proveedor_creado_id = proveedor_actual.id
        print("  TF1 OK")

        print("\n=== TF2: reimportación idempotente ===")
        reporte = importar(client, headers, contenido_dos)
        assert reporte["insertados"] == 0, reporte
        assert reporte["duplicados"] == 2, reporte
        assert reporte["creados_gastos"] == 0, reporte
        assert reporte["matcheados_gastos"] == 0, reporte
        assert db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass.like(f"FLYTEST-{sufijo}-%")
        ).count() == 2
        print("  TF2 OK")

        print("\n=== TF3: placa desconocida ===")
        contenido_placa = workbook_bytes(
            [fila_excel(f"FLYTEST-{sufijo}-3", "NOEXISTE", date(2026, 9, 20), "34567.89")]
        )
        reporte = importar(client, headers, contenido_placa)
        assert reporte["sin_placa"] == 1, reporte
        assert reporte["insertados"] == 0, reporte
        assert reporte["errores"][0]["placa"] == "NOEXISTE", reporte
        assert not db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass == f"FLYTEST-{sufijo}-3"
        ).first()
        print("  TF3 OK")

        print("\n=== TF4: match de gasto existente ===")
        gasto_match = crear_gasto_candidato(
            db, vehiculo.id, proveedor_id_test, date(2026, 9, 22), "45678.90", sufijo, 4
        )
        gasto_ids.append(gasto_match.id)
        contenido_match = workbook_bytes(
            [fila_excel(f"FLYTEST-{sufijo}-4", vehiculo.placa, date(2026, 9, 22), "45678.90")]
        )
        reporte = importar(client, headers, contenido_match)
        assert reporte["matcheados_gastos"] == 1, reporte
        assert reporte["creados_gastos"] == 0, reporte
        assert reporte["insertados"] == 1, reporte
        fila_match = db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass == f"FLYTEST-{sufijo}-4"
        ).one()
        assert fila_match.gasto_id == gasto_match.id
        assert fila_match.legalizado_en_gastos is True
        flypass_ids.append(fila_match.id)
        print("  TF4 OK")

        print("\n=== TF5: más de un gasto candidato ===")
        gasto_ambiguo_1 = crear_gasto_candidato(
            db, vehiculo.id, proveedor_id_test, date(2026, 9, 23), "56789.10", sufijo, 5
        )
        gasto_ambiguo_2 = crear_gasto_candidato(
            db, vehiculo.id, proveedor_id_test, date(2026, 9, 23), "56789.10", sufijo, 6
        )
        gasto_ids.extend([gasto_ambiguo_1.id, gasto_ambiguo_2.id])
        contenido_ambiguo = workbook_bytes(
            [fila_excel(f"FLYTEST-{sufijo}-5", vehiculo.placa, date(2026, 9, 23), "56789.10")]
        )
        reporte = importar(client, headers, contenido_ambiguo)
        assert reporte["ambiguos"] == 1, reporte
        assert reporte["insertados"] == 0, reporte
        assert reporte["creados_gastos"] == 0, reporte
        assert len(reporte["errores"][0]["candidatos"]) == 2, reporte
        assert not db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass == f"FLYTEST-{sufijo}-5"
        ).first()
        print("  TF5 OK")

        print("\n=== TF6: asociación de ODT única y ausencia de ODT ===")
        viaje = crear_odt(
            db, vehiculo.id, conductor.id, date(2026, 9, 25), date(2026, 9, 27)
        )
        viaje_ids.append(viaje.id)
        contenido_odt = workbook_bytes(
            [
                fila_excel(f"FLYTEST-{sufijo}-6", vehiculo.placa, date(2026, 9, 26), "67891.20"),
                fila_excel(f"FLYTEST-{sufijo}-7", vehiculo.placa, date(2026, 10, 15), "67891.21"),
            ]
        )
        reporte = importar(client, headers, contenido_odt)
        assert reporte["insertados"] == 2, reporte
        assert reporte["sin_odt"] == 1, reporte
        fila_odt = db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass == f"FLYTEST-{sufijo}-6"
        ).one()
        fila_sin_odt = db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass == f"FLYTEST-{sufijo}-7"
        ).one()
        assert fila_odt.viaje_id == viaje.id
        assert fila_sin_odt.viaje_id is None
        flypass_ids.extend([fila_odt.id, fila_sin_odt.id])
        gasto_ids.extend([fila_odt.gasto_id, fila_sin_odt.gasto_id])
        print("  TF6 OK")

        print("\n=== TF7: encabezado faltante ===")
        antes = db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass.like(f"FLYTEST-{sufijo}-%")
        ).count()
        headers_invalidos = [h for h in HEADERS if h != "TRANSACCION"]
        invalido = workbook_bytes(
            [fila_excel(f"FLYTEST-{sufijo}-8", vehiculo.placa, date(2026, 9, 28), "78912.30")],
            headers=headers_invalidos,
        )
        respuesta = client.post(
            "/api/v1/flypass/import",
            files={"file": ("invalido.xlsx", invalido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=headers,
        )
        assert respuesta.status_code == 400, respuesta.text
        assert "TRANSACCION" in respuesta.text
        despues = db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass.like(f"FLYTEST-{sufijo}-%")
        ).count()
        assert despues == antes
        print("  TF7 OK")

        print("\n=== TF8: raw_data conserva las 14 columnas ===")
        contenido_raw = workbook_bytes(
            [fila_excel(f"FLYTEST-{sufijo}-9", vehiculo.placa, date(2026, 9, 29), "89123.40")]
        )
        reporte = importar(client, headers, contenido_raw)
        assert reporte["insertados"] == 1, reporte
        fila_raw = db.query(FlypassTransaccion).filter(
            FlypassTransaccion.num_transaccion_flypass == f"FLYTEST-{sufijo}-9"
        ).one()
        assert set(fila_raw.raw_data) == set(HEADERS), fila_raw.raw_data
        assert fila_raw.raw_data["TRANSACCION"] == f"FLYTEST-{sufijo}-9"
        assert fila_raw.raw_data["EMPRESA"] == "Flypass Colombia"
        flypass_ids.append(fila_raw.id)
        gasto_ids.append(fila_raw.gasto_id)
        print("  TF8 OK")

        print("\n[TODOS LOS TESTS FLYPASS IMPORT PASARON]")
        return 0
    finally:
        db.close()
        cleanup = SessionLocal()
        try:
            pendientes = cleanup.query(FlypassTransaccion).filter(
                FlypassTransaccion.num_transaccion_flypass.like(f"FLYTEST-{sufijo}-%")
            ).all()
            for pendiente in pendientes:
                flypass_ids.append(pendiente.id)
                if pendiente.gasto_id:
                    gasto_ids.append(pendiente.gasto_id)
            if flypass_ids:
                cleanup.query(FlypassTransaccion).filter(
                    FlypassTransaccion.id.in_(flypass_ids)
                ).delete(synchronize_session=False)

            gastos_fixture = cleanup.query(Gasto).filter(
                Gasto.hash_comprobante.like(f"flypass-fixture-{sufijo}-%")
            ).all()
            gasto_ids.extend(gasto.id for gasto in gastos_fixture)
            if gasto_ids:
                cleanup.query(Gasto).filter(Gasto.id.in_(gasto_ids)).delete(
                    synchronize_session=False
                )
            if viaje_ids:
                cleanup.query(ViajeODT).filter(ViajeODT.id.in_(viaje_ids)).delete(
                    synchronize_session=False
                )
            if conductor_id_test is not None:
                cleanup.query(Conductor).filter(Conductor.id == conductor_id_test).delete(
                    synchronize_session=False
                )
            if vehiculo_id_test is not None:
                cleanup.query(Vehiculo).filter(Vehiculo.id == vehiculo_id_test).delete(
                    synchronize_session=False
                )
            if proveedor_preexistente_id is None:
                proveedor_a_borrar = proveedor_creado_id
                if proveedor_a_borrar is None:
                    proveedor_actual = cleanup.query(Proveedor).filter(
                        Proveedor.razon_social == "Flypass"
                    ).first()
                    proveedor_a_borrar = proveedor_actual.id if proveedor_actual else None
                if proveedor_a_borrar is not None:
                    cleanup.query(Proveedor).filter(
                        Proveedor.id == proveedor_a_borrar
                    ).delete(synchronize_session=False)
            admin = cleanup.query(UsuarioModel).filter(
                UsuarioModel.correo == "test@celr.com"
            ).first()
            if admin:
                cleanup.query(RefreshToken).filter(
                    RefreshToken.usuario_id == admin.id,
                    RefreshToken.creado_en >= inicio,
                ).delete(synchronize_session=False)
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cleanup.close()


if __name__ == "__main__":
    sys.exit(main())
