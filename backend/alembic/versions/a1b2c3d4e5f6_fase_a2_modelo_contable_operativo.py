"""FASE A2 — Modelo contable/operativo: ODT completa, enums realineados y COMPENSADO_RC.

Revision ID: a1b2c3d4e5f6
Revises: 26c38982f253
Create Date: 2026-09-23

Cambios de esquema (todo en espanol):
* viajes_odt: inputs manuales nuevos (tipo_viaje, fecha_manifiesto,
  empresa_manifiesto_id FK->proveedores, otras_deducciones, anticipo_manifiesto,
  porcentaje_comision) + calculados server-side (comision_conductor,
  saldo_flete_esperado, gastos_totales_viaje, utilidad_neta_odt) + generada anio.
* viajes_odt.flete_neto se recrea incluyendo otras_deducciones (drop+add; PG
  recalcula la generada desde las columnas base, sin perdida de datos).
* Regla 2: indice unico parcial de manifiesto por empresa (NULLs no colisionan).
* ingresos: viaje_id opcional, cliente_origen_id FK, receptor_destino,
  enums tipo_ingreso/estado_pago realineados al dominio de negocio.
* gastos: metodo_pago, estado_pago, generada legalizado.
* flypass_transacciones: generada legalizado_en_gastos.
* movimientos_bancarios: cruzado (SI/PENDIENTE) para anticipos de conductor.
* liquidaciones_conductores (COMPENSADO_RC): salario_basico, auxilio_transporte,
  papeleria, descuento_salud_pension, retiros_tarjeta_anticipos, conteos de
  viajes, comisiones_total; se reformulan total_haberes/total_descuentos/saldo_neto.
* Vista de solo lectura v_odt_resumen con la cadena completa de formulas.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "a1b2c3d4e5f6"
down_revision = "26c38982f253"
branch_labels = None
depends_on = None


def _add_checks(table: str, checks: list[tuple[str, str]]) -> None:
    """DDL de CHECK como SQL crudo (independiente de la version de Alembic)."""
    for nombre, condicion in checks:
        op.execute(text(
            f"ALTER TABLE {table} ADD CONSTRAINT {nombre} CHECK ({condicion})"
        ))


def _drop_checks(table: str, checks: list[str]) -> None:
    for nombre in checks:
        op.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {nombre}"))


def upgrade() -> None:
    # ================= VIAJES_ODT =================
    # Inputs manuales nuevos de la ODT
    op.add_column("viajes_odt", sa.Column("tipo_viaje", sa.String(20),
                  nullable=False, server_default="nacional"))
    op.add_column("viajes_odt", sa.Column("fecha_manifiesto", sa.Date(), nullable=True))
    op.add_column("viajes_odt", sa.Column("empresa_manifiesto_id", sa.Integer(), nullable=True))
    op.add_column("viajes_odt", sa.Column("otras_deducciones", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    op.add_column("viajes_odt", sa.Column("anticipo_manifiesto", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    op.add_column("viajes_odt", sa.Column("porcentaje_comision", sa.Numeric(5, 2), nullable=True))
    # Calculados por el servidor (snapshot contable persistido)
    op.add_column("viajes_odt", sa.Column("comision_conductor", sa.Numeric(14, 2), nullable=True))
    op.add_column("viajes_odt", sa.Column("saldo_flete_esperado", sa.Numeric(14, 2), nullable=True))
    op.add_column("viajes_odt", sa.Column("gastos_totales_viaje", sa.Numeric(14, 2), nullable=True))
    op.add_column("viajes_odt", sa.Column("utilidad_neta_odt", sa.Numeric(14, 2), nullable=True))
    # Anio = ExtractYear(fecha_salida), columna generada
    op.add_column("viajes_odt", sa.Column("anio", sa.Integer(),
                  sa.Computed("(EXTRACT(YEAR FROM fecha_salida))::integer", persisted=True)))
    op.create_foreign_key("fk_viajes_odt_empresa_manifiesto", "viajes_odt",
                          "proveedores", ["empresa_manifiesto_id"], ["id"])

    # Regla 2: manifiesto unico por empresa (se ignoran NULLs y eliminados)
    op.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_viajes_odt_manifiesto_empresa
        ON viajes_odt (empresa_manifiesto_id, num_manifiesto)
        WHERE num_manifiesto IS NOT NULL AND eliminado_en IS NULL
    """))

    # Recrear flete_neto incluyendo otras_deducciones (drop + add)
    op.drop_column("viajes_odt", "flete_neto")
    op.add_column("viajes_odt", sa.Column(
        "flete_neto", sa.Numeric(14, 2),
        sa.Computed(
            "valor_flete_manifiesto - COALESCE(retefuente_valor, 0) "
            "- COALESCE(reteica_valor, 0) - COALESCE(otras_deducciones, 0)",
            persisted=True)))

    _add_checks("viajes_odt", [
        ("ck_viajes_odt_tipo_viaje_valido",
         "tipo_viaje IN ('urbano', 'nacional', 'internacional', 'vacio')"),
        ("ck_viajes_odt_km_coherentes",
         "km_inicial IS NULL OR km_final IS NULL OR km_final >= km_inicial"),
        ("ck_viajes_odt_valores_no_negativos",
         "COALESCE(valor_flete_manifiesto,0) >= 0 AND COALESCE(retefuente_valor,0) >= 0 "
         "AND COALESCE(reteica_valor,0) >= 0 AND otras_deducciones >= 0 AND anticipo_manifiesto >= 0"),
    ])

    # ================= INGRESOS =================
    # ID_VIAJE pasa a ser opcional (una ODT puede tener 0..N ingresos; hay ingresos sin ODT)
    op.alter_column("ingresos", "viaje_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("ingresos", sa.Column("cliente_origen_id", sa.Integer(), nullable=True))
    op.add_column("ingresos", sa.Column("receptor_destino", sa.String(150), nullable=True))
    op.create_foreign_key("fk_ingresos_cliente_origen", "ingresos",
                          "proveedores", ["cliente_origen_id"], ["id"])

    # Mapeo de enums legados -> dominio de negocio (antes de los CHECK nuevos)
    op.execute(text("""
        UPDATE ingresos SET tipo_ingreso = CASE tipo_ingreso
            WHEN 'flete' THEN 'saldo_flete'
            WHEN 'anticipo' THEN 'anticipo_manifiesto'
            WHEN 'cumplido' THEN 'saldo_flete'
            WHEN 'compensacion' THEN 'ajuste_flete'
            WHEN 'aporte_capital' THEN 'aporte_capital'
            ELSE 'otro'
        END
    """))
    op.execute(text("""
        UPDATE ingresos SET estado_pago = CASE estado_pago
            WHEN 'recibido' THEN 'recibido'
            ELSE 'por_cobrar'
        END
    """))
    # El default de la columna tambien debe cumplir el CHECK nuevo
    op.alter_column("ingresos", "estado_pago", existing_type=sa.String(20),
                    server_default="por_cobrar")

    _add_checks("ingresos", [
        ("ck_ingresos_tipo_valido",
         "tipo_ingreso IN ('anticipo_manifiesto', 'saldo_flete', 'ajuste_flete', 'aporte_capital', 'otro')"),
        ("ck_ingresos_estado_valido",
         "estado_pago IN ('por_cobrar', 'recibido', 'conciliado')"),
        ("ck_ingresos_valor_no_negativo", "valor >= 0"),
    ])

    # ================= GASTOS =================
    op.add_column("gastos", sa.Column("metodo_pago", sa.String(20),
                  nullable=False, server_default="efectivo"))
    op.add_column("gastos", sa.Column("estado_pago", sa.String(20),
                  nullable=False, server_default="pagado"))
    op.add_column("gastos", sa.Column("legalizado", sa.Boolean(),
                  sa.Computed("(estado_pago = 'legalizado')", persisted=True)))
    _add_checks("gastos", [
        ("ck_gastos_metodo_pago_valido",
         "metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'tag')"),
        ("ck_gastos_estado_pago_valido",
         "estado_pago IN ('pagado', 'pendiente_por_pagar', 'legalizado')"),
    ])

    # ================= FLYPASS / MOV_TARJETA =================
    op.add_column("flypass_transacciones", sa.Column("legalizado_en_gastos", sa.Boolean(),
                  sa.Computed("(gasto_id IS NOT NULL)", persisted=True)))
    op.add_column("movimientos_bancarios", sa.Column("cruzado", sa.String(10),
                  nullable=False, server_default="pendiente"))
    _add_checks("movimientos_bancarios", [
        ("ck_movimientos_cruzado_valido", "cruzado IN ('si', 'pendiente')"),
    ])

    # ================= COMPENSADO_RC (liquidaciones_conductores) =================
    op.add_column("liquidaciones_conductores", sa.Column("salario_basico", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("auxilio_transporte", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("papeleria", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("descuento_salud_pension", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("retiros_tarjeta_anticipos", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("viajes_nacionales", sa.Integer(),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("viajes_urbanos", sa.Integer(),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("total_viajes", sa.Integer(),
                  nullable=False, server_default="0"))
    op.add_column("liquidaciones_conductores", sa.Column("comisiones_total", sa.Numeric(14, 2),
                  nullable=False, server_default="0"))
    _add_checks("liquidaciones_conductores", [
        ("ck_liquidaciones_valores_no_negativos",
         "salario_basico >= 0 AND auxilio_transporte >= 0 AND papeleria >= 0 "
         "AND descuento_salud_pension >= 0 AND retiros_tarjeta_anticipos >= 0"),
    ])

    # Reformular las generadas (drop + add). saldo_neto va INLINE: PG no permite
    # que una generada referencie otra generada.
    op.drop_column("liquidaciones_conductores", "total_haberes")
    op.drop_column("liquidaciones_conductores", "total_descuentos")
    op.drop_column("liquidaciones_conductores", "saldo_neto")
    op.add_column("liquidaciones_conductores", sa.Column(
        "total_haberes", sa.Numeric(14, 2), sa.Computed(
            "comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes "
            "+ salario_basico + auxilio_transporte + papeleria", persisted=True)))
    op.add_column("liquidaciones_conductores", sa.Column(
        "total_descuentos", sa.Numeric(14, 2), sa.Computed(
            "anticipos_entregados + gastos_a_cargo_conductor + prestamos + otros_descuentos "
            "+ descuento_salud_pension + retiros_tarjeta_anticipos", persisted=True)))
    op.add_column("liquidaciones_conductores", sa.Column(
        "saldo_neto", sa.Numeric(14, 2), sa.Computed(
            "comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes "
            "+ salario_basico + auxilio_transporte + papeleria - anticipos_entregados "
            "- gastos_a_cargo_conductor - prestamos - otros_descuentos "
            "- descuento_salud_pension - retiros_tarjeta_anticipos", persisted=True)))

    # ================= VISTA (solo lectura, para reportes) =================
    op.execute(text("""
        CREATE VIEW v_odt_resumen AS
        SELECT
            id, numero_odt, anio, tipo_viaje, fecha_salida, vehiculo_id, conductor_id,
            empresa_manifiesto_id, num_manifiesto,
            valor_flete_manifiesto,
            COALESCE(retefuente_valor, 0)  AS retencion_fuente,
            COALESCE(reteica_valor, 0)     AS retencion_ica,
            otras_deducciones,
            (COALESCE(retefuente_valor, 0) + COALESCE(reteica_valor, 0)
             + COALESCE(otras_deducciones, 0)) AS total_deducibles,
            flete_neto,
            comision_conductor,
            (COALESCE(flete_neto, 0) - COALESCE(anticipo_manifiesto, 0)) AS saldo_flete_esperado,
            gastos_totales_viaje,
            utilidad_neta_odt,
            km_recorridos
        FROM viajes_odt
    """))


def downgrade() -> None:
    # ================= COMPENSADO_RC =================
    # ORDEN CRITICO: primero se dropean las generadas que dependen de las nuevas
    # columnas; PG no permite dropear columnas base mientras una generada las referencia.
    _drop_checks("liquidaciones_conductores", ["ck_liquidaciones_valores_no_negativos"])
    op.drop_column("liquidaciones_conductores", "saldo_neto")
    op.drop_column("liquidaciones_conductores", "total_descuentos")
    op.drop_column("liquidaciones_conductores", "total_haberes")
    op.execute(text("DROP VIEW IF EXISTS v_odt_resumen"))
    # Ahora si se pueden dropear las columnas regulares nuevas
    for col in ("comisiones_total", "total_viajes", "viajes_urbanos", "viajes_nacionales",
                "retiros_tarjeta_anticipos", "descuento_salud_pension", "papeleria",
                "auxilio_transporte", "salario_basico"):
        op.drop_column("liquidaciones_conductores", col)
    # Restaurar las 3 generadas con la expresion previa a FASE A2
    op.add_column("liquidaciones_conductores", sa.Column(
        "total_haberes", sa.Numeric(14, 2), sa.Computed(
            "comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes",
            persisted=True)))
    op.add_column("liquidaciones_conductores", sa.Column(
        "total_descuentos", sa.Numeric(14, 2), sa.Computed(
            "anticipos_entregados + gastos_a_cargo_conductor + prestamos + otros_descuentos",
            persisted=True)))
    op.add_column("liquidaciones_conductores", sa.Column(
        "saldo_neto", sa.Numeric(14, 2), sa.Computed(
            "comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes "
            "- anticipos_entregados - gastos_a_cargo_conductor - prestamos - otros_descuentos",
            persisted=True)))

    # ================= FLYPASS / MOV_TARJETA =================
    _drop_checks("movimientos_bancarios", ["ck_movimientos_cruzado_valido"])
    op.drop_column("movimientos_bancarios", "cruzado")
    op.drop_column("flypass_transacciones", "legalizado_en_gastos")

    # ================= GASTOS =================
    _drop_checks("gastos", ["ck_gastos_estado_pago_valido", "ck_gastos_metodo_pago_valido"])
    op.drop_column("gastos", "legalizado")
    op.drop_column("gastos", "estado_pago")
    op.drop_column("gastos", "metodo_pago")

    # ================= INGRESOS =================
    _drop_checks("ingresos", ["ck_ingresos_valor_no_negativo", "ck_ingresos_estado_valido",
                              "ck_ingresos_tipo_valido"])
    op.alter_column("ingresos", "estado_pago", existing_type=sa.String(20),
                    server_default="pendiente")
    # ORDEN: la FK se dropea ANTES de la columna (PG borra la FK sola al dropear la
    # columna; hacerlo despues fallaria con "constraint does not exist").
    op.drop_constraint("fk_ingresos_cliente_origen", "ingresos", type_="foreignkey")
    op.drop_column("ingresos", "receptor_destino")
    op.drop_column("ingresos", "cliente_origen_id")
    op.alter_column("ingresos", "viaje_id", existing_type=sa.Integer(), nullable=False)
    # NOTA: el downgrade no revierte los UPDATE de enums (mapeo irreversible).

    # ================= VIAJES_ODT =================
    _drop_checks("viajes_odt", ["ck_viajes_odt_valores_no_negativos", "ck_viajes_odt_km_coherentes",
                                "ck_viajes_odt_tipo_viaje_valido"])
    op.drop_column("viajes_odt", "flete_neto")
    op.add_column("viajes_odt", sa.Column(
        "flete_neto", sa.Numeric(14, 2), sa.Computed(
            "valor_flete_manifiesto - COALESCE(retefuente_valor, 0) "
            "- COALESCE(reteica_valor, 0)", persisted=True)))
    op.execute(text("DROP INDEX IF EXISTS ux_viajes_odt_manifiesto_empresa"))
    op.drop_constraint("fk_viajes_odt_empresa_manifiesto", "viajes_odt", type_="foreignkey")
    op.drop_column("viajes_odt", "anio")
    op.drop_column("viajes_odt", "utilidad_neta_odt")
    op.drop_column("viajes_odt", "gastos_totales_viaje")
    op.drop_column("viajes_odt", "saldo_flete_esperado")
    op.drop_column("viajes_odt", "comision_conductor")
    op.drop_column("viajes_odt", "porcentaje_comision")
    op.drop_column("viajes_odt", "anticipo_manifiesto")
    op.drop_column("viajes_odt", "otras_deducciones")
    op.drop_column("viajes_odt", "empresa_manifiesto_id")
    op.drop_column("viajes_odt", "fecha_manifiesto")
    op.drop_column("viajes_odt", "tipo_viaje")