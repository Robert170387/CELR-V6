from pydantic import BaseModel, Field, model_validator, validator
from typing import Optional
from datetime import date, datetime

from app.core.roles import ROLES_VALIDOS


class UsuarioCreate(BaseModel):
    correo: str = Field(..., max_length=100)
    contrasena: str = Field(..., min_length=6)
    rol: str = Field(default="conductor", max_length=20)
    conductor_id: Optional[int] = None

    @validator("rol")
    def validate_rol(cls, v):
        if v not in ROLES_VALIDOS:
            raise ValueError(f"debe ser uno de {sorted(ROLES_VALIDOS)}")
        return v


class UsuarioLogin(BaseModel):
    """A2 (D1 coexistencia): el login acepta `identificador` (cedula o correo).

    `correo` se conserva como alias legacy para no romper los clientes ya
    desplegados; si llegan ambos campos, `identificador` manda (ver endpoint
    /auth/login). A1 dejo `correo` nullable, asi que la cedula es hoy la
    identidad primaria, pero el alias sigue siendo la via de entrada mas usada.
    """

    identificador: Optional[str] = Field(default=None, max_length=100)
    correo: Optional[str] = Field(default=None, max_length=100)
    contrasena: str = Field(..., max_length=200)

    @model_validator(mode="after")
    def _requiere_identificador(self) -> "UsuarioLogin":
        if not (self.identificador or self.correo):
            raise ValueError(
                "Debe enviar 'identificador' (cedula o correo) o 'correo'"
            )
        return self


class AdminResetPasswordResponse(BaseModel):
    """A3.2 — Respuesta del reset asistido.

    `contrasena_temporal` se devuelve UNA sola vez. El frontend debe pedirla
    explícitamente (botón "generar") y no cachearla.
    """

    usuario_id: int
    correo: Optional[str] = None
    contrasena_temporal: str
    mensaje: str
    debe_cambiar_contrasena: bool = True


class UsuarioResponse(BaseModel):
    id: int
    # A1: la cedula es la identidad primaria y el correo queda opcional.
    cedula: Optional[str] = None
    correo: Optional[str] = None
    rol: str
    conductor_id: Optional[int]
    activo: bool
    debe_cambiar_contrasena: bool = False
    ultimo_acceso: Optional[datetime]
    creado_en: datetime
    actualizado_en: datetime

    class ConfigDict:
        from_attributes = True
