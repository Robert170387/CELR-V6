"""R1 — Lectura del resumen completo de una ODT.

Solo lectura. No recalcula, no commitea, no toca la base de datos.

Por qué NO se usa ``v_odt_resumen``: la vista recalcula
``saldo_flete_esperado`` como ``COALESCE(flete_neto,0) - COALESCE(anticipo,0)``
en vez de leer el snapshot, así que un viaje que el servidor nunca calculó
aparece con un saldo plausible. Aquí se leen los snapshots de la tabla, donde
un ``NULL`` sí significa "no calculado" y se puede propagar.

Fuente única de lectura: el ``saldo_flete_esperado`` que viaja en ``viaje`` y la
cifra citada dentro de ``informativos`` salen del MISMO objeto ORM, en la misma
llamada a ``bloqueos_cierre_odt``. Si se leyeran por separado, una respuesta
podría traer dos números distintos para la misma cosa — que es exactamente el
defecto que R1-pre-2 cerró entre GET y POST.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.financiero import FlypassTransaccion, Ingreso
from app.models.operaciones import Gasto, ViajeODT
from app.services.operaciones import bloqueos_cierre_odt

# Tope por lista. NO hereda el ``le=100`` de ``/gastos``: ese tope es del
# endpoint global y truncaría en silencio. Acá el corte se declara en la
# respuesta con ``truncado``.
TOPE_LISTA_RESUMEN = 200

# Los 6 snapshots que escribe ``recalcular_viaje``. ``otras_deducciones``,
# ``anticipo_manifiesto`` y los porcentajes son base de entrada, no snapshots.
SNAPSHOTS = (
    "retefuente_valor",
    "reteica_valor",
    "comision_conductor",
    "saldo_flete_esperado",
    "gastos_totales_viaje",
    "utilidad_neta_odt",
)


def _lista(db: Session, modelo, filtro, orden, reconstruir) -> dict:
    """Devuelve ``{items, total, truncado}`` para una relación 1:N.

    ``total`` es el conteo real en la BD, no el largo de ``items``: sin eso el
    cliente no puede notar que le cortaron la lista.
    """
    total = db.query(func.count(modelo.id)).filter(*filtro).scalar() or 0
    filas = (
        db.query(modelo)
        .filter(*filtro)
        .order_by(*orden)
        .limit(TOPE_LISTA_RESUMEN)
        .all()
    )
    return {
        "items": [reconstruir(f) for f in filas],
        "total": total,
        "truncado": total > len(filas),
    }


def _total_deducibles(viaje: ViajeODT) -> object:
    """Suma de deducciones, o ``None`` si falta algún snapshot.

    Sumar 0 cuando falta un snapshot es la misma mentira que la vista: produce
    una cifra plausible de algo que nadie calculó. Acá el ``None`` se propaga.
    ``otras_deducciones`` es NOT NULL en el schema, así que la condición real
    es sobre los dos snapshots de retención.
    """
    if viaje.retefuente_valor is None or viaje.reteica_valor is None:
        return None
    return viaje.retefuente_valor + viaje.reteica_valor + viaje.otras_deducciones


def resumen_viaje(db: Session, viaje: ViajeODT) -> dict:
    """Arma el resumen completo de la ODT. No muta ni persiste nada."""
    # 1) Estado de los snapshots, leído de la BD ANTES de tocar nada.
    #    ``faltantes`` no sale en la respuesta: el contrato acordado es un solo
    #    boolean. Si R1-frontend necesita el detalle, se agrega ahí con su
    #    consumidor, no antes por comodidad.
    snapshots_completos = not [c for c in SNAPSHOTS if getattr(viaje, c) is None]
    total_deducibles = _total_deducibles(viaje)
    # Se guardan los valores CRUDO porque el paso 2 puede cambiarlos.
    en_base = {c: getattr(viaje, c) for c in SNAPSHOTS}

    # 2) Bloqueos e informativos: UNA llamada.
    estado = bloqueos_cierre_odt(db, viaje)

    # 2b) Se restauran los snapshots al valor de la BD.
    #
    # `bloqueos_cierre_odt` recalcula EN MEMORIA cuando alguno esta en NULL. Como
    # ningun GET commitea, el cambio se pierde al cerrar la sesion, pero el objeto
    # ORM ya quedo mutado. Serializarlo sin restaurar producia un payload con
    # cifras recalculadas al lado de `snapshots_completos=false`, y el modal se
    # contradia a si mismo: decia "estos valores aparecen como —" mientras
    # mostraba el resultado del recalculo. Detectado por render en R1-frontend.
    #
    # Que la respuesta exponga el estado de la BD y no uno hipotetico es lo que
    # hace confiable `snapshots_completos`: si el flag dice false, los campos de
    # abajo son efectivamente null.
    for campo, valor in en_base.items():
        setattr(viaje, campo, valor)

    # 3) Listas 1:N.
    gastos = _lista(
        db, Gasto,
        (Gasto.viaje_id == viaje.id, Gasto.eliminado_en.is_(None)),
        (Gasto.fecha_gasto, Gasto.id),
        lambda g: {
            "id": g.id,
            "categoria": g.categoria,
            "descripcion": g.descripcion,
            "fecha_gasto": g.fecha_gasto,
            "valor_total": g.valor_total,
            "responsable_pago": g.responsable_pago,
            "asumido_por": g.asumido_por,
            "estado_pago": g.estado_pago,
        },
    )
    ingresos = _lista(
        db, Ingreso,
        (Ingreso.viaje_id == viaje.id, Ingreso.eliminado_en.is_(None)),
        (Ingreso.fecha_ingreso, Ingreso.id),
        lambda i: {
            "id": i.id,
            "tipo_ingreso": i.tipo_ingreso,
            "descripcion": i.descripcion,
            "fecha_ingreso": i.fecha_ingreso,
            "valor": i.valor,
            "estado_pago": i.estado_pago,
        },
    )
    # FlypassTransaccion NO tiene soft delete: no se filtra por eliminado_en.
    peajes = _lista(
        db, FlypassTransaccion,
        (FlypassTransaccion.viaje_id == viaje.id,),
        (FlypassTransaccion.fecha_transaccion, FlypassTransaccion.id),
        lambda f: {
            "id": f.id,
            "num_transaccion_flypass": f.num_transaccion_flypass,
            "nombre_peaje": f.nombre_peaje,
            "ciudad_peaje": f.ciudad_peaje,
            "fecha_transaccion": f.fecha_transaccion,
            "valor": f.valor,
            "legalizado": f.gasto_id is not None,
        },
    )

    return {
        "viaje_id": viaje.id,
        "numero_odt": viaje.numero_odt,
        "snapshots_completos": snapshots_completos,
        "total_deducibles": total_deducibles,
        "viaje": viaje,
        "gastos": gastos,
        "ingresos": ingresos,
        "peajes": peajes,
        "bloqueos": estado["bloqueos"],
        "informativos": estado["informativos"],
    }
