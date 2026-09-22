from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.flota import Usuario
from app.models.ubicacion import Municipio
from app.schemas.municipio import MunicipioResponse

router = APIRouter()


@router.get("/municipios", response_model=List[MunicipioResponse])
def listar_municipios(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(Municipio)
        .order_by(Municipio.departamento, Municipio.municipio)
        .all()
    )