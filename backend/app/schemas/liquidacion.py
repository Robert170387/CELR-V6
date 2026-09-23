from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from decimal import Decimal


class LiquidacionCalculateResponse(BaseModel):
    viaje_id: int
    vehiculo_id: int
    conductor_id: int
    valor_flete_manifiesto: Optional[Decimal] = Field(None, ge=0)
    retefuente_valor: Optional[Decimal] = Field(None, ge=0)
    reteica_valor: Optional[Decimal] = Field(None, ge=0)
    flete_neto: Optional[Decimal] = Field(None, ge=0)
    total_gastos_empresa: Decimal = Field(default=0, ge=0)
    total_gastos_conductor: Decimal = Field(default=0, ge=0)
    total_anticipos: Decimal = Field(default=0, ge=0)
    total_ingresos: Decimal = Field(default=0, ge=0)
    comision_flete: Decimal = Field(default=0, ge=0)
    porcentaje_comision: Decimal = Field(default=0, ge=0, le=100)
    saldo_neto: Decimal = Field(default=0)


class LiquidacionCreate(BaseModel):
    conductor_id: int
    vehiculo_id: int
    periodo_inicio: date
    periodo_fin: date
    comision_flete: Decimal = Field(default=0, ge=0)
    porcentaje_comision: Optional[Decimal] = Field(None, ge=0, le=100)
    bonificaciones: Decimal = Field(default=0, ge=0)
    viaticos_reconocidos: Decimal = Field(default=0, ge=0)
    otros_haberes: Decimal = Field(default=0, ge=0)
    anticipos_entregados: Decimal = Field(default=0, ge=0)
    gastos_a_cargo_conductor: Decimal = Field(default=0, ge=0)
    prestamos: Decimal = Field(default=0, ge=0)
    otros_descuentos: Decimal = Field(default=0, ge=0)
    # FASE A2 — COMPENSADO_RC: inputs manuales adicionales
    salario_basico: Decimal = Field(default=0, ge=0)
    auxilio_transporte: Decimal = Field(default=0, ge=0)
    papeleria: Decimal = Field(default=0, ge=0)
    descuento_salud_pension: Decimal = Field(default=0, ge=0)
    viajes_ids: Optional[list[int]] = None
    estado: Optional[str] = Field("aprobado", max_length=20)
    fecha_pago: Optional[date] = None
    forma_pago_liquidacion: Optional[str] = Field(None, max_length=30)
    num_comprobante_pago: Optional[str] = Field(None, max_length=50)
    observaciones: Optional[str] = None
    creado_por: Optional[int] = None
    aprobado_por: Optional[int] = None