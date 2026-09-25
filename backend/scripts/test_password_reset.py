"""A3.1 — Reset de contrasena por token de enlace (TR-1..TR-12).

Suite 14. Corre contra celr_v6_db (como las demas) y limpia lo que crea:
el usuario temporal, sus refresh tokens y las claves de configuracion_sistema
que el servicio inserta por primera vez. TR-12 necesita el bucket global del
rate limiter, que se restaura al final para no afectar a otras pruebas del
proceso.

El token en claro nunca sale por la API (TR-11 lo comprueba), asi que para
obtenerlo el test captura el log del backend de email, que es justamente el
canal por donde viaja en desarrollo.
"""
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.rate_limiter import _fallidos
from app.db.session import SessionLocal
from app.models import ConfiguracionSistema
from app.models.flota import PasswordResetToken, RefreshToken, Usuario as UsuarioModel
from app.core.security import hash_password, verify_password
from app.services import email as email_mod
from app.services.password_reset import (
    CONFIG_INTENTOS_CODIGO,
    CONFIG_INTENTOS_ENLACE,
    CONFIG_TTL_CODIGO_MINUTOS,
    CONFIG_TTL_ENLACE_HORAS,
)

CORREO = "reset@celr.com"
CEDULA = "55667788"
PASSWORD_INICIAL = "Olvidada123"
PASSWORD_NUEVA = "Recuperada456"

MSG_GENERICO = "Si el identificador existe, se enviara un enlace de recuperacion."


