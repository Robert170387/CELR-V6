from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class IngresoCreate(BaseModel):
    viaje_id: int
    vehiculo_id: int
    tipo_ingreso: str = Field(..., max_length=30)
    descripcion: Optional[str] = None
    fecha_ingreso: date
    valor: Decimal = Field(..., gt=0)
    forma_pago: Optional[str] = Field(None, max_length=30)
    num_referencia: Optional[str] = Field(None, max_length=50)
    estado_pago: str = Field("pendiente", max_length=20)
    observaciones: Optional[str] = None
    creado_por: Optional[int] = None

    @validator("tipo_ingreso")
    def validate_tipo_ingreso(cls, v):
        allowed = {
            "flete", "anticipo", "cumplido", "compensacion",
            "bono", "traslado_fondos", "aporte_capital", "otro",
        }
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("forma_pago")
    def validate_forma_pago(cls, v):
        if v is None:
            return v
        allowed = {"transferencia", "cheque", "efectivo", "otro"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("estado_pago")
    def validate_estado_pago(cls, v):
        allowed = {"pendiente", "recibido", "en_disputa"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class IngresoResponse(BaseModel):
    id: int
    viaje_id: int
    vehiculo_id: int
    tipo_ingreso: str
    descripcion: Optional[str]
    fecha_ingreso: date
    valor: Decimal
    forma_pago: Optional[str]
    num_referencia: Optional[str]
    estado_pago: str
    observaciones: Optional[str]
    creado_por: Optional[int]
    creado_en: datetime

    class ConfigDict:
        from_attributes = True