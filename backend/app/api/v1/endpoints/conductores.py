from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_ESCRITURA_MAESTROS
from app.db.session import get_db
from app.models.flota import Conductor, Usuario
from app.schemas.conductor import ConductorCreate, ConductorUpdate, ConductorResponse

router = APIRouter()


@router.post(
    "/conductores",
    response_model=ConductorResponse,
    status_code=201,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def crear_conductor(
    conductor: ConductorCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_conductor = Conductor(**conductor.model_dump())
    db.add(db_conductor)
    db.commit()
    db.refresh(db_conductor)
    return db_conductor


@router.get("/conductores", response_model=List[ConductorResponse])
def listar_conductores(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(Conductor)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/conductores/{conductor_id}", response_model=ConductorResponse)
def obtener_conductor(
    conductor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_conductor = db.query(Conductor).filter(Conductor.id == conductor_id).first()
    if not db_conductor:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    return db_conductor


@router.put(
    "/conductores/{conductor_id}",
    response_model=ConductorResponse,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def actualizar_conductor(
    conductor_id: int,
    conductor: ConductorUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_conductor = db.query(Conductor).filter(Conductor.id == conductor_id).first()
    if not db_conductor:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    update_data = conductor.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_conductor, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se pudo actualizar: la cédula ya existe o se viola una restricción.",
        )
    db.refresh(db_conductor)
    return db_conductor


@router.delete(
    "/conductores/{conductor_id}",
    status_code=204,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def eliminar_conductor(
    conductor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_conductor = db.query(Conductor).filter(Conductor.id == conductor_id).first()
    if not db_conductor:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    try:
        db.delete(db_conductor)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el conductor tiene viajes, asignaciones o usuarios asociados.",
        )
    return None