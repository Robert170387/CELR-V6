from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, ForeignKey, Text, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.core.roles import SQL_CHECK_ROL

class Vehiculo(Base):
    __tablename__ = "vehiculos"
    
    id = Column(Integer, primary_key=True, index=True)
    placa = Column(String(10), unique=True, nullable=False, index=True)
    marca = Column(String(50), nullable=False)
    modelo = Column(String(50))
    anio = Column(Integer)
    tipo_carroceria = Column(String(50))
    capacidad_ton = Column(Numeric(8,2))
    estado = Column(String(20), nullable=False, default='activo')
    km_actual = Column(Numeric(12,2), nullable=False, default=0)
    km_inicial_sistema = Column(Numeric(12,2), nullable=False, default=0)
    numero_motor = Column(String(50))
    numero_chasis = Column(String(50))
    propietario_nombre = Column(String(100))
    propietario_nit = Column(String(20))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Conductor(Base):
    __tablename__ = "conductores"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(150), nullable=False)
    cedula = Column(String(20), unique=True, nullable=False)
    telefono = Column(String(20))
    correo = Column(String(100))
    direccion = Column(Text)
    num_licencia = Column(String(30))
    categoria_licencia = Column(String(10))
    vencimiento_licencia = Column(Date)
    estado = Column(String(20), nullable=False, default='activo')
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(SQL_CHECK_ROL, name="ck_usuarios_rol_valido"),
    )

    id = Column(Integer, primary_key=True, index=True)
    correo = Column(String(100), unique=True, nullable=False, index=True)
    contrasena_hash = Column(Text, nullable=False)
    rol = Column(String(20), nullable=False, default='conductor')
    conductor_id = Column(Integer, ForeignKey("conductores.id"), index=True)
    activo = Column(Boolean, nullable=False, default=True)
    ultimo_acceso = Column(DateTime(timezone=True))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    conductor = relationship("Conductor")

class ConductorVehiculo(Base):
    __tablename__ = "conductor_vehiculo"
    
    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id", ondelete="CASCADE"), nullable=False)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id", ondelete="CASCADE"), nullable=False)
    fecha_inicio = Column(Date, nullable=False, server_default=func.current_date())
    fecha_fin = Column(Date)
    es_principal = Column(Boolean, nullable=False, default=True)
    observaciones = Column(Text)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
