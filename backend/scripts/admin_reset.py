"""A5.2 — Break-glass: reset de contrasena por CLI, sin HTTP.

POR QUE UN SCRIPT Y NO UN ENDPOINT
---------------------------------
Si el reset administrativo fuera un endpoint publico, cualquiera que pudiera
generar un codigo offline podria tomar la cuenta de un admin: eso no es un
break-glass, es una puerta trasera. Este script corre en el servidor, con
acceso a la base, y no es superficie HTTP: no hay nada que un atacante remoto
pueda alcanzar.

Resuelve el caso que ninguna otra via cubre: una unica cuenta admin, sin
correo, que perdio su contrasena. A3.2 necesita otro admin; A3.1 necesita
buzon; A3.3 necesita que alguien genere el codigo. Este es el unico que no
depende de nada de eso.

ALCANCE MINIMO, A PROPOSITO
---------------------------
Solo contrasenas. NO cambia roles, NO activa ni desactiva cuentas, NO crea
usuarios. Un break-glass con alcance amplio es un backdoor con nombre
tecnico; con una sola operacion es una herramienta. Si alguna vez hace falta
mas, se agrega como comando nuevo y auditado por separado.

USO
---
    # Ver que pasaria (por defecto, no modifica nada)
    docker compose exec backend python scripts/admin_reset.py --correo admin@celr.com

    # Aplicar
    docker compose exec backend python scripts/admin_reset.py --correo admin@celr.com --execute

Correr en una terminal interactiva. NO redirigir stdout a un archivo ni a un
registro persistente: la contrasena temporal se imprime una sola vez y en
plano. Ese es el tradeoff del mecanismo: a cambio de no ser superficie HTTP,
el operador tiene que tratar la salida como un secreto.
"""
import argparse
import os
import secrets
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import func

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.flota import RefreshToken, Usuario
from app.services.auditoria import registrar


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Break-glass: reset de contrasena de UNA cuenta, con acceso directo "
            "a la BD. Dry-run por defecto; usar --execute para aplicar."
        )
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--correo", type=str, help="Correo de la cuenta.")
    grupo.add_argument("--cedula", type=str, help="Cedula de la cuenta.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Aplica el reset. Sin este flag solo muestra el plan.",
    )
    return parser.parse_args()


def _buscar(db, correo: str = None, cedula: str = None):
    """Busca por cedula o correo, case-insensitive.

    Case-insensitive a proposito: el login (A2) resuelve con lower(), asi que
    una herramienta que fallara donde el login funciona seria una trampa en
    el peor momento posible. El break-glass se invoca justamente cuando el
    login ya no sirve.
    """
    if correo is not None:
        return (
            db.query(Usuario)
            .filter(func.lower(Usuario.correo) == correo.strip().lower())
            .first()
        )
    return (
        db.query(Usuario)
        .filter(func.lower(Usuario.cedula) == cedula.strip().lower())
        .first()
    )


def main() -> int:
    args = _parse_args()
    db = SessionLocal()
    try:
        usuario = _buscar(db, correo=args.correo, cedula=args.cedula)
        if usuario is None:
            criterio = args.correo or args.cedula
            print(f"[ERROR] No se encontro ninguna cuenta con '{criterio}'.", file=sys.stderr)
            return 1

        activos = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.usuario_id == usuario.id,
                RefreshToken.revocado.is_(False),
            )
            .count()
        )

        print(f"usuario_id : {usuario.id}")
        print(f"correo     : {usuario.correo or '(sin correo)'}")
        print(f"cedula     : {usuario.cedula or '(sin cedula)'}")
        print(f"rol        : {usuario.rol}")
        print(f"activo     : {usuario.activo}")
        print(f"refresh tokens a revocar: {activos}")

        if not args.execute:
            print("\n[DRY-RUN] No se modifico nada. Agregar --execute para aplicar.")
            return 0

        contrasena = secrets.token_urlsafe(12)
        usuario.contrasena_hash = hash_password(contrasena)
        # A4 hace que esto bloquee de verdad: el usuario entra con la temporal,
        # recibe 403 en los endpoints de negocio y tiene que cambiarla.
        usuario.debe_cambiar_contrasena = True
        usuario.password_version = (usuario.password_version or 0) + 1
        usuario.ultimo_acceso = None
        db.query(RefreshToken).filter(
            RefreshToken.usuario_id == usuario.id,
            RefreshToken.revocado.is_(False),
        ).update({"revocado": True}, synchronize_session=False)

        # A3.4: sin actor porque no hay sesion HTTP; `via=cli` deja claro que
        # la accion vino de aqui y no de la API.
        registrar(
            db,
            "password_reset_break_glass",
            objetivo_id=usuario.id,
            detalle={"via": "cli", "refresh_revocados": activos},
        )
        db.commit()

        print(f"\n[OK] Reset aplicado a usuario_id={usuario.id}")
        print(f"[CONTRASENA TEMPORAL] {contrasena}")
        print(
            "[!] Se muestra UNA sola vez y no se persiste en ningun lado. "
            "Comuniquesela por un canal seguro."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
