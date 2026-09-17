from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_ESCRITURA_MAESTROS
from app.db.session import get_db
from app.models.flota import Usuario, Vehiculo
from app.schemas.vehiculo import VehiculoCreate, VehiculoUpdate, VehiculoResponse

router = APIRouter()


@router.post(
    "/vehiculos",
    response_model=VehiculoResponse,
    status_code=201,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def crear_vehiculo(
    vehiculo: VehiculoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_vehiculo = Vehiculo(**vehiculo.model_dump())
    db.add(db_vehiculo)
    db.commit()
    db.refresh(db_vehiculo)
    return db_vehiculo


@router.get("/vehiculos", response_model=List[VehiculoResponse])
def listar_vehiculos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return db.query(Vehiculo).all()


@router.get("/vehiculos/{vehiculo_id}", response_model=VehiculoResponse)
def obtener_vehiculo(
    vehiculo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_vehiculo = db.query(Vehiculo).filter(Vehiculo.id == vehiculo_id).first()
    if not db_vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return db_vehiculo


@router.put(
    "/vehiculos/{vehiculo_id}",
    response_model=VehiculoResponse,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def actualizar_vehiculo(
    vehiculo_id: int,
    vehiculo: VehiculoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_vehiculo = db.query(Vehiculo).filter(Vehiculo.id == vehiculo_id).first()
    if not db_vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    update_data = vehiculo.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_vehiculo, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se pudo actualizar: la placa ya existe o se viola una restricción.",
        )
    db.refresh(db_vehiculo)
    return db_vehiculo


@router.delete(
    "/vehiculos/{vehiculo_id}",
    status_code=204,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def eliminar_vehiculo(
    vehiculo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_vehiculo = db.query(Vehiculo).filter(Vehiculo.id == vehiculo_id).first()
    if not db_vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    try:
        db.delete(db_vehiculo)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el vehículo tiene viajes, gastos u otros registros asociados.",
        )
    return None