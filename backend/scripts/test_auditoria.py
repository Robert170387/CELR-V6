"""A3.4 — Auditoria de eventos sensibles (TAUD-1..TAUD-12).

Suite 18. Es el CONSUMIDOR de la tabla `auditoria_evento` (D-Aud-4'): lee las
filas y verifica su contenido, no solo que la escritura no explote. Sin esto
seria una tabla sin consumidor, que es el patron que ya mordio dos veces
(`debe_cambiar_contrasena` en A4, `registrar_intento_fallido` en A3.3) y que
en auditoria es peor: un rastro sin verificar contesta preguntas que nadie
comprueba, y por eso da falsa confianza.

EXCEPCION DOCUMENTADA A LA POLITICA APPEND-ONLY: esta suite borra las filas
que genera, para dejar el baseline en cero. `auditoria_evento` es append-only
por CONVENCION en produccion (hoy nada impide UPDATE/DELETE — deuda
append-only); en el test hay que limpiar para poder correr mas de una vez.
"""
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.auditoria import AuditoriaEvento
from app.models import ConfiguracionSistema
from app.models.flota import PasswordResetToken, RefreshToken, Usuario as UsuarioModel
from app.core.security import hash_password
from app.services.password_reset import (
    CONFIG_INTENTOS_CODIGO,
    CONFIG_INTENTOS_ENLACE,
    CONFIG_TTL_CODIGO_MINUTOS,
    CONFIG_TTL_ENLACE_HORAS,
)

PASSWORD_INICIAL = "Inicial123"
SUFIJO = os.environ.get("CELR_TEST_SUFFIX", "a34")


