from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from decimal import Decimal

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario
from app.models.operaciones import ViajeODT, Gasto
from app.models.financiero import LiquidacionConductor, Ingreso
from app.schemas.liquidacion import LiquidacionCalculateResponse, LiquidacionCreate

router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_LIQUIDACIONES))])


@router.get("/liquidaciones/calcular/{viaje_id}", response_model=LiquidacionCalculateResponse)
def calcular_liquidacion(
    viaje_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    viaje = db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    conductor_id = viaje.conductor_id
    vehiculo_id = viaje.vehiculo_id

    gastos_empresa = db.query(func.coalesce(func.sum(Gasto.valor_total), Decimal(0))).filter(
        and_(Gasto.viaje_id == viaje_id, Gasto.asumido_por == "empresa")
    ).scalar() or Decimal(0)

    gastos_conductor = db.query(func.coalesce(func.sum(Gasto.valor_total), Decimal(0))).filter(
        and_(Gasto.viaje_id == viaje_id, Gasto.asumido_por == "conductor")
    ).scalar() or Decimal(0)

    anticipos = db.query(func.coalesce(func.sum(Ingreso.valor), Decimal(0))).filter(
        and_(Ingreso.viaje_id == viaje_id, Ingreso.tipo_ingreso == "anticipo")
    ).scalar() or Decimal(0)

    ingresos_total = db.query(func.coalesce(func.sum(Ingreso.valor), Decimal(0))).filter(
        Ingreso.viaje_id == viaje_id
    ).scalar() or Decimal(0)

    flete_neto = viaje.flete_neto or Decimal(0)
    comision_flete = flete_neto * Decimal("0.10")

    total_anticipos = anticipos
    total_ingresos = ingresos_total

    saldo_neto = flete_neto - gastos_empresa - total_anticipos - comision_flete

    return LiquidacionCalculateResponse(
        viaje_id=viaje_id,
        vehiculo_id=vehiculo_id,
        conductor_id=conductor_id,
        valor_flete_manifiesto=viaje.valor_flete_manifiesto,
        retefuente_valor=viaje.retefuente_valor,
        reteica_valor=viaje.reteica_valor,
        flete_neto=flete_neto,
        total_gastos_empresa=gastos_empresa,
        total_gastos_conductor=gastos_conductor,
        total_anticipos=total_anticipos,
        total_ingresos=total_ingresos,
        comision_flete=comision_flete,
        saldo_neto=saldo_neto,
    )


@router.post("/liquidaciones/cerrar/{viaje_id}")
def cerrar_liquidacion(
    viaje_id: int,
    data: LiquidacionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    viaje = db.query(ViajeODT).filter(ViajeODT.id == viaje_id).first()
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    if viaje.estado == "liquidado":
        raise HTTPException(status_code=400, detail="El viaje ya esta liquidado")

    liquidacion = LiquidacionConductor(
        conductor_id=data.conductor_id,
        vehiculo_id=data.vehiculo_id,
        periodo_inicio=data.periodo_inicio,
        periodo_fin=data.periodo_fin,
        comision_flete=data.comision_flete,
        porcentaje_comision=data.porcentaje_comision,
        bonificaciones=data.bonificaciones,
        viaticos_reconocidos=data.viaticos_reconocidos,
        otros_haberes=data.otros_haberes,
        anticipos_entregados=data.anticipos_entregados,
        gastos_a_cargo_conductor=data.gastos_a_cargo_conductor,
        prestamos=data.prestamos,
        otros_descuentos=data.otros_descuentos,
        viajes_ids=data.viajes_ids,
        estado=data.estado,
        fecha_pago=data.fecha_pago,
        forma_pago_liquidacion=data.forma_pago_liquidacion,
        num_comprobante_pago=data.num_comprobante_pago,
        observaciones=data.observaciones,
        creado_por=data.creado_por or current_user.id,
        aprobado_por=data.aprobado_por or current_user.id,
    )
    db.add(liquidacion)

    viaje.estado = "liquidado"
    db.commit()
    db.refresh(liquidacion)
    db.refresh(viaje)

    return {
        "mensaje": "Liquidacion cerrada y viaje actualizado a liquidado",
        "liquidacion_id": liquidacion.id,
        "viaje_id": viaje.id,
        "estado_viaje": viaje.estado,
        "saldo_neto": liquidacion.saldo_neto,
    }