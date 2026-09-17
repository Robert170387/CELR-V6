import sys
import os
from datetime import date
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, Conductor, Usuario as UsuarioModel
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


def seed_usuario(db: Session):
    print("\n=== Seed: Preparando usuario de prueba ===")
    db_usuario = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
    if not db_usuario:
        hashed = hash_password("admin123")
        usuario = UsuarioModel(
            correo="test@celr.com",
            contrasena_hash=hashed,
            rol="admin",
            activo=True,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        print(f"Usuario creado: id={usuario.id}, correo={usuario.correo}")
    else:
        try:
            pw_ok = verify_password("admin123", db_usuario.contrasena_hash)
        except Exception:
            pw_ok = False
        if not pw_ok:
            db_usuario.contrasena_hash = hash_password("admin123")
        if db_usuario.rol != "admin":
            db_usuario.rol = "admin"
        db.commit()
        db.refresh(db_usuario)
        print(f"Usuario existente actualizado: id={db_usuario.id}, correo={db_usuario.correo}")
    return db_usuario


def test_hash_password():
    print("\n=== Test 1: hash_password y verify_password ===")
    plain = "mysecretpass"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed), "La contrasena no coincide"
    assert not verify_password("wrongpass", hashed), "Contrasena incorrecta no deberia pasar"
    print(f"  hash='{hashed[:20]}...'")
    print(f"  verify('{plain}') -> True: PASADO")
    print(f"  verify('wrongpass') -> False: PASADO")


def test_jwt():
    print("\n=== Test 2: create_access_token y decode_access_token ===")
    token_data = {"usuario_id": 1, "correo": "test@celr.com"}
    token = create_access_token(token_data, expires_delta=None)
    print(f"  token='{token[:30]}...'")
    payload = decode_access_token(token)
    assert payload is not None, "Decodifico fallo"
    assert payload["usuario_id"] == 1, "usuario_id incorrecto"
    assert payload["correo"] == "test@celr.com", "correo incorrecto"
    print(f"  decode -> usuario_id={payload['usuario_id']}, correo={payload['correo']}: PASADO")

    # Token invalido
    payload_invalid = decode_access_token("token.invalido.aqui")
    assert payload_invalid is None, "Token invalido deberia retornar None"
    print(f"  decode('token.invalido') -> None: PASADO")


def test_login():
    print("\n=== Test 3: POST /api/v1/auth/login ===")
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    # Login exitoso
    r = client.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
    print(f"  Login OK -> status={r.status_code}")
    assert r.status_code == 200, f"Login fallido: {r.status_code} {r.json()}"
    response_json = r.json()
    token = response_json["access_token"]
    assert token, "No se obtuvo token"
    print(f"  Token obtenido: {token[:30]}...: PASADO")

    # Login con contrasena incorrecta
    r = client.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "wrong"})
    assert r.status_code == 401, f"Deberia retornar 401: {r.status_code}"
    print(f"  Login incorrecto -> 401: PASADO")

    # Login con usuario inexistente
    r = client.post("/api/v1/auth/login", json={"correo": "nobody@celr.com", "contrasena": "pass"})
    assert r.status_code == 401, f"Deberia retornar 401: {r.status_code}"
    print(f"  Login inexistente -> 401: PASADO")

    return token


def test_get_me(token: str):
    print("\n=== Test 4: GET /api/v1/auth/me ===")
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    # Con token valido
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    print(f"  Con token -> status={r.status_code}")
    assert r.status_code == 200, f"Deberia retornar 200: {r.status_code} {r.json()}"
    assert r.json()["correo"] == "test@celr.com"
    print(f"  Usuario: {r.json()['correo']}, rol={r.json()['rol']}: PASADO")

    # Sin token
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401, f"Deberia retornar 401: {r.status_code}"
    print(f"  Sin token -> 401: PASADO")

    # Token invalido
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token_invalido"})
    assert r.status_code == 401, f"Deberia retornar 401: {r.status_code}"
    print(f"  Token invalido -> 401: PASADO")


def main():
    print("Iniciando prueba de autenticacion JWT CELR v6...")
    db = SessionLocal()
    try:
        usuario = seed_usuario(db)
        test_hash_password()
        test_jwt()
        token = test_login()
        test_get_me(token)
        print("\n[TODOS LOS TESTS DE AUTENTICACION PASARON]")
    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()