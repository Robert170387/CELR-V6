from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, ForeignKey, Text, DateTime, CheckConstraint, Index, text
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
    porcentaje_comision_default = Column(Numeric(5,2))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(SQL_CHECK_ROL, name="ck_usuarios_rol_valido"),
        # A1: identidad canonica y 1:1 persona=cuenta. Son indices PARCIALES
        # (WHERE ... IS NOT NULL) para que las cuentas que aun no tienen cedula
        # ni conductor no colisionen entre si (PG ya lo permite en un UNIQUE,
        # pero el indice explicito documenta la regla y cubre los NULLs).
        Index("ux_usuarios_cedula", "cedula", unique=True,
              postgresql_where=text("cedula IS NOT NULL")),
        Index("ux_usuarios_conductor_id", "conductor_id", unique=True,
              postgresql_where=text("conductor_id IS NOT NULL")),
    )

    id = Column(Integer, primary_key=True, index=True)
    # A1: la cedula es la identidad primaria; el correo queda como atributo
    # opcional (los indices UNIQUE admiten multiples NULL en PostgreSQL).
    cedula = Column(String(20), nullable=True)
    correo = Column(String(100), unique=True, nullable=True, index=True)
    contrasena_hash = Column(Text, nullable=False)
    rol = Column(String(20), nullable=False, default='conductor')
    # A1: unicidad real (indice parcial ux_usuarios_conductor_id en __table_args__),
    # no unique=True en la columna, para que el baseline dinamico create_all()
    # genere el mismo esquema que la migracion Alembic.
    conductor_id = Column(Integer, ForeignKey("conductores.id"))
    activo = Column(Boolean, nullable=False, default=True)
    debe_cambiar_contrasena = Column(Boolean, nullable=False, default=False)
    # Version del hash de contrasena. Cada vez que se cambia la contrasena se
    # incrementa (o re-hashea alternando) y los access tokens emitidos con una
    # version anterior quedan invalidos de inmediato (ver deps.get_current_user).
    password_version = Column(Integer, nullable=False, server_default="1", default=1)
    ultimo_acceso = Column(DateTime(timezone=True))
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    conductor = relationship("Conductor")

class PasswordResetToken(Base):
    """A3.1 — Token de recuperacion de contrasena. Un solo modelo para los dos
    modos de entrega: 'enlace' (secreto largo, va por email) y 'codigo' (6
    digitos, se lee en voz alta). `intentos`/`intentos_max` son la defensa
    principal del modo 'codigo', cuyo espacio de busqueda es bruteforceable."""
    __tablename__ = "password_reset_token"
    __table_args__ = (
        CheckConstraint("tipo IN ('enlace', 'codigo')", name="ck_password_reset_tipo_valido"),
        CheckConstraint("intentos >= 0", name="ck_password_reset_intentos_no_negativo"),
    )

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)
    # SHA-256 en hex (64 chars), igual que refresh_tokens: el secreto en claro
    # nunca se persiste.
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    usado_en = Column(DateTime(timezone=True))
    revocado = Column(Boolean, nullable=False, server_default="false")
    intentos = Column(Integer, nullable=False, server_default="0")
    intentos_max = Column(Integer, nullable=False, server_default="5")
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    usuario = relationship("Usuario")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    revocado = Column(Boolean, nullable=False, default=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    usado_en = Column(DateTime(timezone=True))

    usuario = relationship("Usuario")

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
