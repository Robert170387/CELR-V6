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


class ForgotPasswordRequest(BaseModel):
    """A3.1 — Identificador (cedula o correo). No se revela si existe o no."""

    identificador: str = Field(..., min_length=1, max_length=150)


class ResetPasswordRequest(BaseModel):
    """A3.1 — El token en claro (el que va en el enlace) y la contrasena nueva.

    `nueva_contrasena` no tiene min_length aqui a proposito: la politica real la
    aplica validar_politica_contrasena en el endpoint y devuelve 422 con el
    motivo exacto. Poner un min_length en el schema devolveria un 422 generico
    de pydantic, menos util para el usuario.
    """

    token: str = Field(..., min_length=1, max_length=200)
    nueva_contrasena: str = Field(..., min_length=1, max_length=200)


class ResetCodigoRequest(BaseModel):
    """A3.3 — Canje de un codigo offline de 6 digitos.

    `codigo` es texto a proposito, no int: un int perderia los ceros iniciales
    ("012345" -> 12345) y el codigo generado los lleva. Se valida por longitud.
    """

    codigo: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    nueva_contrasena: str = Field(..., min_length=1, max_length=200)