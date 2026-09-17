from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, Text, DateTime, Computed
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from app.db.base_class import Base

class Ingreso(Base):
    __tablename__ = "ingresos"
    
    id = Column(Integer, primary_key=True, index=True)
    viaje_id = Column(Integer, ForeignKey("viajes_odt.id"), nullable=False, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    tipo_ingreso = Column(String(30), nullable=False, index=True)
    descripcion = Column(Text)
    fecha_ingreso = Column(Date, nullable=False)
    valor = Column(Numeric(14,2), nullable=False)
    forma_pago = Column(String(30))
    num_referencia = Column(String(50))
    estado_pago = Column(String(20), nullable=False, default='pendiente')
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class LiquidacionConductor(Base):
    __tablename__ = "liquidaciones_conductores"
    
    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False)
    periodo_inicio = Column(Date, nullable=False, index=True)
    periodo_fin = Column(Date, nullable=False, index=True)
    
    comision_flete = Column(Numeric(14,2), nullable=False, default=0)
    porcentaje_comision = Column(Numeric(5,2))
    bonificaciones = Column(Numeric(14,2), nullable=False, default=0)
    viaticos_reconocidos = Column(Numeric(14,2), nullable=False, default=0)
    otros_haberes = Column(Numeric(14,2), nullable=False, default=0)
    total_haberes = Column(Numeric(14,2), Computed("comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes", persisted=True))
    
    anticipos_entregados = Column(Numeric(14,2), nullable=False, default=0)
    gastos_a_cargo_conductor = Column(Numeric(14,2), nullable=False, default=0)
    prestamos = Column(Numeric(14,2), nullable=False, default=0)
    otros_descuentos = Column(Numeric(14,2), nullable=False, default=0)
    total_descuentos = Column(Numeric(14,2), Computed("anticipos_entregados + gastos_a_cargo_conductor + prestamos + otros_descuentos", persisted=True))
    
    saldo_neto = Column(Numeric(14,2), Computed("comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes - anticipos_entregados - gastos_a_cargo_conductor - prestamos - otros_descuentos", persisted=True)) 
    
    viajes_ids = Column(ARRAY(Integer))
    estado = Column(String(20), nullable=False, default='borrador')
    fecha_pago = Column(Date)
    forma_pago_liquidacion = Column(String(30))
    num_comprobante_pago = Column(String(50))
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    aprobado_por = Column(Integer, ForeignKey("usuarios.id"))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class MovimientoBancario(Base):
    __tablename__ = "movimientos_bancarios"
    
    id = Column(Integer, primary_key=True, index=True)
    tarjeta_id = Column(Integer, ForeignKey("tarjetas_bancarias.id"))
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), index=True)
    fecha_mov = Column(Date, nullable=False)
    descripcion = Column(Text)
    valor = Column(Numeric(14,2), nullable=False)
    tipo = Column(String(10))
    referencia_banco = Column(String(80))
    gasto_id = Column(Integer, ForeignKey("gastos.id"))
    estado_conciliacion = Column(String(20), nullable=False, default='sin_conciliar', index=True)
    importado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class FlypassTransaccion(Base):
    __tablename__ = "flypass_transacciones"
    
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    fecha_transaccion = Column(DateTime(timezone=True), nullable=False, index=True)
    nombre_peaje = Column(String(100))
    ciudad_peaje = Column(String(80))
    valor = Column(Numeric(10,2), nullable=False)
    num_transaccion_flypass = Column(String(50), unique=True)
    viaje_id = Column(Integer, ForeignKey("viajes_odt.id"))
    gasto_id = Column(Integer, ForeignKey("gastos.id"))
    estado = Column(String(20), nullable=False, default='importado')
    importado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
