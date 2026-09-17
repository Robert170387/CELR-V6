from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, ForeignKey, Text, DateTime
from sqlalchemy.sql import func
from app.db.base_class import Base

class MantenimientoRegla(Base):
    __tablename__ = "mantenimientos_reglas"
    
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    tipo_servicio = Column(String(100), nullable=False)
    descripcion = Column(Text)
    intervalo_km = Column(Numeric(10,2))
    km_ultimo_servicio = Column(Numeric(12,2))
    km_proximo_servicio = Column(Numeric(12,2))
    intervalo_dias = Column(Integer)
    fecha_ultimo_servicio = Column(Date)
    fecha_proximo_servicio = Column(Date)
    alerta_activa = Column(Boolean, nullable=False, default=True)
    km_pre_alerta = Column(Numeric(10,2), default=500)
    dias_pre_alerta = Column(Integer, default=7)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class MantenimientoRegistro(Base):
    __tablename__ = "mantenimientos_registros"
    
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    regla_id = Column(Integer, ForeignKey("mantenimientos_reglas.id"))
    gasto_id = Column(Integer, ForeignKey("gastos.id"))
    tipo_servicio = Column(String(100), nullable=False)
    descripcion = Column(Text)
    taller_proveedor = Column(Integer, ForeignKey("proveedores.id"))
    fecha_servicio = Column(Date, nullable=False)
    km_al_servicio = Column(Numeric(12,2), nullable=False)
    costo_total = Column(Numeric(14,2))
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class DocumentoVencimiento(Base):
    __tablename__ = "documentos_vencimientos"
    
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"))
    tipo_documento = Column(String(50), nullable=False, index=True)
    nombre_documento = Column(String(150), nullable=False)
    entidad_emisora = Column(String(100))
    num_documento = Column(String(80))
    fecha_expedicion = Column(Date)
    fecha_vencimiento = Column(Date, nullable=False, index=True)
    alerta_30_enviada = Column(Boolean, nullable=False, default=False)
    alerta_15_enviada = Column(Boolean, nullable=False, default=False)
    alerta_5_enviada = Column(Boolean, nullable=False, default=False)
    url_documento = Column(Text)
    activo = Column(Boolean, nullable=False, default=True)
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ConfiguracionSistema(Base):
    __tablename__ = "configuracion_sistema"
    
    clave = Column(String(80), primary_key=True)
    valor = Column(Text, nullable=False)
    descripcion = Column(Text)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
