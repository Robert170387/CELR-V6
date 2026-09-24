"""Pruebas del OCR de comprobantes CELR v6.

Contrato validado:
  * Parser de campos (NIT/Proveedor, Fecha, Valor Total + extras).
  * Hash anti-duplicados LÓGICO: MD5(NIT/Proveedor + Fecha + Monto), independiente
    de los bytes de la imagen.
  * Degradación a 200 con campos nulos cuando el OCR no puede leer el recibo.
  * Detección de duplicado por hash lógico.
"""
import os
import sys
import hashlib
from decimal import Decimal
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models.flota import (
    Vehiculo,
    Conductor,
    Usuario as UsuarioModel,
)
from app.models.operaciones import Gasto, ViajeODT
from app.services import ocr_service
from app.services.ocr_parser import (
    extract_receipt_fields,
    parse_money,
    parse_date,
    find_proveedor,
    find_nit,
    find_valor_total,
)
from app.services.ocr_service import compute_logical_hash, process_receipt_image
from _test_helpers import capturar_token_ids, limpiar_tokens_nuevos

RECIBO = """ESTACION DE SERVICIO EL PRADO S.A.S
NIT: 900.123.456-7
Direccion: Calle 10 # 20-30
Fecha de emision: 16/09/2026
Factura No: FE-000123
Combustible Diesel
Galones: 25.50
KM: 152300
Subtotal: 200.000
IVA: 38.000
Total a pagar: $238.000
"""


def seed_db(db):
    veh = db.query(Vehiculo).filter(Vehiculo.placa == "SKN756").first()
    if not veh:
        veh = Vehiculo(placa="SKN756", marca="Chevrolet", modelo="Express", anio=2020, estado="activo")
        db.add(veh)
    cond = db.query(Conductor).filter(Conductor.cedula == "12345678").first()
    if not cond:
        cond = Conductor(nombre_completo="Juan Perez", cedula="12345678", estado="activo")
        db.add(cond)
    usuario = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
    if not usuario:
        usuario = UsuarioModel(
            correo="test@celr.com",
            contrasena_hash=hash_password("admin123"),
            rol="admin",
            activo=True,
        )
        db.add(usuario)
    db.commit()
    db.refresh(veh)
    db.refresh(cond)
    return veh.id, cond.id


def test_parse_money():
    print("\n=== Test 1: parse_money ===")
    cases = {
        "238.000": Decimal("238000"),
        "$238.000": Decimal("238000"),
        "1.234.567,89": Decimal("1234567.89"),
        "1,234,567.89": Decimal("1234567.89"),
        "25.50": Decimal("25.50"),
        "0": Decimal("0"),
        "": None,
        "abc": None,
    }
    for raw, expected in cases.items():
        got = parse_money(raw)
        assert got == expected, f"parse_money({raw!r}) == {got}, esperado {expected}"
        print(f"  {raw!r:>18} -> {got}")
    print("  Formatos COP/US: PASADO")


def test_parse_date():
    print("\n=== Test 2: parse_date ===")
    assert parse_date("16/09/2026") == date(2026, 9, 16)
    assert parse_date("2026-09-16") == date(2026, 9, 16)
    assert parse_date("16-09-26") == date(2026, 9, 16)
    assert parse_date("16 de septiembre de 2026") == date(2026, 9, 16)
    assert parse_date("31/31/2026") is None
    print("  Fechas dd/mm/yyyy, yyyy-mm-dd, dd-mm-yy y texto: PASADO")


def test_extract_fields():
    print("\n=== Test 3: extract_receipt_fields ===")
    fields = extract_receipt_fields(RECIBO)
    print(f"  {fields}")
    assert "EL PRADO" in fields["proveedor"], fields["proveedor"]
    assert fields["nit"] == "900.123.456-7", fields["nit"]
    assert fields["fecha_gasto"] == date(2026, 9, 16), fields["fecha_gasto"]
    assert fields["valor_total"] == Decimal("238000"), fields["valor_total"]
    assert fields["num_factura"] == "FE-000123", fields["num_factura"]
    assert fields["cantidad_galones"] == Decimal("25.50"), fields["cantidad_galones"]
    assert fields["km_registro"] == Decimal("152300"), fields["km_registro"]
    print("  Proveedor, NIT, Fecha, Total, Factura, Galones y KM: PASADO")


