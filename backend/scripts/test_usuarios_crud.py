"""A5.1 — CRUD de usuarios con matriz de concesion (TUC-1..TUC-18).

Suite 20. Verifica que `ROLES_OBJETIVO_POR_EJECUTOR` (A3.2) gobierne las
CUATRO operaciones que la consumen: resetear (A3.2), degradar (A5.2), crear
y listar (esta). Una sola matriz, un solo lugar con la verdad.

Sobre el listado: sigue la convencion del repo (skip/limit + header
X-Total-Count, que es lo que lee conTotal() en el frontend), no un
{data, total} en el body. Con el body, la UI mostraria 0 elementos con el
array lleno.
"""
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.auditoria import AuditoriaEvento
from app.models.flota import (
    Conductor as ConductorModel,
    PasswordResetToken,
    RefreshToken,
    Usuario as UsuarioModel,
)
from app.core.security import hash_password, verify_password

PASSWORD_INICIAL = "Temporal123"
SUFIJO = os.environ.get("CELR_TEST_SUFFIX", "a51")


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


def _correo(etiqueta: str) -> str:
    return f"a51-{etiqueta}-{SUFIJO}@celr.com"


def _cedula(n: int) -> str:
    return f"8{SUFIJO[:1]}{n:07d}"


def run() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    print("Iniciando prueba de CRUD de usuarios (A5.1)...")
    client = TestClient(app)
    captura = CapturaLogs()
    root = logging.getLogger()
    nivel_previo = root.level
    root.addHandler(captura)
    root.setLevel(logging.DEBUG)
    db = SessionLocal()
    marca = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        def crear_directo(etiqueta: str, rol: str, conductor_id=None) -> UsuarioModel:
            correo = _correo(etiqueta)
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
            u.conductor_id = conductor_id
            db.commit()
            db.refresh(u)
            return u

        admin = crear_directo("admin", "admin")
        operador = crear_directo("operador", "operador")
        contador = crear_directo("contador", "contador")
        supervisor = crear_directo("supervisor", "supervisor")
        cliente = crear_directo("cliente", "cliente")
        conductor = crear_directo("conductor", "conductor")
        # El seed tambien es admin: el listado debe reflejarlo.
        semilla = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").one()

        def sesion(usuario: UsuarioModel, contrasena: str = PASSWORD_INICIAL) -> dict:
            r = client.post(
                "/api/v1/auth/login",
                json={"identificador": usuario.correo, "contrasena": contrasena},
            )
            assert r.status_code == 200, f"login de {usuario.correo} fallo: {r.status_code} {r.text}"
            return {"Authorization": f"Bearer {r.json()['access_token']}"}

        h_admin = sesion(admin)
        h_operador = sesion(operador)
        h_cliente = sesion(cliente)
        h_conductor = sesion(conductor)

        def listado(headers):
            return client.get("/api/v1/usuarios", headers=headers)

        # ---------------- TUC-1: admin ve todos ----------------
        r1 = listado(h_admin)
        assert r1.status_code == 200, f"TUC-1 deberia dar 200: {r1.status_code} {r1.text}"
        cuerpo1 = r1.json()
        ids1 = {u["id"] for u in cuerpo1}
        for u in (semilla, operador, contador, supervisor, cliente, conductor, admin):
            assert u.id in ids1, f"TUC-1: admin no ve el usuario {u.id}"
        # Convencion del repo: el total va en el header, no en el body.
        assert r1.headers.get("X-Total-Count") is not None, (
            "TUC-1: falta el header X-Total-Count (conTotal() del frontend lo lee)"
        )
        assert int(r1.headers["X-Total-Count"]) == len(cuerpo1), (
            f"TUC-1: total={r1.headers['X-Total-Count']} pero llegaron {len(cuerpo1)}"
        )
        print(f"  [TUC-1] admin lista {len(cuerpo1)} usuarios + header X-Total-Count: PASADO")

        # ---------------- TUC-2: operador ve conductor/cliente + si mismo -------
        r2 = listado(h_operador)
        assert r2.status_code == 200, f"TUC-2 deberia dar 200: {r2.status_code}"
        ids2 = {u["id"] for u in r2.json()}
        assert operador.id in ids2, "TUC-2: el ejecutor deberia verse a si mismo"
        assert cliente.id in ids2 and conductor.id in ids2, "TUC-2: deberia ver conductor y cliente"
        for oculto in (semilla, admin, contador, supervisor):
            assert oculto.id not in ids2, f"TUC-2: el operador NO deberia ver al usuario {oculto.id}"
        print("  [TUC-2] operador ve conductor+cliente+si mismo, no admins: PASADO")

        # ---------------- TUC-3: conductor no lista ----------------
        r3 = listado(h_conductor)
        assert r3.status_code == 403, f"TUC-3 deberia dar 403: {r3.status_code} {r3.text}"
        assert listado(h_cliente).status_code == 403, "TUC-3: cliente tambien deberia dar 403"
        print("  [TUC-3] conductor y cliente al listar -> 403: PASADO")

        # Filtros
        r_act = client.get("/api/v1/usuarios?activo=true", headers=h_admin)
        assert all(u["activo"] for u in r_act.json()), "TUC-2: filtro activo=true"
        r_rol = client.get("/api/v1/usuarios?rol=cliente", headers=h_admin)
        assert {u["rol"] for u in r_rol.json()} == {"cliente"}, "TUC-2: filtro por rol"
        r_no_permitido = client.get("/api/v1/usuarios?rol=admin", headers=h_operador)
        assert r_no_permitido.status_code == 403, (
            f"TUC-2: filtrar por un rol fuera de la matriz deberia dar 403: {r_no_permitido.status_code}"
        )
        r_limite = client.get("/api/v1/usuarios?limit=9999", headers=h_admin)
        assert r_limite.status_code == 422, f"TUC-2: limit fuera de rango deberia dar 422: {r_limite.status_code}"
        print("  [TUC-2] filtros activo/rol, rol no permitido 403, limit 422: PASADO")

        # ---------------- TUC-4: admin crea operador ----------------
        r4 = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={"cedula": _cedula(4), "correo": _correo("nuevo-op"), "rol": "operador"},
        )
        assert r4.status_code == 201, f"TUC-4 deberia dar 201: {r4.status_code} {r4.text}"
        creado = r4.json()
        assert creado["contrasena_temporal"], "TUC-4: sin contrasena_temporal"
        assert creado["debe_cambiar_contrasena"] is True, "TUC-4: el flag deberia ir en True"
        nuevo_id = creado["usuario_id"]
        temporal = creado["contrasena_temporal"]
        db.expire_all()
        fila = db.query(UsuarioModel).filter(UsuarioModel.id == nuevo_id).one()
        assert fila.debe_cambiar_contrasena is True, "TUC-4: el flag no quedo seteado"
        assert verify_password(temporal, fila.contrasena_hash), "TUC-4: la temporal no es la guardada"
        assert fila.contrasena_hash != temporal, "TUC-4: la contrasena esta en claro"
        ev = [e for e in db.query(AuditoriaEvento).filter(
            AuditoriaEvento.creado_en >= marca, AuditoriaEvento.evento == "usuario_creado"
        ).all()]
        assert ev, "TUC-4: no se audito usuario_creado"
        assert ev[-1].usuario_actor_id == admin.id, "TUC-4: actor incorrecto"
        assert temporal not in json_dumps(ev), "TUC-4: la temporal se filtro en la auditoria"
        print("  [TUC-4] admin crea operador -> 201 + temporal + flag + auditoria: PASADO")

        # ---------------- TUC-5: operador crea admin ----------------
        r5 = client.post(
            "/api/v1/usuarios",
            headers=h_operador,
            json={"cedula": _cedula(5), "correo": _correo("nuevo-admin"), "rol": "admin"},
        )
        assert r5.status_code == 403, f"TUC-5 deberia dar 403: {r5.status_code} {r5.text}"
        print("  [TUC-5] operador intenta crear admin -> 403: PASADO")

        # ---------------- TUC-6: operador crea conductor ----------------
        r6 = client.post(
            "/api/v1/usuarios",
            headers=h_operador,
            json={"cedula": _cedula(6), "correo": _correo("nuevo-cond"), "rol": "conductor"},
        )
        assert r6.status_code == 201, f"TUC-6 deberia dar 201: {r6.status_code} {r6.text}"
        print("  [TUC-6] operador crea conductor -> 201: PASADO")

        # ---------------- TUC-7: cedula duplicada -> 409 ----------------
        db.expire_all()
        existente = db.query(UsuarioModel).filter(UsuarioModel.cedula == _cedula(6)).one()
        r7 = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={"cedula": existente.cedula, "correo": _correo("dup-ced"), "rol": "conductor"},
        )
        assert r7.status_code == 409, f"TUC-7 deberia dar 409: {r7.status_code} {r7.text}"
        print("  [TUC-7] cedula duplicada -> 409: PASADO")

        # ---------------- TUC-8: correo duplicado (case-insensitive) ----------------
        db.expire_all()
        con_correo = db.query(UsuarioModel).filter(UsuarioModel.correo == _correo("nuevo-cond")).one()
        r8 = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={
                "cedula": _cedula(8),
                "correo": con_correo.correo.upper(),
                "rol": "conductor",
            },
        )
        assert r8.status_code == 409, f"TUC-8 deberia dar 409: {r8.status_code} {r8.text}"
        print("  [TUC-8] correo duplicado en mayusculas -> 409: PASADO")

        # ---------------- TUC-9: conductor_id con cedula que no coincide ----------------
        cond = db.query(ConductorModel).filter(ConductorModel.id == 2).one()
        r9 = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={
                "cedula": _cedula(99),
                "correo": _correo("mal-vinculo"),
                "rol": "conductor",
                "conductor_id": cond.id,
            },
        )
        assert r9.status_code == 422, f"TUC-9 deberia dar 422: {r9.status_code} {r9.text}"
        print("  [TUC-9] cedula que no coincide con el conductor -> 422: PASADO")

        # ---------------- TUC-10: conductor ya vinculado -> 409 ----------------
        # Primero se crea una cuenta bien vinculada, luego se intenta la segunda.
        ok10 = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={
                "cedula": cond.cedula,
                "correo": _correo("vinculado"),
                "rol": "conductor",
                "conductor_id": cond.id,
            },
        )
        assert ok10.status_code == 201, f"TUC-10 setup deberia dar 201: {ok10.status_code} {ok10.text}"
        r10 = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={
                "cedula": cond.cedula + "9",
                "correo": _correo("vinculado-2"),
                "rol": "conductor",
                "conductor_id": cond.id,
            },
        )
        assert r10.status_code == 422, (
            f"TUC-10: la cedula no coincide con el conductor, asi que falla antes por 422: {r10.status_code}"
        )
        # Para el 409 hay que reutilizar la MISMA cedula del conductor, que es
        # lo unico que pasa la coherencia: ahi choca el vinculo unico.
        r10b = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={
                "cedula": cond.cedula,
                "correo": _correo("vinculado-3"),
                "rol": "conductor",
                "conductor_id": cond.id,
            },
        )
        assert r10b.status_code == 409, (
            f"TUC-10: conductor ya vinculado deberia dar 409: {r10b.status_code} {r10b.text}"
        )
        print("  [TUC-10] conductor ya vinculado -> 422 (cedula) / 409 (vinculo unico): PASADO")

        # ---------------- TUC-11: PUT edita correo ----------------
        db.expire_all()
        objetivo = db.query(UsuarioModel).filter(UsuarioModel.id == nuevo_id).one()
        nuevo_correo = _correo("editado")
        r11 = client.put(
            f"/api/v1/usuarios/{nuevo_id}",
            headers=h_admin,
            json={"correo": nuevo_correo},
        )
        assert r11.status_code == 200, f"TUC-11 deberia dar 200: {r11.status_code} {r11.text}"
        assert r11.json()["correo"] == nuevo_correo, f"TUC-11: correo={r11.json()['correo']}"
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == nuevo_id
        ).one().correo == nuevo_correo, "TUC-11: el correo no persistio"
        ev = [e for e in db.query(AuditoriaEvento).filter(
            AuditoriaEvento.creado_en >= marca, AuditoriaEvento.evento == "usuario_editado"
        ).all()]
        assert ev, "TUC-11: no se audito usuario_editado"
        assert ev[-1].detalle.get("campos") == ["correo"], f"TUC-11: detalle={ev[-1].detalle}"
        assert nuevo_correo not in json_dumps(ev), "TUC-11: el valor del campo se filtro en la auditoria"
        print("  [TUC-11] PUT edita correo -> 200 + persistido + auditoria con nombres de campo: PASADO")

        # ---------------- TUC-12: PUT con rol -> 422 (no se ignora) ----------------
        r12 = client.put(
            f"/api/v1/usuarios/{nuevo_id}",
            headers=h_admin,
            json={"rol": "admin"},
        )
        assert r12.status_code == 422, (
            f"TUC-12: mandar rol por PUT deberia dar 422, no ignorarlo: {r12.status_code} {r12.text}"
        )
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == nuevo_id
        ).one().rol == "operador", "TUC-12: el rol cambio pese al 422"
        print("  [TUC-12] PUT con rol -> 422 explicito y el rol NO cambia: PASADO")

        # ---------------- TUC-13: PUT que rompe coherencia con conductor ----------------
        db.expire_all()
        vinculado = db.query(UsuarioModel).filter(
            UsuarioModel.correo == _correo("vinculado")
        ).one()
        r13 = client.put(
            f"/api/v1/usuarios/{vinculado.id}",
            headers=h_admin,
            json={"cedula": _cedula(13)},
        )
        assert r13.status_code == 422, f"TUC-13 deberia dar 422: {r13.status_code} {r13.text}"
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == vinculado.id
        ).one().cedula == vinculado.cedula, "TUC-13: la cedula cambio igual"
        print("  [TUC-13] PUT que rompe la coherencia con conductor -> 422: PASADO")

        # ---------------- TUC-14: operador edita a un admin -> 403 ----------------
        r14 = client.put(
            f"/api/v1/usuarios/{admin.id}",
            headers=h_operador,
            json={"correo": _correo("intento")},
        )
        assert r14.status_code == 403, f"TUC-14 deberia dar 403: {r14.status_code} {r14.text}"
        print("  [TUC-14] operador intenta editar a un admin -> 403: PASADO")

        # ---------------- TUC-15: activar desactivado ----------------
        db.expire_all()
        a_desactivar = db.query(UsuarioModel).filter(UsuarioModel.id == nuevo_id).one()
        a_desactivar.activo = False
        db.commit()
        r15 = client.post(f"/api/v1/usuarios/{nuevo_id}/activar", headers=h_admin)
        assert r15.status_code == 200, f"TUC-15 deberia dar 200: {r15.status_code} {r15.text}"
        assert r15.json()["activo"] is True, "TUC-15: activo deberia ser True"
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == nuevo_id
        ).one().activo is True, "TUC-15: no quedo activo"
        ev = [e for e in db.query(AuditoriaEvento).filter(
            AuditoriaEvento.creado_en >= marca, AuditoriaEvento.evento == "usuario_activado"
        ).all()]
        assert ev, "TUC-15: no se audito usuario_activado"
        print("  [TUC-15] activar cuenta desactivada -> 200 + auditoria: PASADO")

        # ---------------- TUC-16: activar ya activo -> 409 ----------------
        r16 = client.post(f"/api/v1/usuarios/{nuevo_id}/activar", headers=h_admin)
        assert r16.status_code == 409, f"TUC-16 deberia dar 409: {r16.status_code} {r16.text}"
        # Solo admin puede activar
        r16b = client.post(f"/api/v1/usuarios/{nuevo_id}/activar", headers=h_operador)
        assert r16b.status_code == 403, f"TUC-16: activar deberia ser solo admin: {r16b.status_code}"
        print("  [TUC-16] activar ya activo -> 409 / solo admin puede -> 403: PASADO")

        # ---------------- TUC-17: integracion con A4 ----------------
        db.expire_all()
        para_a4 = db.query(UsuarioModel).filter(
            UsuarioModel.correo == _correo("nuevo-cond")
        ).one()
        r17a = client.post(
            f"/api/v1/usuarios/{para_a4.id}/reset-password", headers=h_admin
        )
        assert r17a.status_code == 200, f"TUC-17 reset deberia dar 200: {r17a.status_code} {r17a.text}"
        temp17 = r17a.json()["contrasena_temporal"]
        h17 = sesion(para_a4, temp17)
        r17b = client.get("/api/v1/viajes", headers=h17)
        assert r17b.status_code == 403, f"TUC-17 deberia dar 403: {r17b.status_code}"
        assert r17b.headers.get("X-CELR-Requiere-Cambio") == "true", "TUC-17: falta el header de A4"
        r17c = client.post(
            "/api/v1/auth/cambio-contrasena",
            json={"contrasena_actual": temp17, "nueva_contrasena": "CambioReal123"},
            headers=h17,
        )
        assert r17c.status_code == 200, f"TUC-17 cambio deberia dar 200: {r17c.status_code} {r17c.text}"
        h17b = {"Authorization": f"Bearer {r17c.json()['access_token']}"}
        assert client.get("/api/v1/viajes", headers=h17b).status_code == 200, "TUC-17: sigue bloqueado"
        print("  [TUC-17] creada -> reset -> 403+A4 -> cambio -> 200: PASADO")

        # ---------------- TUC-18: la temporal no se filtra ----------------
        captura.registros.clear()
        r18 = client.post(
            "/api/v1/usuarios",
            headers=h_admin,
            json={"cedula": _cedula(18), "correo": _correo("nofiltra"), "rol": "conductor"},
        )
        assert r18.status_code == 201, f"TUC-18 deberia dar 201: {r18.status_code} {r18.text}"
        temp18 = r18.json()["contrasena_temporal"]
        assert temp18 not in captura.texto(), "TUC-18: la temporal aparece en los logs"
        assert temp18 not in str(r18.request.url), "TUC-18: la temporal viaja en la URL"
        # Y no pasa por password_reset_token: el alta genera credencial, no token.
        assert db.query(PasswordResetToken).filter(
            PasswordResetToken.usuario_id == r18.json()["usuario_id"]
        ).count() == 0, "TUC-18: el alta no debe crear filas en password_reset_token"
        print("  [TUC-18] la temporal no aparece en logs, URL ni password_reset_token: PASADO")

        print("\n[TUC] OK: CRUD de usuarios con matriz de concesion funcionando")
    finally:
        root.removeHandler(captura)
        root.setLevel(nivel_previo)
        try:
            correos = [
                _correo(e)
                for e in (
                    "admin", "operador", "contador", "supervisor", "cliente", "conductor",
                    "nuevo-op", "nuevo-cond", "dup-ced", "mal-vinco", "mal-vinculo",
                    "vinculado", "vinculado-2", "vinculado-3", "editado", "intento",
                    "nofiltra", "nuevo-admin",
                )
            ]
            for u in db.query(UsuarioModel).filter(UsuarioModel.correo.in_(correos)).all():
                db.execute(delete(RefreshToken).where(RefreshToken.usuario_id == u.id))
                db.execute(delete(PasswordResetToken).where(PasswordResetToken.usuario_id == u.id))
                db.delete(u)
            db.flush()
            db.execute(delete(AuditoriaEvento).where(AuditoriaEvento.creado_en >= marca))
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"\n[ERROR EN LIMPIEZA]: {e}")
            raise
        finally:
            db.close()


def json_dumps(filas) -> str:
    import json

    return json.dumps([f.detalle for f in filas], default=str)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        import traceback

        print(f"\n[ERROR EN TESTS]: {exc}")
        traceback.print_exc()
        raise
