from pydantic import BaseModel, Field
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    usuario_id: Optional[int] = None
    correo: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20, max_length=200)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20, max_length=200)


class CambioContrasenaRequest(BaseModel):
    contrasena_actual: str = Field(..., max_length=200)
    nueva_contrasena: str = Field(..., min_length=6, max_length=200)