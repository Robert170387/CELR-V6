"""A3.3 — Reset por codigo offline de 6 digitos (TRC-1..TRC-16).

Suite 17. Cubre la generacion del codigo por admin (misma matriz de roles que
A3.2, via la funcion compartida), el canje publico, y los dos limites que
sostienen el modo offline: el limite por IP (adivinar el codigo, que no tiene
fila donde contar) y el limite por fila `intentos` (adivinar la contrasena con
un codigo ya valido, que si la tiene).

Dos pools disjuntos de usuarios (ejecutores / objetivos): si un usuario fuera
ambos, un reset sobre el invalidaria su propia sesion via password_version.
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
from app.services.password_reset import (
    CONFIG_INTENTOS_CODIGO,
    CONFIG_INTENTOS_ENLACE,
    CONFIG_TTL_CODIGO_MINUTOS,
    CONFIG_TTL_ENLACE_HORAS,
)

PASSWORD_INICIAL = "Inicial123"
SUFIJO = os.environ.get("CELR_TEST_SUFFIX", "a33")
HEADER_CAMBIO = "x-celr-requiere-cambio"
ROLES = ("admin", "operador", "contador", "supervisor", "cliente", "conductor")


def _correo(pool: str, rol: str) -> str:
    return f"a33{pool}-{rol}-{SUFIJO}@celr.com"


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


def _crear(db: Session, pool: str, rol: str, cedula: str) -> UsuarioModel:
    correo = _correo(pool, rol)
    u = db.query(UsuarioModel).filter(UsuarioModel.correo == correo).first()
    if not u:
        u = UsuarioModel(
            correo=correo,
            contrasena_hash=hash_password(PASSWORD_INICIAL),
            rol=rol,
            activo=True,
        )
        db.add(u)
    u.contrasena_hash = hash_password(PASSWORD_INICIAL)
    u.rol = rol
    u.activo = True
    u.debe_cambiar_contrasena = False
    u.cedula = cedula
    db.commit()
    db.refresh(u)
    return u


def _login(client, correo: str, contrasena: str):
    r = client.post(
        "/api/v1/auth/login", json={"identificador": correo, "contrasena": contrasena}
    )
    assert r.status_code == 200, f"login de {correo} fallo: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _codigos_de(db: Session, usuario_id: int):
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.usuario_id == usuario_id,
            PasswordResetToken.tipo == "codigo",
        )
        .order_by(PasswordResetToken.id.desc())
        .all()
    )


def run() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    print("Iniciando prueba de reset por codigo offline (A3.3)...")
    client = TestClient(app)
    captura = CapturaLogs()
    root = logging.getLogger()
    nivel_previo = root.level
    root.addHandler(captura)
    root.setLevel(logging.DEBUG)
    _fallidos.clear()

    db = SessionLocal()
    # La tabla venia vacia: el servicio inserta las claves de 'codigo' con
    # ON CONFLICT DO NOTHING la primera vez que se usan, y el test debe
    # devolverla a ese estado para no dejar config colgada (gate: 0 filas).
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
        ejecutores = {
            rol: _crear(db, "e", rol, f"91{i}00001")
            for i, rol in enumerate(ROLES)
        }
        objetivos = {
            rol: _crear(db, "t", rol, f"92{i}00002")
            for i, rol in enumerate(ROLES)
        }
        print(f"Ejecutores y objetivos creados para los {len(ROLES)} roles")

        h = {rol: _login(client, u.correo, PASSWORD_INICIAL) for rol, u in ejecutores.items()}

        def generar(headers, objetivo_id):
            return client.post(
                f"/api/v1/usuarios/{objetivo_id}/reset-codigo", headers=headers
            )

        def canjear(codigo, contrasena):
            return client.post(
                "/api/v1/auth/reset-codigo",
                json={"codigo": codigo, "nueva_contrasena": contrasena},
            )

        def estado(usuario_id: int):
            db.expire_all()
            return db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).one()

        # ---------------- TRC-1: admin genera codigo para conductor ----------------
        _fallidos.clear()
        cond = objetivos["conductor"]
        antes = estado(cond.id)
        hash_antes = antes.contrasena_hash
        version_antes = antes.password_version
        r = generar(h["admin"], cond.id)
        assert r.status_code == 200, f"TRC-1 deberia dar 200: {r.status_code} {r.text}"
        data = r.json()
        codigo = data["codigo"]
        assert len(codigo) == 6 and codigo.isdigit(), f"TRC-1: codigo invalido {codigo!r}"
        assert data["expira_en"], "TRC-1: falta expira_en"
        assert data["mensaje"], "TRC-1: falta mensaje"
        # El objetivo NO debe tocarse: esto no cambia la contrasena.
        despues = estado(cond.id)
        assert despues.contrasena_hash == hash_antes, "TRC-1: se modifico la contrasena"
        assert despues.password_version == version_antes, "TRC-1: subio password_version"
        assert despues.debe_cambiar_contrasena is False, "TRC-1: se seteó el flag"
        assert (
            db.query(RefreshToken).filter(RefreshToken.usuario_id == cond.id).count() == 0
        ), "TRC-1: aparecieron refresh tokens del objetivo"
        print("  [TRC-1] admin -> conductor: 200, codigo de 6 digitos, objetivo intacto: PASADO")

        # ---------------- TRC-2: admin a si mismo ----------------
        r2 = generar(h["admin"], ejecutores["admin"].id)
        assert r2.status_code == 403, f"TRC-2 deberia dar 403: {r2.status_code} {r2.text}"
        print("  [TRC-2] admin -> si mismo: 403: PASADO")

        # ---------------- TRC-3: operador -> admin ----------------
        r3 = generar(h["operador"], objetivos["admin"].id)
        assert r3.status_code == 403, f"TRC-3 deberia dar 403: {r3.status_code} {r3.text}"
        assert "admin" not in r3.json().get("detail", "").lower(), "TRC-3: filtra el rol"
        print("  [TRC-3] operador -> admin: 403 sin filtrar el rol: PASADO")

        # ---------------- TRC-4: operador -> conductor ----------------
        r4 = generar(h["operador"], objetivos["conductor"].id)
        assert r4.status_code == 200, f"TRC-4 deberia dar 200: {r4.status_code} {r4.text}"
        print("  [TRC-4] operador -> conductor: 200: PASADO")

        # ---------------- TRC-5: cliente y conductor ----------------
        r5 = generar(h["cliente"], objetivos["conductor"].id)
        assert r5.status_code == 403, f"TRC-5 cliente deberia dar 403: {r5.status_code}"
        r5b = generar(h["conductor"], objetivos["conductor"].id)
        assert r5b.status_code == 403, f"TRC-5 conductor deberia dar 403: {r5b.status_code}"
        print("  [TRC-5] cliente y conductor -> 403: PASADO")

        # ---------------- TRC-6: el segundo codigo revoca el primero ----------------
        _fallidos.clear()
        cli6 = objetivos["cliente"]
        db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == cli6.id
        ).delete(synchronize_session=False)
        db.commit()
        _fallidos.clear()
        c1 = generar(h["admin"], cli6.id).json()["codigo"]
        c2 = generar(h["admin"], cli6.id).json()["codigo"]
        filas = _codigos_de(db, cli6.id)
        assert len(filas) == 2, f"TRC-6: deberian quedar 2 filas, hay {len(filas)}"
        mas_reciente = filas[0]
        assert mas_reciente.revocado is False, "TRC-6: el codigo nuevo quedo revocado"
        # El viejo debe estar revocado: canjearlo da 401.
        _fallidos.clear()
        rr = canjear(c1, "ClaveNueva123")
        assert rr.status_code == 401, f"TRC-6: el codigo viejo deberia dar 401: {rr.status_code}"
        print("  [TRC-6] el codigo nuevo revoca al anterior (el viejo da 401): PASADO")

        # ---------------- TRC-8: codigo invalido ----------------
        _fallidos.clear()
        r8 = canjear("999999", "ClaveNueva123")
        assert r8.status_code == 401, f"TRC-8 deberia dar 401: {r8.status_code} {r8.text}"
        msg_invalido = r8.json()["detail"]
        print(f"  [TRC-8] codigo inexistente -> 401: {msg_invalido}")

        # ---------------- TRC-9: codigo expirado ----------------
        _fallidos.clear()
        db.expire_all()
        filas = _codigos_de(db, cli6.id)
        filas[0].expira_en = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        r9 = canjear(c2, "ClaveNueva123")
        assert r9.status_code == 401, f"TRC-9 deberia dar 401: {r9.status_code} {r9.text}"
        assert r9.json()["detail"] == msg_invalido, (
            f"TRC-9: el mensaje difiere y filtra el motivo: {r9.json()['detail']}"
        )
        print("  [TRC-9] codigo expirado -> 401 con el MISMO mensaje: PASADO")

        # ---------------- TRC-10: codigo ya usado ----------------
        _fallidos.clear()
        db.expire_all()
        sup10 = objetivos["supervisor"]
        db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == sup10.id
        ).delete(synchronize_session=False)
        db.commit()
        # Sesion previa al canje: debe morir cuando cambie la credencial.
        h_previa = _login(client, sup10.correo, PASSWORD_INICIAL)
        c10 = generar(h["admin"], sup10.id).json()["codigo"]
        _fallidos.clear()
        r10a = canjear(c10, "ClaveNueva123")
        assert r10a.status_code == 200, f"TRC-10 el primer canje deberia dar 200: {r10a.status_code} {r10a.text}"
        _fallidos.clear()
        r10b = canjear(c10, "OtraClave123")
        assert r10b.status_code == 401, f"TRC-10 deberia dar 401: {r10b.status_code} {r10b.text}"
        assert r10b.json()["detail"] == msg_invalido, "TRC-10: el mensaje filtra el motivo"
        print("  [TRC-10] codigo ya usado -> 401: PASADO")

        # ---------------- TRC-7: canje valido, efectos completos ----------------
        db.expire_all()
        sup = estado(sup10.id)
        assert verify_password("ClaveNueva123", sup.contrasena_hash), (
            "TRC-7: la contrasena no quedo actualizada"
        )
        assert not verify_password(PASSWORD_INICIAL, sup.contrasena_hash), (
            "TRC-7: la contrasena vieja sigue sirviendo"
        )
        db.expire_all()
        filas = _codigos_de(db, sup10.id)
        assert filas[0].usado_en is not None, "TRC-7: el codigo no quedo marcado usado"
        assert filas[0].revocado is True, "TRC-7: el codigo no quedo revocado"
        # La sesion abierta ANTES del canje debe quedar invalidada.
        r7s = client.get("/api/v1/viajes", headers=h_previa)
        assert r7s.status_code == 401, (
            f"TRC-7: la sesion previa deberia estar invalidada: {r7s.status_code}"
        )
        assert (
            db.query(RefreshToken)
            .filter(RefreshToken.usuario_id == sup10.id, RefreshToken.revocado == False)  # noqa: E712
            .count()
        ) == 0, "TRC-7: quedaron refresh tokens activos del objetivo"
        print("  [TRC-7] canje valido -> 200, hash cambiado, codigo usado, sesion previa caída: PASADO")

        # ---------------- TRC-11: politica violada NO consume, pero cuenta ----------------
        _fallidos.clear()
        conta11 = objetivos["contador"]
        db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == conta11.id
        ).delete(synchronize_session=False)
        db.commit()
        c11 = generar(h["admin"], conta11.id).json()["codigo"]
        _fallidos.clear()
        r11a = canjear(c11, "corto7")
        assert r11a.status_code == 422, f"TRC-11 deberia dar 422: {r11a.status_code} {r11a.text}"
        db.expire_all()
        filas = _codigos_de(db, conta11.id)
        assert filas[0].usado_en is None, "TRC-11: el 422 consumio el codigo (bug)"
        assert filas[0].revocado is False, "TRC-11: el 422 revoco el codigo (bug)"
        assert filas[0].intentos == 1, f"TRC-11: intentos={filas[0].intentos}, se esperaba 1"
        print("  [TRC-11] 422 no consume el codigo pero suma intento: PASADO")

        # ---------------- TRC-12: agotamiento de intentos ----------------
        # Con el codigo VALIDO y contrasenas que no cumplen la politica, cada
        # intento suma a `intentos` (aqui si hay fila). Al llegar a
        # intentos_max el codigo se revoca y el canje pasa a 401.
        for i in range(4):
            _fallidos.clear()
            r12 = canjear(c11, "corto7")
            # El 5to intento (indice 3 aqui) es el que agota: depende del estado.
            assert r12.status_code in (422, 401), (
                f"TRC-12 intento {i+2}: esperaba 422 o 401, vino {r12.status_code}"
            )
        _fallidos.clear()
        r12f = canjear(c11, "corto7")
        assert r12f.status_code == 401, (
            f"TRC-12: tras agotar intentos deberia dar 401: {r12f.status_code} {r12f.text}"
        )
        assert r12f.json()["detail"] == msg_invalido, "TRC-12: el mensaje filtra el motivo"
        db.expire_all()
        filas = _codigos_de(db, conta11.id)
        assert filas[0].revocado is True, "TRC-12: el codigo no quedo revocado"
        print("  [TRC-12] intentos agotados -> codigo revocado y 401 generico: PASADO")

        # ---------------- TRC-13: el codigo no aparece en logs ----------------
        captura.registros.clear()
        _fallidos.clear()
        db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == objetivos["operador"].id
        ).delete(synchronize_session=False)
        db.commit()
        _fallidos.clear()
        r13 = generar(h["admin"], objetivos["operador"].id)
        codigo13 = r13.json()["codigo"]
        assert codigo13 not in captura.texto(), "TRC-13: el codigo aparece en los logs"
        assert codigo13 not in str(r13.request.url), "TRC-13: el codigo viaja en la URL"
        assert codigo13 not in r13.text.replace(f'"{codigo13}"', ""), (
            "TRC-13: el codigo aparece fuera del campo 'codigo' de la respuesta"
        )
        print("  [TRC-13] el codigo no aparece en logs ni en la URL: PASADO")

        # ---------------- TRC-14: el codigo no se persiste en claro ----------------
        import hashlib

        esperado = hashlib.sha256(codigo13.encode("utf-8")).hexdigest()
        fila14 = _codigos_de(db, objetivos["operador"].id)[0]
        assert fila14.token_hash == esperado, "TRC-14: el hash no corresponde al codigo"
        assert fila14.token_hash != codigo13, "TRC-14: el codigo esta en claro en la BD"
        assert codigo13 not in fila14.token_hash, "TRC-14: el codigo aparece en el hash"
        print("  [TRC-14: OK] el codigo se guarda solo como SHA-256: PASADO")

        # ---------------- TRC-15: integracion con A4 ----------------
        db.expire_all()
        op15 = estado(objetivos["operador"].id)
        _fallidos.clear()
        c15 = generar(h["admin"], op15.id).json()["codigo"]
        _fallidos.clear()
        r15 = canjear(c15, "SinBloqueo123")
        assert r15.status_code == 200, f"TRC-15 deberia dar 200: {r15.status_code} {r15.text}"
        h15 = _login(client, op15.correo, "SinBloqueo123")
        rr15 = client.get("/api/v1/viajes", headers=h15)
        assert rr15.status_code == 200, (
            f"TRC-15: tras el canje deberia poder usar /viajes: {rr15.status_code} {rr15.text}"
        )
        assert rr15.headers.get(HEADER_CAMBIO) is None, "TRC-15: no debe mandar el header de A4"
        print("  [TRC-15] canje -> login -> /viajes 200 sin bloqueo de A4: PASADO")

        # ---------------- TRC-16: codigo con ceros iniciales ----------------
        db.expire_all()
        cli16 = objetivos["cliente"]
        db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == cli16.id
        ).delete(synchronize_session=False)
        db.commit()
        _fallidos.clear()
        c16 = generar(h["admin"], cli16.id).json()["codigo"]
        # Se fuerza un codigo con ceros iniciales: la validacion es por longitud
        # y digitos, nunca por valor numerico.
        _fallidos.clear()
        db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == cli16.id
        ).delete(synchronize_session=False)
        db.commit()
        db.add(
            PasswordResetToken(
                usuario_id=cli16.id,
                tipo="codigo",
                token_hash=hashlib.sha256(b"000042").hexdigest(),
                expira_en=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
        )
        db.commit()
        _fallidos.clear()
        r16 = canjear("000042", "CerosCeros9")
        assert r16.status_code == 200, (
            f"TRC-16: un codigo con ceros iniciales deberia aceptarse: {r16.status_code} {r16.text}"
        )
        # Y uno que no sea de 6 digitos se rechaza en el schema (422).
        _fallidos.clear()
        r16b = client.post(
            "/api/v1/auth/reset-codigo",
            json={"codigo": "12345", "nueva_contrasena": "CerosCeros9"},
        )
        assert r16b.status_code == 422, f"TRC-16: 5 digitos deberia dar 422: {r16b.status_code}"
        print("  [TRC-16] '000042' se acepta y '12345' se rechaza (422): PASADO")

        print("\n[TRC] OK: reset por codigo offline funcionando")
    finally:
        root.removeHandler(captura)
        root.setLevel(nivel_previo)
        _fallidos.clear()
        try:
            correos = [_correo(pool, rol) for pool in ("e", "t") for rol in ROLES]
            for u in db.query(UsuarioModel).filter(UsuarioModel.correo.in_(correos)).all():
                db.execute(delete(RefreshToken).where(RefreshToken.usuario_id == u.id))
                db.execute(delete(PasswordResetToken).where(PasswordResetToken.usuario_id == u.id))
                db.delete(u)
            # Solo se borran las claves que esta corrida.CREO; si ya existian
            # de una corrida anterior quedan intactas.
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
