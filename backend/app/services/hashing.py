"""Hashing anti-duplicados de comprobantes para CELR v6.

Concentra la lógica de hash LÓGICO (independiente de los bytes de la imagen)
usada por el OCR y por la creación manual de gastos:

* Con factura  : MD5(NIT + NumFactura + Fecha + Monto)
* Sin factura  : MD5(NIT + Fecha + Monto + viaje_id)
* OCR sin datos : hash único irrepetible (no deduplicable, no bloquea captura)
"""
import hashlib
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import uuid4


def normalized_emisor(nit: Optional[str], proveedor: Optional[str]) -> Optional[str]:
    """Normaliza el emisor: NIT solo-dígitos, o razón social alfanumérica."""
    if nit:
        digits = "".join(char for char in nit if char.isdigit())
        if digits:
            return digits
    if proveedor:
        normalized = "".join(char for char in proveedor.lower() if char.isalnum())
        return normalized or None
    return None


def compute_logical_hash(
    nit: Optional[str] = None,
    proveedor: Optional[str] = None,
    fecha: Optional[date] = None,
    monto: Optional[Decimal] = None,
) -> Optional[str]:
    """MD5(NIT/Proveedor + Fecha + Monto). None si falta algún componente."""
    emisor = normalized_emisor(nit, proveedor)
    if not emisor or fecha is None or monto is None:
        return None
    if Decimal(monto) <= 0:
        return None

    monto_normalizado = Decimal(monto).quantize(Decimal("0.01"))
    key = f"{emisor}|{fecha.isoformat()}|{monto_normalizado}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def compute_factura_hash(
    nit: Optional[str],
    num_factura: str,
    fecha: date,
    monto: Decimal,
) -> str:
    """MD5(NIT + NumFactura + Fecha + Monto) para gastos con factura."""
    emisor = normalized_emisor(nit, None) or normalized_emisor(None, "s/f") or "s/f"
    monto_normalizado = Decimal(monto).quantize(Decimal("0.01"))
    key = f"{emisor}|{num_factura}|{fecha.isoformat()}|{monto_normalizado}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def compute_no_factura_hash(
    nit: Optional[str],
    proveedor: Optional[str],
    fecha: date,
    monto: Decimal,
    viaje_id: Optional[int],
) -> str:
    """MD5(NIT + Fecha + Monto + viaje_id) para gastos sin factura (ticket)."""
    emisor = normalized_emisor(nit, proveedor) or "s/f"
    monto_normalizado = Decimal(monto).quantize(Decimal("0.01"))
    viaje = viaje_id if viaje_id is not None else 0
    key = f"{emisor}|{fecha.isoformat()}|{monto_normalizado}|{viaje}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def compute_unique_hash() -> str:
    """Hash irrepetible para recibos sin datos legibles (no deduplicables)."""
    return hashlib.md5(f"sin-ocr|{uuid4().hex}".encode("utf-8")).hexdigest()


def compute_gasto_hash(
    *,
    num_factura: Optional[str],
    fecha: date,
    monto: Decimal,
    viaje_id: Optional[int],
    proveedor_nit: Optional[str] = None,
    proveedor_nombre: Optional[str] = None,
) -> str:
    """Hash según el caso: factura (tiene_num_factura) o ticket (sin factura)."""
    if num_factura:
        return compute_factura_hash(proveedor_nit, num_factura, fecha, monto)
    return compute_no_factura_hash(
        proveedor_nit, proveedor_nombre, fecha, monto, viaje_id
    )