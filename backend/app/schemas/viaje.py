from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal


class ViajeCreate(BaseModel):
    num_manifiesto: Optional[str] = Field(None, max_length=30)
    vehiculo_id: int
    conductor_id: int
    origen: str = Field(..., max_length=100)
    destino: str = Field(..., max_length=100)
    origen_municipio_id: Optional[int] = None
    destino_municipio_id: Optional[int] = None
    empresa_manifiesto: Optional[str] = Field(None, max_length=150)
    # FASE A2 — cliente que despacha la carga (FK a proveedores) + fecha de manifiesto
    empresa_manifiesto_id: Optional[int] = None
    fecha_manifiesto: Optional[date] = None
    tipo_carga: Optional[str] = Field(None, max_length=100)
    peso_declarado_ton: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_origen: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_destino: Optional[Decimal] = Field(None, ge=0)
    valor_flete_manifiesto: Optional[Decimal] = Field(None, ge=0)
    retefuente_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    reteica_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    fecha_salida: date
    fecha_llegada: Optional[date] = None
    km_inicial: Optional[Decimal] = Field(None, ge=0)
    km_final: Optional[Decimal] = Field(None, ge=0)
    estado: Optional[str] = Field("en_curso", max_length=20)
    observaciones: Optional[str] = None
    # FASE A2 — inputs manuales de la ODT
    tipo_viaje: str = Field("nacional", max_length=20)
    otras_deducciones: Optional[Decimal] = Field(None, ge=0)
    anticipo_manifiesto: Optional[Decimal] = Field(None, ge=0)
    porcentaje_comision: Optional[Decimal] = Field(None, ge=0, le=100)

    @validator("tipo_viaje")
    def validate_tipo_viaje(cls, v):
        allowed = {"urbano", "nacional", "internacional", "vacio"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class ViajeUpdate(BaseModel):
    numero_odt: Optional[str] = Field(None, max_length=30)
    num_manifiesto: Optional[str] = Field(None, max_length=30)
    vehiculo_id: Optional[int] = None
    conductor_id: Optional[int] = None
    origen: Optional[str] = Field(None, max_length=100)
    destino: Optional[str] = Field(None, max_length=100)
    origen_municipio_id: Optional[int] = None
    destino_municipio_id: Optional[int] = None
    empresa_manifiesto: Optional[str] = Field(None, max_length=150)
    empresa_manifiesto_id: Optional[int] = None
    fecha_manifiesto: Optional[date] = None
    tipo_carga: Optional[str] = Field(None, max_length=100)
    peso_declarado_ton: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_origen: Optional[Decimal] = Field(None, ge=0)
    peso_bascula_destino: Optional[Decimal] = Field(None, ge=0)
    valor_flete_manifiesto: Optional[Decimal] = Field(None, ge=0)
    retefuente_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    reteica_porcentaje: Optional[Decimal] = Field(None, ge=0, le=100)
    fecha_salida: Optional[date] = None
    fecha_llegada: Optional[date] = None
    km_inicial: Optional[Decimal] = Field(None, ge=0)
    km_final: Optional[Decimal] = Field(None, ge=0)
    estado: Optional[str] = Field(None, max_length=20)
    observaciones: Optional[str] = None
    tipo_viaje: Optional[str] = Field(None, max_length=20)
    otras_deducciones: Optional[Decimal] = Field(None, ge=0)
    anticipo_manifiesto: Optional[Decimal] = Field(None, ge=0)
    porcentaje_comision: Optional[Decimal] = Field(None, ge=0, le=100)

    @validator("tipo_viaje")
    def validate_tipo_viaje(cls, v):
        if v is None:
            return v
        allowed = {"urbano", "nacional", "internacional", "vacio"}
        if v not in allowed:
            raise ValueError(f"debe ser uno de {allowed}")
        return v


class ViajeResponse(BaseModel):
    id: int
    numero_odt: str
    num_manifiesto: Optional[str]
    vehiculo_id: int
    conductor_id: int
    origen: str
    destino: str
    origen_municipio_id: Optional[int]
    destino_municipio_id: Optional[int]
    empresa_manifiesto: Optional[str]
    empresa_manifiesto_id: Optional[int]
    fecha_manifiesto: Optional[date]
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
    tipo_viaje: str
    otras_deducciones: Optional[Decimal]
    anticipo_manifiesto: Optional[Decimal]
    porcentaje_comision: Optional[Decimal]
    comision_conductor: Optional[Decimal]
    saldo_flete_esperado: Optional[Decimal]
    gastos_totales_viaje: Optional[Decimal]
    utilidad_neta_odt: Optional[Decimal]
    anio: Optional[int]
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


# --- R1: resumen completo de la ODT (GET /viajes/{id}/resumen) -------------
# Las tres listas repiten la misma envoltura y se diferencian solo en el tipo
# del item. Pydantic v1 no tiene genéricas discriminated, asi que son tres
# clases explicitas en vez de un ``Any``.

class GastoResumenItem(BaseModel):
    id: int
    categoria: str
    descripcion: Optional[str]
    fecha_gasto: date
    valor_total: Decimal
    responsable_pago: str
    asumido_por: str
    estado_pago: str

    class ConfigDict:
        from_attributes = True


class IngresoResumenItem(BaseModel):
    id: int
    tipo_ingreso: str
    descripcion: Optional[str]
    fecha_ingreso: date
    valor: Decimal
    estado_pago: str

    class ConfigDict:
        from_attributes = True


class PeajeResumenItem(BaseModel):
    id: int
    num_transaccion_flypass: str
    nombre_peaje: Optional[str]
    ciudad_peaje: Optional[str]
    fecha_transaccion: datetime
    valor: Decimal
    # Derivado: un peaje sin gasto cruzado sigue sin legalizar (regla de B6).
    legalizado: bool

    class ConfigDict:
        from_attributes = True


class ResumenGastos(BaseModel):
    items: List[GastoResumenItem]
    total: int
    truncado: bool


class ResumenIngresos(BaseModel):
    items: List[IngresoResumenItem]
    total: int
    truncado: bool


class ResumenPeajes(BaseModel):
    items: List[PeajeResumenItem]
    total: int
    truncado: bool


class ViajeResumenResponse(BaseModel):
    viaje_id: int
    numero_odt: str
    # false = algun snapshot nunca fue calculado. El resumen NO rellena con 0.
    snapshots_completos: bool
    # None cuando falta retefuente_valor o reteica_valor. Propagar, no inventar.
    total_deducibles: Optional[Decimal]
    viaje: ViajeResponse
    gastos: ResumenGastos
    ingresos: ResumenIngresos
    peajes: ResumenPeajes
    bloqueos: List[str]
    informativos: List[str]
