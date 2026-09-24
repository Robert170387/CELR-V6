from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


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


class FlypassListResponse(BaseModel):
    data: list[FlypassListItem]
    total: int
