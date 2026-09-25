"""A4 — Enforcement del primer login (TA-FL1..TA-FL9).

Suite 15. Verifica que `debe_cambiar_contrasena=True` bloquee de verdad los
endpoints de negocio, que el usuario bloqueado pueda igual desbloquearse, y
que la excepcion de `/municipios` (que evita el loop de recarga en
/cambiar-contrasena) quede escrita en un test y no solo en un comentario.

La elecucion de la cabecera X-CELR-Requiere-Cambio se comprueba ademas en el
cuerpo de la respuesta: si el 403 llegara sin el header, el frontend no
rediria y el usuario veria una app rota.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.flota import RefreshToken, Usuario as UsuarioModel
from app.core.security import hash_password

CORREO = "primerlogin@celr.com"
PASSWORD_INICIAL = "Temporal123"
PASSWORD_NUEVA = "Cambiada456"
HEADER_CAMBIO = "x-celr-requiere-cambio"


def _preparar(db: Session, debe_cambiar: bool) -> UsuarioModel:
    u = db.query(UsuarioModel).filter(UsuarioModel.correo == CORREO).first()
    if not u:
        u = UsuarioModel(
            correo=CORREO,
            contrasena_hash=hash_password(PASSWORD_INICIAL),
            rol="admin",
            activo=True,
        )
        db.add(u)
    u.contrasena_hash = hash_password(PASSWORD_INICIAL)
    u.rol = "admin"
    u.activo = True
    u.debe_cambiar_contrasena = debe_cambiar
    db.commit()
    db.refresh(u)
    return u


def run() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    print("Iniciando prueba de enforcement del primer login (A4)...")
    client = TestClient(app)
    db = SessionLocal()
    usuario_id = None
    try:
        # ---------------- TA-FL1: negocio bloqueado + header ----------------
        u = _preparar(db, True)
        usuario_id = u.id
        db.query(RefreshToken).filter(RefreshToken.usuario_id == usuario_id).delete()
        db.commit()

        r = client.post(
            "/api/v1/auth/login", json={"correo": CORREO, "contrasena": PASSWORD_INICIAL}
        )
        assert r.status_code == 200, f"login inicial fallo: {r.status_code} {r.text}"
        token = r.json()["access_token"]
        refresh = r.json()["refresh_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r1 = client.get("/api/v1/viajes", headers=headers)
        assert r1.status_code == 403, f"TA-FL1 deberia dar 403: {r1.status_code} {r1.text}"
        assert r1.headers.get(HEADER_CAMBIO) == "true", (
            f"TA-FL1: falta el header {HEADER_CAMBIO}: {dict(r1.headers)}"
        )
        assert r1.json().get("detail"), "TA-FL1: el 403 deberia traer detalle"
        print("  [TA-FL1] GET /viajes con flag activo -> 403 + header: PASADO")

        # ---------------- TA-FL2: /auth/me exceptuado ----------------
        r2 = client.get("/api/v1/auth/me", headers=headers)
        assert r2.status_code == 200, f"TA-FL2 /auth/me deberia dar 200: {r2.status_code} {r2.text}"
        assert r2.json()["debe_cambiar_contrasena"] is True, "TA-FL2: el flag deberia seguir True"
        print("  [TA-FL2] GET /auth/me con flag activo -> 200 (exceptuado): PASADO")

        # ---------------- TA-FL6: /auth/refresh exceptuado ----------------
        r6 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r6.status_code == 200, f"TA-FL6 refresh deberia dar 200: {r6.status_code} {r6.text}"
        # La rotacion invalida el par anterior: se usa el nuevo de aqui en mas.
        token = r6.json()["access_token"]
        refresh = r6.json()["refresh_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [TA-FL6] POST /auth/refresh con flag activo -> 200 (exceptuado): PASADO")

        # ---------------- TA-FL8: transversal, no solo /viajes ----------------
        for ruta in ("/api/v1/gastos", "/api/v1/vehiculos", "/api/v1/liquidaciones/calcular/1"):
            rr = client.get(ruta, headers=headers)
            assert rr.status_code == 403, f"TA-FL8 {ruta} deberia dar 403: {rr.status_code}"
            assert rr.headers.get(HEADER_CAMBIO) == "true", f"TA-FL8 {ruta}: sin header"
        print("  [TA-FL8] gastos/vehiculos/liquidaciones con flag -> 403 (transversal): PASADO")

        # ---------------- TA-FL9: /municipios EXENTO ----------------
        r9 = client.get("/api/v1/municipios", headers=headers)
        assert r9.status_code == 200, (
            f"TA-FL9 /municipios deberia estar exento y dar 200: {r9.status_code} {r9.text}"
        )
        assert r9.headers.get(HEADER_CAMBIO) is None, "TA-FL9: municipios no debe mandar el header"
        # Si municipalitiesprotected, MunicipiosProvider (montado por encima de
        # las rutas) dispararia un 403 en /cambiar-contrasena y el interceptor
        # recargaria la pagina en loop.
        print("  [TA-FL9] GET /municipios con flag activo -> 200 (exento, sin header): PASADO")

        # ---------------- TA-FL3: cambio de contrasena ----------------
        r3 = client.post(
            "/api/v1/auth/cambio-contrasena",
            json={"contrasena_actual": PASSWORD_INICIAL, "nueva_contrasena": PASSWORD_NUEVA},
            headers=headers,
        )
        assert r3.status_code == 200, f"TA-FL3 deberia dar 200: {r3.status_code} {r3.text}"
        db.expire_all()
        u = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
        assert u.debe_cambiar_contrasena is False, "TA-FL3: el flag debio limpiarse"
        token = r3.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [TA-FL3] POST /auth/cambio-contrasena -> 200 y flag -> False: PASADO")

        # ---------------- TA-FL4: desbloqueado ----------------
        r4 = client.get("/api/v1/viajes", headers=headers)
        assert r4.status_code == 200, f"TA-FL4 tras el cambio deberia dar 200: {r4.status_code}"
        assert r4.headers.get(HEADER_CAMBIO) is None, "TA-FL4: no debe mandar el header ya"
        print("  [TA-FL4] GET /viajes tras el cambio -> 200 (desbloqueado): PASADO")

        # ---------------- TA-FL7: /auth/logout exceptuado (con flag activo) ----------------
        db.expire_all()
        u = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
        u.debe_cambiar_contrasena = True
        db.commit()
        r7 = client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
        assert r7.status_code == 204, f"TA-FL7 logout deberia dar 204: {r7.status_code} {r7.text}"
        print("  [TA-FL7] POST /auth/logout con flag activo -> 204 (exceptuado): PASADO")

        # ---------------- TA-FL5: sin regresion para usuarios normales ----------------
        u.debe_cambiar_contrasena = False
        u.contrasena_hash = hash_password(PASSWORD_INICIAL)
        db.commit()
        r5 = client.post(
            "/api/v1/auth/login", json={"correo": CORREO, "contrasena": PASSWORD_INICIAL}
        )
        assert r5.status_code == 200, f"TA-FL5 login fallo: {r5.status_code} {r5.text}"
        h5 = {"Authorization": f"Bearer {r5.json()['access_token']}"}
        for ruta in ("/api/v1/viajes", "/api/v1/gastos", "/api/v1/vehiculos", "/api/v1/municipios"):
            rr = client.get(ruta, headers=h5)
            assert rr.status_code == 200, f"TA-FL5 {ruta} deberia dar 200: {rr.status_code}"
        assert client.get("/api/v1/auth/me", headers=h5).status_code == 200
        print("  [TA-FL5] usuario normal -> viajes/gastos/vehiculos/municipios/me = 200: PASADO")

        print("\n[TA-FL] OK: enforcement del primer login funcionando")
    finally:
        try:
            if usuario_id is not None:
                db.execute(delete(RefreshToken).where(RefreshToken.usuario_id == usuario_id))
                u = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
                if u is not None:
                    db.delete(u)
            # Barrido defensivo por correo (D-cleanup: rastrear por ID, pero si
            # una corrida previa fallo antes de fijar el id, esto lo recupera).
            for huerfano in db.query(UsuarioModel).filter(
                UsuarioModel.correo == CORREO
            ).all():
                db.execute(
                    delete(RefreshToken).where(RefreshToken.usuario_id == huerfano.id)
                )
                db.delete(huerfano)
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
