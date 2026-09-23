"""FASE A2 — Servicio canonico de calculo operativo/contable (CELR v6).

Centraliza TODAS las formulas que el sistema calcula automaticamente (espanol):
  * ODT: retenciones, total deducibles, comision conductor, saldo flete esperado,
    gastos totales del viaje y utilidad neta.
  * Regla 2: unicidad de manifiesto por empresa.
  * Regla 3: cruce de retiros de tarjeta como anticipos del conductor.
  * Regla 4: cierre operativo de ODT (saldo cubierto, flypass sin legalizar).

Contrato: el usuario NUNCA envia estos valores; el servidor los deriva de los
inputs manuales (ver documento DISENO_FASE_A2). Este modulo requiere la migracion
FASE A2 aplicada (columnas nuevas en viajes_odt, ingresos, gastos,
flypass_transacciones, movimientos_bancarios, liquidaciones_conductores).
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.flota import Conductor
from app.models.financiero import FlypassTransaccion, Ingreso, MovimientoBancario
from app.models.operaciones import Gasto, TarjetaBancaria, ViajeODT

CERO = Decimal("0")
CENTAVOS = Decimal("0.01")
PORCIENTO = Decimal("100")


# ---------------------------------------------------------------------------
# ODT — formulas calculadas por el servidor
# ---------------------------------------------------------------------------
def _porcentaje_comision(db: Session, viaje: ViajeODT) -> Decimal:
    """% de comision del conductor: override por ODT > default del conductor > global."""
    if viaje.porcentaje_comision is not None:
        return Decimal(str(viaje.porcentaje_comision))
    conductor = db.query(Conductor).filter(Conductor.id == viaje.conductor_id).first()
    if conductor and conductor.porcentaje_comision_default is not None:
        return Decimal(str(conductor.porcentaje_comision_default))
    return Decimal(str(settings.COMISION_CONDUCTOR_DEFAULT_PORCENTAJE))


def _gastos_totales_viaje(db: Session, viaje_id: int) -> Decimal:
    """Suma de TODOS los gastos vinculados a la ODT (sin importar quien los asume)."""
    total = (
        db.query(func.coalesce(func.sum(Gasto.valor_total), CERO))
        .filter(and_(Gasto.viaje_id == viaje_id, Gasto.eliminado_en.is_(None)))
        .scalar()
    )
    return total or CERO


def _flypass_pendientes(db: Session, viaje_id: int) -> int:
    """Peajes Flypass de la ruta aun sin legalizar en gastos (gasto_id es NULL)."""
    return (
        db.query(func.count(FlypassTransaccion.id))
        .filter(and_(
            FlypassTransaccion.viaje_id == viaje_id,
            FlypassTransaccion.gasto_id.is_(None),
        ))
        .scalar()
        or 0
    )


def recalcular_viaje(db: Session, viaje: ViajeODT) -> None:
    """Recomputa y persiste todos los calculados de una ODT.

    Debe llamarse antes del commit (los cambios se persisten en la misma
    transaccion). La columna generada flete_neto la recalcula PostgreSQL al
    hacer flush sobre las columnas base.
    """
    flete = viaje.valor_flete_manifiesto or CERO
    ret_fuente = (flete * (viaje.retefuente_porcentaje or CERO) / PORCIENTO).quantize(CENTAVOS)
    ret_ica = (flete * (viaje.reteica_porcentaje or CERO) / PORCIENTO).quantize(CENTAVOS)
    otras = viaje.otras_deducciones or CERO
    flete_neto = flete - ret_fuente - ret_ica - otras

    comision = (flete_neto * _porcentaje_comision(db, viaje) / PORCIENTO).quantize(CENTAVOS)
    gastos = _gastos_totales_viaje(db, viaje.id)
    anticipo = viaje.anticipo_manifiesto or CERO

    # Columnas base que alimentan la generada flete_neto
    viaje.retefuente_valor = ret_fuente
    viaje.reteica_valor = ret_ica
    # Snapshots calculados por el servidor (historia contable)
    viaje.comision_conductor = comision
    viaje.saldo_flete_esperado = (flete_neto - anticipo).quantize(CENTAVOS)
    viaje.gastos_totales_viaje = gastos.quantize(CENTAVOS)
    viaje.utilidad_neta_odt = (flete_neto - comision - gastos).quantize(CENTAVOS)


# ---------------------------------------------------------------------------
# Regla 2 — unicidad de manifiesto por empresa
# ---------------------------------------------------------------------------
def validar_manifiesto_unico(
    db: Session,
    num_manifiesto: str | None,
    empresa_manifiesto_id: int | None,
    viaje_id: int | None = None,
) -> None:
    """Un numero de manifiesto no puede duplicarse por empresa/cliente (Regla 2)."""
    if not num_manifiesto or not empresa_manifiesto_id:
        return
    query = db.query(ViajeODT).filter(
        ViajeODT.num_manifiesto == num_manifiesto,
        ViajeODT.empresa_manifiesto_id == empresa_manifiesto_id,
        ViajeODT.eliminado_en.is_(None),
    )
    if viaje_id is not None:
        query = query.filter(ViajeODT.id != viaje_id)
    if query.first():
        raise HTTPException(
            status_code=409,
            detail="El numero de manifiesto ya existe para esa empresa",
        )


# ---------------------------------------------------------------------------
# Regla 4 — cierre operativo de la ODT
# ---------------------------------------------------------------------------
def bloqueos_cierre_odt(db: Session, viaje: ViajeODT) -> list[str]:
    """Devuelve la lista de bloqueos para marcar una ODT como finalizada.

    Vacía = la ODT puede cerrarse. Regla 4:
      * saldo_flete_esperado cubierto por ingresos recibidos/conciliados;
      * sin peajes Flypass pendientes de legalizar en la ruta.
    """
    bloqueos: list[str] = []
    if viaje.saldo_flete_esperado is None or viaje.gastos_totales_viaje is None:
        recalcular_viaje(db, viaje)  # snapshots al dia antes de evaluar

    saldo = viaje.saldo_flete_esperado or CERO
    if saldo > 0:
        recaudado = (
            db.query(func.coalesce(func.sum(Ingreso.valor), CERO))
            .filter(and_(
                Ingreso.viaje_id == viaje.id,
                Ingreso.estado_pago.in_(("recibido", "conciliado")),
                Ingreso.eliminado_en.is_(None),
            ))
            .scalar()
            or CERO
        )
        if recaudado < saldo:
            bloqueos.append(
                f"Saldo flete esperado sin cubrir: faltan {(saldo - recaudado):,.2f}"
            )

    pendientes = _flypass_pendientes(db, viaje.id)
    if pendientes:
        bloqueos.append(f"{pendientes} peaje(s) Flypass pendientes de legalizar en la ruta")

    return bloqueos


# ---------------------------------------------------------------------------
# COMPENSADO_RC — consolidacion mensual del conductor (Regla 3)
# ---------------------------------------------------------------------------
def consolidar_compensado(
    db: Session,
    conductor_id: int,
    periodo_inicio,
    periodo_fin,
) -> dict:
    """Consolidados automaticos del mes para la liquidacion de un conductor.

    Devuelve SOLO los calculados (contadores, comisiones, retiros de tarjeta
    cruzados). Los inputs manuales (salario, auxilio, papeleria, salud/pension,
    prestamos, etc.) los aporta el endpoint que llama a esta funcion.
    """
    odts = (
        db.query(ViajeODT)
        .filter(
            ViajeODT.conductor_id == conductor_id,
            ViajeODT.fecha_salida >= periodo_inicio,
            ViajeODT.fecha_salida <= periodo_fin,
            ViajeODT.eliminado_en.is_(None),
            ViajeODT.estado != "cancelado",
        )
        .all()
    )

    # Tarjetas asignadas al conductor -> retiros cruzados como anticipo (Regla 3)
    tarjetas_sub = select(TarjetaBancaria.id).where(
        TarjetaBancaria.conductor_id == conductor_id
    )
    retiros = (
        db.query(func.coalesce(func.sum(MovimientoBancario.valor), CERO))
        .filter(
            MovimientoBancario.tarjeta_id.in_(tarjetas_sub),
            MovimientoBancario.fecha_mov >= periodo_inicio,
            MovimientoBancario.fecha_mov <= periodo_fin,
            MovimientoBancario.cruzado == "si",
        )
        .scalar()
        or CERO
    )

    return {
        "conductor_id": conductor_id,
        "periodo_inicio": periodo_inicio,
        "periodo_fin": periodo_fin,
        "total_viajes": len(odts),
        "viajes_nacionales": sum(1 for v in odts if v.tipo_viaje == "nacional"),
        "viajes_urbanos": sum(1 for v in odts if v.tipo_viaje == "urbano"),
        "comisiones_total": sum((v.comision_conductor or CERO) for v in odts),
        "retiros_tarjeta_anticipos": retiros,
        # La utilidad real del periodo puede derivarse de la vista v_odt_resumen
        "odts_incluidas": [v.id for v in odts],
    }