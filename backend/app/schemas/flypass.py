from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


ESTADOS_VALIDOS = ("importado", "asignado_a_viaje", "sin_viaje", "ignorar")


class FlypassUpdate(BaseModel):
    viaje_id: int | None = None
    estado: str | None = None

    @field_validator("estado")
    @classmethod
    def _validar_estado(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ESTADOS_VALIDOS:
            raise ValueError(
                f"estado invalido: {v!r}. Validos: {ESTADOS_VALIDOS}"
            )
        return v


class FlypassListItem(BaseModel):
    id: int
    fecha_transaccion: datetime
    valor: Decimal
    num_transaccion_flypass: str
    nombre_peaje: str | None
    vehiculo_id: int
    placa: str | None
    viaje_id: int | None
    gasto_id: int | None
    legalizado_en_gastos: bool
    estado: str


class FlypassListResponse(BaseModel):
    data: list[FlypassListItem]
    total: int
