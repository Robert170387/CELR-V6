import sys
import os
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.flota import Vehiculo, Conductor, RefreshToken, Usuario as UsuarioModel
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from _test_helpers import capturar_token_ids, limpiar_tokens_nuevos


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

    # Contrasena actual incorrecta -> 400.
    # "new45678" (>=8) es valida para la politica A1, asi que el 400 no puede
    # atribuirse a la politica: solo a la contrasena actual incorrecta.
    r = client.post("/api/v1/auth/cambio-contrasena", json={"contrasena_actual": "wrongold", "nueva_contrasena": "new45678"}, headers=headers)
    assert r.status_code == 400, f"contrasena actual incorrecta deberia ser 400: {r.status_code}"
    print("  cambio con contrasena actual incorrecta -> 400: PASADO")

    # Cambio correcto -> 200 + tokens nuevos, y el flag se limpia.
    # A1: "new45678" cumple la politica (>=8 caracteres).
    r = client.post("/api/v1/auth/cambio-contrasena", json={"contrasena_actual": "old123", "nueva_contrasena": "new45678"}, headers=headers)
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
    r = client.post("/api/v1/auth/login", json={"correo": "ratelimit@celr.com", "contrasena": "new45678"})
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


def test_politica_contrasenas():
    """A1 — TP-P1..TP-P6: politica de contrasenas en /auth/cambio-contrasena."""
    print("\n=== Test 7: politica de contrasenas (A1) ===")
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import SessionLocal as SL
    from app.core.security import (
        CONTRASENAS_BLOQUEADAS,
        LONGITUD_MINIMA_CONTRASENA,
        validar_politica_contrasena,
    )

    # --- Unidad: el helper de politica, sin HTTP ---
    # Regla: longitud minima
    try:
        validar_politica_contrasena("a" * (LONGITUD_MINIMA_CONTRASENA - 1))
        raise AssertionError("Deberia rechazar una contrasena corta")
    except ValueError as e:
        print(f"  [TP-P1] longitud {LONGITUD_MINIMA_CONTRASENA - 1} -> ValueError: PASADO")
        assert str(LONGITUD_MINIMA_CONTRASENA) in str(e)

    # Regla: vacia / solo espacios
    try:
        validar_politica_contrasena("        ")
        raise AssertionError("Deberia rechazar una contrasena vacia")
    except ValueError:
        print("  contrasena de solo espacios -> ValueError: PASADO")

    # Regla: igual a la cedula (case-insensitive, ignora espacios)
    try:
        validar_politica_contrasena("  12345678  ", cedula="12345678")
        raise AssertionError("Deberia rechazar la contrasena igual a la cedula")
    except ValueError as e:
        print(f"  [TP-P2] igual a cedula -> ValueError: PASADO ({e})")

    # Regla: igual al correo (case-insensitive)
    try:
        validar_politica_contrasena("USUARIO@CELR.COM", correo="usuario@celr.com")
        raise AssertionError("Deberia rechazar la contrasena igual al correo")
    except ValueError as e:
        print(f"  [TP-P3] igual a correo -> ValueError: PASADO ({e})")

    # Regla: contrasena comun bloqueada
    assert "admin123" in CONTRASENAS_BLOQUEADAS, "admin123 debe estar bloqueada"
    for bloqueada in sorted(CONTRASENAS_BLOQUEADAS):
        try:
            validar_politica_contrasena(bloqueada)
            raise AssertionError(f"Deberia rechazar la contrasena comun '{bloqueada}'")
        except ValueError:
            pass
    print(f"  [TP-P4] {len(CONTRASENAS_BLOQUEADAS)} contrasenas comunes bloqueadas: PASADO")

    # Regla: un solo caracter repetido
    for repetida in ("aaaaaaaa", "11111111"):
        try:
            validar_politica_contrasena(repetida)
            raise AssertionError(f"Deberia rechazar '{repetida}'")
        except ValueError:
            pass
    print("  [TP-P5] 'aaaaaaaa' / '11111111' (un solo caracter) -> ValueError: PASADO")

    # Regla: una contrasena valida pasa el helper
    validar_politica_contrasena("CargaSegura2026", cedula="12345678", correo="u@celr.com")
    print("  contrasena valida ('CargaSegura2026') -> aceptada: PASADO")

    # --- Integracion HTTP: 422 en el endpoint, 200 y efectos al exito ---
    db = SL()
    try:
        pol_user = db.query(UsuarioModel).filter(UsuarioModel.correo == "politica@celr.com").first()
        if not pol_user:
            pol_user = UsuarioModel(
                correo="politica@celr.com",
                contrasena_hash=hash_password("old123"),
                rol="admin",
                activo=True,
                debe_cambiar_contrasena=True,
            )
            db.add(pol_user)
        else:
            pol_user.contrasena_hash = hash_password("old123")
            pol_user.debe_cambiar_contrasena = True
        # Cedula canonica para probar TP-P2 por HTTP (A1 no hace backfill).
        pol_user.cedula = "99887766"
        db.commit()
        db.refresh(pol_user)
        version_inicial = pol_user.password_version
    finally:
        db.close()

    client = TestClient(app)
    r = client.post("/api/v1/auth/login", json={"correo": "politica@celr.com", "contrasena": "old123"})
    assert r.status_code == 200, f"login inicial fallo: {r.status_code} {r.json()}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me expone la cedula y el correo (H1)
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200, f"me fallo: {r.status_code}"
    assert r.json()["cedula"] == "99887766", f"cedula no expuesta: {r.json()}"
    print("  /auth/me -> cedula='99887766', correo='politica@celr.com': PASADO (H1)")

    # 422 por HTTP para cada regla de la politica
    casos_422 = [
        ("[TP-P1] 7 caracteres", "abc1234"),
        ("[TP-P2] igual a la cedula", "99887766"),
        ("[TP-P3] igual al correo", "politica@celr.com"),
        ("[TP-P4] contrasena comun", "admin123"),
        ("[TP-P5] un solo caracter", "aaaaaaaa"),
    ]
    for etiqueta, nueva in casos_422:
        r = client.post(
            "/api/v1/auth/cambio-contrasena",
            json={"contrasena_actual": "old123", "nueva_contrasena": nueva},
            headers=headers,
        )
        assert r.status_code == 422, f"{etiqueta} deberia ser 422: {r.status_code} {r.text}"
        detalle = r.json().get("detail", "")
        assert detalle, "El 422 debe traer detalle en espanol"
        print(f"  {etiqueta} -> 422: {detalle}")

    # Ningun rechazo cambio nada: la contrasena sigue siendo la original
    r = client.post("/api/v1/auth/login", json={"correo": "politica@celr.com", "contrasena": "old123"})
    assert r.status_code == 200, "Los rechazos no debian alterar la contrasena"
    print("  contrasena intacta tras los 5 rechazos: PASADO")

    # Cambio valido -> 200, password_version incrementa y los refresh se revocan
    r = client.post(
        "/api/v1/auth/cambio-contrasena",
        json={"contrasena_actual": "old123", "nueva_contrasena": "CargaSegura2026"},
        headers=headers,
    )
    assert r.status_code == 200, f"[TP-P6] cambio valido deberia ser 200: {r.status_code} {r.text}"
    nuevo_access = r.json()["access_token"]
    assert nuevo_access and nuevo_access != token, "El access token nuevo debe ser distinto"
    print("  [TP-P6] cambio valido -> 200 + tokens nuevos: PASADO")

    # El access viejo quedo invalidado de inmediato (password_version)
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 401, f"access viejo deberia quedar invalidado: {r.status_code}"
    print("  /auth/me con access viejo -> 401 (password_version): PASADO")

    db = SL()
    try:
        pol_user = db.query(UsuarioModel).filter(UsuarioModel.correo == "politica@celr.com").first()
        assert pol_user.password_version == version_inicial + 1, (
            f"password_version deberia ser {version_inicial + 1}: {pol_user.password_version}"
        )
        activos = (
            db.query(RefreshToken)
            .filter(RefreshToken.usuario_id == pol_user.id, RefreshToken.revocado == False)  # noqa: E712
            .count()
        )
        # Tras el cambio solo queda vigente el refresh recien emitido.
        assert activos == 1, f"Deberia quedar 1 refresh activo, hay {activos}"
        print("  [TP-P6] password_version incrementado + refreshes previos revocados: PASADO")
    finally:
        db.close()

    # Login con la nueva contrasena
    r = client.post("/api/v1/auth/login", json={"correo": "politica@celr.com", "contrasena": "CargaSegura2026"})
    assert r.status_code == 200, f"login con la nueva contrasena fallo: {r.status_code} {r.json()}"
    r = client.post("/api/v1/auth/login", json={"correo": "politica@celr.com", "contrasena": "old123"})
    assert r.status_code == 401, "La contrasena vieja deberia fallar"
    print("  login con nueva / vieja contrasena -> 200 / 401: PASADO")


