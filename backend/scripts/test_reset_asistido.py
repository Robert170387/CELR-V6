"""A3.2 — Reset asistido por admin (TRA-1..TRA-16).

Suite 16. Cubre la matriz de roles completa (los 6 roles del enum), la
anti-escalada, que la contrasena temporal no se filtre ni a logs ni a la tabla
password_reset_token, y la integracion con A4 (el flag bloquea de verdad) y
con A1 (la politica de contrasenas).

Dos pools DISJUNTOS de usuarios: ejecutores y objetivos. Si un usuario fuera
ambos, un reset sobre el invalidaria su propia sesion de ejecutor (el
password_version sube y el access token queda viejo -> 401), y el test
fallaria por un motivo que no es el que cree comprobar. Con pools separados,
cada caso mide lo que dice medir.

NORMATIVA — esta suite no afirma ningun total global de la app DB. La BD de
desarrollo tiene datos reales (cuentas creadas a mano, tokens de recuperacion
pendientes), y un `count() == 0` pasa en una BD limpia y falla con el uso
diario: el gate se pone rojo sin que nadie haya tocado el codigo. Los asserts
miden delta o filtran por los usuarios del propio test.

Limpieza por ID y resolucion por correo (norma D-cleanup de A3.1).
"""
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.flota import PasswordResetToken, RefreshToken, Usuario as UsuarioModel
from app.core.security import hash_password, validar_politica_contrasena

PASSWORD_INICIAL = "Inicial123"
SUFIJO = os.environ.get("CELR_TEST_SUFFIX", "a32")
HEADER_CAMBIO = "x-celr-requiere-cambio"
ROLES = ("admin", "operador", "contador", "supervisor", "cliente", "conductor")


def _correo(pool: str, rol: str) -> str:
    return f"a32{pool}-{rol}-{SUFIJO}@celr.com"


class CapturaLogs(logging.Handler):
    """Acumula todos los registros emitidos durante un bloque."""

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


