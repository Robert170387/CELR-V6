from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_INGRESOS
from app.db.session import get_db
from app.models.flota import Usuario
from app.models.financiero import Ingreso
from app.schemas.ingreso import IngresoCreate, IngresoUpdate, IngresoResponse

router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_INGRESOS))])


@router.post("/ingresos", response_model=IngresoResponse, status_code=201)
def registrar_ingreso(
    ingreso: IngresoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    data = ingreso.model_dump()
    if not data.get("creado_por"):
        data["creado_por"] = current_user.id
    db_ingreso = Ingreso(**data)
    db.add(db_ingreso)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=404, detail="El viaje o vehículo especificado no existe")
    db.refresh(db_ingreso)
    return db_ingreso


@router.get("/ingresos", response_model=List[IngresoResponse])
def listar_ingresos(
    viaje_id: Optional[int] = Query(None, description="Filtrar por viaje"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(Ingreso)
    if viaje_id:
        query = query.filter(Ingreso.viaje_id == viaje_id)
    return query.all()


@router.get("/ingresos/{ingreso_id}", response_model=IngresoResponse)
def obtener_ingreso(
    ingreso_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_ingreso = db.query(Ingreso).filter(Ingreso.id == ingreso_id).first()
    if not db_ingreso:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    return db_ingreso


@router.put("/ingresos/{ingreso_id}", response_model=IngresoResponse)
def actualizar_ingreso(
    ingreso_id: int,
    ingreso: IngresoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_ingreso = db.query(Ingreso).filter(Ingreso.id == ingreso_id).first()
    if not db_ingreso:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    update_data = ingreso.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_ingreso, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=404, detail="El viaje o vehículo especificado no existe")
    db.refresh(db_ingreso)
    return db_ingreso


@router.delete("/ingresos/{ingreso_id}", status_code=204)
def eliminar_ingreso(
    ingreso_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_ingreso = db.query(Ingreso).filter(Ingreso.id == ingreso_id).first()
    if not db_ingreso:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    try:
        db.delete(db_ingreso)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el ingreso tiene registros asociados.",
        )
    return None