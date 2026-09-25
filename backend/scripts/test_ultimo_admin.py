"""A5.2 — Proteccion del ultimo admin + break-glass CLI (TUA-1..TUA-12).

Suite 19. El CLI se prueba por SUBPROCESS y no importado: una herramienta de
emergencia que solo funciona importada no es una herramienta de emergencia.
Asi se verifica tambien el `sys.exit(main())` y el codigo de salida real.

Sobre `es_ultimo_admin_activo`: cuenta TODOS los admins activos, incluido el
semilla test@celr.com (id=1). Por eso el test lo desactiva primero mediante el
PROPIO endpoint — es la unica forma de que un admin temporal sea realmente el
ultimo, y de paso ejercita el endpoint con un caso real. El setup restaura
id=1 antes de empezar, asi que una corrida fallida previa se auto-repara.

NORMATIVA — los conteos globales de la app DB no son invariante. La BD de
desarrollo tiene datos reales: cuentas creadas a mano, tokens de recuperacion
pendientes. Un test que asume "hay exactamente N admins" o "la tabla X esta
vacia" pasa en una BD limpia y falla con el uso diario, que es peor: el gate
se pone rojo sin que nadie haya tocado el codigo. Por eso aca NO se afirma un
total global: TUA-2 neutraliza los admins ajenos al test (snapshot ->
desactivar -> afirmar -> restaurar en el finally) para llevar el helper a un
escenario controlado de un solo admin, y restaura los reales al terminar.
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.auditoria import AuditoriaEvento
from app.models.flota import PasswordResetToken, RefreshToken, Usuario as UsuarioModel
from app.core.security import hash_password, validar_politica_contrasena

PASSWORD_INICIAL = "Inicial123"
SUFIJO = os.environ.get("CELR_TEST_SUFFIX", "a52")
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLI = os.path.join(os.path.dirname(__file__), "admin_reset.py")
PYTHON = os.path.join(BACKEND, "venv", "Scripts", "python.exe")


def _correo(etiqueta: str) -> str:
    return f"a52-{etiqueta}-{SUFIJO}@celr.com"


def run_cli(*args) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("DATABASE_URL", "postgresql://postgres:admin@localhost:5433/celr_v6_db")
    return subprocess.run(
        [PYTHON, CLI, *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    print("Iniciando prueba de proteccion del ultimo admin (A5.2)...")
    client = TestClient(app)
    db = SessionLocal()
    marca = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        def preparar(etiqueta: str, rol: str, cedula: str) -> UsuarioModel:
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
            u.cedula = cedula
            db.commit()
            db.refresh(u)
            return u

        # Auto-reparacion: si una corrida previa fallo a mitad, el setup deja
        # el estado consistente antes de empezar.
        semilla = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").one()
        semilla.activo = True
        # TUA-2 neutraliza admins ajenos y los restaura en su finally. Si un
        # proceso muere sin ejecutar ese finally (Ctrl+C), el admin real
        # quedaria inactivo. Se repara aqui: un admin con cedula NO sintetica
        # (las de este test empiezan con 9) no es del test, asi que se
        # reactiva. Los admins del propio test se borran en el teardown.
        reparados = [
            u.id
            for u in db.query(UsuarioModel)
            .filter(UsuarioModel.rol == "admin", UsuarioModel.activo.is_(False))
            .all()
            if not (u.cedula or "").startswith("9")
        ]
        if reparados:
            db.execute(
                UsuarioModel.__table__.update()
                .where(UsuarioModel.__table__.c.id.in_(reparados))
                .values(activo=True)
            )
            print(f"  [setup] admin(s) real(es) reactivados: {reparados}")
        db.commit()

        admin_a = preparar("admin-a", "admin", "90000001")
        admin_b = preparar("admin-b", "admin", "90000002")
        operador = preparar("operador", "operador", "90000003")
        meta = preparar("meta", "conductor", "90000004")

        h_a = {"Authorization": "Bearer " + client.post(
            "/api/v1/auth/login",
            json={"identificador": admin_a.correo, "contrasena": PASSWORD_INICIAL},
        ).json()["access_token"]}
        h_op = {"Authorization": "Bearer " + client.post(
            "/api/v1/auth/login",
            json={"identificador": operador.correo, "contrasena": PASSWORD_INICIAL},
        ).json()["access_token"]}

        def eventos():
            db.expire_all()
            return (
                db.query(AuditoriaEvento)
                .filter(AuditoriaEvento.creado_en >= marca)
                .order_by(AuditoriaEvento.id)
                .all()
            )

        def desactivar(headers, objetivo_id, confirmacion, motivo=None):
            return client.post(
                f"/api/v1/usuarios/{objetivo_id}/desactivar",
                headers=headers,
                json={"confirmacion": confirmacion, "motivo": motivo},
            )

        # --------- TUA-8: operador no puede desactivar (antes de tocar admins) -----
        r8 = desactivar(h_op, meta.id, meta.correo)
        assert r8.status_code == 403, f"TUA-8 deberia dar 403: {r8.status_code} {r8.text}"
        print("  [TUA-8] operador intenta desactivar -> 403: PASADO")

        # --------- Colocar el escenario: desactivar al admin semilla -------------
        # Necesario porque el contador de "ultimo admin" incluye al admin del
        # seed. Se hace por el propio endpoint, no por UPDATE directo.
        r_seed = desactivar(h_a, semilla.id, semilla.correo, motivo="setup TUA")
        assert r_seed.status_code == 200, f"setup: no se pudo desactivar la semilla: {r_seed.status_code} {r_seed.text}"

        # --------- TUA-1: desactivar un admin que NO es el ultimo ---------------
        r1 = desactivar(h_a, admin_b.id, admin_b.correo, motivo="TUA-1")
        assert r1.status_code == 200, f"TUA-1 deberia dar 200: {r1.status_code} {r1.text}"
        cuerpo = r1.json()
        assert cuerpo["activo"] is False, "TUA-1: activo deberia ser False"
        assert cuerpo["era_ultimo_admin"] is False, (
            "TUA-1: admin_a sigue activo, asi que no era el ultimo"
        )
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == admin_b.id
        ).one().activo is False, "TUA-1: la cuenta quedo activa"
        ev = [e for e in eventos() if e.evento == "usuario_desactivado"]
        assert ev, "TUA-1: no se registro usuario_desactivado"
        assert ev[-1].detalle.get("motivo") == "TUA-1", f"TUA-1: detalle={ev[-1].detalle}"
        assert ev[-1].detalle.get("era_ultimo_admin") is False, "TUA-1: flag en detalle"
        print("  [TUA-1] desactivar admin no-ultimo -> 200 + auditoria: PASADO")

        # --------- TUA-2: la invariante real — nunca queda CERO admins ----------
        # Por diseno, era_ultimo_admin=True NO es alcanzable por la API: el
        # ejecutor es siempre un admin activo, asi que si el objetivo fuera el
        # ultimo, el ejecutor seria "otro" admin activo y quedaria al menos
        # uno. Sumado al bloqueo de auto-accion, esta API no puede dejar el
        # sistema sin administracion de cuentas. Lo que se verifica aca es esa
        # garantia, no que la bandera gire.
        from app.services.usuarios import contar_admins_activos, es_ultimo_admin_activo

        r2 = desactivar(h_a, admin_b.id, admin_b.cedula, motivo="TUA-2")
        assert r2.status_code == 409, f"TUA-2 setup: admin_b ya estaba inactivo: {r2.status_code}"
        db.expire_all()
        admin_b.activo = True
        db.commit()

        # Desactivar a todos los admins posibles desde la API.
        for objetivo in (admin_b,):
            r = desactivar(h_a, objetivo.id, objetivo.cedula, motivo="TUA-2 barrido")
            assert r.status_code == 200, f"TUA-2: {r.status_code} {r.text}"
        restantes = contar_admins_activos(db)
        assert restantes >= 1, (
            f"TUA-2: la API dejo {restantes} admins activos; el sistema quedaria "
            "sin gestion de cuentas"
        )
        # Y el ejecutor mismo no puede desactivarse (la unica via que falta).
        r_self = desactivar(h_a, admin_a.id, admin_a.cedula)
        assert r_self.status_code == 403, f"TUA-2: auto-desactivacion deberia dar 403: {r_self.status_code}"
        assert contar_admins_activos(db) >= 1, "TUA-2: sigue habiendo admins tras el barrido"
        print(
            f"  [TUA-2] invariante: tras desactivar a los demas quedan "
            f"{restantes} admins activos y la auto-accion esta bloqueada: PASADO"
        )

        # El helper SI alcanza el caso ultimo: se comprueba a nivel de servicio,
        # construyendo el estado directamente (que es como se llegaria si
        # mañana otro rol ganara el permiso).
        #
        # `es_ultimo_admin_activo` cuenta admins activos de TODA la base, asi
        # que un admin real creado a mano (p. ej. desde la propia pantalla de
        # gestion) hace que el helper responda False aunque el escenario del
        # test sea el correcto. No se puede afirmar un total global. Se
        # neutralizan los admins ajenos —los que este test no creo— para
        # llevar la base a "un solo admin activo", que es la precondicion que
        # TUA-2 quiere verificar. Se guardan sus ids y se restauran en el
        # finally: los datos reales del usuario no se borran ni se pierden.
        ajenos = [
            u.id
            for u in db.query(UsuarioModel)
            .filter(UsuarioModel.rol == "admin", UsuarioModel.activo.is_(True))
            .all()
            if u.id not in (meta.id, admin_a.id)
        ]
        if ajenos:
            db.execute(
                UsuarioModel.__table__.update()
                .where(UsuarioModel.__table__.c.id.in_(ajenos))
                .values(activo=False)
            )
            db.commit()
        try:
            # Escenario controlado: meta pasa a ser admin y admin_a (el otro
            # admin del test) queda inactivo, de modo que meta es el UNICO
            # admin activo una vez neutralizados los ajenos.
            db.expire_all()
            meta.rol = "admin"
            admin_a.activo = False
            db.commit()
            db.expire_all()
            assert contar_admins_activos(db) == 1, (
                f"TUA-2: se esperaba 1 admin activo y hay "
                f"{contar_admins_activos(db)}; la neutralizacion no alcanzo"
            )
            assert es_ultimo_admin_activo(db, meta.id) is True, (
                "TUA-2: es_ultimo_admin_activo deberia dar True con un unico admin activo"
            )
        finally:
            db.expire_all()
            meta.rol = "conductor"
            admin_a.activo = True
            db.commit()
            if ajenos:
                db.execute(
                    UsuarioModel.__table__.update()
                    .where(UsuarioModel.__table__.c.id.in_(ajenos))
                    .values(activo=True)
                )
                db.commit()
        assert es_ultimo_admin_activo(db, operador.id) is False, (
            "TUA-2: un no-admin no es 'ultimo admin'"
        )
        assert es_ultimo_admin_activo(db, 99999999) is False, (
            "TUA-2: un id inexistente no es 'ultimo admin'"
        )
        # meta.rol y admin_a.activo los restaura el finally del bloque de
        # arriba: dejar el estado en un solo lugar evita que una excepcion a
        # mitad deje a meta como admin o a admin_a inactivo.
        print("  [TUA-2] es_ultimo_admin_activo: True/False/no-existente correctos: PASADO")

        # --------- TUA-3: confirmacion incorrecta -> 422, sin cambios ------------
        r3 = desactivar(h_a, meta.id, "no-es-su-identificador")
        assert r3.status_code == 422, f"TUA-3 deberia dar 422: {r3.status_code} {r3.text}"
        assert "Nada se ha modificado" in r3.json().get("detail", ""), (
            f"TUA-3: el mensaje deberia decir que nada cambio: {r3.json()}"
        )
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == meta.id
        ).one().activo is True, "TUA-3: la cuenta se desactivo igual"
        print("  [TUA-3] confirmacion incorrecta -> 422 y sin cambios: PASADO")

        # --------- TUA-4: sin confirmacion -> 422 --------------------------------
        r4 = client.post(
            f"/api/v1/usuarios/{meta.id}/desactivar", headers=h_a, json={"motivo": "x"}
        )
        assert r4.status_code == 422, f"TUA-4 deberia dar 422: {r4.status_code} {r4.text}"
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == meta.id
        ).one().activo is True, "TUA-4: la cuenta se desactivo igual"
        print("  [TUA-4] sin confirmacion -> 422: PASADO")

        # --------- TUA-5: auto-desactivacion -> 403 ------------------------------
        r5 = desactivar(h_a, admin_a.id, admin_a.correo)
        assert r5.status_code == 403, f"TUA-5 deberia dar 403: {r5.status_code} {r5.text}"
        print("  [TUA-5] auto-desactivacion -> 403: PASADO")

        # --------- TUA-6: desactivar uno ya inactivo -> 409 -----------------------
        r6 = desactivar(h_a, admin_b.id, admin_b.correo)
        assert r6.status_code == 409, f"TUA-6 deberia dar 409: {r6.status_code} {r6.text}"
        print("  [TUA-6] desactivar ya inactivo -> 409: PASADO")

        # --------- TUA-7: degradar rol -----------------------------------------
        def degradar(headers, objetivo_id, confirmacion, nuevo_rol, motivo=None):
            return client.post(
                f"/api/v1/usuarios/{objetivo_id}/degradar",
                headers=headers,
                json={"confirmacion": confirmacion, "nuevo_rol": nuevo_rol, "motivo": motivo},
            )

        # Degradar al otro admin. era_ultimo_admin es False por la invariante de
        # TUA-2: el ejecutor (admin_a) sigue activo, asi que admin_b nunca es el
        # ultimo. Lo que importa aca es que el rol cambie y quede auditado.
        r7 = degradar(h_a, admin_b.id, admin_b.correo, "operador", motivo="TUA-7")
        assert r7.status_code == 200, f"TUA-7 deberia dar 200: {r7.status_code} {r7.text}"
        assert r7.json()["rol"] == "operador", f"TUA-7: rol={r7.json()['rol']}"
        db.expire_all()
        fila = db.query(UsuarioModel).filter(UsuarioModel.id == admin_b.id).one()
        assert fila.rol == "operador", f"TUA-7: el rol no cambio: {fila.rol}"
        ev = [e for e in eventos() if e.evento == "usuario_degradado"]
        assert ev, "TUA-7: no se registro usuario_degradado"
        assert ev[-1].detalle.get("rol_anterior") == "admin", f"TUA-7: detalle={ev[-1].detalle}"
        assert ev[-1].detalle.get("rol_nuevo") == "operador", f"TUA-7: detalle={ev[-1].detalle}"
        assert ev[-1].usuario_actor_id == admin_a.id, "TUA-7: actor incorrecto"
        assert ev[-1].usuario_objetivo_id == admin_b.id, "TUA-7: objetivo incorrecto"
        print("  [TUA-7] degradar admin -> 200 + rol_anterior/rol_nuevo en auditoria: PASADO")

        # Auto-degradacion: mismo bloqueo que la auto-desactivacion.
        r7self = degradar(h_a, admin_a.id, admin_a.cedula, "conductor")
        assert r7self.status_code == 403, (
            f"TUA-7: la auto-degradacion deberia dar 403: {r7self.status_code} {r7self.text}"
        )
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == admin_a.id
        ).one().rol == "admin", "TUA-7: se degrado a si mismo"
        print("  [TUA-7] auto-degradacion -> 403: PASADO")

        # Rol invalido y rol ya vigente
        r_inv = degradar(h_a, meta.id, meta.correo, "superusuario")
        assert r_inv.status_code == 422, f"rol desconocido deberia dar 422: {r_inv.status_code}"
        r_igual = degradar(h_a, admin_b.id, admin_b.correo, "operador")
        assert r_igual.status_code == 409, f"mismo rol deberia dar 409: {r_igual.status_code}"
        print("  [TUA-7] rol desconocido -> 422 / rol ya vigente -> 409: PASADO")

        # --------- TUA-9 / TUA-10 / TUA-11 / TUA-12: el CLI ---------------------
        # Dry-run primero: no debe modificar nada.
        cli_meta = preparar("cli", "conductor", "90000009")
        hash_antes = cli_meta.contrasena_hash
        rdry = run_cli("--correo", cli_meta.correo)
        assert rdry.returncode == 0, f"dry-run deberia salir 0: {rdry.returncode} {rdry.stderr}"
        assert "DRY-RUN" in rdry.stdout, f"dry-run deberia avisar: {rdry.stdout}"
        assert "CONTRASENA TEMPORAL" not in rdry.stdout, "dry-run no debe imprimir la temporal"
        db.expire_all()
        assert db.query(UsuarioModel).filter(
            UsuarioModel.id == cli_meta.id
        ).one().contrasena_hash == hash_antes, "dry-run modifico la contrasena"
        print("  [TUA-9] CLI dry-run -> exit 0, sin cambios y sin temporal: PASADO")

        # Sesion abierta que el CLI debe revocar.
        h_cli = {"Authorization": "Bearer " + client.post(
            "/api/v1/auth/login",
            json={"identificador": cli_meta.correo, "contrasena": PASSWORD_INICIAL},
        ).json()["access_token"]}
        assert client.get("/api/v1/viajes", headers=h_cli).status_code == 200, "TUA-9: la sesion deberia andar"

        r9 = run_cli("--correo", cli_meta.correo, "--execute")
        assert r9.returncode == 0, f"TUA-9 deberia salir 0: {r9.returncode} {r9.stderr}"
        m = re.search(r"\[CONTRASENA TEMPORAL\]\s+(\S+)", r9.stdout)
        assert m, f"TUA-9: no se encontro la temporal en stdout: {r9.stdout!r}"
        temporal = m.group(1)

        db.expire_all()
        fila = db.query(UsuarioModel).filter(UsuarioModel.id == cli_meta.id).one()
        assert fila.debe_cambiar_contrasena is True, "TUA-9: el flag deberia quedar en True"
        assert fila.ultimo_acceso is None, "TUA-9: deberia limpiar ultimo_acceso"
        from app.core.security import verify_password

        assert verify_password(temporal, fila.contrasena_hash), "TUA-9: la temporal no es la guardada"
        # El hash NO debe ser la temporal en claro.
        assert fila.contrasena_hash != temporal, "TUA-9: la contrasena esta en claro"
        # Sesiones abiertas: la anterior debe caer (password_version).
        r_stale = client.get("/api/v1/viajes", headers=h_cli)
        assert r_stale.status_code == 401, f"TUA-9: la sesion previa deberia caer: {r_stale.status_code}"
        ev = [e for e in eventos() if e.evento == "password_reset_break_glass"]
        assert ev, "TUA-9: no se registro password_reset_break_glass"
        assert ev[-1].usuario_actor_id is None, "TUA-9: sin actor (no hay sesion HTTP)"
        assert ev[-1].usuario_objetivo_id == cli_meta.id, "TUA-9: objetivo incorrecto"
        assert ev[-1].detalle.get("via") == "cli", f"TUA-9: detalle={ev[-1].detalle}"
        print("  [TUA-9] CLI --correo --execute -> temporal + flag + sesion caída + auditoria: PASADO")

        # TUA-12: la temporal cumple la politica de A1
        db.expire_all()
        objetivo12 = db.query(UsuarioModel).filter(UsuarioModel.id == cli_meta.id).one()
        validar_politica_contrasena(
            temporal, cedula=objetivo12.cedula, correo=objetivo12.correo
        )
        assert len(temporal) >= 8, f"TUA-12: la temporal es muy corta: {len(temporal)}"
        print(f"  [TUA-12] la temporal ({len(temporal)} chars) cumple la politica de A1: PASADO")

        # TUA-10: por cedula
        cli_c = preparar("cli-ced", "conductor", "90000010")
        r10 = run_cli("--cedula", cli_c.cedula, "--execute")
        assert r10.returncode == 0, f"TUA-10 deberia salir 0: {r10.returncode} {r10.stderr}"
        m10 = re.search(r"\[CONTRASENA TEMPORAL\]\s+(\S+)", r10.stdout)
        assert m10, f"TUA-10: no se encontro la temporal: {r10.stdout!r}"
        db.expire_all()
        fila10 = db.query(UsuarioModel).filter(UsuarioModel.id == cli_c.id).one()
        assert verify_password(m10.group(1), fila10.contrasena_hash), "TUA-10: no se aplico"
        print("  [TUA-10] CLI --cedula --execute -> temporal aplicada: PASADO")

        # Case-insensitive, igual que el login de A2.
        r10b = run_cli("--correo", cli_c.correo.upper(), "--execute")
        assert r10b.returncode == 0, (
            f"TUA-10: el CLI deberia ser case-insensitive como el login: {r10b.returncode} {r10b.stderr}"
        )
        print("  [TUA-10] CLI case-insensitive (mismo criterio que el login): PASADO")

        # TUA-11: inexistente -> exit 1
        r11 = run_cli("--correo", "nadie-aqui@celr.com", "--execute")
        assert r11.returncode == 1, f"TUA-11 deberia salir 1: {r11.returncode}"
        assert "No se encontro" in r11.stderr, f"TUA-11: stderr={r11.stderr!r}"
        print("  [TUA-11] CLI con identificador inexistente -> exit 1: PASADO")

        print("\n[TUA] OK: proteccion del ultimo admin y break-glass funcionando")
    finally:
        try:
            # Restaurar la semilla ANTES de borrar nada: si algo fallo a mitad,
            # el sistema no puede quedar sin admin.
            db.rollback()
            s = db.query(UsuarioModel).filter(UsuarioModel.correo == "test@celr.com").one()
            s.activo = True
            db.commit()
            correos = [
                _correo(e)
                for e in ("admin-a", "admin-b", "operador", "meta", "cli", "cli-ced")
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


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        import traceback

        print(f"\n[ERROR EN TESTS]: {exc}")
        traceback.print_exc()
        raise
