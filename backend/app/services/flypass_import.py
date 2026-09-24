"""Importador de consumos Flypass desde archivos Excel.

El servicio conserva la fila original en ``raw_data``, resuelve la placa a un
vehiculo, hace matching de gastos existentes y crea los gastos peaje que no
tengan un match unico. Toda la escritura se ejecuta en una sola transaccion.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
from typing import Any
import math

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.financiero import FlypassTransaccion
from app.models.flota import Vehiculo
from app.models.operaciones import Gasto, Proveedor, ViajeODT

CERO = Decimal("0")
CENTAVOS = Decimal("0.01")
MAX_ARCHIVO_BYTES = 5 * 1024 * 1024
CATEGORIA_PEAJES = "peajes"
PROVEEDOR_FLYPASS = "Flypass"
MAX_MONTO_FLYPASS = Decimal("99999999.99")

CABECERAS_REQUERIDAS = {
    "TRANSACCION",
    "PLACA",
    "FECHA_MVTO",
    "MONTO",
    "PUNTO ATENCION",
}


def _normalizar_encabezado(valor: Any) -> str:
    """Normaliza encabezados sin alterar su contenido de presentación."""
    if valor is None:
        return ""
    return " ".join(str(valor).replace("\ufeff", "").strip().upper().split())


def _valor_jsonable(valor: Any) -> Any:
    """Convierte valores de Excel a tipos seguros para JSONB."""
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, float) and not math.isfinite(valor):
        return str(valor)
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def _parsear_fecha_hora(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            return valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc)
    if isinstance(valor, date):
        return datetime.combine(valor, time.min).replace(tzinfo=timezone.utc)
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        try:
            convertido = from_excel(valor)
            if isinstance(convertido, datetime):
                if convertido.tzinfo is None:
                    return convertido.replace(tzinfo=timezone.utc)
                return convertido.astimezone(timezone.utc)
            if isinstance(convertido, date):
                return datetime.combine(convertido, time.min).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass

    texto = "" if valor is None else str(valor).strip()
    if not texto:
        raise ValueError("FECHA_MVTO está vacío")

    formatos = (
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    )
    for formato in formatos:
        try:
            convertido = datetime.strptime(texto, formato)
            return convertido.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        convertido = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        if convertido.tzinfo is None:
            return convertido.replace(tzinfo=timezone.utc)
        return convertido.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f"FECHA_MVTO inválida: {texto!r}") from exc


def _parsear_monto(valor: Any) -> Decimal:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValueError("MONTO está vacío")
    if isinstance(valor, bool):
        raise ValueError("MONTO no es numérico")

    if isinstance(valor, Decimal):
        monto = valor
    elif isinstance(valor, (int, float)):
        try:
            monto = Decimal(str(valor))
        except InvalidOperation as exc:
            raise ValueError(f"MONTO no es numérico: {valor!r}") from exc
    else:
        texto = str(valor).strip().replace("$", "").replace("COP", "").replace(" ", "")
        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        elif "," in texto:
            texto = texto.replace(",", ".")
        try:
            monto = Decimal(texto)
        except InvalidOperation as exc:
            raise ValueError(f"MONTO no es numérico: {valor!r}") from exc

    if not monto.is_finite() or monto <= CERO:
        raise ValueError(f"MONTO debe ser mayor que cero: {valor!r}")
    if monto > MAX_MONTO_FLYPASS:
        raise ValueError(f"MONTO supera el máximo permitido: {valor!r}")
    if monto.as_tuple().exponent < -2:
        raise ValueError(f"MONTO tiene más de dos decimales: {valor!r}")
    return monto.quantize(CENTAVOS)


def _parsear_fila(
    valores: tuple,
    encabezados: list[tuple[str, str, int]],
    indices: dict[str, int],
    numero_fila: int,
) -> dict[str, Any]:
    def obtener(nombre: str) -> Any:
        indice = indices[nombre]
        return valores[indice] if indice < len(valores) else None

    def texto_requerido(nombre: str) -> str:
        valor = obtener(nombre)
        texto = "" if valor is None else str(valor).strip()
        if not texto:
            raise ValueError(f"{nombre} está vacío")
        return texto

    transaccion = texto_requerido("TRANSACCION")
    if len(transaccion) > 50:
        raise ValueError("TRANSACCION supera 50 caracteres")

    placa = texto_requerido("PLACA").upper()
    fecha_hora = _parsear_fecha_hora(obtener("FECHA_MVTO"))
    fecha = fecha_hora.date()
    monto = _parsear_monto(obtener("MONTO"))
    punto = "" if obtener("PUNTO ATENCION") is None else str(obtener("PUNTO ATENCION")).strip()
    if len(punto) > 100:
        raise ValueError("PUNTO ATENCION supera 100 caracteres")

    raw_data = {
        etiqueta: _valor_jsonable(valores[indice] if indice < len(valores) else None)
        for etiqueta, _normalizada, indice in encabezados
    }
    return {
        "fila": numero_fila,
        "transaccion": transaccion,
        "placa": placa,
        "fecha": fecha,
        "fecha_hora": fecha_hora,
        "monto": monto,
        "punto": punto,
        "raw_data": raw_data,
    }


def _parsear_libro(contenido: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Valida la estructura y devuelve filas válidas y diagnósticos por fila."""
    try:
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"No se pudo leer el archivo .xlsx: {exc}") from exc

    try:
        hojas = libro.worksheets
        if not hojas:
            raise ValueError("El archivo no contiene hojas")

        filas_iter = hojas[0].iter_rows(values_only=True)
        primera_fila = next(filas_iter, None)
        if not primera_fila:
            raise ValueError("La primera hoja está vacía")

        encabezados: list[tuple[str, str, int]] = []
        vistos: set[str] = set()
        for indice, valor in enumerate(primera_fila):
            normalizado = _normalizar_encabezado(valor)
            if not normalizado:
                continue
            if normalizado in vistos:
                raise ValueError(f"Encabezado duplicado: {normalizado}")
            vistos.add(normalizado)
            encabezados.append((str(valor).strip(), normalizado, indice))

        faltan = sorted(CABECERAS_REQUERIDAS - vistos)
        if faltan:
            raise ValueError("Faltan columnas requeridas: " + ", ".join(faltan))

        indices = {
            normalizado: indice
            for _, normalizado, indice in encabezados
        }
        filas: list[dict[str, Any]] = []
        errores: list[dict[str, Any]] = []
        for numero_fila, valores in enumerate(filas_iter, start=2):
            if not valores or all(
                valor is None or (isinstance(valor, str) and not valor.strip())
                for valor in valores
            ):
                continue
            try:
                filas.append(_parsear_fila(valores, encabezados, indices, numero_fila))
            except ValueError as exc:
                errores.append(
                    {
                        "fila": numero_fila,
                        "tipo": "dato_invalido",
                        "error": str(exc),
                    }
                )
        return filas, errores
    finally:
        libro.close()


