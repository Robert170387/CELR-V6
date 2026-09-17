from pydantic import BaseModel, Field, validator
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
    correo: str = Field(..., max_length=100)
    contrasena: str = Field(..., max_length=200)


class UsuarioResponse(BaseModel):
    id: int
    correo: str
    rol: str
    conductor_id: Optional[int]
    activo: bool
    ultimo_acceso: Optional[datetime]
    creado_en: datetime
    actualizado_en: datetime

    class ConfigDict:
        from_attributes = True
