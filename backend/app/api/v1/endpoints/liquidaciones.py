from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from decimal import Decimal

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.config import settings
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario, Conductor
from app.models.operaciones import ViajeODT, Gasto
from app.models.financiero import LiquidacionConductor, Ingreso
from app.schemas.liquidacion import LiquidacionCalculateResponse, LiquidacionCreate
from app.services.operaciones import consolidar_compensado

router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))])


def _porcentaje_comision_default(db: Session, conductor_id: int) -> Decimal:
    """% de comisión del conductor (si lo tiene configurado) o el global."""
    conductor = db.query(Conductor).filter(Conductor.id == conductor_id).first()
    if conductor and conductor.porcentaje_comision_default is not None:
        return Decimal(str(conductor.porcentaje_comision_default))
    return Decimal(str(settings.COMISION_CONDUCTOR_DEFAULT_PORCENTAJE))


def _calcular_servidor(db: Session, viaje: ViajeODT) -> dict:
    """Cálculo canónico SERVER-SIDE compartido por /calcular y /cerrar."""
    conductor_id = viaje.conductor_id
    vehiculo_id = viaje.vehiculo_id

    gastos_empresa = (
        db.query(func.coalesce(func.sum(Gasto.valor_total), Decimal(0)))
        .filter(
            and_(
                Gasto.viaje_id == viaje.id,
                Gasto.asumido_por == "empresa",
                Gasto.eliminado_en.is_(None),
            )
        )
        .scalar()
        or Decimal(0)
    )
    gastos_conductor = (
        db.query(func.coalesce(func.sum(Gasto.valor_total), Decimal(0)))
        .filter(
            and_(
                Gasto.viaje_id == viaje.id,
                Gasto.asumido_por == "conductor",
                Gasto.eliminado_en.is_(None),
            )
        )
        .scalar()
        or Decimal(0)
    )
    anticipos = (
        db.query(func.coalesce(func.sum(Ingreso.valor), Decimal(0)))
        .filter(
            and_(
                Ingreso.viaje_id == viaje.id,
                Ingreso.tipo_ingreso == "anticipo",
                Ingreso.eliminado_en.is_(None),
            )
        )
        .scalar()
        or Decimal(0)
    )
    ingresos_total = (
        db.query(func.coalesce(func.sum(Ingreso.valor), Decimal(0)))
        .filter(
            and_(
                Ingreso.viaje_id == viaje.id,
                Ingreso.eliminado_en.is_(None),
            )
        )
        .scalar()
        or Decimal(0)
    )

    flete_neto = viaje.flete_neto or Decimal(0)
    porcentaje = _porcentaje_comision_default(db, conductor_id)
    comision_flete = (flete_neto * porcentaje / Decimal(100)).quantize(Decimal("0.01"))
    saldo_neto = flete_neto - gastos_empresa - anticipos - comision_flete

    return {
        "viaje_id": viaje.id,
        "vehiculo_id": vehiculo_id,
        "conductor_id": conductor_id,
        "valor_flete_manifiesto": viaje.valor_flete_manifiesto,
        "retefuente_valor": viaje.retefuente_valor,
        "reteica_valor": viaje.reteica_valor,
        "flete_neto": flete_neto,
        "total_gastos_empresa": gastos_empresa,
        "total_gastos_conductor": gastos_conductor,
        "total_anticipos": anticipos,
        "total_ingresos": ingresos_total,
        "porcentaje_comision": porcentaje,
        "comision_flete": comision_flete,
        "saldo_neto": saldo_neto,
    }


