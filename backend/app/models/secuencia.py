from sqlalchemy import Column, Integer, String
from app.db.base_class import Base

class SecuenciaDocumento(Base):
    __tablename__ = "secuencias_documento"

    clave = Column(String(50), primary_key=True)
    valor = Column(Integer, nullable=False, default=0)