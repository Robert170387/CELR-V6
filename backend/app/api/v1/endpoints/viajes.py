from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario
from app.models.operaciones import ViajeODT
from app.schemas.viaje import ViajeCreate, ViajeUpdate, ViajeResponse

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
    db_viaje = ViajeODT(**data)
    db.add(db_viaje)
    db.commit()
    db.refresh(db_viaje)
    return db_viaje


@router.get("/viajes", response_model=List[ViajeResponse])
def listar_viajes(
    activo: bool = True,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(ViajeODT)
    query = query.filter(ViajeODT.estado == "en_curso") if activo else query
    return query.all()


@router.get("/viajes/{viaje_id}", response_model=ViajeResponse)
def obtener_viaje(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_viaje = db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
    if not db_viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return db_viaje


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
    db_viaje = db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
    if not db_viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    update_data = viaje.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_viaje, key, value)
    try:
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
    db_viaje = db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
    if not db_viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    try:
        db.delete(db_viaje)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el viaje tiene gastos, ingresos o liquidaciones asociados.",
        )
    return None


@router.get("/viajes/vehiculo/{vehiculo_id}", response_model=List[ViajeResponse])
def listar_viajes_por_vehiculo(
    vehiculo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return db.query(ViajeODT).filter(ViajeODT.vehiculo_id == vehiculo_id).all()


@router.get("/viajes/conductor/{conductor_id}", response_model=List[ViajeResponse])
def listar_viajes_por_conductor(
    conductor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return db.query(ViajeODT).filter(ViajeODT.conductor_id == conductor_id).all()