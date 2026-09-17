from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime


class ConductorCreate(BaseModel):
    nombre_completo: str = Field(..., max_length=150)
    cedula: str = Field(..., max_length=20)
    telefono: Optional[str] = Field(None, max_length=20)
    correo: Optional[str] = Field(None, max_length=100)
    direccion: Optional[str] = None
    num_licencia: Optional[str] = Field(None, max_length=30)
    categoria_licencia: Optional[str] = Field(None, max_length=10)
    vencimiento_licencia: Optional[date] = None
    estado: str = Field("activo", max_length=20)

    @validator("estado")
    def validate_estado(cls, v):
        allowed = {"activo", "inactivo", "vacaciones", "incapacitado"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class ConductorUpdate(BaseModel):
    nombre_completo: Optional[str] = Field(None, max_length=150)
    cedula: Optional[str] = Field(None, max_length=20)
    telefono: Optional[str] = Field(None, max_length=20)
    correo: Optional[str] = Field(None, max_length=100)
    direccion: Optional[str] = None
    num_licencia: Optional[str] = Field(None, max_length=30)
    categoria_licencia: Optional[str] = Field(None, max_length=10)
    vencimiento_licencia: Optional[date] = None
    estado: Optional[str] = Field(None, max_length=20)

    @validator("estado")
    def validate_estado(cls, v):
        allowed = {"activo", "inactivo", "vacaciones", "incapacitado"}
        if v is not None and v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class ConductorResponse(BaseModel):
    id: int
    nombre_completo: str
    cedula: str
    telefono: Optional[str]
    correo: Optional[str]
    direccion: Optional[str]
    num_licencia: Optional[str]
    categoria_licencia: Optional[str]
    vencimiento_licencia: Optional[date]
    estado: str
    creado_en: datetime
    actualizado_en: datetime

    class ConfigDict:
        from_attributes = True