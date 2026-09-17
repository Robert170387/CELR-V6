from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class ViajeCreate(BaseModel):
    numero_odt: str = Field(..., max_length=30)
    num_manifiesto: Optional[str] = Field(None, max_length=30)
    vehiculo_id: int
    conductor_id: int
    origen: str = Field(..., max_length=100)
    destino: str = Field(..., max_length=100)
    empresa_manifiesto: Optional[str] = Field(None, max_length=150)
    tipo_carga: Optional[str] = Field(None, max_length=100)
    peso_declarado_ton: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_origen: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_destino: Optional[Decimal] = Field(None, ge=0)
    valor_flete_manifiesto: Optional[Decimal] = Field(None, ge=0)
    retefuente_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    retefuente_valor: Optional[Decimal] = Field(None, ge=0)
    reteica_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    reteica_valor: Optional[Decimal] = Field(None, ge=0)
    fecha_salida: date
    fecha_llegada: Optional[date] = None
    km_inicial: Optional[Decimal] = Field(None, ge=0)
    km_final: Optional[Decimal] = Field(None, ge=0)
    estado: Optional[str] = Field("en_curso", max_length=20)
    observaciones: Optional[str] = None
    creado_por: Optional[int] = None


class ViajeUpdate(BaseModel):
    numero_odt: Optional[str] = Field(None, max_length=30)
    num_manifiesto: Optional[str] = Field(None, max_length=30)
    vehiculo_id: Optional[int] = None
    conductor_id: Optional[int] = None
    origen: Optional[str] = Field(None, max_length=100)
    destino: Optional[str] = Field(None, max_length=100)
    empresa_manifiesto: Optional[str] = Field(None, max_length=150)
    tipo_carga: Optional[str] = Field(None, max_length=100)
    peso_declarado_ton: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_origen: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_destino: Optional[Decimal] = Field(None, ge=0)
    valor_flete_manifiesto: Optional[Decimal] = Field(None, ge=0)
    retefuente_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    retefuente_valor: Optional[Decimal] = Field(None, ge=0)
    reteica_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    reteica_valor: Optional[Decimal] = Field(None, ge=0)
    fecha_salida: Optional[date] = None
    fecha_llegada: Optional[date] = None
    km_inicial: Optional[Decimal] = Field(None, ge=0)
    km_final: Optional[Decimal] = Field(None, ge=0)
    estado: Optional[str] = Field(None, max_length=20)
    observaciones: Optional[str] = None
    creado_por: Optional[int] = None


class ViajeResponse(BaseModel):
    id: int
    numero_odt: str
    num_manifiesto: Optional[str]
    vehiculo_id: int
    conductor_id: int
    origen: str
    destino: str
    empresa_manifiesto: Optional[str]
    tipo_carga: Optional[str]
    peso_declarado_ton: Optional[Decimal]
    peso_bascula_origen: Optional[Decimal]
    peso_bascula_destino: Optional[Decimal]
    valor_flete_manifiesto: Optional[Decimal]
    retefuente_porcentaje: Optional[Decimal]
    retefuente_valor: Optional[Decimal]
    reteica_porcentaje: Optional[Decimal]
    reteica_valor: Optional[Decimal]
    flete_neto: Optional[Decimal]
    fecha_salida: date
    fecha_llegada: Optional[date]
    km_inicial: Optional[Decimal]
    km_final: Optional[Decimal]
    km_recorridos: Optional[Decimal]
    estado: str
    observaciones: Optional[str]
    creado_por: Optional[int]
    creado_en: datetime
    actualizado_en: datetime

    class ConfigDict:
        from_attributes = True