def test_login_por_identificador():
    """A2 — TA-ID-1..TA-ID-10: login por cedula o correo (D1 coexistencia)."""
    print("\n=== Test 8: login por identificador (A2) ===")
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import SessionLocal as SL
    from app.core.rate_limiter import _fallidos

    CEDULA = "77889900"
    CORREO = "identidad@celr.com"

    def _limpiar_buckets(*claves):
        for c in claves:
            _fallidos.pop(c, None)

    # --- Usuario temporal con cedula y correo, los dos como puerta de entrada ---
    db = SL()
    try:
        u = db.query(UsuarioModel).filter(UsuarioModel.correo == CORREO).first()
        if not u:
            u = UsuarioModel(
                correo=CORREO,
                contrasena_hash=hash_password("Vieja123"),
                rol="admin",
                activo=True,
            )
            db.add(u)
        else:
            u.contrasena_hash = hash_password("Vieja123")
            u.activo = True
        u.cedula = CEDULA
        db.commit()
        db.refresh(u)
        uid = u.id
        _limpiar_buckets(f"usuario:{uid}", CORREO, CEDULA, "nadie@celr.com", "noexiste123")
    finally:
        db.close()

    client = TestClient(app)
    _fallidos.clear()  # punto limpio: el rate limit es global en memoria

    def login(payload):
        return client.post("/api/v1/auth/login", json=payload)

    # TA-ID-1: login por cedula -> 200 + par de tokens
    r = login({"identificador": CEDULA, "contrasena": "Vieja123"})
    assert r.status_code == 200, f"[TA-ID-1] cedula deberia dar 200: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("access_token") and body.get("refresh_token"), "Faltan tokens"
    print(f"  [TA-ID-1] login por cedula {CEDULA} -> 200 + tokens: PASADO")

    # TA-ID-2: login por correo -> 200 + par de tokens
    r = login({"identificador": CORREO, "contrasena": "Vieja123"})
    assert r.status_code == 200, f"[TA-ID-2] correo deberia dar 200: {r.status_code} {r.text}"
    print(f"  [TA-ID-2] login por correo {CORREO} -> 200 + tokens: PASADO")

    # TA-ID-3: normalizacion (espacios alrededor) en ambos campos
    r = login({"identificador": f"  {CEDULA}  ", "contrasena": "Vieja123"})
    assert r.status_code == 200, f"[TA-ID-3] cedula con espacios deberia dar 200: {r.status_code}"
    r = login({"identificador": f" {CORREO} ", "contrasena": "Vieja123"})
    assert r.status_code == 200, f"[TA-ID-3] correo con espacios deberia dar 200: {r.status_code}"
    print("  [TA-ID-3] cedula y correo con espacios -> normalizados y 200: PASADO")

    # TA-ID-4: correo en mayusculas -> 200 (case-insensitive)
    r = login({"identificador": CORREO.upper(), "contrasena": "Vieja123"})
    assert r.status_code == 200, f"[TA-ID-4] correo en mayusculas deberia dar 200: {r.status_code} {r.text}"
    print(f"  [TA-ID-4] login con {CORREO.upper()} -> 200 (case-insensitive): PASADO")

    # TA-ID-7: payload legacy {correo, contrasena} -> 200 (retrocompatibilidad D1)
    r = login({"correo": CORREO, "contrasena": "Vieja123"})
    assert r.status_code == 200, f"[TA-ID-7] payload legacy deberia dar 200: {r.status_code} {r.text}"
    print("  [TA-ID-7] payload legacy {correo, contrasena} -> 200: PASADO")

    # Precedencia: si llegan ambos, manda `identificador`
    r = login({"identificador": CEDULA, "correo": "nadie@celr.com", "contrasena": "Vieja123"})
    assert r.status_code == 200, f"identificador deberia ganar sobre correo: {r.status_code} {r.text}"
    print("  precedencia: con ambos campos, `identificador` gana -> 200: PASADO")

    # TA-ID-5: identificador inexistente -> 401 generico
    r = login({"identificador": "noexiste123", "contrasena": "Vieja123"})
    assert r.status_code == 401, f"[TA-ID-5] inexistente deberia dar 401: {r.status_code}"
    msg_inexistente = r.json().get("detail")
    print(f"  [TA-ID-5] identificador inexistente -> 401: {msg_inexistente}")

    # TA-ID-6: contrasena incorrecta -> 401 con el MISMO mensaje (sin enumeracion)
    r = login({"identificador": CEDULA, "contrasena": "Incorrecta999"})
    assert r.status_code == 401, f"[TA-ID-6] contrasena incorrecta deberia dar 401: {r.status_code}"
    msg_incorrecta = r.json().get("detail")
    assert msg_incorrecta == msg_inexistente, (
        f"Los mensajes deben ser identicos: {msg_incorrecta!r} != {msg_inexistente!r}"
    )
    print(f"  [TA-ID-6] contrasena incorrecta -> 401, mismo mensaje: PASADO")

    # TA-ID-8: sin identificador ni correo -> 422
    r = login({"contrasena": "Vieja123"})
    assert r.status_code == 422, f"[TA-ID-8] payload sin identificador deberia dar 422: {r.status_code} {r.text}"
    print("  [TA-ID-8] payload sin identificador ni correo -> 422: PASADO")

    # TA-ID-10: la cubeta es por CUENTA, no por puerta de entrada.
    # 3 fallos por correo + 3 por cedula del mismo usuario -> el 6to overall
    # debe dar 429. Si el limite fuera por identificador, aqui saldria 401.
    _fallidos.clear()
    for i in range(3):
        r = login({"identificador": CORREO, "contrasena": "Incorrecta999"})
        assert r.status_code == 401, f"fallo {i+1} por correo deberia dar 401: {r.status_code}"
    print("  3 intentos fallidos por correo -> 401: PASADO")
    for i in range(2):
        r = login({"identificador": CEDULA, "contrasena": "Incorrecta999"})
        assert r.status_code == 401, f"fallo {i+3} por cedula deberia dar 401: {r.status_code}"
    print("  +2 intentos fallidos por cedula (mismo usuario) -> 401: PASADO")
    # Sexto intento overall, ahora por la OTRA puerta: debe estar bloqueado.
    r = login({"identificador": CEDULA, "contrasena": "Incorrecta999"})
    assert r.status_code == 429, (
        f"[TA-ID-10] el 6to intento total deberia dar 429 (cubeta por cuenta): {r.status_code} {r.text}"
    )
    print("  [TA-ID-10] 6to intento alternando cedula/correo -> 429: PASADO")

    # Y la cedula correcta tambien queda bloqueada: el bloqueo es de la cuenta.
    r = login({"identificador": CEDULA, "contrasena": "Vieja123"})
    assert r.status_code == 429, f"[TA-ID-10] la cuenta debe quedar bloqueada: {r.status_code}"
    print("  [TA-ID-10] la cuenta sigue bloqueada aunque la cedula sea correcta: PASADO")

    # TA-ID-9: tras limpiar, un identificador inexistente tambien se limita (5+1)
    _fallidos.clear()
    for i in range(5):
        r = login({"identificador": "fantasma@celr.com", "contrasena": "Vieja123"})
        assert r.status_code == 401, f"intento {i+1} deberia dar 401: {r.status_code}"
    r = login({"identificador": "fantasma@celr.com", "contrasena": "Vieja123"})
    assert r.status_code == 429, f"[TA-ID-9] el 6to intento deberia dar 429: {r.status_code} {r.text}"
    print("  [TA-ID-9] rate limit por identificador inexistente (5+1) -> 429: PASADO")

    # Un login correcto limpia la cubeta: no queda arrastrado el historial.
    _fallidos.clear()
    r = login({"identificador": CORREO, "contrasena": "Vieja123"})
    assert r.status_code == 200, f"login correcto posterior fallo: {r.status_code}"
    _fallidos.clear()


