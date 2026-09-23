from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, ForeignKey, Text, DateTime, Computed, CheckConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from app.db.base_class import Base

class Ingreso(Base):
    __tablename__ = "ingresos"
    
    id = Column(Integer, primary_key=True, index=True)
    viaje_id = Column(Integer, ForeignKey("viajes_odt.id"), nullable=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    # FASE A2 — cliente origen (empresa que despacha la carga) y receptor destino
    cliente_origen_id = Column(Integer, ForeignKey("proveedores.id"))
    receptor_destino = Column(String(150))
    tipo_ingreso = Column(String(30), nullable=False, index=True)
    descripcion = Column(Text)
    fecha_ingreso = Column(Date, nullable=False)
    valor = Column(Numeric(14,2), nullable=False)
    forma_pago = Column(String(30))
    num_referencia = Column(String(50))
    estado_pago = Column(String(20), nullable=False, default='por_cobrar')
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    eliminado_en = Column(DateTime(timezone=True))
    eliminado_por = Column(Integer, ForeignKey("usuarios.id"))

class LiquidacionConductor(Base):
    __tablename__ = "liquidaciones_conductores"
    __table_args__ = (
        CheckConstraint("salario_basico >= 0 AND auxilio_transporte >= 0 AND papeleria >= 0 "
                        "AND descuento_salud_pension >= 0 AND retiros_tarjeta_anticipos >= 0",
                        name="ck_liquidaciones_valores_no_negativos"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    # B2: en cierres mensuales el vehículo vive en cada ODT; la liquidación del
    # mes no necesita uno propio (NULL permitido solo en es_cierre_mensual=true).
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=True)
    periodo_inicio = Column(Date, nullable=False, index=True)
    periodo_fin = Column(Date, nullable=False, index=True)
    # B2: clave de periodo normalizada ('YYYY-MM') calculada por PG; el índice
    # real es el UNIQUE parcial de un solo cierre mensual por conductor+mes
    # (creado en la migración B2, no aquí: Alembic es el mecanismo oficial).
    # La expresión debe ser inmutable (PG): por eso EXTRACT+LPAD, no to_char.
    periodo_ym = Column(String(7), Computed("lpad(extract(year from periodo_inicio)::int::text, 4, '0') || '-' || lpad(extract(month from periodo_inicio)::int::text, 2, '0')", persisted=True))
    es_cierre_mensual = Column(Boolean, nullable=False, default=False, server_default="false")
    
    comision_flete = Column(Numeric(14,2), nullable=False, default=0)
    porcentaje_comision = Column(Numeric(5,2))
    bonificaciones = Column(Numeric(14,2), nullable=False, default=0)
    viaticos_reconocidos = Column(Numeric(14,2), nullable=False, default=0)
    otros_haberes = Column(Numeric(14,2), nullable=False, default=0)

    # FASE A2 — COMPENSADO_RC: inputs manuales adicionales de la liquidacion
    salario_basico = Column(Numeric(14,2), nullable=False, default=0, server_default="0")
    auxilio_transporte = Column(Numeric(14,2), nullable=False, default=0, server_default="0")
    papeleria = Column(Numeric(14,2), nullable=False, default=0, server_default="0")
    descuento_salud_pension = Column(Numeric(14,2), nullable=False, default=0, server_default="0")
    retiros_tarjeta_anticipos = Column(Numeric(14,2), nullable=False, default=0, server_default="0")
    viajes_nacionales = Column(Integer, nullable=False, default=0, server_default="0")
    viajes_urbanos = Column(Integer, nullable=False, default=0, server_default="0")
    total_viajes = Column(Integer, nullable=False, default=0, server_default="0")
    comisiones_total = Column(Numeric(14,2), nullable=False, default=0, server_default="0")

    total_haberes = Column(Numeric(14,2), Computed("comision_flete + bonificaciones + viaticos_reconocidos "
                                                   "+ otros_haberes + salario_basico + auxilio_transporte + papeleria", persisted=True))
    
    anticipos_entregados = Column(Numeric(14,2), nullable=False, default=0)
    gastos_a_cargo_conductor = Column(Numeric(14,2), nullable=False, default=0)
    prestamos = Column(Numeric(14,2), nullable=False, default=0)
    otros_descuentos = Column(Numeric(14,2), nullable=False, default=0)
    total_descuentos = Column(Numeric(14,2), Computed("anticipos_entregados + gastos_a_cargo_conductor + prestamos "
                                                      "+ otros_descuentos + descuento_salud_pension + retiros_tarjeta_anticipos", persisted=True))
    
    saldo_neto = Column(Numeric(14,2), Computed("comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes "
                                                "+ salario_basico + auxilio_transporte + papeleria - anticipos_entregados "
                                                "- gastos_a_cargo_conductor - prestamos - otros_descuentos "
                                                "- descuento_salud_pension - retiros_tarjeta_anticipos", persisted=True)) 
    
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
    eliminado_en = Column(DateTime(timezone=True))
    eliminado_por = Column(Integer, ForeignKey("usuarios.id"))

class MovimientoBancario(Base):
    __tablename__ = "movimientos_bancarios"
    __table_args__ = (
        CheckConstraint("cruzado IN ('si', 'pendiente')", name="ck_movimientos_cruzado_valido"),
    )
    
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
    # FASE A2 — cruce del retiro como anticipo del conductor (SI/PENDIENTE)
    cruzado = Column(String(10), nullable=False, default='pendiente', server_default='pendiente')
    importado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class FlypassTransaccion(Base):
    __tablename__ = "flypass_transacciones"
    
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    fecha_transaccion = Column(DateTime(timezone=True), nullable=False, index=True)
    nombre_peaje = Column(String(100))
    ciudad_peaje = Column(String(80))
    ciudad_peaje_municipio_id = Column(Integer, ForeignKey("municipios.id"), index=True)
    valor = Column(Numeric(10,2), nullable=False)
    num_transaccion_flypass = Column(String(50), unique=True)
    viaje_id = Column(Integer, ForeignKey("viajes_odt.id"))
    gasto_id = Column(Integer, ForeignKey("gastos.id"))
    # FASE A2 — generada: la transaccion queda legalizada cuando se vincula a un gasto
    legalizado_en_gastos = Column(Boolean, Computed("(gasto_id IS NOT NULL)", persisted=True))
    estado = Column(String(20), nullable=False, default='importado')
    importado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)