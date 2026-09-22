from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Iterable

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.flota import Usuario

# Cabecera que el frontend lee para redirigir al flujo de cambio obligatorio de
# contrasena cuando un endpoint de negocio responde 403 por S1 (hardenig auth).
CABECERA_REQUIERE_CAMBIO = "X-Celr-Requiere-Cambio"

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if payload is None or payload.get("usuario_id") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar las credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )
    usuario = db.query(Usuario).filter(Usuario.id == payload["usuario_id"]).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )

    # S2/hardening: el access token solo es valido si su password_version es
    # la actual. Al cambiar la contrasena se incrementa password_version
    # (endpoint /auth/cambio-contrasena), por lo que cualquier access token
    # emitido antes del cambio queda invalidado al instante (revocacion
    # server-side de sesiones tras rotar credenciales).
    if payload.get("password_version") != usuario.password_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu contraseña fue cambiada; inicia sesión nuevamente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario


def exigir_contrasena_actualizada(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    """S1/hardening: bloquea endpoints de negocio si el usuario aun debe
    cambiar su contrasena (debe_cambiar_contrasena=True).

    El frontend detecta el 403 + cabecera X-CELR-Requiere-Cambio y redirige a
    /cambiar-contrasena. NO debe aplicarse a /auth/*: el flujo de cambio
    forzado necesita poder llamar a /auth/me, /auth/cambio-contrasena,
    /auth/refresh y /auth/logout.
    """
    if current_user.debe_cambiar_contrasena:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu contraseña antes de continuar",
            headers={"X-CELR-Requiere-Cambio": "true"},
        )
    return current_user


def RoleChecker(roles_permitidos: Iterable[str]):
    """Inyector de dependencias que restringe el acceso por rol.

    Uso:
        @router.post("/ruta", dependencies=[Depends(RoleChecker(["admin"]))])
        # o a nivel de router:
        router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))])

    Lanza HTTP 403 Forbidden si el rol del usuario autenticado no esta permitido.
    """
    permitidos = frozenset(roles_permitidos)

    def verificar_rol(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"El rol '{current_user.rol}' no tiene permisos para "
                    f"esta operación. Roles permitidos: {sorted(permitidos)}"
                ),
            )
        return current_user

    return verificar_rol