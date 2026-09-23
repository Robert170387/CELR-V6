import sys
import os
from datetime import date, datetime, timezone
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, Conductor, RefreshToken, Usuario as UsuarioModel
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


def test_refresh_flow():
    print("\n=== Test 5: POST /api/v1/auth/refresh (rotacion) ===")
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.flota import RefreshToken
    client = TestClient(app)

    r = client.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
    assert r.status_code == 200
    body = r.json()
    access_1 = body["access_token"]
    refresh_1 = body["refresh_token"]
    assert refresh_1, "No se emitió refresh token"
    print(f"  login -> refresh_token='{refresh_1[:20]}...': PASADO")

    # Rotación: el mismo refresh NO se puede reutilizar después de usarlo.
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert r.status_code == 200, f"refresh fallo: {r.status_code} {r.json()}"
    body2 = r.json()
    assert body2["access_token"] != access_1, "El nuevo access token debe ser distinto"
    assert body2["refresh_token"] != refresh_1, "El refresh token debe rotarse"
    refresh_2 = body2["refresh_token"]
    print(f"  refresh -> nuevo par emitido, access distinto: PASADO")

    # El token usado ya no sirve (replay/revocado).
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert r.status_code == 401, f"Refresh reutilizado deberia ser 401: {r.status_code}"
    print(f"  reuso de refresh revocado -> 401: PASADO")

    # El nuevo refresh sí funciona con /auth/me.
    r2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body2['access_token']}"})
    assert r2.status_code == 200, f"me con access renovado fallo: {r2.status_code}"
    print(f"  /auth/me con access renovado -> 200: PASADO")

    # Logout revoca el refresh vigente.
    r = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_2})
    assert r.status_code == 204, f"logout fallo: {r.status_code} {r.json()}"
    print(f"  logout -> 204: PASADO")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_2})
    assert r.status_code == 401, f"Refresh tras logout deberia ser 401: {r.status_code}"
    print(f"  refresh tras logout -> 401: PASADO")

    # Refresh inexistente / inventado (longitud válida)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "token_inventado_abcdefghijklmnopqrstuvwxyz012345"})
    assert r.status_code == 401, f"Refresh inventado deberia ser 401: {r.status_code}"
    print(f"  refresh inventado -> 401: PASADO")


