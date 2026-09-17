from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import timedelta, datetime, timezone

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.flota import Usuario as UsuarioModel
from app.core.security import verify_password, create_access_token
from app.schemas.usuario import UsuarioLogin, UsuarioResponse
from app.schemas.token import Token

router = APIRouter()


@router.post("/auth/login", response_model=Token)
def login(login_data: UsuarioLogin, db: Session = Depends(get_db)):
    db_usuario = db.execute(
        select(UsuarioModel).where(UsuarioModel.correo == login_data.correo)
    ).scalar_one_or_none()
    if not db_usuario or not verify_password(login_data.contrasena, db_usuario.contrasena_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not db_usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    token_data = {"usuario_id": db_usuario.id, "correo": db_usuario.correo}
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=30))
    db_usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    return Token(access_token=access_token)


@router.get("/auth/me", response_model=UsuarioResponse)
def get_current_user_endpoint(current_user: UsuarioModel = Depends(get_current_user)):
    return current_user