def test_logical_hash():
    print("\n=== Test 4: hash lógico (independiente de la imagen) ===")
    h1 = compute_logical_hash(
        nit="900.123.456-7", proveedor="EL PRADO", fecha=date(2026, 9, 16), monto=Decimal("238000")
    )
    h2 = compute_logical_hash(
        nit="9001234567", proveedor="Otro nombre", fecha=date(2026, 9, 16), monto=Decimal("238000.00")
    )
    assert h1 == h2, "El NIT normalizado debe producir el mismo hash"
    assert len(h1) == 32

    h3 = compute_logical_hash(
        nit="900.123.456-7", proveedor="EL PRADO", fecha=date(2026, 9, 16), monto=Decimal("238001")
    )
    assert h3 != h1, "Distinto monto debe producir distinto hash"

    assert compute_logical_hash(proveedor="EL PRADO", fecha=date(2026, 9, 16), monto=Decimal("0")) is None
    assert compute_logical_hash(nit="900123", fecha=None, monto=Decimal("100")) is None
    print(f"  hash lógico = {h1[:16]}...")
    print("  Determinista, NIT-normalizado, sensible al monto y nulo sin datos: PASADO")


def test_degraded_ocr():
    print("\n=== Test 5: degradación del OCR (sin excepción) ===")
    fake_bytes = b"esto-no-es-una-imagen-valida"
    result = process_receipt_image(fake_bytes)

    assert isinstance(result["hash_comprobante"], str) and len(result["hash_comprobante"]) == 32
    assert result["valor_total"] is None, "Un recibo ilegible no debe reportar monto"
    assert result["fecha_gasto"] is None
    assert result["datos_ocr_json"]["confiable"] is False
    assert result["datos_ocr_json"]["campos_extraidos"]["valor_total"] is None
    print(f"  hash único = {result['hash_comprobante'][:16]}...")
    print(f"  confianza = {result['confianza']}, error = {result['datos_ocr_json']['error']}")
    print("  Degradación segura: PASADO")


def login(client) -> str:
    r = client.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
    assert r.status_code == 200, f"Login fallido: {r.status_code} {r.text}"
    return r.json()["access_token"]


def cleanup(db, viaje_id: int):
    db.query(Gasto).filter(Gasto.viaje_id == viaje_id).delete()
    db.query(ViajeODT).filter(ViajeODT.id == viaje_id).delete()
    db.commit()


def test_scan_receipt_security():
    print("\n=== Test 6: scan-receipt - seguridad de acceso y archivo ===")
    client = TestClient(app)

    r = client.post(
        "/api/v1/gastos/scan-receipt",
        files={"file": ("r.jpg", b"abc", "image/jpeg")},
        data={"viaje_id": "1", "vehiculo_id": "1"},
    )
    assert r.status_code == 401, f"Sin token debe ser 401: {r.status_code}"
    print("  Sin token -> 401: PASADO")

    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/v1/gastos/scan-receipt",
        files={"file": ("r.jpg", b"", "image/jpeg")},
        data={"viaje_id": "1", "vehiculo_id": "1"},
        headers=headers,
    )
    assert r.status_code == 400, f"Archivo vacío debe ser 400: {r.status_code}"
    print("  Archivo vacío -> 400: PASADO")

    r = client.post(
        "/api/v1/gastos/scan-receipt",
        files={"file": ("r.zip", b"PK\x03\x04", "application/zip")},
        data={"viaje_id": "1", "vehiculo_id": "1"},
        headers=headers,
    )
    assert r.status_code == 415, f"Formato no soportado debe ser 415: {r.status_code}"
    print("  Formato no soportado -> 415: PASADO")


