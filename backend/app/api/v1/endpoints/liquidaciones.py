from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from decimal import Decimal
from calendar import monthrange

from app.api.v1.deps import get_current_user, RoleChecker
from app.core.config import settings
from app.core.roles import ROLES_LIQUIDACIONES
from app.db.session import get_db
from app.models.flota import Usuario, Conductor
from app.models.operaciones import ViajeODT, Gasto
from app.models.financiero import LiquidacionConductor, Ingreso
from app.schemas.liquidacion import (
    LiquidacionCalculateResponse,
    LiquidacionCreate,
    CierreMensualCreate,
    CierreMensualResponse,
)
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
                Ingreso.tipo_ingreso == "anticipo_manifiesto",
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

    # B2: un viaje que ya pertenece a un cierre mensual (borrador o aprobado)
    # no puede cerrarse individualmente: evita el doble conteo del periodo.
    # Va ANTES del check de estado para dar el mensaje específico: el cierre
    # mensual marca las ODTs como 'liquidado', así que el 400 genérico llegaría
    # antes y enmascararía la causa real.
    cierre_existente = (
        db.query(LiquidacionConductor)
        .filter(
            LiquidacionConductor.es_cierre_mensual.is_(True),
            LiquidacionConductor.eliminado_en.is_(None),
            LiquidacionConductor.viajes_ids.any(viaje_id),
        )
        .first()
    )
    if cierre_existente:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El viaje ya pertenece al cierre mensual #{cierre_existente.id} "
                f"({cierre_existente.periodo_ym}). Cerrar individualmente causaría doble conteo."
            ),
        )

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


# ---------------------------------------------------------------------------
# B2 — Cierre mensual COMPENSADO_RC
# ---------------------------------------------------------------------------
def _limites_mes(periodo_ym: str) -> tuple:
    """Primer y último día del mes 'YYYY-MM' (para el filtro del consolidado)."""
    anio, mes = int(periodo_ym[:4]), int(periodo_ym[5:7])
    ultimo_dia = monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo_dia)


@router.post("/liquidaciones/cierre-mensual", response_model=CierreMensualResponse)
def crear_cierre_mensual(
    data: CierreMensualCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """B2 — Crea el cierre mensual consolidado del conductor (estado borrador).

    Reglas cerradas con el negocio:
      * mes = liquidación del conductor (misma tabla, es_cierre_mensual=true);
      * un solo cierre por (conductor, periodo_ym) -> si existe, 409;
      * D5-c: si hay ODTs del rango ya liquidadas individualmente -> 409 preventivo
        (reabrí esas liquidaciones o cerrá solo las no liquidadas);
      * deja el cierre en borrador: mientras exista, /cerrar/{viaje_id} rechaza 409.
    """
    conductor = db.query(Conductor).filter(Conductor.id == data.conductor_id).first()
    if not conductor:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")

    periodo_inicio, periodo_fin = _limites_mes(data.periodo_ym)

    # 1) Un solo cierre mensual por conductor+mes (aunque sea borrador).
    existente = (
        db.query(LiquidacionConductor)
        .filter(
            LiquidacionConductor.conductor_id == data.conductor_id,
            LiquidacionConductor.periodo_ym == data.periodo_ym,
            LiquidacionConductor.es_cierre_mensual.is_(True),
            LiquidacionConductor.eliminado_en.is_(None),
        )
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ya existe un cierre mensual #{existente.id} para el periodo "
                f"{data.periodo_ym} de este conductor"
            ),
        )

    # 2) D5-c: ODTs del rango ya liquidadas individualmente -> doble conteo.
    odts_ya_liquidadas = (
        db.query(ViajeODT)
        .filter(
            ViajeODT.conductor_id == data.conductor_id,
            ViajeODT.estado == "liquidado",
            ViajeODT.fecha_salida >= periodo_inicio,
            ViajeODT.fecha_salida <= periodo_fin,
            ViajeODT.eliminado_en.is_(None),
        )
        .all()
    )
    if odts_ya_liquidadas:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Hay {len(odts_ya_liquidadas)} viaje(s) del periodo ya liquidados "
                "individualmente (ids: "
                + ", ".join(str(v.id) for v in odts_ya_liquidadas[:5])
                + "). Reabrí esas liquidaciones o cerrá el mes solo sobre las no liquidadas."
            ),
        )

    # 3) Consolidado del mes (fuente de verdad server-side).
    consolidado = consolidar_compensado(db, data.conductor_id, periodo_inicio, periodo_fin)
    viajes_ids = consolidado["odts_incluidas"]

    # 4) Liquidación mensual. La comisión del mes se calcula y se persiste como
    #    comision_flete (sumando único de total_haberes) para que las columnas
    #    GENERATED sumen el mes sin doble conteo.
    liquidacion = LiquidacionConductor(
        conductor_id=data.conductor_id,
        vehiculo_id=None,  # B2: el vehículo vive en cada ODT, el cierre no lo necesita
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        es_cierre_mensual=True,
        comision_flete=consolidado["comisiones_total"],
        porcentaje_comision=None,
        # COMPENSADO_RC — inputs manuales del usuario
        salario_basico=data.salario_basico,
        auxilio_transporte=data.auxilio_transporte,
        papeleria=data.papeleria,
        descuento_salud_pension=data.descuento_salud_pension,
        bonificaciones=data.bonificaciones,
        viaticos_reconocidos=data.viaticos_reconocidos,
        otros_haberes=data.otros_haberes,
        anticipos_entregados=data.anticipos_entregados,
        gastos_a_cargo_conductor=data.gastos_a_cargo_conductor,
        prestamos=data.prestamos,
        otros_descuentos=data.otros_descuentos,
        # COMPENSADO_RC — calculados por el servidor
        retiros_tarjeta_anticipos=consolidado["retiros_tarjeta_anticipos"],
        viajes_nacionales=consolidado["viajes_nacionales"],
        viajes_urbanos=consolidado["viajes_urbanos"],
        total_viajes=consolidado["total_viajes"],
        comisiones_total=consolidado["comisiones_total"],
        viajes_ids=viajes_ids,
        estado="borrador",
        observaciones=data.observaciones,
        creado_por=current_user.id,
    )
    db.add(liquidacion)

    # 5) Los viajes del mes quedan "liquidados" por el cierre mensual.
    if viajes_ids:
        db.query(ViajeODT).filter(ViajeODT.id.in_(viajes_ids)).update(
            {ViajeODT.estado: "liquidado"}, synchronize_session=False
        )

    db.commit()
    db.refresh(liquidacion)
    return liquidacion


