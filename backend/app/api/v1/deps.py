from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Iterable

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.flota import Usuario

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
    return usuario


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