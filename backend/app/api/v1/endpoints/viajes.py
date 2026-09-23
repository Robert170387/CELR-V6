from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario
from app.models.operaciones import ViajeODT
from app.schemas.viaje import ViajeCreate, ViajeUpdate, ViajeResponse
from app.services.operaciones import bloqueos_cierre_odt, recalcular_viaje, validar_manifiesto_unico
from app.services.secuencias import siguiente_consecutivo
from app.services.ubicacion import autocompletar_municipio_texto, autocompletar_municipio_orm

router = APIRouter()


@router.post("/viajes", response_model=ViajeResponse, status_code=201)
def crear_viaje(
    viaje: ViajeCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    data = viaje.model_dump()
    if not data.get("creado_por"):
        data["creado_por"] = current_user.id
    autocompletar_municipio_texto(db, data, "origen", "origen_municipio_id")
    autocompletar_municipio_texto(db, data, "destino", "destino_municipio_id")
    # Regla 2: un numero de manifiesto no se duplica por empresa/cliente
    validar_manifiesto_unico(db, data.get("num_manifiesto"), data.get("empresa_manifiesto_id"))
    anio = data["fecha_salida"].year if data.get("fecha_salida") else datetime.now().year
    consecutivo = siguiente_consecutivo(db, f"odt_{anio}")
    data["numero_odt"] = f"ODT-{anio}-{consecutivo:06d}"
    db_viaje = ViajeODT(**data)
    db.add(db_viaje)
    db.flush()
    # Formulas FASE A2 server-side (retenciones, comision, saldo, utilidad):
    # el cliente nunca envia estos calculados
    recalcular_viaje(db, db_viaje)
    db.commit()
    db.refresh(db_viaje)
    return db_viaje


@router.get("/viajes", response_model=List[ViajeResponse])
def listar_viajes(
    activo: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(ViajeODT).filter(ViajeODT.eliminado_en.is_(None))
    query = query.filter(ViajeODT.estado == "en_curso") if activo else query
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/viajes/{viaje_id}", response_model=ViajeResponse)
def obtener_viaje(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_viaje = (
        db.query(ViajeODT)
        .filter(ViajeODT.id == viaje_id, ViajeODT.eliminado_en.is_(None))
        .first()
    )
    if not db_viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return db_viaje


@router.get("/viajes/{viaje_id}/bloqueos-cierre")
def obtener_bloqueos_cierre_odt(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Regla 4 (FASE A2): bloqueos para finalizar la ODT.

    Devuelve los impedimentos vigentes (saldo flete esperado sin cubrir y
    peajes Flypass pendientes de legalizar). Lista vacia = la ODT es cercable.
    """
    db_viaje = (
        db.query(ViajeODT)
        .filter(ViajeODT.id == viaje_id, ViajeODT.eliminado_en.is_(None))
        .first()
    )
    if not db_viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    bloqueos = bloqueos_cierre_odt(db, db_viaje)
    return {
        "viaje_id": db_viaje.id,
        "numero_odt": db_viaje.numero_odt,
        "cercable": len(bloqueos) == 0,
        "bloqueos": bloqueos,
    }


@router.put(
    "/viajes/{viaje_id}",
    response_model=ViajeResponse,
    dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))],
)
def actualizar_viaje(
    viaje_id: int,
    viaje: ViajeUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_viaje = (
        db.query(ViajeODT)
        .filter(ViajeODT.id == viaje_id, ViajeODT.eliminado_en.is_(None))
        .first()
    )
    if not db_viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    update_data = viaje.model_dump(exclude_unset=True)
    if "numero_odt" in update_data and current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo el rol admin puede corregir el número de ODT")
    for key, value in update_data.items():
        setattr(db_viaje, key, value)
    autocompletar_municipio_orm(db, db_viaje, "origen", "origen_municipio_id")
    autocompletar_municipio_orm(db, db_viaje, "destino", "destino_municipio_id")
    # Regla 2 (excluye el propio viaje) + recálculo FASE A2 antes del commit
    validar_manifiesto_unico(
        db, db_viaje.num_manifiesto, db_viaje.empresa_manifiesto_id, viaje_id=db_viaje.id
    )
    # El flush() es el que revienta la FK si vehiculo/conductor no existe:
    # flush + commit deben ir dentro del try para mapear IntegrityError -> 404.
    try:
        db.flush()
        recalcular_viaje(db, db_viaje)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="El vehículo o conductor especificado no existe",
        )
    db.refresh(db_viaje)
    return db_viaje


@router.delete(
    "/viajes/{viaje_id}",
    status_code=204,
    dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))],
)
def eliminar_viaje(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_viaje = (
        db.query(ViajeODT)
        .filter(ViajeODT.id == viaje_id, ViajeODT.eliminado_en.is_(None))
        .first()
    )
    if not db_viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    db_viaje.eliminado_en = datetime.now(timezone.utc)
    db_viaje.eliminado_por = current_user.id
    db.commit()
    return None


@router.get("/viajes/vehiculo/{vehiculo_id}", response_model=List[ViajeResponse])
def listar_viajes_por_vehiculo(
    vehiculo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(ViajeODT)
        .filter(ViajeODT.vehiculo_id == vehiculo_id, ViajeODT.eliminado_en.is_(None))
        .all()
    )


@router.get("/viajes/conductor/{conductor_id}", response_model=List[ViajeResponse])
def listar_viajes_por_conductor(
    conductor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(ViajeODT)
        .filter(ViajeODT.conductor_id == conductor_id, ViajeODT.eliminado_en.is_(None))
        .all()
    )