def _hash_gasto_flypass(num_transaccion: str) -> str:
    return sha256(f"flypass-import|{num_transaccion}".encode("utf-8")).hexdigest()


def _vehiculo_por_placa(db: Session, placa: str) -> Vehiculo | None:
    return (
        db.query(Vehiculo)
        .filter(func.upper(func.trim(Vehiculo.placa)) == placa)
        .first()
    )


def _proveedor_flypass(db: Session) -> Proveedor:
    proveedor = (
        db.query(Proveedor)
        .filter(
            (func.lower(func.trim(Proveedor.razon_social)) == PROVEEDOR_FLYPASS.lower())
            | (
                func.lower(func.trim(Proveedor.nombre_comercial))
                == PROVEEDOR_FLYPASS.lower()
            )
        )
        .first()
    )
    if proveedor:
        return proveedor

    # nit es nullable en el modelo; no se requiere un placeholder artificial.
    proveedor = Proveedor(
        nit=None,
        razon_social=PROVEEDOR_FLYPASS,
        nombre_comercial=PROVEEDOR_FLYPASS,
        tipo="pasarela_pagos",
    )
    db.add(proveedor)
    db.flush()
    return proveedor


def _gastos_candidatos(
    db: Session,
    vehiculo_id: int,
    monto: Decimal,
    fecha: date,
) -> list[Gasto]:
    gastos_vinculados = select(FlypassTransaccion.gasto_id).where(
        FlypassTransaccion.gasto_id.is_not(None)
    )
    return (
        db.query(Gasto)
        .filter(
            Gasto.vehiculo_id == vehiculo_id,
            Gasto.categoria == CATEGORIA_PEAJES,
            Gasto.valor_total == monto,
            Gasto.fecha_gasto >= fecha - timedelta(days=1),
            Gasto.fecha_gasto <= fecha + timedelta(days=1),
            Gasto.eliminado_en.is_(None),
            ~Gasto.id.in_(gastos_vinculados),
        )
        .order_by(Gasto.id)
        .all()
    )


def _odt_para_fecha(db: Session, vehiculo_id: int, fecha: date) -> ViajeODT | None:
    candidatos = (
        db.query(ViajeODT)
        .filter(
            ViajeODT.vehiculo_id == vehiculo_id,
            ViajeODT.eliminado_en.is_(None),
            ViajeODT.estado != "cancelado",
            ViajeODT.fecha_salida <= fecha,
            (ViajeODT.fecha_llegada.is_(None)) | (ViajeODT.fecha_llegada >= fecha),
        )
        .order_by(ViajeODT.id)
        .all()
    )
    return candidatos[0] if len(candidatos) == 1 else None