def test_cambio_contrasena_y_rate_limit():
    print("\n=== Test 6: cambio de contraseña + rate limit de login ===")
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import SessionLocal as SL

    db = SL()
    try:
        # Usuario dedicado para el flujo de cambio de contraseña
        # Idempotencia: el test rota la contrasena cada corrida, asi que al
        # re-ejecutarlo sobre una BD sucia se restaura la contrasena inicial.
        rate_user = db.query(UsuarioModel).filter(UsuarioModel.correo == "ratelimit@celr.com").first()
        if not rate_user:
            rate_user = UsuarioModel(
                correo="ratelimit@celr.com",
                contrasena_hash=hash_password("old123"),
                rol="admin",
                activo=True,
                debe_cambiar_contrasena=True,
            )
            db.add(rate_user)
        else:
            rate_user.contrasena_hash = hash_password("old123")
            rate_user.debe_cambiar_contrasena = True
        db.commit()
        db.refresh(rate_user)
    finally:
        db.close()

    client = TestClient(app)

    # Login con password inicial (permite entrar aunque deba cambiar la contrasena)
    r = client.post("/api/v1/auth/login", json={"correo": "ratelimit@celr.com", "contrasena": "old123"})
    assert r.status_code == 200, f"login inicial fallo: {r.status_code} {r.json()}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  login con contrasena inicial -> 200: PASADO")

    # /auth/me debe reportar debe_cambiar_contrasena=True
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["debe_cambiar_contrasena"] is True, "debe_cambiar_contrasena deberia ser True"
    print("  /auth/me -> debe_cambiar_contrasena=True: PASADO")

    # Contrasena actual incorrecta -> 400
    r = client.post("/api/v1/auth/cambio-contrasena", json={"contrasena_actual": "wrongold", "nueva_contrasena": "new456"}, headers=headers)
    assert r.status_code == 400, f"contrasena actual incorrecta deberia ser 400: {r.status_code}"
    print("  cambio con contrasena actual incorrecta -> 400: PASADO")

    # Cambio correcto -> 200 + tokens nuevos, y el flag se limpia
    r = client.post("/api/v1/auth/cambio-contrasena", json={"contrasena_actual": "old123", "nueva_contrasena": "new456"}, headers=headers)
    assert r.status_code == 200, f"cambio correcto deberia ser 200: {r.status_code} {r.text}"
    nuevo_body = r.json()
    nuevo_access = nuevo_body["access_token"]
    assert nuevo_access and nuevo_access != token, "El access token nuevo debe ser distinto al usado para el cambio"
    print("  cambio correcto -> 200 + tokens nuevos: PASADO")

    # El access token viejo (emitido antes del cambio) queda invalidado de inmediato:
    # password_version se incrementó (revocación server-side, sin esperar expiración).
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 401, f"access viejo deberia quedar invalidado: {r.status_code}"
    print("  /auth/me con access viejo tras cambio -> 401: PASADO")

    # Login con la nueva contrasena
    r = client.post("/api/v1/auth/login", json={"correo": "ratelimit@celr.com", "contrasena": "new456"})
    assert r.status_code == 200, f"login con nueva contrasena fallo: {r.status_code}"
    print("  login con nueva contrasena -> 200: PASADO")
    r = client.post("/api/v1/auth/login", json={"correo": "ratelimit@celr.com", "contrasena": "old123"})
    assert r.status_code == 401, f"login con contrasena vieja deberia ser 401: {r.status_code}"
    print("  login con contrasena vieja -> 401: PASADO")

    # Rate limit: 5 fallos y el 6to intento se bloquea (429)
    bloqueado = "blocked@celr.com"
    for i in range(5):
        r = client.post("/api/v1/auth/login", json={"correo": bloqueado, "contrasena": "clave"})
        assert r.status_code == 401, f"try {i+1} deberia ser 401: {r.status_code}"
    print("  5 intentos fallidos -> 401: PASADO")
    r = client.post("/api/v1/auth/login", json={"correo": bloqueado, "contrasena": "clave"})
    assert r.status_code == 429, f"6to intento deberia ser 429: {r.status_code} {r.json()}"
    print("  6to intento (bloqueado) -> 429: PASADO")

    # Un login correcto en otra cuenta no se ve afectado (unico por clave)
    r = client.post("/api/v1/auth/login", json={"correo": "test@celr.com", "contrasena": "admin123"})
    assert r.status_code == 200, f"login de otra cuenta afectado por rate limit: {r.status_code}"
    print("  login correcto de otra cuenta -> 200 (rate limit por clave): PASADO")


def main():
    print("Iniciando prueba de autenticacion JWT CELR v6...")
    db = SessionLocal()
    inicio = datetime.now(timezone.utc)
    try:
        usuario = seed_usuario(db)
        test_hash_password()
        test_jwt()
        token = test_login()
        test_get_me(token)
        test_refresh_flow()
        test_cambio_contrasena_y_rate_limit()
        print("\n[TODOS LOS TESTS DE AUTENTICACION PASARON]")
    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpieza 2.B: DELETE real solo de lo creado por esta corrida.
        # Orden inverso de FK: refresh_tokens antes que usuarios (FK sin CASCADE).
        # Nunca se borra test@celr.com (usuario semilla del stack).
        try:
            rl = db.query(UsuarioModel).filter(UsuarioModel.correo == "ratelimit@celr.com").first()
            if rl:
                db.query(RefreshToken).filter(RefreshToken.usuario_id == rl.id).delete(
                    synchronize_session=False
                )
                db.delete(rl)
            admin = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").first()
            if admin:
                db.query(RefreshToken).filter(
                    RefreshToken.usuario_id == admin.id,
                    RefreshToken.creado_en >= inicio,
                ).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


if __name__ == "__main__":
    main()