def test_scan_receipt_duplicate_detection():
    print("\n=== Test 7: scan-receipt - anti-duplicado por hash lógico ===")
    client = TestClient(app)
    db = SessionLocal()
    try:
        vehicle_id, cond_id = seed_db(db)
        odt = ViajeODT(
            vehiculo_id=vehicle_id, conductor_id=cond_id,
            origen="Bogota", destino="Medellin", fecha_salida=date.today(), estado="en_curso",
        )
        db.add(odt)
        db.commit()
        db.refresh(odt)
        viaje_id = odt.id

        token = login(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Simula el OCR: mismo recibo -> mismo hash canónico, aunque los bytes difieran.
        from app.services.hashing import compute_gasto_hash

        hash_logico = compute_logical_hash(
            nit="9001234567", proveedor=None, fecha=date(2026, 9, 16), monto=Decimal("238000")
        )
        esperado = compute_gasto_hash(
            num_factura="FE-000123",
            fecha=date(2026, 9, 16),
            monto=Decimal("238000"),
            viaje_id=viaje_id,
            proveedor_nit="9001234567",
            proveedor_nombre="EL PRADO",
        )
        resultado_fijo = {
            "hash_comprobante": hash_logico,
            "hash_logico": hash_logico,
            "nit": "900.123.456-7",
            "proveedor": "EL PRADO",
            "num_factura": "FE-000123",
            "fecha_gasto": date(2026, 9, 16),
            "valor_total": 238000.0,
            "cantidad_galones": 25.5,
            "km_registro": 152300.0,
            "confianza": 92.0,
            "datos_ocr_json": {"motor": "fake", "hash_logico": hash_logico},
        }
        original = ocr_service.process_receipt_image
        ocr_service.process_receipt_image = lambda _bytes: dict(resultado_fijo)
        try:
            with open(__file__, "rb") as f:
                r1 = client.post(
                    "/api/v1/gastos/scan-receipt",
                    files={"file": ("recibo.jpg", f, "image/jpeg")},
                    data={"viaje_id": str(viaje_id), "vehiculo_id": str(vehicle_id)},
                    headers=headers,
                )
            assert r1.status_code == 200, f"Primera llamada: {r1.status_code} {r1.text}"
            assert r1.json()["hash_comprobante"] == esperado
            assert r1.json()["valor_total"] == 238000.0
            gasto_id = r1.json()["gasto_id"]
            print(f"  Primera llamada -> 200, gasto_id={gasto_id}")

            r2 = client.post(
                "/api/v1/gastos/scan-receipt",
                files={"file": ("recibo_recomprimido.jpg", b"otros-bytes-distintos", "image/jpeg")},
                data={"viaje_id": str(viaje_id), "vehiculo_id": str(vehicle_id)},
                headers=headers,
            )
            assert r2.status_code == 400, f"Duplicado debe ser 400: {r2.status_code} {r2.text}"
            assert "duplicado" in r2.json()["detail"].lower()
            print(f"  Recibo recomprimido -> 400: {r2.json()['detail']}")

            db.refresh(odt)
            stored = db.query(Gasto).filter(Gasto.id == gasto_id).first()
            assert stored is not None and stored.hash_comprobante == esperado
        finally:
            ocr_service.process_receipt_image = original
            cleanup(db, viaje_id)
    finally:
        db.close()


def test_scan_receipt_manual_fallback():
    print("\n=== Test 8: scan-receipt - recibo ilegible crea Gasto pendiente (200) ===")
    client = TestClient(app)
    db = SessionLocal()
    try:
        vehicle_id, cond_id = seed_db(db)
        odt = ViajeODT(
            vehiculo_id=vehicle_id, conductor_id=cond_id,
            origen="Bogota", destino="Medellin", fecha_salida=date.today(), estado="en_curso",
        )
        db.add(odt)
        db.commit()
        db.refresh(odt)

        token = login(client)
        headers = {"Authorization": f"Bearer {token}"}
        with open(__file__, "rb") as f:
            r = client.post(
                "/api/v1/gastos/scan-receipt",
                files={"file": ("ilegible.jpg", f, "image/jpeg")},
                data={"viaje_id": str(odt.id), "vehiculo_id": str(vehicle_id)},
                headers=headers,
            )
        assert r.status_code == 200, f"OCR ilegible debe ser 200: {r.status_code} {r.text}"
        body = r.json()
        assert body["gasto_id"], "Debe crear el Gasto para captura manual"
        assert body["valor_total"] is None
        stored = db.query(Gasto).filter(Gasto.id == body["gasto_id"]).first()
        assert stored.estado_validacion == "pendiente"
        assert stored.valor_total == Decimal("0")
        print(f"  Recibo ilegible -> 200, gasto_id={body['gasto_id']}, estado=pendiente")
    finally:
        cleanup(db, odt.id)
        db.close()


def main():
    print("Iniciando pruebas de OCR/visión CELR v6 (Tesseract + hash lógico)...")
    db = SessionLocal()
    tokens_antes_test = capturar_token_ids(db, "test@celr.com")
    try:
        test_parse_money()
        test_parse_date()
        test_extract_fields()
        test_logical_hash()
        test_degraded_ocr()
        test_scan_receipt_security()
        test_scan_receipt_duplicate_detection()
        test_scan_receipt_manual_fallback()
        print("\n[TODOS LOS TESTS DE OCR PASARON]")
    finally:
        # Limpieza 2.B: refresh_tokens de test@celr.com creados por los logins de esta
        # corrida (los viajes/gastos del OCR ya se limpian dentro de cada test).
        # Nunca se borra test@celr.com ni el seed (SKN756 / cédula 12345678).
        try:
            limpiar_tokens_nuevos(db, "test@celr.com", tokens_antes_test)
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.close()


if __name__ == "__main__":
    main()