@router.get("/liquidaciones/cierre-mensual", response_model=CierreMensualResponse)
def obtener_cierre_mensual(
    conductor_id: int,
    periodo_ym: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """B2 — Devuelve el cierre mensual existente o 404."""
    liquidacion = (
        db.query(LiquidacionConductor)
        .filter(
            LiquidacionConductor.conductor_id == conductor_id,
            LiquidacionConductor.periodo_ym == periodo_ym,
            LiquidacionConductor.es_cierre_mensual.is_(True),
            LiquidacionConductor.eliminado_en.is_(None),
        )
        .first()
    )
    if not liquidacion:
        raise HTTPException(
            status_code=404,
            detail=f"No existe cierre mensual para {periodo_ym} de ese conductor",
        )
    return liquidacion


@router.post("/liquidaciones/{liquidacion_id}/reabrir")
def reabrir_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """B2 — Reabre una liquidación aprobada a borrador (con rastro en observaciones).

    No sobrescribe en silencio: el histórico queda documentado con
    '[reabierto YYYY-MM-DD por <usuario>]' y se libera aprobado_por.
    """
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
    if liquidacion.estado != "aprobado":
        raise HTTPException(status_code=400, detail="Solo se puede reabrir una liquidación aprobada")

    liquidacion.estado = "borrador"
    liquidacion.aprobado_por = None
    rastro = f"[reabierto {date.today().isoformat()} por {current_user.correo}]"
    liquidacion.observaciones = f"{liquidacion.observaciones or ''}\n{rastro}".strip()

    # B2: si es un cierre mensual reabierto, los viajes del mes siguen bloqueados
    # para cierre individual mientras exista el cierre (borrador inclusive).
    db.commit()
    db.refresh(liquidacion)
    return {
        "mensaje": "Liquidación reabierta a borrador",
        "liquidacion_id": liquidacion.id,
        "estado": liquidacion.estado,
        "rastro": rastro,
    }


@router.post("/liquidaciones/{liquidacion_id}/cancelar")
def cancelar_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """B2 — Cancela una liquidación en borrador y libera los viajes asociados.

    Solo borrador (lo aprobado se reabre antes de cancelar). El soft-delete
    (eliminado_en) libera la restricción del cierre mensual, por lo que:
      * las ODTs del cierre vuelven a 'en_curso' (pueden cerrarse individualmente);
      * el periodo vuelve a poder cerrarse (el UNIQUE parcial ignora eliminados).
    """
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
    if liquidacion.estado != "borrador":
        raise HTTPException(status_code=400, detail="Solo se puede cancelar una liquidación en borrador")

    liquidacion.eliminado_en = func.now()
    liquidacion.eliminado_por = current_user.id

    # Libera los viajes que el cierre/liq marcó como liquidados.
    viajes_ids = liquidacion.viajes_ids or []
    if viajes_ids:
        db.query(ViajeODT).filter(
            ViajeODT.id.in_(viajes_ids),
            ViajeODT.estado == "liquidado",
        ).update({ViajeODT.estado: "en_curso"}, synchronize_session=False)

    db.commit()
    db.refresh(liquidacion)
    return {
        "mensaje": "Liquidación cancelada; viajes liberados para cierre individual",
        "liquidacion_id": liquidacion.id,
        "estado": liquidacion.estado,
        "viajes_liberados": len(viajes_ids),
    }