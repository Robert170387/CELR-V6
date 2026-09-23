from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class GastoCreate(BaseModel):
    viaje_id: Optional[int] = None
    vehiculo_id: int
    proveedor_id: Optional[int] = None
    categoria: str = Field(..., max_length=80)
    descripcion: Optional[str] = None
    num_factura: Optional[str] = Field(None, max_length=50)
    fecha_gasto: date
    valor_total: Decimal = Field(..., gt=0)
    km_registro: Optional[Decimal] = Field(None, ge=0)
    cantidad_galones: Optional[Decimal] = Field(None, ge=0)
    precio_por_galon: Optional[Decimal] = Field(None, ge=0)
    ciudad_abastecimiento: Optional[str] = Field(None, max_length=80)
    ciudad_abastecimiento_municipio_id: Optional[int] = None
    responsable_pago: str = Field(default="conductor", max_length=50)
    asumido_por: str = Field(default="empresa", max_length=50)
    tarjeta_id: Optional[int] = None
    tiene_num_factura: bool = False
    url_imagen: Optional[str] = None
    datos_ocr_json: Optional[dict] = None
    estado_validacion: Optional[str] = Field("pendiente", max_length=20)
    # FASE A2 — pago y legalizacion del gasto
    metodo_pago: str = Field(default="efectivo", max_length=20)
    estado_pago: str = Field(default="pagado", max_length=20)

    @validator("responsable_pago")
    def validate_responsable_pago(cls, v):
        allowed = {"conductor", "empresa", "tarjeta_empresa"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("asumido_por")
    def validate_asumido_por(cls, v):
        allowed = {"empresa", "owner", "conductor"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("metodo_pago")
    def validate_metodo_pago(cls, v):
        allowed = {"efectivo", "tarjeta", "transferencia", "tag"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("estado_pago")
    def validate_estado_pago(cls, v):
        allowed = {"pagado", "pendiente_por_pagar", "legalizado"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class GastoUpdate(BaseModel):
    viaje_id: Optional[int] = None
    vehiculo_id: Optional[int] = None
    proveedor_id: Optional[int] = None
    categoria: Optional[str] = Field(None, max_length=80)
    descripcion: Optional[str] = None
    num_factura: Optional[str] = Field(None, max_length=50)
    fecha_gasto: Optional[date] = None
    valor_total: Optional[Decimal] = Field(None, ge=0)
    km_registro: Optional[Decimal] = Field(None, ge=0)
    cantidad_galones: Optional[Decimal] = Field(None, ge=0)
    precio_por_galon: Optional[Decimal] = Field(None, ge=0)
    ciudad_abastecimiento: Optional[str] = Field(None, max_length=80)
    ciudad_abastecimiento_municipio_id: Optional[int] = None
    responsable_pago: Optional[str] = Field(None, max_length=50)
    asumido_por: Optional[str] = Field(None, max_length=50)
    tarjeta_id: Optional[int] = None
    tiene_num_factura: Optional[bool] = None
    url_imagen: Optional[str] = None
    datos_ocr_json: Optional[dict] = None
    estado_validacion: Optional[str] = Field(None, max_length=20)
    metodo_pago: Optional[str] = Field(None, max_length=20)
    estado_pago: Optional[str] = Field(None, max_length=20)

    @validator("responsable_pago")
    def validate_responsable_pago(cls, v):
        allowed = {"conductor", "empresa", "tarjeta_empresa"}
        if v is not None and v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("asumido_por")
    def validate_asumido_por(cls, v):
        allowed = {"empresa", "owner", "conductor"}
        if v is not None and v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("metodo_pago")
    def validate_metodo_pago(cls, v):
        allowed = {"efectivo", "tarjeta", "transferencia", "tag"}
        if v is not None and v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v

    @validator("estado_pago")
    def validate_estado_pago(cls, v):
        allowed = {"pagado", "pendiente_por_pagar", "legalizado"}
        if v is not None and v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class GastoResponse(BaseModel):
    id: int
    viaje_id: Optional[int]
    vehiculo_id: int
    proveedor_id: Optional[int]
    categoria: str
    descripcion: Optional[str]
    num_factura: Optional[str]
    fecha_gasto: date
    valor_total: Decimal
    km_registro: Optional[Decimal]
    cantidad_galones: Optional[Decimal]
    precio_por_galon: Optional[Decimal]
    ciudad_abastecimiento: Optional[str]
    ciudad_abastecimiento_municipio_id: Optional[int]
    responsable_pago: str
    asumido_por: str
    tarjeta_id: Optional[int]
    tiene_num_factura: bool
    hash_comprobante: str
    url_imagen: Optional[str]
    datos_ocr_json: Optional[dict]
    estado_validacion: str
    aprobado_por: Optional[int]
    fecha_aprobacion: Optional[datetime]
    motivo_rechazo: Optional[str]
    reportado_por: Optional[int]
    metodo_pago: str
    estado_pago: str
    legalizado: Optional[bool]
    creado_en: datetime
    actualizado_en: datetime

    class ConfigDict:
        from_attributes = True
