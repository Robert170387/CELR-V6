from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import RoleChecker, get_current_user
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.financiero import FlypassTransaccion
from app.models.flota import Usuario, Vehiculo
from app.models.operaciones import ViajeODT
from app.schemas.flypass import FlypassListItem, FlypassListResponse, FlypassUpdate
from app.services.flypass_import import MAX_ARCHIVO_BYTES, importar_excel_flypass

router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))])


@router.get("/flypass", response_model=FlypassListResponse)
def listar_flypass(
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    placa: str | None = Query(None),
    sin_odt: bool | None = Query(None),
    sin_gasto: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista transacciones Flypass con filtros y paginación."""
    consulta = db.query(FlypassTransaccion, Vehiculo.placa).outerjoin(
        Vehiculo,
        FlypassTransaccion.vehiculo_id == Vehiculo.id,
    )
    filtros = []
    if fecha_desde is not None:
        filtros.append(
            FlypassTransaccion.fecha_transaccion
            >= datetime.combine(fecha_desde, time.min).replace(tzinfo=timezone.utc)
        )
    if fecha_hasta is not None:
        filtros.append(
            FlypassTransaccion.fecha_transaccion
            <= datetime.combine(fecha_hasta, time.max).replace(tzinfo=timezone.utc)
        )
    if placa is not None:
        filtros.append(Vehiculo.placa == placa)
    if sin_odt is not None:
        filtros.append(
            FlypassTransaccion.viaje_id.is_(None)
            if sin_odt
            else FlypassTransaccion.viaje_id.is_not(None)
        )
    if sin_gasto is not None:
        filtros.append(
            FlypassTransaccion.gasto_id.is_(None)
            if sin_gasto
            else FlypassTransaccion.gasto_id.is_not(None)
        )
    if filtros:
        consulta = consulta.filter(*filtros)

    total = consulta.with_entities(func.count(FlypassTransaccion.id)).scalar() or 0
    filas = (
        consulta.order_by(
            FlypassTransaccion.fecha_transaccion.desc(),
            FlypassTransaccion.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "data": [
            {
                "id": transaccion.id,
                "fecha_transaccion": transaccion.fecha_transaccion,
                "valor": transaccion.valor,
                "num_transaccion_flypass": transaccion.num_transaccion_flypass,
                "nombre_peaje": transaccion.nombre_peaje,
                "vehiculo_id": transaccion.vehiculo_id,
                "placa": placa_resuelta,
                "viaje_id": transaccion.viaje_id,
                "gasto_id": transaccion.gasto_id,
                "legalizado_en_gastos": transaccion.legalizado_en_gastos,
                "estado": transaccion.estado,
            }
            for transaccion, placa_resuelta in filas
        ],
        "total": total,
    }


@router.post("/flypass/import")
async def importar_flypass(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Importa un Excel Flypass y devuelve el reporte de la operación."""
    nombre_archivo = file.filename or ""
    if not nombre_archivo.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Formato inválido: solo se admiten archivos .xlsx",
        )

    contenido = await file.read(MAX_ARCHIVO_BYTES + 1)
    await file.close()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="El archivo supera el límite de 5 MB",
        )

    try:
        return importar_excel_flypass(db, contenido, nombre_archivo)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/flypass/{flypass_id}", response_model=FlypassListItem)
def editar_flypass(
    flypass_id: int,
    update: FlypassUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Actualiza solo la asociación y el estado de una transacción Flypass."""
    flypass = db.query(FlypassTransaccion).filter(
        FlypassTransaccion.id == flypass_id
    ).first()
    if not flypass:
        raise HTTPException(status_code=404, detail="Flypass transaccion no encontrada")

    campos_provistos = update.model_fields_set
    if not campos_provistos:
        raise HTTPException(
            status_code=422,
            detail="Debe proveer al menos viaje_id o estado",
        )

    if "estado" in campos_provistos and update.estado is None:
        raise HTTPException(status_code=422, detail="estado no puede ser null")

    if "viaje_id" in campos_provistos and update.viaje_id is not None:
        viaje = (
            db.query(ViajeODT)
            .filter(
                ViajeODT.id == update.viaje_id,
                ViajeODT.eliminado_en.is_(None),
            )
            .first()
        )
        if not viaje:
            raise HTTPException(status_code=404, detail="Viaje no encontrado")
        if viaje.vehiculo_id != flypass.vehiculo_id:
            raise HTTPException(
                status_code=409,
                detail="El viaje pertenece a otro vehiculo",
            )

    if "viaje_id" in campos_provistos:
        flypass.viaje_id = update.viaje_id
        if "estado" not in campos_provistos:
            flypass.estado = (
                "asignado_a_viaje" if flypass.viaje_id is not None else "sin_viaje"
            )

    if "estado" in campos_provistos:
        flypass.estado = update.estado

    db.commit()
    db.refresh(flypass)

    placa = (
        db.query(Vehiculo.placa)
        .join(
            FlypassTransaccion,
            FlypassTransaccion.vehiculo_id == Vehiculo.id,
        )
        .filter(FlypassTransaccion.id == flypass.id)
        .scalar()
    )
    return {
        "id": flypass.id,
        "fecha_transaccion": flypass.fecha_transaccion,
        "valor": flypass.valor,
        "num_transaccion_flypass": flypass.num_transaccion_flypass,
        "nombre_peaje": flypass.nombre_peaje,
        "vehiculo_id": flypass.vehiculo_id,
        "placa": placa,
        "viaje_id": flypass.viaje_id,
        "gasto_id": flypass.gasto_id,
        "legalizado_en_gastos": flypass.legalizado_en_gastos,
        "estado": flypass.estado,
    }
