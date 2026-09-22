-- =============================================================
-- CELR v6 - Esquema de Base de Datos
-- Script consolidado para creación de tablas e índices
-- =============================================================

-- =============================================================
-- TABLA: vehiculos
-- =============================================================
CREATE TABLE vehiculos (
    id                  SERIAL          PRIMARY KEY,
    placa               VARCHAR(10)     NOT NULL UNIQUE,
    marca               VARCHAR(50)     NOT NULL,
    modelo              VARCHAR(50),
    anio                INTEGER,
    tipo_carroceria     VARCHAR(50),
    capacidad_ton       NUMERIC(8,2),
    estado              VARCHAR(20)     NOT NULL DEFAULT 'activo'
                        CHECK (estado IN ('activo', 'en_taller', 'inactivo')),
    km_actual           NUMERIC(12,2)   NOT NULL DEFAULT 0,
    km_inicial_sistema  NUMERIC(12,2)   NOT NULL DEFAULT 0,
    numero_motor        VARCHAR(50),
    numero_chasis       VARCHAR(50),
    propietario_nombre  VARCHAR(100),
    propietario_nit     VARCHAR(20),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_vehiculos_placa ON vehiculos(placa);
COMMENT ON TABLE vehiculos IS 'Registro maestro de vehículos de la flota. Multi-vehículo desde el día 1.';
COMMENT ON COLUMN vehiculos.km_actual IS 'Se actualiza automáticamente con cada reporte de odómetro del conductor.';

-- =============================================================
-- TABLA: conductores
-- =============================================================
CREATE TABLE conductores (
    id                  SERIAL          PRIMARY KEY,
    nombre_completo     VARCHAR(150)    NOT NULL,
    cedula              VARCHAR(20)     NOT NULL UNIQUE,
    telefono            VARCHAR(20),
    correo              VARCHAR(100),
    direccion           TEXT,
    num_licencia        VARCHAR(30),
    categoria_licencia  VARCHAR(10),
    vencimiento_licencia DATE,
    estado              VARCHAR(20)     NOT NULL DEFAULT 'activo'
                        CHECK (estado IN ('activo', 'inactivo', 'vacaciones', 'incapacitado')),
    porcentaje_comision_default NUMERIC(5,2),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE conductores IS 'Perfil laboral de conductores. Un conductor puede operar múltiples vehículos en el tiempo.';

-- =============================================================
-- TABLA: usuarios
-- =============================================================
CREATE TABLE usuarios (
    id                  SERIAL          PRIMARY KEY,
    correo              VARCHAR(100)    NOT NULL UNIQUE,
    contrasena_hash     TEXT            NOT NULL,
    rol                 VARCHAR(20)     NOT NULL DEFAULT 'conductor'
                        CHECK (rol IN ('admin', 'operador', 'contador', 'supervisor', 'cliente', 'conductor')),
    conductor_id        INTEGER         REFERENCES conductores(id) ON DELETE SET NULL,
    debe_cambiar_contrasena BOOLEAN      NOT NULL DEFAULT FALSE,
    activo              BOOLEAN         NOT NULL DEFAULT TRUE,
    ultimo_acceso       TIMESTAMPTZ,
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usuarios_correo ON usuarios(correo);
CREATE INDEX idx_usuarios_conductor ON usuarios(conductor_id);
COMMENT ON TABLE usuarios IS 'Cuentas de acceso al sistema. Separado de conductores para mayor flexibilidad de roles.';

-- =============================================================
-- TABLA: refresh_tokens (rotación de refresh JWT, B2)
-- =============================================================
CREATE TABLE refresh_tokens (
    id                  SERIAL          PRIMARY KEY,
    usuario_id          INTEGER         NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash          VARCHAR(64)     NOT NULL UNIQUE,
    jti                 VARCHAR(64),
    expira_en           TIMESTAMPTZ     NOT NULL,
    revocado_en         TIMESTAMPTZ,
    reemplazado_por     INTEGER         REFERENCES refresh_tokens(id),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_usuario ON refresh_tokens(usuario_id);
CREATE INDEX idx_refresh_tokens_expira ON refresh_tokens(expira_en);

-- =============================================================
-- TABLA: conductor_vehiculo
-- =============================================================
CREATE TABLE conductor_vehiculo (
    id                  SERIAL          PRIMARY KEY,
    conductor_id        INTEGER         NOT NULL REFERENCES conductores(id) ON DELETE CASCADE,
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id) ON DELETE CASCADE,
    fecha_inicio        DATE            NOT NULL DEFAULT CURRENT_DATE,
    fecha_fin           DATE,
    es_principal        BOOLEAN         NOT NULL DEFAULT TRUE,
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_cv_activo_unico
    ON conductor_vehiculo(conductor_id, vehiculo_id)
    WHERE fecha_fin IS NULL;
COMMENT ON TABLE conductor_vehiculo IS 'Historial de asignaciones conductor-vehículo. Muchos-a-muchos con período de vigencia.';

-- =============================================================
-- TABLA: proveedores
-- =============================================================
CREATE TABLE proveedores (
    id                  SERIAL          PRIMARY KEY,
    nit                 VARCHAR(20)     UNIQUE,
    razon_social        VARCHAR(150)    NOT NULL,
    nombre_comercial    VARCHAR(150),
    tipo                VARCHAR(50)     NOT NULL
                        CHECK (tipo IN (
                            'combustible', 'peaje', 'taller', 'aseguradora',
                            'repuestos', 'viaticos', 'administrativo', 'otro'
                        )),
    telefono            VARCHAR(20),
    correo              VARCHAR(100),
    ciudad              VARCHAR(80),
    banco               VARCHAR(80),
    tipo_cuenta         VARCHAR(30)     CHECK (tipo_cuenta IN ('ahorros', 'corriente')),
    numero_cuenta       VARCHAR(50),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_proveedores_nit ON proveedores(nit);
CREATE INDEX idx_proveedores_tipo ON proveedores(tipo);
COMMENT ON TABLE proveedores IS 'Terceros proveedores: combustible, talleres, peajes, aseguradoras, etc.';

-- =============================================================
-- TABLA: viajes_odt
-- =============================================================
CREATE TABLE viajes_odt (
    id                  SERIAL          PRIMARY KEY,
    numero_odt          VARCHAR(30)     NOT NULL UNIQUE,
    num_manifiesto      VARCHAR(30),
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id),
    conductor_id        INTEGER         NOT NULL REFERENCES conductores(id),
    origen              VARCHAR(100)    NOT NULL,
    destino             VARCHAR(100)    NOT NULL,
    empresa_manifiesto  VARCHAR(150),
    tipo_carga          VARCHAR(100),
    peso_declarado_ton  NUMERIC(8,2),
    peso_bascula_origen NUMERIC(8,2),
    peso_bascula_destino NUMERIC(8,2),
    valor_flete_manifiesto NUMERIC(14,2),
    retefuente_porcentaje  NUMERIC(5,2),
    retefuente_valor       NUMERIC(14,2),
    reteica_porcentaje     NUMERIC(5,2),
    reteica_valor          NUMERIC(14,2),
    flete_neto             NUMERIC(14,2)   GENERATED ALWAYS AS
                           (valor_flete_manifiesto - COALESCE(retefuente_valor, 0) - COALESCE(reteica_valor, 0)) STORED,
    fecha_salida        DATE            NOT NULL,
    fecha_llegada       DATE,
    km_inicial          NUMERIC(12,2),
    km_final            NUMERIC(12,2),
    km_recorridos       NUMERIC(12,2)   GENERATED ALWAYS AS
                        (km_final - km_inicial) STORED,
    estado              VARCHAR(20)     NOT NULL DEFAULT 'en_curso'
                        CHECK (estado IN ('programado', 'en_curso', 'completado', 'liquidado', 'cancelado')),
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    creado_por          INTEGER         REFERENCES usuarios(id),
    eliminado_en        TIMESTAMPTZ,
    eliminado_por       INTEGER         REFERENCES usuarios(id)
);
CREATE INDEX idx_viajes_vehiculo ON viajes_odt(vehiculo_id);
CREATE INDEX idx_viajes_conductor ON viajes_odt(conductor_id);
CREATE INDEX idx_viajes_fecha ON viajes_odt(fecha_salida);
CREATE INDEX idx_viajes_estado ON viajes_odt(estado);
CREATE INDEX idx_viajes_eliminado ON viajes_odt(eliminado_en);
COMMENT ON TABLE viajes_odt IS 'Orden de Trabajo (ODT). Centro de costo por viaje. Todo gasto e ingreso se asocia aquí.';

-- =============================================================
-- TABLA: tarjetas_bancarias
-- =============================================================
CREATE TABLE tarjetas_bancarias (
    id                  SERIAL          PRIMARY KEY,
    vehiculo_id         INTEGER         REFERENCES vehiculos(id),
    conductor_id        INTEGER         REFERENCES conductores(id),
    banco               VARCHAR(80)     NOT NULL,
    tipo_tarjeta        VARCHAR(20)     CHECK (tipo_tarjeta IN ('debito', 'credito')),
    ultimos_4_digitos   CHAR(4)         NOT NULL,
    nombre_en_tarjeta   VARCHAR(100),
    activa              BOOLEAN         NOT NULL DEFAULT TRUE,
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE tarjetas_bancarias IS 'Tarjetas bancarias dedicadas por vehículo/conductor para trazabilidad de pagos.';

-- =============================================================
-- TABLA: gastos
-- =============================================================
CREATE TABLE gastos (
    id                  SERIAL          PRIMARY KEY,
    viaje_id            INTEGER         NOT NULL REFERENCES viajes_odt(id),
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id),
    proveedor_id        INTEGER         REFERENCES proveedores(id),
    categoria           VARCHAR(80)     NOT NULL,
    descripcion         TEXT,
    num_factura         VARCHAR(50),
    fecha_gasto         DATE            NOT NULL,
    valor_total         NUMERIC(14,2)   NOT NULL CHECK (valor_total >= 0),
    km_registro         NUMERIC(12,2),
    cantidad_galones    NUMERIC(8,3),
    precio_por_galon    NUMERIC(10,2),
    ciudad_abastecimiento VARCHAR(80),
    responsable_pago    VARCHAR(50)     NOT NULL DEFAULT 'conductor',
    asumido_por         VARCHAR(50)     NOT NULL DEFAULT 'empresa',
    tarjeta_id          INTEGER         REFERENCES tarjetas_bancarias(id),
    tiene_num_factura   BOOLEAN         NOT NULL DEFAULT FALSE,
    hash_comprobante    VARCHAR(64)     UNIQUE NOT NULL,
    url_imagen          TEXT,
    datos_ocr_json      JSONB,
    estado_validacion   VARCHAR(20)     NOT NULL DEFAULT 'pendiente'
                        CHECK (estado_validacion IN ('pendiente', 'aprobado', 'rechazado', 'observado')),
    aprobado_por        INTEGER         REFERENCES usuarios(id),
    fecha_aprobacion    TIMESTAMPTZ,
    motivo_rechazo      TEXT,
    reportado_por       INTEGER         REFERENCES usuarios(id),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    eliminado_en        TIMESTAMPTZ,
    eliminado_por       INTEGER         REFERENCES usuarios(id)
);
CREATE INDEX idx_gastos_viaje ON gastos(viaje_id);
CREATE INDEX idx_gastos_vehiculo ON gastos(vehiculo_id);
CREATE INDEX idx_gastos_categoria ON gastos(categoria);
CREATE INDEX idx_gastos_fecha ON gastos(fecha_gasto);
CREATE INDEX idx_gastos_estado ON gastos(estado_validacion);
CREATE INDEX idx_gastos_hash ON gastos(hash_comprobante);
CREATE INDEX idx_gastos_eliminado ON gastos(eliminado_en);
COMMENT ON TABLE gastos IS 'Registro de gastos operativos. Incluye hash anti-duplicados, responsabilidad de pago y foto del comprobante.';
COMMENT ON COLUMN gastos.responsable_pago IS '¿Quién realizó el pago físicamente? (conductor, empresa, tarjeta_empresa)';
COMMENT ON COLUMN gastos.asumido_por IS '¿Quién absorbe el costo contablemente? (empresa/Owner vs conductor)';
COMMENT ON COLUMN gastos.hash_comprobante IS 'Con factura: MD5(NIT+NumFact+Fecha+Monto). Sin factura: MD5(NIT+Fecha+Monto+viaje_id). Bloqueo automático de duplicados.';

-- =============================================================
-- TABLA: ingresos
-- =============================================================
CREATE TABLE ingresos (
    id                  SERIAL          PRIMARY KEY,
    viaje_id            INTEGER         NOT NULL REFERENCES viajes_odt(id),
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id),
    tipo_ingreso        VARCHAR(30)     NOT NULL
                        CHECK (tipo_ingreso IN (
                            'flete', 'anticipo', 'cumplido', 'compensacion',
                            'bono', 'traslado_fondos', 'aporte_capital', 'otro'
                        )),
    descripcion         TEXT,
    fecha_ingreso       DATE            NOT NULL,
    valor               NUMERIC(14,2)   NOT NULL CHECK (valor > 0),
    forma_pago          VARCHAR(30)
                        CHECK (forma_pago IN ('transferencia', 'cheque', 'efectivo', 'otro')),
    num_referencia      VARCHAR(50),
    estado_pago         VARCHAR(20)     NOT NULL DEFAULT 'pendiente'
                        CHECK (estado_pago IN ('pendiente', 'recibido', 'en_disputa')),
    observaciones       TEXT,
    creado_por          INTEGER         REFERENCES usuarios(id),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    eliminado_en        TIMESTAMPTZ,
    eliminado_por       INTEGER         REFERENCES usuarios(id)
);
CREATE INDEX idx_ingresos_viaje ON ingresos(viaje_id);
CREATE INDEX idx_ingresos_vehiculo ON ingresos(vehiculo_id);
CREATE INDEX idx_ingresos_tipo ON ingresos(tipo_ingreso);
CREATE INDEX idx_ingresos_eliminado ON ingresos(eliminado_en);
COMMENT ON TABLE ingresos IS 'Ingresos por viaje: fletes, anticipos, cumplidos y compensaciones.';

-- =============================================================
-- TABLA: liquidaciones_conductores
-- =============================================================
CREATE TABLE liquidaciones_conductores (
    id                  SERIAL          PRIMARY KEY,
    conductor_id        INTEGER         NOT NULL REFERENCES conductores(id),
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id),
    periodo_inicio      DATE            NOT NULL,
    periodo_fin         DATE            NOT NULL,
    comision_flete      NUMERIC(14,2)   NOT NULL DEFAULT 0,
    porcentaje_comision NUMERIC(5,2),
    bonificaciones      NUMERIC(14,2)   NOT NULL DEFAULT 0,
    viaticos_reconocidos NUMERIC(14,2)  NOT NULL DEFAULT 0,
    otros_haberes       NUMERIC(14,2)   NOT NULL DEFAULT 0,
    total_haberes       NUMERIC(14,2)   GENERATED ALWAYS AS
                        (comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes) STORED,
    anticipos_entregados    NUMERIC(14,2)   NOT NULL DEFAULT 0,
    gastos_a_cargo_conductor NUMERIC(14,2)  NOT NULL DEFAULT 0,
    prestamos               NUMERIC(14,2)   NOT NULL DEFAULT 0,
    otros_descuentos        NUMERIC(14,2)   NOT NULL DEFAULT 0,
    total_descuentos        NUMERIC(14,2)   GENERATED ALWAYS AS
                        (anticipos_entregados + gastos_a_cargo_conductor + prestamos + otros_descuentos) STORED,
    saldo_neto          NUMERIC(14,2)   GENERATED ALWAYS AS
                        (comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes
                         - anticipos_entregados - gastos_a_cargo_conductor - prestamos - otros_descuentos) STORED,
    viajes_ids          INTEGER[],
    estado              VARCHAR(20)     NOT NULL DEFAULT 'borrador'
                        CHECK (estado IN ('borrador', 'revisado', 'aprobado', 'pagado')),
    fecha_pago          DATE,
    forma_pago_liquidacion VARCHAR(30),
    num_comprobante_pago VARCHAR(50),
    observaciones       TEXT,
    creado_por          INTEGER         REFERENCES usuarios(id),
    aprobado_por        INTEGER         REFERENCES usuarios(id),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    eliminado_en        TIMESTAMPTZ,
    eliminado_por       INTEGER         REFERENCES usuarios(id)
);
CREATE INDEX idx_liquidaciones_conductor ON liquidaciones_conductores(conductor_id);
CREATE INDEX idx_liquidaciones_periodo ON liquidaciones_conductores(periodo_inicio, periodo_fin);
CREATE INDEX idx_liquidaciones_eliminado ON liquidaciones_conductores(eliminado_en);
COMMENT ON TABLE liquidaciones_conductores IS 'Módulo de Compensados. Liquidación periódica: comisiones, anticipos, viáticos, descuentos y saldo neto.';
COMMENT ON COLUMN liquidaciones_conductores.saldo_neto IS 'Positivo: empresa debe al conductor. Negativo: conductor debe a la empresa.';

-- =============================================================
-- TABLA: movimientos_bancarios
-- =============================================================
CREATE TABLE movimientos_bancarios (
    id                  SERIAL          PRIMARY KEY,
    tarjeta_id          INTEGER         REFERENCES tarjetas_bancarias(id),
    vehiculo_id         INTEGER         REFERENCES vehiculos(id),
    fecha_mov           DATE            NOT NULL,
    descripcion         TEXT,
    valor               NUMERIC(14,2)   NOT NULL,
    tipo                VARCHAR(10)     CHECK (tipo IN ('debito', 'credito')),
    referencia_banco    VARCHAR(80),
    gasto_id            INTEGER         REFERENCES gastos(id),
    estado_conciliacion VARCHAR(20)     NOT NULL DEFAULT 'sin_conciliar'
                        CHECK (estado_conciliacion IN ('sin_conciliar', 'conciliado', 'diferencia', 'ignorar')),
    importado_en        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_movimientos_conciliacion ON movimientos_bancarios(estado_conciliacion);
CREATE INDEX idx_movimientos_vehiculo ON movimientos_bancarios(vehiculo_id);

-- =============================================================
-- TABLA: flypass_transacciones
-- =============================================================
CREATE TABLE flypass_transacciones (
    id                  SERIAL          PRIMARY KEY,
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id),
    fecha_transaccion   TIMESTAMPTZ     NOT NULL,
    nombre_peaje        VARCHAR(100),
    ciudad_peaje        VARCHAR(80),
    valor               NUMERIC(10,2)   NOT NULL,
    num_transaccion_flypass VARCHAR(50) UNIQUE,
    viaje_id            INTEGER         REFERENCES viajes_odt(id),
    gasto_id            INTEGER         REFERENCES gastos(id),
    estado              VARCHAR(20)     NOT NULL DEFAULT 'importado'
                        CHECK (estado IN ('importado', 'asignado_a_viaje', 'sin_viaje', 'ignorar')),
    importado_en        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_flypass_vehiculo ON flypass_transacciones(vehiculo_id);
CREATE INDEX idx_flypass_fecha ON flypass_transacciones(fecha_transaccion);

-- =============================================================
-- TABLA: mantenimientos_reglas
-- =============================================================
CREATE TABLE mantenimientos_reglas (
    id                  SERIAL          PRIMARY KEY,
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id),
    tipo_servicio       VARCHAR(100)    NOT NULL,
    descripcion         TEXT,
    intervalo_km        NUMERIC(10,2),
    km_ultimo_servicio  NUMERIC(12,2),
    km_proximo_servicio NUMERIC(12,2),
    intervalo_dias      INTEGER,
    fecha_ultimo_servicio DATE,
    fecha_proximo_servicio DATE,
    alerta_activa       BOOLEAN         NOT NULL DEFAULT TRUE,
    km_pre_alerta       NUMERIC(10,2)   DEFAULT 500,
    dias_pre_alerta     INTEGER         DEFAULT 7,
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_mant_reglas_vehiculo ON mantenimientos_reglas(vehiculo_id);
COMMENT ON TABLE mantenimientos_reglas IS 'Reglas de mantenimiento preventivo. El motor de alertas evalúa estas reglas con cada reporte de km.';

-- =============================================================
-- TABLA: mantenimientos_registros
-- =============================================================
CREATE TABLE mantenimientos_registros (
    id                  SERIAL          PRIMARY KEY,
    vehiculo_id         INTEGER         NOT NULL REFERENCES vehiculos(id),
    regla_id            INTEGER         REFERENCES mantenimientos_reglas(id),
    gasto_id            INTEGER         REFERENCES gastos(id),
    tipo_servicio       VARCHAR(100)    NOT NULL,
    descripcion         TEXT,
    taller_proveedor    INTEGER         REFERENCES proveedores(id),
    fecha_servicio      DATE            NOT NULL,
    km_al_servicio      NUMERIC(12,2)   NOT NULL,
    costo_total         NUMERIC(14,2),
    observaciones       TEXT,
    creado_por          INTEGER         REFERENCES usuarios(id),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_mant_registros_vehiculo ON mantenimientos_registros(vehiculo_id);

-- =============================================================
-- TABLA: documentos_vencimientos
-- =============================================================
CREATE TABLE documentos_vencimientos (
    id                  SERIAL          PRIMARY KEY,
    vehiculo_id         INTEGER         REFERENCES vehiculos(id),
    conductor_id        INTEGER         REFERENCES conductores(id),
    tipo_documento      VARCHAR(50)     NOT NULL
                        CHECK (tipo_documento IN (
                            'soat', 'rtm', 'poliza_contractual', 'poliza_extracontractual',
                            'poliza_todo_riesgo', 'licencia_conduccion', 'tarjeta_operacion',
                            'certificado_gases', 'otro'
                        )),
    nombre_documento    VARCHAR(150)    NOT NULL,
    entidad_emisora     VARCHAR(100),
    num_documento       VARCHAR(80),
    fecha_expedicion    DATE,
    fecha_vencimiento   DATE            NOT NULL,
    alerta_30_enviada   BOOLEAN         NOT NULL DEFAULT FALSE,
    alerta_15_enviada   BOOLEAN         NOT NULL DEFAULT FALSE,
    alerta_5_enviada    BOOLEAN         NOT NULL DEFAULT FALSE,
    url_documento       TEXT,
    activo              BOOLEAN         NOT NULL DEFAULT TRUE,
    observaciones       TEXT,
    creado_por          INTEGER         REFERENCES usuarios(id),
    creado_en           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_docs_vehiculo ON documentos_vencimientos(vehiculo_id);
CREATE INDEX idx_docs_vencimiento ON documentos_vencimientos(fecha_vencimiento);
CREATE INDEX idx_docs_tipo ON documentos_vencimientos(tipo_documento);
COMMENT ON TABLE documentos_vencimientos IS 'Control de vencimientos: SOAT, RTM, pólizas, licencias. Alertas a 30/15/5 días.';

-- =============================================================
-- TABLA: configuracion_sistema
-- =============================================================
CREATE TABLE configuracion_sistema (
    clave               VARCHAR(80)     PRIMARY KEY,
    valor               TEXT            NOT NULL,
    descripcion         TEXT,
    actualizado_en      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
INSERT INTO configuracion_sistema (clave, valor, descripcion) VALUES
    ('placa_principal',         'SKN756',   'Placa del vehículo principal inicial'),
    ('moneda',                  'COP',      'Moneda del sistema'),
    ('zona_horaria',            'America/Bogota', 'Zona horaria del sistema'),
    ('dias_alerta_docs_1',      '30',       'Primera alerta de vencimiento de documentos (días)'),
    ('dias_alerta_docs_2',      '15',       'Segunda alerta de vencimiento de documentos (días)'),
    ('dias_alerta_docs_3',      '5',        'Tercera alerta de vencimiento de documentos (días)'),
    ('correo_alertas',          '',         'Correo electrónico para recibir alertas'),
    ('version_esquema',         '1.0.0',    'Versión del esquema de base de datos');