def run() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    print("Iniciando prueba de reset asistido por admin (A3.2)...")
    client = TestClient(app)
    captura = CapturaLogs()
    root = logging.getLogger()
    nivel_previo = root.level
    root.addHandler(captura)
    root.setLevel(logging.DEBUG)

    db = SessionLocal()
    try:
        # Pool de EJECUTORES: nunca son objetivo de un reset.
        ejecutores, obj_admin, obj_conductor, obj_contador, obj_cliente, obj_supervisor = {}, {}, {}, {}, {}, {}
        for i, rol in enumerate(ROLES):
            ejecutores[rol] = _crear(db, "e", rol, f"90{i}00001")
        # Pool de OBJETIVOS: nunca son ejecutores.
        objetivos = {
            "admin": _crear(db, "t", "admin", "90000011"),
            "operador": _crear(db, "t", "operador", "90000012"),
            "contador": _crear(db, "t", "contador", "90000013"),
            "supervisor": _crear(db, "t", "supervisor", "90000014"),
            "cliente": _crear(db, "t", "cliente", "90000015"),
            "conductor": _crear(db, "t", "conductor", "90000016"),
        }
        print(f"Ejecutores y objetivos creados para los {len(ROLES)} roles")

        # NORMATIVA — los conteos globales de la app DB no son invariante: un
        # token de recuperacion pendiente (pedido desde /recuperar o generado
        # desde la pantalla de gestion) deja filas en password_reset_token sin
        # que este test intervenga. Los asserts de esta suite miden DELTA
        # (snapshot antes/despues) o filtran por los usuarios propios, nunca un
        # total global. Ver TRA-13.
        tokens_antes = db.query(PasswordResetToken).count()

        h = {rol: _login(client, u.correo, PASSWORD_INICIAL) for rol, u in ejecutores.items()}

        def reset(headers, objetivo_id):
            return client.post(
                f"/api/v1/usuarios/{objetivo_id}/reset-password", headers=headers
            )

        def estado(usuario_id: int):
            db.expire_all()
            return db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).one()

        # ---------------- TRA-1: admin resetea a operador ----------------
        op = objetivos["operador"]
        version_previa = estado(op.id).password_version
        _login(client, op.correo, PASSWORD_INICIAL)  # sesion que debe caer
        r = reset(h["admin"], op.id)
        assert r.status_code == 200, f"TRA-1 deberia dar 200: {r.status_code} {r.text}"
        data = r.json()
        assert data["contrasena_temporal"], "TRA-1: sin contrasena_temporal"
        assert data["debe_cambiar_contrasena"] is True, "TRA-1: falta el flag en la respuesta"
        assert data["usuario_id"] == op.id, "TRA-1: usuario_id incorrecto"
        fila = estado(op.id)
        assert fila.debe_cambiar_contrasena is True, "TRA-1: el flag no quedo seteado"
        assert fila.password_version == version_previa + 1, (
            f"TRA-1: password_version {fila.password_version} != {version_previa + 1}"
        )
        activos = db.query(RefreshToken).filter(
            RefreshToken.usuario_id == op.id, RefreshToken.revocado == False  # noqa: E712
        ).count()
        assert activos == 0, f"TRA-1: quedaron {activos} refresh tokens activos del objetivo"
        print("  [TRA-1] admin -> operador: 200 + flag + version++ + refreshes revocados: PASADO")

        # ---------------- TRA-2: admin no se resetea a si mismo ----------------
        r2 = reset(h["admin"], ejecutores["admin"].id)
        assert r2.status_code == 403, f"TRA-2 deberia dar 403: {r2.status_code} {r2.text}"
        print("  [TRA-2] admin -> si mismo: 403: PASADO")

        # ---------------- TRA-3: admin -> conductor ----------------
        r3 = reset(h["admin"], objetivos["conductor"].id)
        assert r3.status_code == 200, f"TRA-3 deberia dar 200: {r3.status_code} {r3.text}"
        print("  [TRA-3] admin -> conductor: 200: PASADO")

        # ---------------- TRA-4: operador -> conductor ----------------
        r4 = reset(h["operador"], objetivos["conductor"].id)
        assert r4.status_code == 200, f"TRA-4 deberia dar 200: {r4.status_code} {r4.text}"
        print("  [TRA-4] operador -> conductor: 200: PASADO")

        # ---------------- TRA-5: operador -> admin (anti-escalada) ----------------
        r5 = reset(h["operador"], objetivos["admin"].id)
        assert r5.status_code == 403, f"TRA-5 deberia dar 403: {r5.status_code} {r5.text}"
        assert "admin" not in r5.json().get("detail", "").lower(), (
            f"TRA-5: el mensaje filtra el rol del objetivo: {r5.json().get('detail')}"
        )
        print("  [TRA-5] operador -> admin: 403 sin filtrar el rol del objetivo: PASADO")

        # ---------------- TRA-6: operador -> otro operador ----------------
        r6 = reset(h["operador"], objetivos["operador"].id)
        assert r6.status_code == 403, f"TRA-6 deberia dar 403: {r6.status_code} {r6.text}"
        print("  [TRA-6] operador -> otro operador: 403: PASADO")

        # ---------------- TRA-7: contador -> conductor ----------------
        r7 = reset(h["contador"], objetivos["conductor"].id)
        assert r7.status_code == 200, f"TRA-7 deberia dar 200: {r7.status_code} {r7.text}"
        print("  [TRA-7] contador -> conductor: 200: PASADO")

        # ---------------- TRA-8: supervisor -> admin ----------------
        r8 = reset(h["supervisor"], objetivos["admin"].id)
        assert r8.status_code == 403, f"TRA-8 deberia dar 403: {r8.status_code} {r8.text}"
        print("  [TRA-8] supervisor -> admin: 403: PASADO")

        # ---------------- TRA-9 / TRA-10: cliente yconductor no pueden ----------------
        r9 = reset(h["cliente"], objetivos["conductor"].id)
        assert r9.status_code == 403, f"TRA-9 deberia dar 403: {r9.status_code} {r9.text}"
        r10 = reset(h["conductor"], objetivos["conductor"].id)
        assert r10.status_code == 403, f"TRA-10 deberia dar 403: {r10.status_code} {r10.text}"
        print("  [TRA-9] cliente -> 403 / [TRA-10] conductor -> 403: PASADO")

        # ---------------- TRA-11: usuario inexistente ----------------
        r11 = reset(h["admin"], 99999999)
        assert r11.status_code == 404, f"TRA-11 deberia dar 404: {r11.status_code} {r11.text}"
        print("  [TRA-11] usuario_id inexistente: 404: PASADO")

        # ---------------- TRA-12: la temporal no aparece en logs ----------------
        captura.registros.clear()
        r12 = reset(h["admin"], objetivos["contador"].id)
        assert r12.status_code == 200, f"TRA-12 deberia dar 200: {r12.status_code} {r12.text}"
        temporal = r12.json()["contrasena_temporal"]
        assert temporal not in captura.texto(), (
            "TRA-12: la contrasena temporal aparece en los logs de la aplicacion"
        )
        # request.url es un yarl.URL: hay que castearlo para inspeccionarlo.
        url_pedida = str(r12.request.url)
        assert temporal not in url_pedida, "TRA-12: la temporal viaja en la URL"
        assert "?" not in url_pedida, f"TRA-12: la URL lleva query string: {url_pedida}"
        print("  [TRA-12] la temporal no aparece en logs ni en la URL: PASADO")

        # ---------------- TRA-13: no pasa por password_reset_token ----------------
        # Delta, NO conteo global contra 0. La tabla no es una invariante de la
        # app DB: un token de recuperacion pedido desde /recuperar, o generado
        # a mano desde la pantalla de gestion, la deja con filas sin que este
        # test haya hecho nada. Lo que TRA-13 quiere verificar es que el reset
        # ADMINISTRATIVO no cree filas, y eso se mide sobre el delta: si el
        # numero de filas no cambio, este test no agrego ninguna.
        assert db.query(PasswordResetToken).count() == tokens_antes, (
            f"TRA-13: el reset asistido no debe crear filas en password_reset_token; "
            f"habia {tokens_antes} y ahora hay {db.query(PasswordResetToken).count()}"
        )
        print("  [TRA-13] password_reset_token sin delta (A3.2 no usa esa tabla): PASADO")

        # ---------------- TRA-16: la temporal cumple la politica de A1 ----------------
        sup = estado(objetivos["supervisor"].id)
        r16 = reset(h["admin"], sup.id)
        assert r16.status_code == 200, f"TRA-16 deberia dar 200: {r16.status_code} {r16.text}"
        temporal16 = r16.json()["contrasena_temporal"]
        validar_politica_contrasena(
            temporal16, cedula=sup.cedula, correo=sup.correo
        )
        assert len(temporal16) >= 8, f"TRA-16: la temporal es muy corta: {len(temporal16)}"
        print(f"  [TRA-16] la temporal ({len(temporal16)} chars) cumple la politica de A1: PASADO")

        # ---------------- TRA-14: integracion con A4 ----------------
        cond = estado(objetivos["conductor"].id)
        r14 = reset(h["admin"], cond.id)
        assert r14.status_code == 200, f"TRA-14 reset deberia dar 200: {r14.status_code} {r14.text}"
        temporal14 = r14.json()["contrasena_temporal"]

        h_bloqueado = _login(client, cond.correo, temporal14)
        rr = client.get("/api/v1/viajes", headers=h_bloqueado)
        assert rr.status_code == 403, (
            f"TRA-14: con la temporal el usuario deberia quedar bloqueado: {rr.status_code}"
        )
        assert rr.headers.get(HEADER_CAMBIO) == "true", "TRA-14: falta el header de A4"
        assert client.get("/api/v1/auth/me", headers=h_bloqueado).status_code == 200
        rc = client.post(
            "/api/v1/auth/cambio-contrasena",
            json={"contrasena_actual": temporal14, "nueva_contrasena": "NuevaClave99"},
            headers=h_bloqueado,
        )
        assert rc.status_code == 200, f"TRA-14 cambio deberia dar 200: {rc.status_code} {rc.text}"
        h_libre = {"Authorization": f"Bearer {rc.json()['access_token']}"}
        assert client.get("/api/v1/viajes", headers=h_libre).status_code == 200
        print("  [TRA-14] temporal -> 403+A4 en /viajes -> cambio -> 200: PASADO")

        # ---------------- TRA-15: integracion con A1 ----------------
        cli = estado(objetivos["cliente"].id)
        r15 = reset(h["admin"], cli.id)
        assert r15.status_code == 200, f"TRA-15 reset deberia dar 200: {r15.status_code} {r15.text}"
        temporal15 = r15.json()["contrasena_temporal"]
        h15 = _login(client, cli.correo, temporal15)
        r15b = client.post(
            "/api/v1/auth/cambio-contrasena",
            json={"contrasena_actual": temporal15, "nueva_contrasena": "corto7"},
            headers=h15,
        )
        assert r15b.status_code == 422, (
            f"TRA-15: una contrasena de 7 chars deberia dar 422: {r15b.status_code} {r15b.text}"
        )
        r15c = client.post(
            "/api/v1/auth/cambio-contrasena",
            json={"contrasena_actual": temporal15, "nueva_contrasena": "ValidaClave88"},
            headers=h15,
        )
        assert r15c.status_code == 200, (
            f"TRA-15: la temporal deberia seguir vigente tras el 422: {r15c.status_code} {r15c.text}"
        )
        print("  [TRA-15] 422 por politica y la temporal sigue vigente: PASADO")

        print("\n[TRA] OK: reset asistido por admin funcionando")
    finally:
        root.removeHandler(captura)
        root.setLevel(nivel_previo)
        try:
            correos = [_correo(pool, rol) for pool in ("e", "t") for rol in ROLES]
            for u in db.query(UsuarioModel).filter(UsuarioModel.correo.in_(correos)).all():
                db.execute(delete(RefreshToken).where(RefreshToken.usuario_id == u.id))
                db.execute(delete(PasswordResetToken).where(PasswordResetToken.usuario_id == u.id))
                db.delete(u)
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
