import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.config import settings
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario
from app.models.operaciones import Gasto
from app.schemas.gasto import GastoCreate, GastoUpdate, GastoResponse
from app.services.ocr_service import OCRService

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_RECEIPT_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/tiff",
    "image/bmp",
    "application/pdf",
    "application/octet-stream",
}


@router.post("/gastos", response_model=GastoResponse, status_code=201)
def registrar_gasto(
    gasto: GastoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    existing = db.query(Gasto).filter(Gasto.hash_comprobante == gasto.hash_comprobante).first()
    if existing:
        raise HTTPException(status_code=400, detail="Gasto duplicado detectado")
    data = gasto.model_dump()
    if not data.get("reportado_por"):
        data["reportado_por"] = current_user.id
    db_gasto = Gasto(**data)
    db.add(db_gasto)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=404, detail="El viaje o vehículo especificado no existe")
    db.refresh(db_gasto)
    return db_gasto


@router.get("/gastos", response_model=List[GastoResponse])
def listar_gastos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return db.query(Gasto).all()


@router.get("/gastos/viaje/{viaje_id}", response_model=List[GastoResponse])
def listar_gastos_por_viaje(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return db.query(Gasto).filter(Gasto.viaje_id == viaje_id).all()


@router.get("/gastos/{gasto_id}", response_model=GastoResponse)
def obtener_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_gasto = db.query(Gasto).filter(Gasto.id == gasto_id).first()
    if not db_gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return db_gasto


@router.put(
    "/gastos/{gasto_id}",
    response_model=GastoResponse,
    dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))],
)
def actualizar_gasto(
    gasto_id: int,
    gasto: GastoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_gasto = db.query(Gasto).filter(Gasto.id == gasto_id).first()
    if not db_gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    update_data = gasto.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_gasto, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=404, detail="El viaje o vehículo especificado no existe")
    db.refresh(db_gasto)
    return db_gasto


@router.delete(
    "/gastos/{gasto_id}",
    status_code=204,
    dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))],
)
def eliminar_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_gasto = db.query(Gasto).filter(Gasto.id == gasto_id).first()
    if not db_gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    try:
        db.delete(db_gasto)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el gasto tiene registros asociados.",
        )
    return None


@router.post("/gastos/scan-receipt")
async def scan_receipt(
    file: UploadFile = File(...),
    viaje_id: Optional[int] = Form(None),
    vehiculo_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Escanea un comprobante y crea el Gasto asociado.

    Lee la imagen en memoria (sin archivos temporales), valida tipo y tamaño y
    delega el OCR. Si el motor no puede leer el recibo o no identifica el monto,
    responde 200 con campos nulos para que el usuario complete a mano: el OCR
    nunca provoca un 500.
    """
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_RECEIPT_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Formato no soportado. Usa JPG, PNG, WEBP, TIFF o PDF.",
        )

    max_bytes = settings.OCR_MAX_FILE_MB * 1024 * 1024
    file_bytes = await file.read(max_bytes + 1)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el límite de {settings.OCR_MAX_FILE_MB} MB.",
        )

    service = OCRService(db)
    try:
        return service.save_scan_result(
            file_bytes,
            vehiculo_id=vehiculo_id,
            viaje_id=viaje_id,
            reportado_por=current_user.id,
        )
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="El viaje o vehículo especificado no existe",
        )
    except Exception:
        logger.exception("Error inesperado procesando el comprobante")
        raise HTTPException(
            status_code=503,
            detail="No se pudo procesar el comprobante en este momento. Reintenta o regístralo manualmente.",
        )