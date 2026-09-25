"""Usuarios — gestion de cuentas (A3.2, andamio para A5).

A3.2 implementa solo el reset asistido por admin. Los endpoints de CRUD
(listar, crear, editar, desactivar) llegan en A5.
"""
import logging
import secrets
from typing import Dict, FrozenSet

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import RoleChecker, get_current_user
from app.core.roles import RolUsuario
from app.core.security import hash_password
from app.db.session import get_db
from app.models.flota import RefreshToken as RefreshTokenModel
from app.models.flota import Usuario as UsuarioModel
from app.schemas.usuario import AdminResetPasswordResponse

logger = logging.getLogger(__name__)

# A3.2 — Reset asistido: el admin (o un rol de escritura) genera una contrasena
# temporal para un usuario que no puede entrar. Es distinto del reset por enlace
# de A3.1: aqui no hay token ni email, hay una credencial que el administrador
# comunica por un canal presencial. Por eso NO usa `password_reset_token`, que
# queda reservado para el codigo offline de A3.3.
ROLES_RESET_PERMITIDOS: FrozenSet[str] = frozenset(
    {
        RolUsuario.ADMIN.value,
        RolUsuario.OPERADOR.value,
        RolUsuario.CONTADOR.value,
        RolUsuario.SUPERVISOR.value,
    }
)

# Matriz anti-escalada: que rol de OBJETIVO puede resetear cada rol de EJECUTOR.
# Sin esto, un operador podria resetearle la contrasena a un admin y tomar su
# cuenta: la escalada no es "quien deberia", es "quien no debe poder tomar".
# Se construye desde el enum para que un rol nuevo no quede sin cobertura
# silenciosa (el error de A3.1 fue exactamente un rol huerfano).
ROLES_OBJETIVO_POR_EJECUTOR: Dict[str, FrozenSet[str]] = {
    RolUsuario.ADMIN.value: frozenset(rol.value for rol in RolUsuario),
    RolUsuario.OPERADOR.value: frozenset(
        {RolUsuario.CONDUCTOR.value, RolUsuario.CLIENTE.value}
    ),
    RolUsuario.CONTADOR.value: frozenset(
        {RolUsuario.CONDUCTOR.value, RolUsuario.CLIENTE.value}
    ),
    RolUsuario.SUPERVISOR.value: frozenset(
        {RolUsuario.CONDUCTOR.value, RolUsuario.CLIENTE.value}
    ),
}

router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_RESET_PERMITIDOS))])


@router.post(
    "/usuarios/{usuario_id}/reset-password",
    response_model=AdminResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
def reset_password_asistido(
    usuario_id: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """Genera una contrasena temporal para el usuario objetivo.

    La contrasena en claro se devuelve SOLO en esta respuesta HTTP: nunca se
    loguea, nunca se persiste y no vuelve a mostrarse. Por eso va en el cuerpo
    de un POST y no en la URL, que acabaria en los access logs del servidor.
    """
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Admin no se resetea a si mismo por esta via. La temporal se muestra una
    # sola vez: si el admin la pierde, se queda fuera del sistema de gestion de
    # cuentas y no hay forma de volver. Para su propia cuenta esta el flujo
    # /auth/forgot-password (que ademas exige correo) o /auth/cambio-contrasena.
    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes restablecer tu propia contraseña por esta vía",
        )

    permitidos = ROLES_OBJETIVO_POR_EJECUTOR.get(current_user.rol, frozenset())
    if usuario.rol not in permitidos:
        # Mensaje generico a proposito: incluir el rol del objetivo confirmaria
        # a un ejecutor sin permisos que tipo de cuenta es la que probed.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para restablecer la contraseña de este usuario",
        )

    contrasena_temporal = secrets.token_urlsafe(12)

    usuario.contrasena_hash = hash_password(contrasena_temporal)
    # A4 ya hace que este flag bloquee de verdad: el usuario no entra a
    # endpoints de negocio hasta cambiarla.
    usuario.debe_cambiar_contrasena = True
    usuario.password_version = (usuario.password_version or 0) + 1
    usuario.ultimo_acceso = None

    # La credencial cambio: el resto de sesiones abiertas deben caer.
    db.query(RefreshTokenModel).filter(
        RefreshTokenModel.usuario_id == usuario.id,
        RefreshTokenModel.revocado.is_(False),
    ).update({"revocado": True}, synchronize_session=False)

    db.commit()
    # Traza minima: QUIEN reseteo y a QUIEN, nunca la contrasena. La auditoria
    # completa llega en A3.4.
    logger.info(
        "Reset asistido: usuario_id=%s por usuario_id=%s (rol=%s)",
        usuario.id,
        current_user.id,
        current_user.rol,
    )

    return AdminResetPasswordResponse(
        usuario_id=usuario.id,
        correo=usuario.correo,
        contrasena_temporal=contrasena_temporal,
        mensaje=(
            "Comuníquela al usuario por un canal seguro. No se mostrará de nuevo. "
            "El usuario deberá cambiarla al iniciar sesión."
        ),
        debe_cambiar_contrasena=True,
    )
