from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, ForeignKey, Text, DateTime, CheckConstraint, Computed, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func, text
from datetime import datetime
from app.db.base_class import Base

class Proveedor(Base):
    __tablename__ = "proveedores"
    
    id = Column(Integer, primary_key=True, index=True)
    nit = Column(String(20), unique=True, index=True)
    razon_social = Column(String(150), nullable=False)
    nombre_comercial = Column(String(150))
    tipo = Column(String(50), nullable=False, index=True)
    telefono = Column(String(20))
    correo = Column(String(100))
    ciudad = Column(String(80))
    ciudad_municipio_id = Column(Integer, ForeignKey("municipios.id"), index=True)
    banco = Column(String(80))
    tipo_cuenta = Column(String(30))
    numero_cuenta = Column(String(50))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class ViajeODT(Base):
    __tablename__ = "viajes_odt"
    
    id = Column(Integer, primary_key=True, index=True)
    numero_odt = Column(String(30), unique=True, nullable=False)
    num_manifiesto = Column(String(30))
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    origen = Column(String(100), nullable=False)
    destino = Column(String(100), nullable=False)
    origen_municipio_id = Column(Integer, ForeignKey("municipios.id"), index=True)
    destino_municipio_id = Column(Integer, ForeignKey("municipios.id"), index=True)
    empresa_manifiesto = Column(String(150))
    tipo_carga = Column(String(100))
    peso_declarado_ton = Column(Numeric(8,2))
    peso_bascula_origen = Column(Numeric(8,2))
    peso_bascula_destino = Column(Numeric(8,2))
    valor_flete_manifiesto = Column(Numeric(14,2))
    retefuente_porcentaje = Column(Numeric(5,2))
    retefuente_valor = Column(Numeric(14,2))
    reteica_porcentaje = Column(Numeric(5,2))
    reteica_valor = Column(Numeric(14,2))
    flete_neto = Column(Numeric(14,2), Computed("valor_flete_manifiesto - COALESCE(retefuente_valor, 0) - COALESCE(reteica_valor, 0)", persisted=True))
    fecha_salida = Column(Date, nullable=False, index=True)
    fecha_llegada = Column(Date)
    km_inicial = Column(Numeric(12,2))
    km_final = Column(Numeric(12,2))
    km_recorridos = Column(Numeric(12,2), Computed("km_final - km_inicial", persisted=True))
    estado = Column(String(20), nullable=False, default='en_curso', index=True)
    observaciones = Column(Text)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    eliminado_en = Column(DateTime(timezone=True))
    eliminado_por = Column(Integer, ForeignKey("usuarios.id"))
    
class TarjetaBancaria(Base):
    __tablename__ = "tarjetas_bancarias"
    
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"))
    conductor_id = Column(Integer, ForeignKey("conductores.id"))
    banco = Column(String(80), nullable=False)
    tipo_tarjeta = Column(String(20))
    ultimos_4_digitos = Column(String(4), nullable=False)
    nombre_en_tarjeta = Column(String(100))
    activa = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class Gasto(Base):
    __tablename__ = "gastos"
    __table_args__ = (
        CheckConstraint("valor_total >= 0", name="ck_gastos_valor_total_no_negativo"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    viaje_id = Column(Integer, ForeignKey("viajes_odt.id"), nullable=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"), nullable=False, index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"))
    categoria = Column(String(80), nullable=False, index=True)
    descripcion = Column(Text)
    num_factura = Column(String(50))
    fecha_gasto = Column(Date, nullable=False, index=True)
    valor_total = Column(Numeric(14,2), nullable=False)
    km_registro = Column(Numeric(12,2))
    cantidad_galones = Column(Numeric(8,3))
    precio_por_galon = Column(Numeric(10,2))
    ciudad_abastecimiento = Column(String(80))
    ciudad_abastecimiento_municipio_id = Column(Integer, ForeignKey("municipios.id"), index=True)
    responsable_pago = Column(String(50), nullable=False, default='conductor')
    asumido_por = Column(String(50), nullable=False, default='empresa')
    tarjeta_id = Column(Integer, ForeignKey("tarjetas_bancarias.id"))
    tiene_num_factura = Column(Boolean, nullable=False, default=False)
    hash_comprobante = Column(String(64), unique=True, nullable=False, index=True)

    url_imagen = Column(Text)
    datos_ocr_json = Column(JSONB)
    estado_validacion = Column(String(20), nullable=False, default='pendiente', index=True)
    aprobado_por = Column(Integer, ForeignKey("usuarios.id"))
    fecha_aprobacion = Column(DateTime(timezone=True))
    motivo_rechazo = Column(Text)
    reportado_por = Column(Integer, ForeignKey("usuarios.id"))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    eliminado_en = Column(DateTime(timezone=True))
    eliminado_por = Column(Integer, ForeignKey("usuarios.id"))


@event.listens_for(ViajeODT, "before_insert")
def _asignar_numero_odt(mapper, connection, target):
    """Genera numero_odt automaticamente cuando se crea un ViajeODT sin el.

    Aplica solos a inserts ORM/script que no pasan por el endpoint (que usa
    app.services.secuencias). El consecutivo es atomico (UPSERT ... RETURNING)
    sobre la tabla secuencias_documento en la misma transaccion/conn.
    """
    if target.numero_odt:
        return
    fecha = target.fecha_salida
    if isinstance(fecha, str):
        fecha = fecha[:4] if fecha else ""
        anio = int(fecha) if fecha else datetime.now().year
    else:
        anio = fecha.year if fecha else datetime.now().year
    valor = connection.execute(
        text(
            "INSERT INTO secuencias_documento (clave, valor) VALUES (:clave, 1) "
            "ON CONFLICT (clave) DO UPDATE SET valor = secuencias_documento.valor + 1 "
            "RETURNING valor"
        ),
        {"clave": f"odt_{anio}"},
    ).scalar()
    target.numero_odt = f"ODT-{anio}-{valor:06d}"