class CapturaLogs(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.registros = []

    def emit(self, record):
        try:
            self.registros.append(record.getMessage())
        except Exception:  # noqa: BLE001
            pass

    def texto(self) -> str:
        return "\n".join(self.registros)


def _correo(rol: str) -> str:
    return f"a34-{rol}-{SUFIJO}@celr.com"


def run() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    print("Iniciando prueba de auditoria (A3.4)...")
    client = TestClient(app)
    captura = CapturaLogs()
    root = logging.getLogger()
    nivel_previo = root.level
    root.addHandler(captura)
    root.setLevel(logging.DEBUG)

    db = SessionLocal()
    # Corte: toda fila creada DESDE ahora. Las de antes son de otras corridas.
    marca = datetime.now(timezone.utc) - timedelta(seconds=1)
    # El servicio inserta las claves de reset con ON CONFLICT DO NOTHING la
    # primera vez que se usan; el test las restaura (gate: 0 filas).
    claves_previas = {
        clave
        for (clave,) in db.query(ConfiguracionSistema.clave).all()
        if clave
        in {
            CONFIG_TTL_ENLACE_HORAS,
            CONFIG_TTL_CODIGO_MINUTOS,
            CONFIG_INTENTOS_ENLACE,
            CONFIG_INTENTOS_CODIGO,
        }
    }
    try:
        def nuevo(etiqueta: str) -> UsuarioModel:
            correo = _correo(etiqueta)
            u = db.query(UsuarioModel).filter(UsuarioModel.correo == correo).first()
            if not u:
                u = UsuarioModel(
                    correo=correo,
                    contrasena_hash=hash_password(PASSWORD_INICIAL),
                    rol="conductor",
                    activo=True,
                )
                db.add(u)
            u.contrasena_hash = hash_password(PASSWORD_INICIAL)
            u.activo = True
            u.debe_cambiar_contrasena = False
            db.commit()
            db.refresh(u)
            return u

        admin = nuevo("admin")
        admin.rol = "admin"
        # El sufijo del correo es una ETIQUETA del test, no el rol: el CHECK
        # ck_usuarios_rol_valido solo acepta los 6 roles del enum.
        inactivo = nuevo("inactivo")
        inactivo.rol = "cliente"
        inactivo.activo = False
        db.commit()
        meta = nuevo("meta")
        meta.rol = "operador"
        cond = nuevo("conductor")
        cond.rol = "conductor"
        db.commit()

        def eventos(desde=marca):
            db.expire_all()
            return (
                db.query(AuditoriaEvento)
                .filter(AuditoriaEvento.creado_en >= desde)
                .order_by(AuditoriaEvento.id)
                .all()
            )

        def ultimo(evento_nombre, desde=marca):
            filas = [f for f in eventos(desde) if f.evento == evento_nombre]
            assert filas, f"no se registro ningun evento '{evento_nombre}'"
            return filas[-1]

        # ---------------- TAUD-1: login OK ----------------
        r = client.post(
            "/api/v1/auth/login",
            json={"identificador": admin.correo, "contrasena": PASSWORD_INICIAL},
        )
        assert r.status_code == 200, f"TAUD-1 login fallo: {r.status_code} {r.text}"
        f1 = ultimo("login_ok")
        assert f1.usuario_actor_id == admin.id, f"TAUD-1: actor={f1.usuario_actor_id}"
        assert f1.usuario_objetivo_id == admin.id, f"TAUD-1: objetivo={f1.usuario_objetivo_id}"
        assert f1.ip, "TAUD-1: no se capturo la IP"
        assert f1.detalle is None or "contrasena" not in json.dumps(f1.detalle)
        print(f"  [TAUD-1] login_ok: actor=objetivo={admin.id}, ip='{f1.ip}': PASADO")

        # ---------------- TAUD-2: login fallido ----------------
        antes = len(eventos())
        r2 = client.post(
            "/api/v1/auth/login",
            json={"identificador": admin.correo, "contrasena": "Incorrecta123"},
        )
        assert r2.status_code == 401, f"TAUD-2 deberia dar 401: {r2.status_code}"
        nuevos = eventos()[antes:]
        assert len(nuevos) == 1, f"TAUD-2: se esperaban 1 evento, hubo {len(nuevos)}"
        assert nuevos[0].evento == "login_fail", f"TAUD-2: evento={nuevos[0].evento}"
        assert nuevos[0].usuario_actor_id is None, "TAUD-2: actor no deberia filtrar la cuenta"
        assert nuevos[0].usuario_objetivo_id is None, "TAUD-2: objetivo no deberia filtrar la cuenta"
        assert nuevos[0].ip, "TAUD-2: no se capturo la IP"
        assert nuevos[0].detalle == {"motivo": "credenciales"}, f"TAUD-2: detalle={nuevos[0].detalle}"
        print("  [TAUD-2] login_fail: actor=objetivo=None, detalle sin secretos: PASADO")

        # ---------------- TAUD-3: usuario inactivo ----------------
        antes = len(eventos())
        r3 = client.post(
            "/api/v1/auth/login",
            json={"identificador": inactivo.correo, "contrasena": PASSWORD_INICIAL},
        )
        assert r3.status_code == 403, f"TAUD-3 deberia dar 403: {r3.status_code} {r3.text}"
        nuevos = eventos()[antes:]
        assert len(nuevos) == 1 and nuevos[0].evento == "login_inactivo", (
            f"TAUD-3: eventos={[e.evento for e in nuevos]}"
        )
        assert nuevos[0].usuario_actor_id == inactivo.id, "TAUD-3: actor incorrecto"
        assert nuevos[0].usuario_objetivo_id == inactivo.id, "TAUD-3: objetivo incorrecto"
        print("  [TAUD-3] login_inactivo: actor=objetivo=inactivo.id: PASADO")

        # ---------------- TAUD-4: forgot que resuelve ----------------
        antes = len(eventos())
        r4 = client.post("/api/v1/auth/forgot-password", json={"identificador": cond.correo})
        assert r4.status_code == 200, f"TAUD-4 deberia dar 200: {r4.status_code}"
        nuevos = eventos()[antes:]
        assert len(nuevos) == 1 and nuevos[0].evento == "password_reset_solicitado", (
            f"TAUD-4: eventos={[e.evento for e in nuevos]}"
        )
        assert nuevos[0].usuario_objetivo_id == cond.id, "TAUD-4: objetivo incorrecto"
        assert nuevos[0].usuario_actor_id is None, "TAUD-4: el endpoint es publico, sin actor"
        assert nuevos[0].detalle == {"con_correo": True}, f"TAUD-4: detalle={nuevos[0].detalle}"
        print("  [TAUD-4] password_reset_solicitado: objetivo=cond.id: PASADO")

        # ---------------- TAUD-5: forgot que NO resuelve -> 0 filas ----------------
        antes = len(eventos())
        r5 = client.post(
            "/api/v1/auth/forgot-password", json={"identificador": "nadie-aqui@celr.com"}
        )
        assert r5.status_code == 200, f"TAUD-5 deberia dar 200: {r5.status_code}"
        assert len(eventos()) == antes, (
            "TAUD-5: un identificador inexistent no debe generar eventos "
            "(evita que el rastro sea un segundo canal de enumeracion)"
        )
        print("  [TAUD-5] forgot inexistente -> 0 eventos (no filtra existencia): PASADO")

        # ---------------- TAUD-6: reset por enlace ----------------
        # El token viaja por el log del backend de email (D2: en local es la
        # unica forma de completar el flujo). Se busca el registro que lo
        # contiene en vez de asumir que es el ultimo: otros flujos loguean.
        enlaces = [m for m in captura.registros if "token=" in m]
        assert enlaces, "no se encontro el email-mock con el enlace de recuperacion"
        token = enlaces[-1].split("token=")[1].split()[0].strip()
        assert token, "no se pudo extraer el token del enlace"
        antes = len(eventos())
        r6 = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "nueva_contrasena": "NuevaClave99"},
        )
        assert r6.status_code == 200, f"TAUD-6 deberia dar 200: {r6.status_code} {r6.text}"
        nuevos = eventos()[antes:]
        assert len(nuevos) == 1 and nuevos[0].evento == "password_reset_enlace", (
            f"TAUD-6: eventos={[e.evento for e in nuevos]}"
        )
        assert nuevos[0].usuario_objetivo_id == cond.id, "TAUD-6: objetivo incorrecto"
        assert nuevos[0].usuario_actor_id is None, "TAUD-6: sin actor (endpoint publico)"
        print("  [TAUD-6] password_reset_enlace: objetivo=cond.id, sin actor: PASADO")

        # ---------------- TAUD-7: reset admin ----------------
        h_admin = {
            "Authorization": "Bearer "
            + client.post(
                "/api/v1/auth/login",
                json={"identificador": admin.correo, "contrasena": PASSWORD_INICIAL},
            ).json()["access_token"]
        }
        antes = len(eventos())
        r7 = client.post(
            f"/api/v1/usuarios/{meta.id}/reset-password", headers=h_admin
        )
        assert r7.status_code == 200, f"TAUD-7 deberia dar 200: {r7.status_code} {r7.text}"
        temporal = r7.json()["contrasena_temporal"]
        nuevos = eventos()[antes:]
        assert len(nuevos) == 1 and nuevos[0].evento == "password_reset_admin", (
            f"TAUD-7: eventos={[e.evento for e in nuevos]}"
        )
        assert nuevos[0].usuario_actor_id == admin.id, "TAUD-7: actor incorrecto"
        assert nuevos[0].usuario_objetivo_id == meta.id, "TAUD-7: objetivo incorrecto"
        print("  [TAUD-7] password_reset_admin: actor=admin.id, objetivo=meta.id: PASADO")

        # ---------------- TAUD-8: generar codigo + canjear ----------------
        antes = len(eventos())
        r8a = client.post(
            f"/api/v1/usuarios/{cond.id}/reset-codigo", headers=h_admin
        )
        assert r8a.status_code == 200, f"TAUD-8 generar deberia dar 200: {r8a.status_code} {r8a.text}"
        codigo = r8a.json()["codigo"]
        r8b = client.post(
            "/api/v1/auth/reset-codigo",
            json={"codigo": codigo, "nueva_contrasena": "Canjeada456"},
        )
        assert r8b.status_code == 200, f"TAUD-8 canje deberia dar 200: {r8b.status_code} {r8b.text}"
        nuevos = eventos()[antes:]
        nombres = [e.evento for e in nuevos]
        assert nombres == ["password_reset_codigo_generado", "password_reset_codigo_canje"], (
            f"TAUD-8: eventos={nombres}"
        )
        generado = nuevos[0]
        canjeado = nuevos[1]
        assert generado.usuario_actor_id == admin.id, "TAUD-8: actor del generador"
        assert generado.usuario_objetivo_id == cond.id, "TAUD-8: objetivo del generador"
        assert canjeado.usuario_actor_id is None, "TAUD-8: el canje es publico, sin actor"
        assert canjeado.usuario_objetivo_id == cond.id, "TAUD-8: objetivo del canje"
        print("  [TAUD-8] generado (actor=admin) + canje (sin actor): PASADO")

        # ---------------- TAUD-9: cambio de contrasena propio ----------------
        h_meta = {
            "Authorization": "Bearer "
            + client.post(
                "/api/v1/auth/login",
                json={"identificador": meta.correo, "contrasena": temporal},
            ).json()["access_token"]
        }
        antes = len(eventos())
        r9 = client.post(
            "/api/v1/auth/cambio-contrasena",
            json={"contrasena_actual": temporal, "nueva_contrasena": "PropiaCambio1"},
            headers=h_meta,
        )
        assert r9.status_code == 200, f"TAUD-9 deberia dar 200: {r9.status_code} {r9.text}"
        nuevos = eventos()[antes:]
        assert len(nuevos) == 1 and nuevos[0].evento == "password_change", (
            f"TAUD-9: eventos={[e.evento for e in nuevos]}"
        )
        assert nuevos[0].usuario_actor_id == meta.id, "TAUD-9: actor incorrecto"
        assert nuevos[0].usuario_objetivo_id == meta.id, "TAUD-9: objetivo incorrecto"
        print("  [TAUD-9] password_change: actor=objetivo=meta.id: PASADO")

        # ---------------- TAUD-10: INVARIANTE — ningun secreto en el rastro ----
        secretos = [
            temporal,          # contrasena temporal de A3.2
            codigo,             # codigo offline de 6 digitos
            token,              # token de enlace de A3.1
            "PropiaCambio1",    # contrasena nueva
            "NuevaClave99",     # contrasena del reset por enlace
            "Canjeada456",      # contrasena del canje
        ]
        for fila in eventos():
            blob = json.dumps(fila.detalle) if fila.detalle else ""
            # La IP y el user-agent no son secretos; se comparan los secretos
            # contra TODA la fila serializada, no solo contra `detalle`.
            completa = f"{fila.evento}|{blob}|{fila.ip}|{fila.user_agent}"
            for secreto in secretos:
                assert secreto not in completa, (
                    f"TAUD-10: el secreto '{secreto[:6]}...' aparece en la fila "
                    f"de '{fila.evento}' (id={fila.id})"
                )
        print(f"  [TAUD-10] invariante: {len(eventos())} filas, 0 secretos filtrados: PASADO")

        # ---------------- TAUD-12: user_agent capturado ----------------
        filas_con_ua = [f for f in eventos() if f.user_agent]
        assert filas_con_ua, "TAUD-12: no se capturo user_agent en ninguna fila"
        assert all(len(f.user_agent) <= 500 for f in filas_con_ua), "TAUD-12: user_agent excede 500"
        print(f"  [TAUD-12] user_agent capturado en {len(filas_con_ua)} filas: PASADO")

        # ---------------- TAUD-11: conteo consolidado ----------------
        from collections import Counter

        conteo = Counter(f.evento for f in eventos())
        esperado = {
            "login_ok": 3,          # admin x2 (TAUD-1, TAUD-7) + el de TAUD-9/TAUD-8
            "login_fail": 1,
            "login_inactivo": 1,
            "password_reset_solicitado": 1,
            "password_reset_enlace": 1,
            "password_reset_admin": 1,
            "password_reset_codigo_generado": 1,
            "password_reset_codigo_canje": 1,
            "password_change": 1,
        }
        for nombre, cantidad in esperado.items():
            assert conteo.get(nombre) == cantidad, (
                f"TAUD-11: '{nombre}' aparece {conteo.get(nombre)} veces, se esperaba {cantidad}"
            )
        print(f"  [TAUD-11] conteo por tipo de evento coincide: {dict(conteo)}: PASADO")

        print("\n[TAUD] OK: auditoria de eventos sensibles funcionando")
    finally:
        root.removeHandler(captura)
        root.setLevel(nivel_previo)
        try:
            correos = [_correo(r) for r in ("admin", "inactivo", "meta", "conductor")]
            # Primero borrar los usuarios (ON DELETE SET NULL deja las filas de
            # auditoria huerfanas con actor=objetivo NULL), despues las filas.
            for u in db.query(UsuarioModel).filter(UsuarioModel.correo.in_(correos)).all():
                db.execute(delete(RefreshToken).where(RefreshToken.usuario_id == u.id))
                db.execute(delete(PasswordResetToken).where(PasswordResetToken.usuario_id == u.id))
                db.delete(u)
            db.flush()
            db.execute(
                delete(AuditoriaEvento).where(AuditoriaEvento.creado_en >= marca)
            )
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
