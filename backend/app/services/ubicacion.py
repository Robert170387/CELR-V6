"""Autocompletado del texto legible de ciudad a partir del *_municipio_id."""
from sqlalchemy.orm import Session

from app.models.ubicacion import Municipio


def autocompletar_municipio_texto(db: Session, data: dict, texto_col: str, municipio_id_col: str) -> None:
    """Si data contiene municipio_id_col, rellena texto_col con 'municipio (departamento)'."""
    municipio_id = data.get(municipio_id_col)
    if municipio_id is None:
        return
    municipio = db.query(Municipio).filter(Municipio.id == municipio_id).first()
    if municipio:
        data[texto_col] = f"{municipio.municipio} ({municipio.departamento})"


def autocompletar_municipio_orm(db: Session, obj, texto_attr: str, municipio_id_attr: str) -> None:
    """Version para objetos ORM ya persistidos (actualizaciones)."""
    municipio_id = getattr(obj, municipio_id_attr)
    if municipio_id is None:
        return
    municipio = db.query(Municipio).filter(Municipio.id == municipio_id).first()
    if municipio:
        setattr(obj, texto_attr, f"{municipio.municipio} ({municipio.departamento})")