@router.get("/liquidaciones/calcular/{viaje_id}", response_model=LiquidacionCalculateResponse)
def calcular_liquidacion(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    viaje = (
        db.query(ViajeODT)
        .filter(ViajeODT.id == viaje_id, ViajeODT.eliminado_en.is_(None))
        .first()
    )
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return LiquidacionCalculateResponse(**_calcular_servidor(db, viaje))


@router.get("/liquidaciones/compensado")
def obtener_compensado(
    conductor_id: int,
    periodo_inicio: date,
    periodo_fin: date,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """COMPENSADO_RC mensual (solo lectura).

    Consolidados automaticos del conductor en el periodo (conteo de viajes,
    comisiones totales y retiros de tarjeta cruzados como anticipos). Los
    inputs manuales los captura el usuario en la pantalla de liquidaciones.
    """
    return consolidar_compensado(db, conductor_id, periodo_inicio, periodo_fin)


@router.post("/liquidaciones/cerrar/{viaje_id}")
def cerrar_liquidacion(
    viaje_id: int,
    data: LiquidacionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    viaje = (
        db.query(ViajeODT)
        .filter(ViajeODT.id == viaje_id, ViajeODT.eliminado_en.is_(None))
        .first()
    )
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    if viaje.estado == "liquidado":
        raise HTTPException(status_code=400, detail="El viaje ya esta liquidado")

    # Cálculo canónico server-side: el cliente no decide la comisión.
    calculo = _calcular_servidor(db, viaje)
    if Decimal(str(data.comision_flete)).quantize(Decimal("0.01")) != calculo["comision_flete"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Comisión no coincide con el cálculo del servidor: "
                f"{data.comision_flete} vs {calculo['comision_flete']}"
            ),
        )

    # Todos los viajes declarados se marcan como liquidados en la misma transacción.
    viajes_ids = data.viajes_ids or [viaje_id]
    viajes_a_liquidar = (
        db.query(ViajeODT)
        .filter(ViajeODT.id.in_(viajes_ids), ViajeODT.eliminado_en.is_(None))
        .all()
    )
    if len(viajes_a_liquidar) != len(set(viajes_ids)):
        raise HTTPException(status_code=404, detail="Alguno de los viajes especificados no existe")
    for v in viajes_a_liquidar:
        if v.estado == "liquidado":
            raise HTTPException(status_code=400, detail="Uno de los viajes ya está liquidado")

    # Quien crea no puede auto-aprobarse al cierre.
    if data.aprobado_por is not None and data.aprobado_por == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Quien crea la liquidación no puede ser quien la aprueba",
        )

    # COMPENSADO_RC (FASE A2): consolidados del periodo calculados por el servidor
    # (conteo de viajes, comisiones totales y retiros de tarjeta cruzados).
    consolidado = consolidar_compensado(db, data.conductor_id, data.periodo_inicio, data.periodo_fin)

    liquidacion = LiquidacionConductor(
        conductor_id=data.conductor_id,
        vehiculo_id=data.vehiculo_id,
        periodo_inicio=data.periodo_inicio,
        periodo_fin=data.periodo_fin,
        comision_flete=calculo["comision_flete"],
        porcentaje_comision=calculo["porcentaje_comision"],
        # COMPENSADO_RC: inputs manuales adicionales
        salario_basico=data.salario_basico,
        auxilio_transporte=data.auxilio_transporte,
        papeleria=data.papeleria,
        descuento_salud_pension=data.descuento_salud_pension,
        # COMPENSADO_RC: calculados por el servidor
        retiros_tarjeta_anticipos=consolidado["retiros_tarjeta_anticipos"],
        viajes_nacionales=consolidado["viajes_nacionales"],
        viajes_urbanos=consolidado["viajes_urbanos"],
        total_viajes=consolidado["total_viajes"],
        comisiones_total=consolidado["comisiones_total"],
        bonificaciones=data.bonificaciones,
        viaticos_reconocidos=data.viaticos_reconocidos,
        otros_haberes=data.otros_haberes,
        anticipos_entregados=data.anticipos_entregados,
        gastos_a_cargo_conductor=data.gastos_a_cargo_conductor,
        prestamos=data.prestamos,
        otros_descuentos=data.otros_descuentos,
        viajes_ids=viajes_ids,
        estado=data.estado,
        fecha_pago=data.fecha_pago,
        forma_pago_liquidacion=data.forma_pago_liquidacion,
        num_comprobante_pago=data.num_comprobante_pago,
        observaciones=data.observaciones,
        creado_por=current_user.id,
        aprobado_por=data.aprobado_por,
    )
    db.add(liquidacion)
    for v in viajes_a_liquidar:
        v.estado = "liquidado"
    db.commit()
    db.refresh(liquidacion)

    return {
        "mensaje": "Liquidacion cerrada y viajes actualizados a liquidado",
        "liquidacion_id": liquidacion.id,
        "viaje_id": viaje.id,
        "estado_viaje": viaje.estado,
        "saldo_neto": liquidacion.saldo_neto,
    }


@router.post("/liquidaciones/{liquidacion_id}/aprobar")
def aprobar_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    liquidacion = (
        db.query(LiquidacionConductor)
        .filter(
            LiquidacionConductor.id == liquidacion_id,
            LiquidacionConductor.eliminado_en.is_(None),
        )
        .first()
    )
    if not liquidacion:
        raise HTTPException(status_code=404, detail="Liquidación no encontrada")
    if liquidacion.aprobado_por is not None:
        raise HTTPException(status_code=400, detail="La liquidación ya está aprobada")
    if liquidacion.creado_por == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Quien crea la liquidación no puede aprobarla",
        )
    liquidacion.aprobado_por = current_user.id
    liquidacion.estado = "aprobado"
    db.commit()
    db.refresh(liquidacion)
    return {
        "mensaje": "Liquidación aprobada",
        "liquidacion_id": liquidacion.id,
        "aprobado_por": liquidacion.aprobado_por,
        "estado": liquidacion.estado,
    }