def main():
    print("Iniciando prueba de autenticacion JWT CELR v6...")
    db = SessionLocal()
    tokens_antes_test = capturar_token_ids(db, "test@celr.com")
    tokens_antes_ratelimit = capturar_token_ids(db, "ratelimit@celr.com")
    try:
        usuario = seed_usuario(db)
        test_hash_password()
        test_jwt()
        token = test_login()
        test_get_me(token)
        test_refresh_flow()
        test_cambio_contrasena_y_rate_limit()
        test_politica_contrasenas()
        test_login_por_identificador()
        print("\n[TODOS LOS TESTS DE AUTENTICACION PASARON]")
    except Exception as e:
        print(f"\n[ERROR EN TESTS]: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Limpieza 2.B: DELETE real solo de lo creado por esta corrida.
        # Orden inverso de FK: refresh_tokens antes que usuarios (FK sin CASCADE).
        # Nunca se borra test@celr.com (usuario semilla del stack).
        # politica@celr.com e identidad@celr.com son temporales de A1/A2
        # (cedulas de prueba 99887766 y 77889900).
        try:
            limpiar_tokens_nuevos(db, "ratelimit@celr.com", tokens_antes_ratelimit)
            rl = db.query(UsuarioModel).filter(UsuarioModel.correo == "ratelimit@celr.com").first()
            if rl:
                # El usuario temporal se elimina; también se limpian tokens viejos
                # de una corrida anterior que pudieran haber quedado.
                db.query(RefreshToken).filter(RefreshToken.usuario_id == rl.id).delete(
                    synchronize_session=False
                )
                db.delete(rl)
            limpiar_tokens_nuevos(db, "test@celr.com", tokens_antes_test)
            pol = db.query(UsuarioModel).filter(UsuarioModel.correo == "politica@celr.com").first()
            if pol:
                db.query(RefreshToken).filter(RefreshToken.usuario_id == pol.id).delete(
                    synchronize_session=False
                )
                db.delete(pol)
            ident = db.query(UsuarioModel).filter(
                UsuarioModel.correo == "identidad@celr.com"
            ).first()
            if ident:
                db.query(RefreshToken).filter(RefreshToken.usuario_id == ident.id).delete(
                    synchronize_session=False
                )
                db.delete(ident)
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.close()


if __name__ == "__main__":
    main()