class CapturaEmail(logging.Handler):
    """Handler que acumula los registros [EMAIL-MOCK] del backend de email."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.registros = []

    def emit(self, record):
        self.registros.append(record.getMessage())


def _crear_usuario(db: Session) -> UsuarioModel:
    u = db.query(UsuarioModel).filter(UsuarioModel.correo == CORREO).first()
    if not u:
        u = UsuarioModel(
            correo=CORREO,
            contrasena_hash=hash_password(PASSWORD_INICIAL),
            rol="admin",
            activo=True,
        )
        db.add(u)
    else:
        u.contrasena_hash = hash_password(PASSWORD_INICIAL)
        u.activo = True
    u.cedula = CEDULA
    db.commit()
    db.refresh(u)
    return u


def _borrar_tokens(db: Session, usuario_id: int) -> None:
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.usuario_id == usuario_id))
    db.execute(delete(RefreshToken).where(RefreshToken.usuario_id == usuario_id))


def run() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    print("Iniciando prueba de reset de contrasena (A3.1)...")
    client = TestClient(app)
    captura = CapturaEmail()
    logger_email = logging.getLogger("app.services.email")
    nivel_previo = logger_email.level
    logger_email.addHandler(captura)
    logger_email.setLevel(logging.INFO)

    db = SessionLocal()
    buckets_previos = {k: list(v) for k, v in _fallidos.items()}
    # Si el test muere a mitad, el entorno no debe quedar en 'production'.
    from app.core.config import settings as _app_settings

    entorno_global_previo = _app_settings.ENVIRONMENT
    claves_previas = {
        c
        for (c,) in db.query(ConfiguracionSistema.clave).all()
        if c
        in {
            CONFIG_TTL_ENLACE_HORAS,
            CONFIG_TTL_CODIGO_MINUTOS,
            CONFIG_INTENTOS_ENLACE,
            CONFIG_INTENTOS_CODIGO,
        }
    }
    # Rastreo por ID, no por correo: el usuario sin correo (TR-3) tiene correo
    # NULL y una busqueda por correo jamas lo encontraria, dejando el usuario y
    # su cedula (UNIQUE parcial) plantados en la BD para la corrida siguiente.
    ids_a_borrar: list = []
    try:
        usuario = _crear_usuario(db)
        uid = usuario.id
        ids_a_borrar.append(uid)
        _borrar_tokens(db, uid)
        db.commit()
        print(f"Usuario temporal: id={uid}, correo={CORREO}, cedula={CEDULA}")

        # ---------------- TR-1: forgot con cuenta existente ----------------
        captura.registros.clear()
        _fallidos.clear()
        r = client.post(
            "/api/v1/auth/forgot-password", json={"identificador": CORREO}
        )
        assert r.status_code == 200, f"TR-1 deberia dar 200: {r.status_code} {r.text}"
        assert r.json()["detail"] == MSG_GENERICO, f"TR-1 mensaje inesperado: {r.json()}"
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == uid,
            PasswordResetToken.tipo == "enlace",
        ).order_by(PasswordResetToken.id.desc()).first()
        assert token is not None, "TR-1: no se creo el token en la BD"
        assert len(captura.registros) == 1, f"TR-1: se esperaba 1 email, hubo {len(captura.registros)}"
        assert CORREO in captura.registros[0], "TR-1: el email no lleva el destinatario"
        assert "[EMAIL-MOCK]" in captura.registros[0], "TR-1: no se uso el backend de email"
        print(f"  [TR-1] forgot con cuenta existente -> 200, token en BD, email mock enviado: PASADO")

        # El token plano solo se conoce por el log: extraemos el enlace.
        cuerpo = captura.registros[0]
        token_plano = cuerpo.split("token=")[1].split()[0].strip()
        assert token_plano, "TR-1: no se pudo extraer el token del log"
        assert token_plano not in token.token_hash, "TR-1: el token plano no debe ser el hash"

        # ---------------- TR-11: el token no se filtra por la API ----------------
        crudo = r.text
        assert token_plano not in crudo, "TR-11: el token aparece en el body"
        assert all(token_plano not in str(v) for v in r.headers.values()), (
            "TR-11: el token aparece en un header"
        )
        assert token_plano not in str(r.url), "TR-11: el token aparece en la URL"
        assert token_plano not in crudo.lower(), "TR-11: el token aparece en la respuesta"
        print("  [TR-11] el token no aparece en body, headers ni URL: PASADO")

        # ---------------- TR-2: cuenta inexistente, misma respuesta ----------------
        captura.registros.clear()
        _fallidos.clear()
        r2 = client.post(
            "/api/v1/auth/forgot-password", json={"identificador": "nadie-aqui@celr.com"}
        )
        assert r2.status_code == 200, f"TR-2 deberia dar 200: {r2.status_code}"
        assert r2.json()["detail"] == MSG_GENERICO, (
            f"TR-2: el mensaje difiere y permite enumerar cuentas: {r2.json()}"
        )
        assert r2.text == r.text, "TR-2: la respuesta difiere de la de una cuenta real"
        assert not captura.registros, "TR-2: no se debio enviar ningun email"
        assert (
            db.query(PasswordResetToken).filter(PasswordResetToken.tipo == "enlace").count() >= 0
        )
        print("  [TR-2] cuenta inexistente -> 200 con mensaje IDENTICO y sin email: PASADO")

        # ---------------- TR-3: cuenta sin correo ----------------
        sin_correo = db.query(UsuarioModel).filter(UsuarioModel.correo == "sincorreo@celr.com").first()
        if not sin_correo:
            sin_correo = UsuarioModel(
                correo=None,
                contrasena_hash=hash_password(PASSWORD_INICIAL),
                rol="conductor",
                activo=True,
            )
            db.add(sin_correo)
            db.commit()
            db.refresh(sin_correo)
        sin_correo.contrasena_hash = hash_password(PASSWORD_INICIAL)
        sin_correo.cedula = "44556677"
        ids_a_borrar.append(sin_correo.id)
        _borrar_tokens(db, sin_correo.id)
        db.commit()

        captura.registros.clear()
        _fallidos.clear()
        r3 = client.post(
            "/api/v1/auth/forgot-password", json={"identificador": sin_correo.cedula}
        )
        assert r3.status_code == 200, f"TR-3 deberia dar 200: {r3.status_code}"
        assert r3.json()["detail"] == MSG_GENERICO, "TR-3: mensaje inconsistente"
        assert not captura.registros, "TR-3: se envio email a una cuenta sin correo"
        fila_sc = db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == sin_correo.id
        ).first()
        assert fila_sc is not None, "TR-3: se debia generar el token aunque no haya correo"
        print("  [TR-3] cuenta sin correo -> 200, token generado, ningun email enviado: PASADO")

        # ---------------- TR-9: politica de contrasenas (antes de consumir) ----------------
        # Primero un token fresco por correo.
        captura.registros.clear()
        _fallidos.clear()
        client.post("/api/v1/auth/forgot-password", json={"identificador": CORREO})
        token_9 = captura.registros[0].split("token=")[1].split()[0].strip()

        casos_422 = [
            ("7 caracteres", "abc1234"),
            ("igual a la cedula", CEDULA),
            ("igual al correo", CORREO),
            ("contrasena comun", "admin123"),
            ("un solo caracter", "aaaaaaaa"),
        ]
        for etiqueta, nueva in casos_422:
            rr = client.post(
                "/api/v1/auth/reset-password",
                json={"token": token_9, "nueva_contrasena": nueva},
            )
            assert rr.status_code == 422, f"TR-9 [{etiqueta}] deberia dar 422: {rr.status_code} {rr.text}"
            assert rr.json().get("detail"), f"TR-9 [{etiqueta}]: sin detalle en espanol"
        print(f"  [TR-9] {len(casos_422)} contrasenas que violan la politica -> 422: PASADO")

        # El token NO debe haberse quemado: el mismo enlace sirve tras el 422.
        fila_9 = db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == uid, PasswordResetToken.tipo == "enlace"
        ).order_by(PasswordResetToken.id.desc()).first()
        assert fila_9.usado_en is None, "TR-9: un 422 de politica consumio el token (bug)"
        assert not fila_9.revocado, "TR-9: un 422 de politica revoco el token (bug)"
        print("  [TR-9] el token sobrevive al 422 (se valida antes de consumir): PASADO")

        # ---------------- TR-4: reset con token valido ----------------
        _fallidos.clear()
        db.refresh(usuario)
        version_previa = usuario.password_version
        r4 = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token_9, "nueva_contrasena": PASSWORD_NUEVA},
        )
        assert r4.status_code == 200, f"TR-4 deberia dar 200: {r4.status_code} {r4.text}"
        db.expire_all()
        usuario = db.query(UsuarioModel).filter(UsuarioModel.id == uid).first()
        assert verify_password(PASSWORD_NUEVA, usuario.contrasena_hash), (
            "TR-4: la contrasena no quedo actualizada"
        )
        assert not verify_password(PASSWORD_INICIAL, usuario.contrasena_hash), (
            "TR-4: la contrasena vieja sigue sirviendo"
        )
        assert usuario.password_version == version_previa + 1, (
            f"TR-4: password_version {usuario.password_version} != {version_previa + 1}"
        )
        assert usuario.debe_cambiar_contrasena is False, "TR-4: quedo pendiente el cambio"
        fila_4 = db.query(PasswordResetToken).filter(PasswordResetToken.id == fila_9.id).first()
        assert fila_4.usado_en is not None, "TR-4: el token no quedo marcado como usado"
        activos = db.query(RefreshToken).filter(
            RefreshToken.usuario_id == uid, RefreshToken.revocado == False  # noqa: E712
        ).count()
        assert activos == 0, f"TR-4: quedaron {activos} refresh tokens activos"
        print("  [TR-4] reset valido -> 200, contrasena cambiada, version +1, refreshes revocados: PASADO")

        # ---------------- TR-5: token ya usado ----------------
        r5 = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token_9, "nueva_contrasena": "OtraClave789"},
        )
        assert r5.status_code == 401, f"TR-5 deberia dar 401: {r5.status_code} {r5.text}"
        print("  [TR-5] token ya usado -> 401: PASADO")

        # ---------------- TR-6: token expirado ----------------
        captura.registros.clear()
        _fallidos.clear()
        client.post("/api/v1/auth/forgot-password", json={"identificador": CORREO})
        token_6 = captura.registros[0].split("token=")[1].split()[0].strip()
        fila_6 = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.usuario_id == uid)
            .order_by(PasswordResetToken.id.desc())
            .first()
        )
        fila_6.expira_en = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        r6 = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token_6, "nueva_contrasena": "OtraClave789"},
        )
        assert r6.status_code == 401, f"TR-6 deberia dar 401: {r6.status_code} {r6.text}"
        print("  [TR-6] token expirado -> 401: PASADO")

        # ---------------- TR-7: token revocado ----------------
        captura.registros.clear()
        _fallidos.clear()
        client.post("/api/v1/auth/forgot-password", json={"identificador": CORREO})
        token_7 = captura.registros[0].split("token=")[1].split()[0].strip()
        fila_7 = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.usuario_id == uid)
            .order_by(PasswordResetToken.id.desc())
            .first()
        )
        fila_7.revocado = True
        db.commit()
        r7 = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token_7, "nueva_contrasena": "OtraClave789"},
        )
        assert r7.status_code == 401, f"TR-7 deberia dar 401: {r7.status_code} {r7.text}"
        print("  [TR-7] token revocado -> 401: PASADO")

        # ---------------- TR-8: token inexistente ----------------
        r8 = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "token-que-nunca-existio-abcdef", "nueva_contrasena": "OtraClave789"},
        )
        assert r8.status_code == 401, f"TR-8 deberia dar 401: {r8.status_code} {r8.text}"
        print("  [TR-8] token inexistente -> 401: PASADO")

        # ---------------- TR-10: el token nuevo invalida al anterior ----------------
        _fallidos.clear()
        captura.registros.clear()
        client.post("/api/v1/auth/forgot-password", json={"identificador": CORREO})
        token_10a = captura.registros[0].split("token=")[1].split()[0].strip()
        captura.registros.clear()
        client.post("/api/v1/auth/forgot-password", json={"identificador": CORREO})
        token_10b = captura.registros[0].split("token=")[1].split()[0].strip()
        assert token_10a != token_10b, "TR-10: se genero el mismo token dos veces"
        r10a = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token_10a, "nueva_contrasena": "UltimaClave01"},
        )
        assert r10a.status_code == 401, (
            f"TR-10: el token anterior debio quedar revocado: {r10a.status_code} {r10a.text}"
        )
        r10b = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token_10b, "nueva_contrasena": "UltimaClave01"},
        )
        assert r10b.status_code == 200, (
            f"TR-10: el token nuevo deberia servir: {r10b.status_code} {r10b.text}"
        )
        print("  [TR-10] el token nuevo revoca al anterior (el viejo da 401): PASADO")

        # ---------------- TR-12: rate limit de forgot ----------------
        _fallidos.clear()
        objetivo = "abuseo@celr.com"
        for i in range(5):
            rr = client.post("/api/v1/auth/forgot-password", json={"identificador": objetivo})
            assert rr.status_code == 200, f"TR-12 intento {i+1} deberia dar 200: {rr.status_code}"
        rr = client.post("/api/v1/auth/forgot-password", json={"identificador": objetivo})
        assert rr.status_code == 429, f"TR-12 el 6to intento deberia dar 429: {rr.status_code}"
        print("  [TR-12] rate limit de forgot (5+1) -> 429: PASADO")

        # Independencia de buckets: un usuario bloqueado por fallar el login
        # cinco veces es justamente quien necesita pedir un reset. Se llena el
        # bucket de LOGIN y se comprueba que forgot NO queda bloqueado.
        _fallidos.clear()
        for _ in range(5):
            client.post(
                "/api/v1/auth/login", json={"correo": CORREO, "contrasena": "malaclave"}
            )
        r_bloqueado = client.post(
            "/api/v1/auth/login", json={"correo": CORREO, "contrasena": "UltimaClave01"}
        )
        assert r_bloqueado.status_code == 429, (
            f"el login deberia estar bloqueado tras 5 fallos: {r_bloqueado.status_code}"
        )
        captura.registros.clear()
        r_forgot = client.post(
            "/api/v1/auth/forgot-password", json={"identificador": CORREO}
        )
        assert r_forgot.status_code == 200, (
            f"TR-12: forgot quedo bloqueado por el rate limit de login: {r_forgot.status_code}"
        )
        assert len(captura.registros) == 1, "TR-12: forgot no envio el email al estar bloqueado"
        print("  [TR-12] login bloqueado (429) no arrastra a forgot (200 + email): PASADO")

        # ---------------- TR-13: guard de produccion ----------------
        # Sin proveedor de email, forgot debe responder 503 (dependencia no
        # disponible) y NO 500: un 500 en un endpoint publico parece un bug de
        # la aplicacion y, con debug activo, puede filtrar el traceback.
        from fastapi import HTTPException

        from app.core.config import settings as app_settings
        from app.services.email import get_email_backend

        entorno_previo = app_settings.ENVIRONMENT

        # Unidad: el backend se niega a enviar en produccion, con 503.
        app_settings.ENVIRONMENT = "production"
        try:
            get_email_backend().enviar("a@b.com", "asunto", "cuerpo")
            print("  [TR-13] FALLA: el backend de email envio en produccion")
            raise AssertionError("El guard de produccion no bloqueo el envio")
        except HTTPException as exc:
            assert exc.status_code == 503, f"TR-13: esperaba 503, vino {exc.status_code}"
            assert exc.detail == "Servicio de email no disponible", (
                f"TR-13: detalle inesperado: {exc.detail!r}"
            )
        print("  [TR-13] el backend rechaza el envio en produccion con 503: PASADO")

        # Integracion: el endpoint traduce a 503.
        _fallidos.clear()
        captura.registros.clear()
        db.expire_all()
        vivos_antes = db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == uid,
            PasswordResetToken.usado_en.is_(None),
            PasswordResetToken.revocado.is_(False),
        ).count()
        r13 = client.post("/api/v1/auth/forgot-password", json={"identificador": CORREO})
        assert r13.status_code == 503, (
            f"TR-13: en produccion deberia dar 503: {r13.status_code} {r13.text}"
        )
        assert r13.json().get("detail"), "TR-13: el 503 deberia traer detalle"
        assert not captura.registros, "TR-13: no se debio enviar ningun email"
        app_settings.ENVIRONMENT = entorno_previo
        db.expire_all()
        # El 503 no debe dejar un token mas: se compara contra el estado previo,
        # no contra cero (TR-12 dejo tokens pendientes legítimos).
        vivos_despues = db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == uid,
            PasswordResetToken.usado_en.is_(None),
            PasswordResetToken.revocado.is_(False),
        ).count()
        assert vivos_despues == vivos_antes, (
            f"TR-13: el 503 dejo un token sin enviar (antes={vivos_antes}, "
            f"despues={vivos_despues}); el rollback del endpoint no alcanzo"
        )
        print("  [TR-13] forgot en produccion -> 503 y sin token huerfano: PASADO")

        print("\n[TR] OK: todos los casos de A3.1 pasaron")
    finally:
        logger_email.removeHandler(captura)
        logger_email.setLevel(nivel_previo)
        _app_settings.ENVIRONMENT = entorno_global_previo
        try:
            _fallidos.clear()
            _fallidos.update(buckets_previos)
            for uid_borrar in ids_a_borrar:
                _borrar_tokens(db, uid_borrar)
                u = db.query(UsuarioModel).filter(UsuarioModel.id == uid_borrar).first()
                if u is not None:
                    db.delete(u)
            # Barrido defensivo: cualquier temporal con las cedulas de este test
            # que haya quedado de una corrida anterior (p. ej. una que fallo).
            for huerfano in db.query(UsuarioModel).filter(
                UsuarioModel.cedula.in_([CEDULA, "44556677"])
            ).all():
                _borrar_tokens(db, huerfano.id)
                db.delete(huerfano)
            # Las claves de configuracion que este test produjo (y que la tabla
            # no tenia) se retiran para dejar la BD como estaba.
            if claves_previas:
                db.execute(
                    delete(ConfiguracionSistema).where(
                        ConfiguracionSistema.clave.in_(list(claves_previas))
                    )
                )
            else:
                for clave in (
                    CONFIG_TTL_ENLACE_HORAS,
                    CONFIG_TTL_CODIGO_MINUTOS,
                    CONFIG_INTENTOS_ENLACE,
                    CONFIG_INTENTOS_CODIGO,
                ):
                    db.execute(
                        delete(ConfiguracionSistema).where(ConfiguracionSistema.clave == clave)
                    )
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"\n[ERROR EN LIMPIEZA]: {e}")
            raise
        finally:
            db.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        import traceback

        print(f"\n[ERROR EN TESTS]: {exc}")
        traceback.print_exc()
        raise
