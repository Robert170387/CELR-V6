from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class ProveedorCreate(BaseModel):
    nit: Optional[str] = Field(None, max_length=20)
    razon_social: str = Field(..., max_length=150)
    nombre_comercial: Optional[str] = Field(None, max_length=150)
    tipo: str = Field(..., max_length=50)
    telefono: Optional[str] = Field(None, max_length=20)
    correo: Optional[str] = Field(None, max_length=100)
    ciudad: Optional[str] = Field(None, max_length=80)
    ciudad_municipio_id: Optional[int] = None
    banco: Optional[str] = Field(None, max_length=80)
    tipo_cuenta: Optional[str] = Field(None, max_length=30)
    numero_cuenta: Optional[str] = Field(None, max_length=50)

    @validator("tipo")
    def validate_tipo(cls, v):
        allowed = {
            "combustible", "peaje", "taller", "aseguradora",
            "repuestos", "viaticos", "administrativo", "otro",
        }
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("tipo_cuenta")
    def validate_tipo_cuenta(cls, v):
        if v is None:
            return v
        allowed = {"ahorros", "corriente"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class ProveedorUpdate(BaseModel):
    nit: Optional[str] = Field(None, max_length=20)
    razon_social: Optional[str] = Field(None, max_length=150)
    nombre_comercial: Optional[str] = Field(None, max_length=150)
    tipo: Optional[str] = Field(None, max_length=50)
    telefono: Optional[str] = Field(None, max_length=20)
    correo: Optional[str] = Field(None, max_length=100)
    ciudad: Optional[str] = Field(None, max_length=80)
    ciudad_municipio_id: Optional[int] = None
    banco: Optional[str] = Field(None, max_length=80)
    tipo_cuenta: Optional[str] = Field(None, max_length=30)
    numero_cuenta: Optional[str] = Field(None, max_length=50)

    @validator("tipo")
    def validate_tipo(cls, v):
        allowed = {
            "combustible", "peaje", "taller", "aseguradora",
            "repuestos", "viaticos", "administrativo", "otro",
        }
        if v is not None and v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("tipo_cuenta")
    def validate_tipo_cuenta(cls, v):
        if v is None:
            return v
        allowed = {"ahorros", "corriente"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class ProveedorResponse(BaseModel):
    id: int
    nit: Optional[str]
    razon_social: str
    nombre_comercial: Optional[str]
    tipo: str
    telefono: Optional[str]
    correo: Optional[str]
    ciudad: Optional[str]
    ciudad_municipio_id: Optional[int]
    banco: Optional[str]
    tipo_cuenta: Optional[str]
    numero_cuenta: Optional[str]
    creado_en: datetime

    class ConfigDict:
        from_attributes = True