"""
CELR v6 - Prueba de extremo a extremo (E2E Flow)
Valida el ciclo completo de negocio:
  1. Registro e inicio de sesión (JWT)
  2. Creación de ODT / Viaje activo
  3. Escaneo e inserción de gasto vía OCR (rechazo de duplicados)
  4. Consulta y cálculo de balance de liquidación
  5. Cierre definitivo de la ODT
"""
import sys
import os
import time
import requests
from decimal import Decimal

BASE_URL = os.getenv("CELR_BASE_URL", "http://localhost:8000")

SUFFIX = str(int(time.time() * 1000))
ODT_NUMERO = f"ODT-E2E-{SUFFIX}"
HASH_GASTO_1 = f"e2e-hash-{SUFFIX}-1"
HASH_GASTO_2 = f"e2e-hash-{SUFFIX}-2"


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_01_auth():
    print_section("TEST 1: Autenticación - Login con JWT")
    payload = {"correo": "test@celr.com", "contrasena": "admin123"}
    r = requests.post(f"{BASE_URL}/api/v1/auth/login", json=payload)
    print(f"  POST /api/v1/auth/login -> status={r.status_code}")
    assert r.status_code == 200, f"Login fallido: {r.text}"
    token = r.json()["access_token"]
    print(f"  Token recibido: {token[:40]}...")

    headers = {"Authorization": f"Bearer {token}"}
    r2 = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
    print(f"  GET /api/v1/auth/me -> status={r2.status_code}")
    assert r2.status_code == 200, f"getMe fallido: {r2.text}"
    user_data = r2.json()
    print(f"  Usuario autenticado: {user_data['correo']} (rol={user_data['rol']})")
    return token, headers


def test_02_create_viaje(headers):
    print_section("TEST 2: Crear ODT / Viaje Activo")
    viaje_data = {
        "numero_odt": ODT_NUMERO,
        "vehiculo_id": 1,
        "conductor_id": 1,
        "origen": "Bogota",
        "destino": "Medellin",
        "fecha_salida": "2026-09-16",
        "valor_flete_manifiesto": "1000000.00",
        "retefuente_valor": "100000.00",
        "reteica_valor": "50000.00",
        "estado": "en_curso",
    }
    r = requests.post(f"{BASE_URL}/api/v1/viajes", json=viaje_data, headers=headers)
    print(f"  POST /api/v1/viajes -> status={r.status_code}")
    assert r.status_code == 201, f"Crear viaje fallido: {r.text}"
    viaje = r.json()
    print(f"  Viaje creado: id={viaje['id']}, numero_odt={viaje['numero_odt']}")
    print(f"  flete_neto={viaje['flete_neto']}")
    return viaje['id'], viaje['flete_neto']


def test_03_scan_receipt(headers, viaje_id):
    print_section("TEST 3: Scan Receipt - OCR + Anti-Duplicado")

    # Registrar gasto directamente para simular scan
    gasto_data = {
        "viaje_id": viaje_id,
        "vehiculo_id": 1,
        "categoria": "combustible",
        "fecha_gasto": "2026-09-16",
        "valor_total": "300000.00",
        "hash_comprobante": HASH_GASTO_1,
        "km_registro": "500.00",
        "responsable_pago": "conductor",
        "asumido_por": "empresa",
        "tiene_num_factura": True,
    }
    r1 = requests.post(f"{BASE_URL}/api/v1/gastos", json=gasto_data, headers=headers)
    print(f"  POST /api/v1/gastos (primer gasto) -> status={r1.status_code}")
    assert r1.status_code == 201, f"Registrar gasto fallido: {r1.text}"
    gasto1 = r1.json()
    print(f"  Gasto creado: id={gasto1['id']}, hash={gasto1['hash_comprobante'][:20]}...")

    # Intentar duplicado
    r2 = requests.post(f"{BASE_URL}/api/v1/gastos", json=gasto_data, headers=headers)
    print(f"  POST /api/v1/gastos (duplicado) -> status={r2.status_code}")
    assert r2.status_code == 400, f"Deberia retornar 400: {r2.text}"
    assert "duplicado" in r2.json()["detail"].lower(), f"Detalle inesperado: {r2.json()}"
    print(f"  Anti-duplicado activo: {r2.json()['detail']}")

    # Segundo gasto diferente
    gasto2_data = {
        "viaje_id": viaje_id,
        "vehiculo_id": 1,
        "categoria": "peaje",
        "fecha_gasto": "2026-09-16",
        "valor_total": "50000.00",
        "hash_comprobante": HASH_GASTO_2,
        "km_registro": "600.00",
        "responsable_pago": "conductor",
        "asumido_por": "empresa",
    }
    r3 = requests.post(f"{BASE_URL}/api/v1/gastos", json=gasto2_data, headers=headers)
    print(f"  POST /api/v1/gastos (segundo gasto) -> status={r3.status_code}")
    assert r3.status_code == 201, f"Segundo gasto fallido: {r3.text}"
    print(f"  Gasto 2 creado: id={r3.json()['id']}")

    return [gasto1['id'], r3.json()['id']]


