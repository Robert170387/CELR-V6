from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from decimal import Decimal


class VehiculoCreate(BaseModel):
    placa: str = Field(..., max_length=10)
    marca: str = Field(..., max_length=50)
    modelo: Optional[str] = Field(None, max_length=50)
    anio: Optional[int] = None
    tipo_carroceria: Optional[str] = Field(None, max_length=50)
    capacidad_ton: Optional[Decimal] = Field(None, ge=0)
    estado: str = Field("activo", max_length=20)
    km_actual: Decimal = Field(default=0, ge=0)
    km_inicial_sistema: Decimal = Field(default=0, ge=0)
    numero_motor: Optional[str] = Field(None, max_length=50)
    numero_chasis: Optional[str] = Field(None, max_length=50)
    propietario_nombre: Optional[str] = Field(None, max_length=100)
    propietario_nit: Optional[str] = Field(None, max_length=20)

    @validator("estado")
    def validate_estado(cls, v):
        allowed = {"activo", "en_taller", "inactivo"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class VehiculoResponse(BaseModel):
    id: int
    placa: str
    marca: str
    modelo: Optional[str]
    anio: Optional[int]
    tipo_carroceria: Optional[str]
    capacidad_ton: Optional[Decimal]
    estado: str
    km_actual: Decimal
    km_inicial_sistema: Decimal
    numero_motor: Optional[str]
    numero_chasis: Optional[str]
    propietario_nombre: Optional[str]
    propietario_nit: Optional[str]
    creado_en: datetime
    actualizado_en: datetime

    class ConfigDict:
        from_attributes = True