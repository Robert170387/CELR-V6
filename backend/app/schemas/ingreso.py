from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class IngresoCreate(BaseModel):
    # FASE A2 — una ODT puede tener 0..N ingresos; existen ingresos sin ODT
    viaje_id: Optional[int] = None
    vehiculo_id: int
    # FASE A2 — cliente que despacha (FK a proveedores) y receptor destino
    cliente_origen_id: Optional[int] = None
    receptor_destino: Optional[str] = Field(None, max_length=150)
    tipo_ingreso: str = Field(..., max_length=30)
    descripcion: Optional[str] = None
    fecha_ingreso: date
    valor: Decimal = Field(..., gt=0)
    forma_pago: Optional[str] = Field(None, max_length=30)
    num_referencia: Optional[str] = Field(None, max_length=50)
    estado_pago: str = Field("por_cobrar", max_length=20)
    observaciones: Optional[str] = None

    @validator("tipo_ingreso")
    def validate_tipo_ingreso(cls, v):
        allowed = {
            "anticipo_manifiesto", "saldo_flete", "ajuste_flete",
            "aporte_capital", "otro",
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
        allowed = {"por_cobrar", "recibido", "conciliado"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class IngresoUpdate(BaseModel):
    viaje_id: Optional[int] = None
    vehiculo_id: Optional[int] = None
    cliente_origen_id: Optional[int] = None
    receptor_destino: Optional[str] = Field(None, max_length=150)
    tipo_ingreso: Optional[str] = Field(None, max_length=30)
    descripcion: Optional[str] = None
    fecha_ingreso: Optional[date] = None
    valor: Optional[Decimal] = Field(None, gt=0)
    forma_pago: Optional[str] = Field(None, max_length=30)
    num_referencia: Optional[str] = Field(None, max_length=50)
    estado_pago: Optional[str] = Field(None, max_length=20)
    observaciones: Optional[str] = None

    @validator("tipo_ingreso")
    def validate_tipo_ingreso(cls, v):
        if v is None:
            return v
        allowed = {
            "anticipo_manifiesto", "saldo_flete", "ajuste_flete",
            "aporte_capital", "otro",
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
        if v is None:
            return v
        allowed = {"por_cobrar", "recibido", "conciliado"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class IngresoResponse(BaseModel):
    id: int
    viaje_id: Optional[int]
    vehiculo_id: int
    cliente_origen_id: Optional[int]
    receptor_destino: Optional[str]
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