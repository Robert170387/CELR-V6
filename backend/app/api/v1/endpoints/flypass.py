from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import RoleChecker, get_current_user
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario
from app.services.flypass_import import MAX_ARCHIVO_BYTES, importar_excel_flypass

router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))])


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
