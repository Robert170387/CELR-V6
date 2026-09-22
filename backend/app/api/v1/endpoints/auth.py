from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from datetime import timedelta, datetime, timezone

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.flota import Usuario as UsuarioModel
from app.models.flota import RefreshToken as RefreshTokenModel
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    hash_refresh_token,
)
from app.core.config import settings
from app.core.rate_limiter import excede_limite, registrar_fallo, limpiar_fallos
from app.schemas.usuario import UsuarioLogin, UsuarioResponse
from app.schemas.token import Token, RefreshRequest, LogoutRequest, CambioContrasenaRequest

router = APIRouter()


@router.post("/auth/login", response_model=Token)
def login(login_data: UsuarioLogin, db: Session = Depends(get_db)):
    clave = (login_data.correo or "").strip().lower()
    if excede_limite(clave):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión. Inténtalo nuevamente en 15 minutos.",
        )
    db_usuario = db.execute(
        select(UsuarioModel).where(UsuarioModel.correo == login_data.correo)
    ).scalar_one_or_none()
    if not db_usuario or not verify_password(login_data.contrasena, db_usuario.contrasena_hash):
        registrar_fallo(clave)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not db_usuario.activo:
        registrar_fallo(clave)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    limpiar_fallos(clave)
    token_data = {"usuario_id": db_usuario.id, "correo": db_usuario.correo}
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(db, db_usuario)
    db_usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/refresh", response_model=Token)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_refresh_token(request.refresh_token)
    registro = db.execute(
        select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
    ).scalar_one_or_none()
    if (
        registro is None
        or registro.revocado
        or registro.expira_en <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db_usuario = db.execute(
        select(UsuarioModel).where(UsuarioModel.id == registro.usuario_id)
    ).scalar_one_or_none()
    if db_usuario is None or not db_usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rotación: revoca el token usado y emite un par nuevo
    registro.revocado = True
    registro.usado_en = datetime.now(timezone.utc)

    new_refresh = create_refresh_token(db, db_usuario)
    token_data = {"usuario_id": db_usuario.id, "correo": db_usuario.correo}
    new_access = create_access_token(token_data, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    db.commit()
    return Token(access_token=new_access, refresh_token=new_refresh)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: LogoutRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(db, hash_refresh_token(request.refresh_token))
    db.commit()
    return None


@router.get("/auth/me", response_model=UsuarioResponse)
def get_current_user_endpoint(current_user: UsuarioModel = Depends(get_current_user)):
    return current_user


@router.post("/auth/cambio-contrasena", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_contrasena(
    data: CambioContrasenaRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    if not verify_password(data.contrasena_actual, current_user.contrasena_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta",
        )
    current_user.contrasena_hash = hash_password(data.nueva_contrasena)
    current_user.debe_cambiar_contrasena = False
    current_user.ultimo_acceso = datetime.now(timezone.utc)
    # Revoca todos los refresh tokens activos: el resto de sesiones debe volver a iniciar sesión.
    db.execute(
        update(RefreshTokenModel)
        .where(
            RefreshTokenModel.usuario_id == current_user.id,
            RefreshTokenModel.revocado == False,  # noqa: E712
        )
        .values(revocado=True)
    )
    db.commit()
    return None