def test_04_calculate_liquidacion(headers, viaje_id):
    print_section("TEST 4: Calcular Liquidación - Balance Financiero")
    r = requests.get(f"{BASE_URL}/api/v1/liquidaciones/calcular/{viaje_id}", headers=headers)
    print(f"  GET /api/v1/liquidaciones/calcular/{viaje_id} -> status={r.status_code}")
    assert r.status_code == 200, f"Cálculo fallido: {r.text}"
    balance = r.json()
    print(f"  flete_neto = {balance['flete_neto']}")
    print(f"  total_gastos_empresa = {balance['total_gastos_empresa']}")
    print(f"  total_anticipos = {balance['total_anticipos']}")
    print(f"  comision_flete = {balance['comision_flete']}")
    print(f"  saldo_neto = {balance['saldo_neto']}")

    # Validación matemática
    expected = float(balance['flete_neto']) - float(balance['total_gastos_empresa']) - float(balance['total_anticipos']) - float(balance['comision_flete'])
    print(f"  Validación: saldo_neto={balance['saldo_neto']} == esperado={expected}")
    assert abs(float(balance['saldo_neto']) - expected) < 0.01, "Balance incorrecto"
    print(f"  ✓ Balance matemático verificado")
    return balance


def test_05_close_viaje(headers, viaje_id, balance):
    print_section("TEST 5: Cierre Definitivo de ODT")
    close_data = {
        "conductor_id": 1,
        "vehiculo_id": 1,
        "periodo_inicio": "2026-09-01",
        "periodo_fin": "2026-09-16",
        "comision_flete": float(balance['comision_flete']),
        "porcentaje_comision": 10.00,
        "bonificaciones": 0.00,
        "viaticos_reconocidos": 0.00,
        "otros_haberes": 0.00,
        "anticipos_entregados": float(balance['total_anticipos']),
        "gastos_a_cargo_conductor": 0.00,
        "prestamos": 0.00,
        "otros_descuentos": 0.00,
        "viajes_ids": [viaje_id],
        "estado": "aprobado",
    }
    r = requests.post(f"{BASE_URL}/api/v1/liquidaciones/cerrar/{viaje_id}", json=close_data, headers=headers)
    print(f"  POST /api/v1/liquidaciones/cerrar/{viaje_id} -> status={r.status_code}")
    assert r.status_code == 200, f"Cierre fallido: {r.text}"
    result = r.json()
    print(f"  Resultado: {result['mensaje']}")
    print(f"  Estado del viaje: {result['estado_viaje']}")
    print(f"  Liquidacion ID: {result['liquidacion_id']}")
    print(f"  Saldo neto: {result['saldo_neto']}")

    # Verificar que el viaje está liquidado
    r2 = requests.get(f"{BASE_URL}/api/v1/viajes/{viaje_id}", headers=headers)
    viaje = r2.json()
    assert viaje['estado'] == 'liquidado', f"Estado esperado 'liquidado', obtenido: {viaje['estado']}"
    print(f"  ✓ Viaje confirmado como 'liquidado'")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  CELR v6 - PRUEBA E2E FLOW COMPLETO")
    print("  Ciclo de negocio: Auth -> Viaje -> Gastos -> Liquidación -> Cierre")
    print("="*60)

    try:
        # Paso 1: Autenticación
        token, headers = test_01_auth()

        # Paso 2: Crear Viaje
        viaje_id, flete_neto = test_02_create_viaje(headers)

        # Paso 3: Scan Receipt / Gastos
        test_03_scan_receipt(headers, viaje_id)

        # Paso 4: Calcular Liquidación
        balance = test_04_calculate_liquidacion(headers, viaje_id)

        # Paso 5: Cierre de ODT
        test_05_close_viaje(headers, viaje_id, balance)

        print("\n" + "="*60)
        print("  [✓] TODOS LOS TESTS E2E PASARON")
        print("  Ciclo completo validado: Auth → Viaje → Gastos → Liquidación → Cierre")
        print("="*60 + "\n")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] No se pudo conectar al backend. Verifica que el servidor esté corriendo en http://localhost:8000")
        sys.exit(1)
    except AssertionError as e:
        print(f"\n[ERROR] Assertión fallida: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Excepción: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
