from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_ESCRITURA_MAESTROS
from app.db.session import get_db
from app.models.flota import Usuario
from app.models.operaciones import Proveedor
from app.schemas.proveedor import ProveedorCreate, ProveedorUpdate, ProveedorResponse
from app.services.ubicacion import autocompletar_municipio_texto, autocompletar_municipio_orm

router = APIRouter()


@router.post(
    "/proveedores",
    response_model=ProveedorResponse,
    status_code=201,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def crear_proveedor(
    proveedor: ProveedorCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    data = proveedor.model_dump()
    autocompletar_municipio_texto(db, data, "ciudad", "ciudad_municipio_id")
    db_proveedor = Proveedor(**data)
    db.add(db_proveedor)
    db.commit()
    db.refresh(db_proveedor)
    return db_proveedor


@router.get("/proveedores", response_model=List[ProveedorResponse])
def listar_proveedores(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(Proveedor)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/proveedores/{proveedor_id}", response_model=ProveedorResponse)
def obtener_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_proveedor = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not db_proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return db_proveedor


@router.put(
    "/proveedores/{proveedor_id}",
    response_model=ProveedorResponse,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def actualizar_proveedor(
    proveedor_id: int,
    proveedor: ProveedorUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_proveedor = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not db_proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    update_data = proveedor.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_proveedor, key, value)
    autocompletar_municipio_orm(db, db_proveedor, "ciudad", "ciudad_municipio_id")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se pudo actualizar: el NIT ya existe o se viola una restricción.",
        )
    db.refresh(db_proveedor)
    return db_proveedor


@router.delete(
    "/proveedores/{proveedor_id}",
    status_code=204,
    dependencies=[Depends(RoleChecker(ROLES_ESCRITURA_MAESTROS))],
)
def eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db_proveedor = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not db_proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    try:
        db.delete(db_proveedor)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el proveedor tiene gastos u otros registros asociados.",
        )
    return None