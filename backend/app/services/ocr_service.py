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

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.operaciones import Gasto, ViajeODT
from app.services.hashing import (
    normalized_emisor,
    compute_logical_hash,
    compute_unique_hash,
)
from app.services.ocr_engines import get_ocr_engine
from app.services.ocr_parser import extract_receipt_fields
from app.services.operaciones import recalcular_viaje

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
# Hashing (extraído a app/services/hashing.py; acá solo se re-exporta)
# ---------------------------------------------------------------------------


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
        vehiculo_id: int,
        viaje_id: Optional[int] = None,
        reportado_por: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Procesa el recibo y persiste el Gasto. Devuelve el resultado + gasto_id."""
        try:
            result = process_receipt_image(file_bytes)
        except Exception:  # pragma: no cover - red de seguridad
            logger.exception("OCR falló de forma inesperada; se crea gasto pendiente")
            result = _empty_result()

        # Hash canónico SERVER-SIDE (misma regla que la captura manual):
        # con factura MD5(NIT+NumFactura+Fecha+Monto); sin factura MD5(NIT+Fecha+Monto+viaje_id).
        # Si el OCR no extrajo monto, se conserva un hash único irrepetible.
        from app.services.hashing import compute_gasto_hash

        num_factura = result.get("num_factura")
        fecha_efectiva = result.get("fecha_gasto") or date.today()
        valor = result.get("valor_total")
        if valor is not None:
            hash_comprobante = compute_gasto_hash(
                num_factura=num_factura,
                fecha=fecha_efectiva,
                monto=Decimal(str(valor)),
                viaje_id=viaje_id,
                proveedor_nit=result.get("nit"),
                proveedor_nombre=result.get("proveedor"),
            )
        else:
            hash_comprobante = result["hash_comprobante"]
        result["hash_comprobante"] = hash_comprobante

        # Solo los gastos vivos cuentan como duplicado (consistente con POST /gastos).
        existing = (
            self.db.query(Gasto)
            .filter(Gasto.hash_comprobante == hash_comprobante, Gasto.eliminado_en.is_(None))
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
            hash_comprobante=hash_comprobante,
            datos_ocr_json=result["datos_ocr_json"],
            estado_validacion="observado" if valor_total is not None else "pendiente",
            tiene_num_factura=bool(result["num_factura"]),
            reportado_por=reportado_por,
        )
        self.db.add(gasto)
        # FASE A2: mantener los snapshots de la ODT al dia (gastos_totales_viaje)
        if viaje_id:
            viaje = self.db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
            if viaje:
                self.db.flush()
                recalcular_viaje(self.db, viaje)
        self.db.commit()
        self.db.refresh(gasto)

        return {"gasto_id": gasto.id, **result}
