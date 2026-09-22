from sqlalchemy import Column, Integer, String, Index
from app.db.base_class import Base

class Municipio(Base):
    __tablename__ = "municipios"

    id = Column(Integer, primary_key=True, index=True)
    codigo_dane = Column(String(10), unique=True, nullable=False, index=True)
    departamento = Column(String(80), nullable=False)
    municipio = Column(String(80), nullable=False)

    __table_args__ = (
        Index("ix_municipios_departamento", "departamento"),
        Index("ix_municipios_departamento_municipio", "departamento", "municipio"),
    )