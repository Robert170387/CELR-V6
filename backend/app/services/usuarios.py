"""A5.2 — Servicio de usuarios: invariantes de administracion y confirmacion.

Tres helpers, todos derivados de `RolUsuario` (nunca literales sueltos: la
leccion de A3.1 fue exactamente un rol escrito a mano que quedo huerfano).

Que NO hace este modulo: concede roles. `ROLES_OBJETIVO_POR_EJECUTOR` vive
en el endpoint (A3.2) y se reutiliza desde ahi. Aca solo vive lo que es
invariante de seguridad y por lo tanto conviene tener en un solo lugar.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.roles import RolUsuario
from app.models.flota import Usuario

ROL_ADMIN = RolUsuario.ADMIN.value


def contar_admins_activos(db: Session, excluyendo_id: Optional[int] = None) -> int:
    """Cuenta usuarios activos con rol admin, opcionalmente excluyendo uno.

    El `excluyendo_id` es lo que permite responder "¿este usuario es el
    ultimo admin?" en vez de "¿cuantos admins hay?": la pregunta util es la
    primera.
    """
    q = db.query(Usuario).filter(
        Usuario.rol == ROL_ADMIN,
        Usuario.activo.is_(True),
    )
    if excluyendo_id is not None:
        q = q.filter(Usuario.id != excluyendo_id)
    return q.count()


def es_ultimo_admin_activo(db: Session, usuario_id: int) -> bool:
    """True si el usuario es admin activo y, sin el, no queda ningun admin.

    False si el usuario no existe, no es admin, o ya esta inactivo: en esos
    casos la pregunta no aplica y responder True seria un falso positivo que
    freeria al admin a escribir una confirmacion que no hace falta.
    """
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if usuario is None or usuario.rol != ROL_ADMIN or not usuario.activo:
        return False
    return contar_admins_activos(db, excluyendo_id=usuario_id) == 0


def validar_confirmacion_identificador(usuario: Usuario, valor: Optional[str]) -> None:
    """Exige que el ejecutor escriba la cedula o el correo del objetivo.

    No es un `confirmar=true`: eso lo puede mandar un script sin humano
    detras. Un identificador que tiene que teclear una persona es la
    diferencia entre "se dejo carried away" y "decidio hacerlo". El valor
    queda ademas en la fila de auditoria, asi que el rastro dice no solo que
    paso sino que hubo confirmacion.

    Compara contra cedula O correo, case-insensitive y con strip, igual que
    el login de A2: si el login acepta "ADMIN@CELR.COM", la confirmacion
    tambien.
    """
    if valor is None or not valor.strip():
        raise ValueError(
            "Debe confirmar escribiendo la cedula o el correo del usuario. "
            "Nada se ha modificado."
        )
    esperado = valor.strip().casefold()
    candidatos = set()
    if usuario.cedula:
        candidatos.add(usuario.cedula.strip().casefold())
    if usuario.correo:
        candidatos.add(usuario.correo.strip().casefold())
    if not candidatos:
        raise ValueError(
            "El usuario no tiene cedula ni correo, asi que no hay forma de "
            "confirmar la operacion. Nada se ha modificado."
        )
    if esperado not in candidatos:
        raise ValueError(
            "La confirmacion no coincide con la cedula ni el correo del "
            "usuario. Nada se ha modificado."
        )
