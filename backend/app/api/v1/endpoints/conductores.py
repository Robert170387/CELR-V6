from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_ESCRITURA_MAESTROS
from app.db.session import get_db
from app.models.flota import Conductor, Usuario
from app.schemas.conductor import ConductorCreate, ConductorResponse

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
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return db.query(Conductor).all()


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