"""Servicio OCR de comprobantes para CELR v6.

Flujo:
    bytes de imagen -> motor OCR (pluggable) -> parser de campos -> hash lógico
    -> persistencia del Gasto.

Reglas clave:
* Si el motor falla o la confianza es baja, se devuelven campos nulos y el
  Gasto se crea como pendiente de captura manual. Nunca se lanza un 500.
* El hash anti-duplicados es LÓGICO: MD5(NIT/Proveedor + Fecha + Monto). No
  depende de los bytes de la imagen, por lo que un mismo recibo reenviado (o
  recomprimido) se detecta como duplicado.
* Si no hay datos suficientes para un hash lógico, se usa un hash único: no se
  puede deduplicar un recibo que no se pudo leer, pero tampoco se bloquea su
  captura.
"""

import hashlib
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.operaciones import Gasto
from app.services.ocr_engines import get_ocr_engine
from app.services.ocr_parser import extract_receipt_fields

logger = logging.getLogger(__name__)

OCR_VERSION = "CELR-v6-ocr-2.0.0"

_EMPTY_FIELDS: Dict[str, Any] = {
    "nit": None,
    "proveedor": None,
    "fecha_gasto": None,
    "valor_total": None,
    "num_factura": None,
    "cantidad_galones": None,
    "km_registro": None,
}


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _normalize_emisor(nit: Optional[str], proveedor: Optional[str]) -> Optional[str]:
    if nit:
        digits = "".join(char for char in nit if char.isdigit())
        if digits:
            return digits
    if proveedor:
        normalized = "".join(
            char for char in proveedor.lower() if char.isalnum()
        )
        return normalized or None
    return None


def compute_logical_hash(
    nit: Optional[str] = None,
    proveedor: Optional[str] = None,
    fecha: Optional[date] = None,
    monto: Optional[Decimal] = None,
) -> Optional[str]:
    """MD5(NIT/Proveedor + Fecha + Monto). None si falta algún componente."""
    emisor = _normalize_emisor(nit, proveedor)
    if not emisor or fecha is None or monto is None:
        return None
    if Decimal(monto) <= 0:
        return None

    monto_normalizado = Decimal(monto).quantize(Decimal("0.01"))
    key = f"{emisor}|{fecha.isoformat()}|{monto_normalizado}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def compute_unique_hash() -> str:
    """Hash irrepetible para recibos sin datos legibles (no deduplicables)."""
    return hashlib.md5(f"sin-ocr|{uuid4().hex}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------


def _as_float(value: Optional[Decimal]) -> Optional[float]:
    return float(value) if value is not None else None


def process_receipt_image(file_bytes: bytes) -> Dict[str, Any]:
    """Ejecuta el OCR y devuelve los campos extraídos (sin persistir)."""
    engine = get_ocr_engine()
    ocr = engine.extract(file_bytes)

    confiable = ocr.ok and ocr.confidence >= settings.OCR_MIN_CONFIDENCE
    fields = extract_receipt_fields(ocr.text) if confiable else dict(_EMPTY_FIELDS)

    valor_total: Optional[Decimal] = fields.get("valor_total")
    fecha_gasto: Optional[date] = fields.get("fecha_gasto")
    proveedor: Optional[str] = fields.get("proveedor")
    nit: Optional[str] = fields.get("nit")

    hash_logico = compute_logical_hash(
        nit=nit, proveedor=proveedor, fecha=fecha_gasto, monto=valor_total
    )
    hash_comprobante = hash_logico or compute_unique_hash()

    datos_ocr_json = {
        "motor": ocr.engine,
        "confianza": round(ocr.confidence, 2),
        "confiable": confiable,
        "error": ocr.error,
        "ocr_text": ocr.text,
        "campos_extraidos": {
            "nit": nit,
            "proveedor": proveedor,
            "fecha_gasto": fecha_gasto.isoformat() if fecha_gasto else None,
            "valor_total": _as_float(valor_total),
            "num_factura": fields.get("num_factura"),
            "cantidad_galones": _as_float(fields.get("cantidad_galones")),
            "km_registro": _as_float(fields.get("km_registro")),
        },
        "hash_logico": hash_logico,
        "procesado_en": datetime.now().isoformat(),
        "version_modelo": OCR_VERSION,
    }

    return {
        "hash_comprobante": hash_comprobante,
        "hash_logico": hash_logico,
        "nit": nit,
        "proveedor": proveedor,
        "num_factura": fields.get("num_factura"),
        "fecha_gasto": fecha_gasto,
        "valor_total": _as_float(valor_total),
        "cantidad_galones": _as_float(fields.get("cantidad_galones")),
        "km_registro": _as_float(fields.get("km_registro")),
        "confianza": round(ocr.confidence, 2),
        "datos_ocr_json": datos_ocr_json,
    }


def _empty_result() -> Dict[str, Any]:
    """Resultado neutro cuando el OCR revienta de forma inesperada."""
    return {
        "hash_comprobante": compute_unique_hash(),
        "hash_logico": None,
        "nit": None,
        "proveedor": None,
        "num_factura": None,
        "fecha_gasto": None,
        "valor_total": None,
        "cantidad_galones": None,
        "km_registro": None,
        "confianza": 0.0,
        "datos_ocr_json": {
            "motor": get_ocr_engine().name,
            "confianza": 0.0,
            "confiable": False,
            "error": "Fallo inesperado del motor OCR",
            "ocr_text": "",
            "campos_extraidos": dict(_EMPTY_FIELDS),
            "hash_logico": None,
            "procesado_en": datetime.now().isoformat(),
            "version_modelo": OCR_VERSION,
        },
    }


class OCRService:
    def __init__(self, db: Session):
        self.db = db

    def save_scan_result(
        self,
        file_bytes: bytes,
        viaje_id: int,
        vehiculo_id: int,
        reportado_por: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Procesa el recibo y persiste el Gasto. Devuelve el resultado + gasto_id."""
        try:
            result = process_receipt_image(file_bytes)
        except Exception:  # pragma: no cover - red de seguridad
            logger.exception("OCR falló de forma inesperada; se crea gasto pendiente")
            result = _empty_result()

        existing = (
            self.db.query(Gasto)
            .filter(Gasto.hash_comprobante == result["hash_comprobante"])
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gasto duplicado detectado",
            )

        valor_total = result["valor_total"]
        gasto = Gasto(
            viaje_id=viaje_id,
            vehiculo_id=vehiculo_id,
            categoria="combustible",
            num_factura=result["num_factura"],
            fecha_gasto=result["fecha_gasto"] or date.today(),
            valor_total=Decimal(str(valor_total)) if valor_total is not None else Decimal("0"),
            cantidad_galones=(
                Decimal(str(result["cantidad_galones"]))
                if result["cantidad_galones"] is not None
                else None
            ),
            km_registro=(
                Decimal(str(result["km_registro"]))
                if result["km_registro"] is not None
                else None
            ),
            hash_comprobante=result["hash_comprobante"],
            datos_ocr_json=result["datos_ocr_json"],
            estado_validacion="observado" if valor_total is not None else "pendiente",
            tiene_num_factura=bool(result["num_factura"]),
            reportado_por=reportado_por,
        )
        self.db.add(gasto)
        self.db.commit()
        self.db.refresh(gasto)

        return {"gasto_id": gasto.id, **result}
