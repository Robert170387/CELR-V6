import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.config import settings
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario, Vehiculo
from app.models.operaciones import Gasto, ViajeODT
from app.schemas.gasto import GastoCreate, GastoUpdate, GastoResponse
from app.services.ocr_service import OCRService
from app.services.operaciones import recalcular_viaje
from app.services.ubicacion import autocompletar_municipio_texto, autocompletar_municipio_orm

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
    data = gasto.model_dump()
    autocompletar_municipio_texto(db, data, "ciudad_abastecimiento", "ciudad_abastecimiento_municipio_id")
    hash_comprobante = _calcular_hash_gasto(db, data, viaje_id=data.get("viaje_id"))
    data["hash_comprobante"] = hash_comprobante
    existing = db.query(Gasto).filter(Gasto.hash_comprobante == hash_comprobante).first()
    if existing:
        raise HTTPException(status_code=400, detail="Gasto duplicado detectado")
    if not data.get("reportado_por"):
        data["reportado_por"] = current_user.id
    estado = _estado_validacion_combustible(db, data)
    if estado:
        data["estado_validacion"] = estado
    db_gasto = Gasto(**data)
    db.add(db_gasto)
    _aplicar_km_actual(db, data)
    _recalcular_viaje_de_gasto(db, data.get("viaje_id"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=404, detail="El viaje o vehículo especificado no existe")
    db.refresh(db_gasto)
    return db_gasto


def _estado_validacion_combustible(db: Session, data: dict) -> Optional[str]:
    """Detecta inconsistencias en un gasto de combustible.

    - Diferencia aritmética (cantidad_galones * precio_por_galon) vs valor_total
      mayor a ±100 COP.
    - km_registro menor al km_actual vigente del vehículo.

    Nunca rechaza el registro; devuelve 'observado' para que quien aprueba lo revise.
    """
    if data.get("categoria") != "combustible":
        return None
    cant = data.get("cantidad_galones")
    precio = data.get("precio_por_galon")
    valor = data.get("valor_total")
    if cant is not None and precio is not None and valor is not None:
        try:
            esperado = Decimal(cant) * Decimal(precio)
            if abs(esperado - Decimal(valor)) > Decimal("100"):
                return "observado"
        except (InvalidOperation, TypeError, ValueError):
            pass
    km = data.get("km_registro")
    vehiculo_id = data.get("vehiculo_id")
    if km is not None and vehiculo_id:
        try:
            veh = db.query(Vehiculo).filter(Vehiculo.id == vehiculo_id).first()
            if veh and Decimal(km) < veh.km_actual:
                return "observado"
        except (InvalidOperation, TypeError, ValueError):
            pass
    return None


def _aplicar_km_actual(db: Session, data: dict) -> None:
    """Actualiza vehiculo.km_actual con el km_registro del gasto de combustible.

    Solo cuando km_registro es MAYOR que el km_actual vigente (nunca retrocede
    el odómetro). Misma transacción del commit del gasto.
    """
    if data.get("categoria") != "combustible":
        return
    km = data.get("km_registro")
    vehiculo_id = data.get("vehiculo_id")
    if km is None or not vehiculo_id:
        return
    veh = db.query(Vehiculo).filter(Vehiculo.id == vehiculo_id).first()
    if veh and Decimal(km) > veh.km_actual:
        veh.km_actual = Decimal(km)


def _recalcular_viaje_de_gasto(db: Session, viaje_id: Optional[int]) -> None:
    """Recalcula la ODT vinculada tras crear/editar/eliminar un gasto.

    Los snapshots de la ODT (gastos_totales_viaje, utilidad_neta_odt, comision)
    dependen de los gastos; FASE A2 los mantiene al dia en la misma transaccion.
    """
    if not viaje_id:
        return
    viaje = db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
    if not viaje:
        return
    db.flush()
    recalcular_viaje(db, viaje)


def _calcular_hash_gasto(db: Session, data: dict, viaje_id: Optional[int]) -> str:
    """Hash anti-duplicados calculado siempre SERVER-SIDE (Bloque 3).

    Con factura (num_factura): MD5(NIT + NumFactura + Fecha + Monto).
    Sin factura: MD5(NIT + Fecha + Monto + viaje_id).
    """
    from app.models.operaciones import Proveedor as ProveedorModel
    from app.services.hashing import compute_gasto_hash

    proveedor_nit: Optional[str] = None
    proveedor_nombre: Optional[str] = None
    if data.get("proveedor_id"):
        proveedor = db.query(ProveedorModel).filter(ProveedorModel.id == data["proveedor_id"]).first()
        if proveedor:
            proveedor_nit = proveedor.nit
            proveedor_nombre = proveedor.razon_social or proveedor.nombre_comercial
    return compute_gasto_hash(
        num_factura=data.get("num_factura"),
        fecha=data["fecha_gasto"],
        monto=data["valor_total"],
        viaje_id=viaje_id,
        proveedor_nit=proveedor_nit,
        proveedor_nombre=proveedor_nombre,
    )


@router.get("/gastos", response_model=List[GastoResponse])
def listar_gastos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(Gasto).filter(Gasto.eliminado_en.is_(None))
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/gastos/viaje/{viaje_id}", response_model=List[GastoResponse])
def listar_gastos_por_viaje(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(Gasto)
        .filter(Gasto.viaje_id == viaje_id, Gasto.eliminado_en.is_(None))
        .all()
    )


@router.get("/gastos/{gasto_id}", response_model=GastoResponse)
def obtener_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_gasto = (
        db.query(Gasto)
        .filter(Gasto.id == gasto_id, Gasto.eliminado_en.is_(None))
        .first()
    )
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
    db_gasto = (
        db.query(Gasto)
        .filter(Gasto.id == gasto_id, Gasto.eliminado_en.is_(None))
        .first()
    )
    if not db_gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    update_data = gasto.model_dump(exclude_unset=True)
    viaje_original_id = db_gasto.viaje_id
    for key, value in update_data.items():
        setattr(db_gasto, key, value)
    autocompletar_municipio_orm(db, db_gasto, "ciudad_abastecimiento", "ciudad_abastecimiento_municipio_id")
    campos_hash = {"num_factura", "fecha_gasto", "valor_total", "proveedor_id", "viaje_id"}
    if campos_hash.intersection(update_data.keys()):
        nuevo_hash = _calcular_hash_gasto(
            db,
            {
                "num_factura": db_gasto.num_factura,
                "fecha_gasto": db_gasto.fecha_gasto,
                "valor_total": db_gasto.valor_total,
                "proveedor_id": db_gasto.proveedor_id,
            },
            viaje_id=db_gasto.viaje_id,
        )
        dupe = (
            db.query(Gasto)
            .filter(
                Gasto.hash_comprobante == nuevo_hash,
                Gasto.id != db_gasto.id,
            )
            .first()
        )
        if dupe:
            raise HTTPException(status_code=409, detail="Gasto duplicado detectado")
        db_gasto.hash_comprobante = nuevo_hash
    efectivo = {
        "categoria": update_data.get("categoria", db_gasto.categoria),
        "valor_total": update_data.get("valor_total", db_gasto.valor_total),
        "cantidad_galones": update_data.get("cantidad_galones", db_gasto.cantidad_galones),
        "precio_por_galon": update_data.get("precio_por_galon", db_gasto.precio_por_galon),
        "vehiculo_id": update_data.get("vehiculo_id", db_gasto.vehiculo_id),
        "km_registro": update_data.get("km_registro", db_gasto.km_registro),
    }
    estado = _estado_validacion_combustible(db, efectivo)
    if estado:
        db_gasto.estado_validacion = estado
    _aplicar_km_actual(db, efectivo)
    # Recalcular la ODT vincula entrante y, si se cambio de viaje, tambien la anterior
    for vid in {db_gasto.viaje_id, viaje_original_id}:
        _recalcular_viaje_de_gasto(db, vid)
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
    db_gasto = (
        db.query(Gasto)
        .filter(Gasto.id == gasto_id, Gasto.eliminado_en.is_(None))
        .first()
    )
    if not db_gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    db_gasto.eliminado_en = datetime.now(timezone.utc)
    db_gasto.eliminado_por = current_user.id
    _recalcular_viaje_de_gasto(db, db_gasto.viaje_id)
    db.commit()
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