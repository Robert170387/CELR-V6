"""Usuarios — gestion de cuentas (A3.2, andamio para A5).

A3.2 implementa solo el reset asistido por admin. Los endpoints de CRUD
(listar, crear, editar, desactivar) llegan en A5.
"""
import logging
import secrets
from typing import Dict, FrozenSet

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import RoleChecker, get_current_user
from app.core.roles import RolUsuario
from app.core.security import hash_password
from app.db.session import get_db
from app.models.flota import PasswordResetToken
from app.models.flota import RefreshToken as RefreshTokenModel
from app.models.flota import Usuario as UsuarioModel
from app.schemas.usuario import AdminResetCodigoResponse, AdminResetPasswordResponse
from app.services.auditoria import obtener_ip, obtener_user_agent
from app.services.auditoria import registrar as registrar_auditoria
from app.services.password_reset import generar_token_reset, ttl_por_tipo

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


def _resolver_objetivo(db: Session, usuario_id: int, current_user: UsuarioModel) -> UsuarioModel:
    """Valida el objetivo de un reset. Compartido por A3.2 y A3.3.

    Aplica las tres reglas que no dependen de como se entrega la credencial:
    existe, no sos vos mismo, y tu rol puede resetear ese rol. Que las dos
    vias compartan esta funcion es lo que garantiza que un endpoint nuevo no
    se CUERDE con una matriz mas laxa.
    """
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Admin no se resetea a si mismo por esta via. La credencial se muestra una
    # sola vez: si se pierde, se queda fuera del sistema de gestion de cuentas
    # y no hay forma de volver. Para su propia cuenta esta el flujo
    # /auth/forgot-password (que exige correo) o /auth/cambio-contrasena.
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
    return usuario


@router.post(
    "/usuarios/{usuario_id}/reset-password",
    response_model=AdminResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
def reset_password_asistido(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """Genera una contrasena temporal para el usuario objetivo.

    La contrasena en claro se devuelve SOLO en esta respuesta HTTP: nunca se
    loguea, nunca se persiste y no vuelve a mostrarse. Por eso va en el cuerpo
    de un POST y no en la URL, que acabaria en los access logs del servidor.
    """
    usuario = _resolver_objetivo(db, usuario_id, current_user)

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

    # A3.4: la contrasena temporal NO va en `detalle` ni en el log (invariante
    # TAUD-10). El rastro dice QUIEN reseteo a QUIEN, no QUE credencial.
    registrar_auditoria(
        db,
        "password_reset_admin",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
    )

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


@router.post(
    "/usuarios/{usuario_id}/reset-codigo",
    response_model=AdminResetCodigoResponse,
    status_code=status.HTTP_200_OK,
)
def reset_codigo_asistido(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """A3.3 — Genera un codigo de 6 digitos para un usuario sin acceso a email.

    A diferencia de A3.2, esto NO cambia la contrasena: solo emite un codigo que
    el usuario canjeara en /auth/reset-codigo. La contrasena se cambia cuando
    el usuario la elija, no cuando el admin lo decida.

    No se envia por email a proposito: el caso de uso es justamente quien no
    tiene buzon. El admin lo dicta por telefono/WhatsApp/presencial. Por eso
    este endpoint NO toca LogEmailBackend — si lo hiciera, el codigo caeria en
    los logs de la aplicacion.
    """
    usuario = _resolver_objetivo(db, usuario_id, current_user)

    codigo = generar_token_reset(db, usuario.id, tipo="codigo")
    # A3.4: el codigo de 6 digitos NO va en `detalle` (invariante TAUD-10).
    registrar_auditoria(
        db,
        "password_reset_codigo_generado",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
    )
    db.commit()
    fila = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.usuario_id == usuario.id,
            PasswordResetToken.tipo == "codigo",
        )
        .order_by(PasswordResetToken.id.desc())
        .first()
    )
    minutos = int(ttl_por_tipo(db, "codigo").total_seconds() // 60)

    # Traza minima: QUIEN genero el codigo y para QUIEN. Nunca el codigo.
    logger.info(
        "Codigo de reset generado: usuario_id=%s por usuario_id=%s (rol=%s)",
        usuario.id,
        current_user.id,
        current_user.rol,
    )

    return AdminResetCodigoResponse(
        usuario_id=usuario.id,
        correo=usuario.correo,
        codigo=codigo,
        expira_en=fila.expira_en if fila else None,
        mensaje=(
            f"Díctele el código al usuario por un canal seguro. No se mostrará de "
            f"nuevo. Caduca en {minutos} minutos."
        ),
    )