def _detalle_candidatos(candidatos: list[Gasto]) -> list[dict[str, Any]]:
    return [
        {
            "gasto_id": candidato.id,
            "valor": str(candidato.valor_total),
            "fecha_gasto": candidato.fecha_gasto.isoformat(),
        }
        for candidato in candidatos
    ]


def importar_excel_flypass(db: Session, contenido: bytes, nombre_archivo: str) -> dict:
    """Parsea el `.xlsx`, valida filas e importa; devuelve el reporte.

    Los errores de una fila se acumulan en ``errores`` y no impiden procesar
    las demás. Los errores estructurales del libro abortan antes de escribir.
    """
    if not nombre_archivo.lower().endswith(".xlsx"):
        raise ValueError("Solo se admiten archivos .xlsx")
    if not contenido:
        raise ValueError("El archivo está vacío")
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise ValueError("El archivo supera el límite de 5 MB")

    filas, errores = _parsear_libro(contenido)
    reporte: dict[str, Any] = {
        "insertados": 0,
        "duplicados": 0,
        "sin_placa": 0,
        "ambiguos": 0,
        "creados_gastos": 0,
        "matcheados_gastos": 0,
        "sin_odt": 0,
        "errores": errores,
    }
    vistas: set[str] = set()
    proveedor: Proveedor | None = None

    try:
        for fila in filas:
            transaccion = fila["transaccion"]
            if transaccion in vistas:
                reporte["duplicados"] += 1
                continue

            existente = (
                db.query(FlypassTransaccion)
                .filter(FlypassTransaccion.num_transaccion_flypass == transaccion)
                .first()
            )
            if existente:
                vistas.add(transaccion)
                reporte["duplicados"] += 1
                continue

            vehiculo = _vehiculo_por_placa(db, fila["placa"])
            if vehiculo is None:
                reporte["sin_placa"] += 1
                reporte["errores"].append(
                    {
                        "fila": fila["fila"],
                        "tipo": "sin_placa",
                        "placa": fila["placa"],
                    }
                )
                continue

            candidatos = _gastos_candidatos(
                db, vehiculo.id, fila["monto"], fila["fecha"]
            )
            if len(candidatos) > 1:
                reporte["ambiguos"] += 1
                reporte["errores"].append(
                    {
                        "fila": fila["fila"],
                        "tipo": "gastos_ambiguos",
                        "candidatos": _detalle_candidatos(candidatos),
                    }
                )
                continue

            gasto_creado = False
            if len(candidatos) == 1:
                gasto = candidatos[0]
                reporte["matcheados_gastos"] += 1
            else:
                if proveedor is None:
                    proveedor = _proveedor_flypass(db)
                gasto = Gasto(
                    viaje_id=None,
                    vehiculo_id=vehiculo.id,
                    proveedor_id=proveedor.id,
                    categoria=CATEGORIA_PEAJES,
                    descripcion=(
                        f"Peaje Flypass {fila['punto']} — {fila['transaccion']}"
                    ),
                    fecha_gasto=fila["fecha"],
                    valor_total=fila["monto"],
                    responsable_pago="empresa",
                    asumido_por="empresa",
                    metodo_pago="tag",
                    estado_pago="pendiente_por_pagar",
                    tiene_num_factura=False,
                    hash_comprobante=_hash_gasto_flypass(transaccion),
                )
                db.add(gasto)
                db.flush()
                gasto_creado = True
                reporte["creados_gastos"] += 1

            odt = _odt_para_fecha(db, vehiculo.id, fila["fecha"])
            if odt is None:
                reporte["sin_odt"] += 1
            elif gasto_creado:
                gasto.viaje_id = odt.id

            transaccion_db = FlypassTransaccion(
                vehiculo_id=vehiculo.id,
                fecha_transaccion=fila["fecha_hora"],
                nombre_peaje=fila["punto"] or None,
                ciudad_peaje=None,
                ciudad_peaje_municipio_id=None,
                valor=fila["monto"],
                num_transaccion_flypass=transaccion,
                viaje_id=odt.id if odt else None,
                gasto_id=gasto.id,
                raw_data=fila["raw_data"],
                estado="importado",
                importado_en=datetime.now(timezone.utc),
            )
            db.add(transaccion_db)
            db.flush()
            vistas.add(transaccion)
            reporte["insertados"] += 1

        db.commit()
        return reporte
    except Exception:
        db.rollback()
        raise
