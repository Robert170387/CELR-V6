"""R1 — GET /api/v1/viajes/{id}/resumen (suite propia).

Cubre el contrato acordado: ``snapshots_completos`` como boolean unico sobre
los 6 snapshots, ``total_deducibles`` que propaga NULL en vez de rellenar con 0,
truncado explicito en las 3 listas 1:N, y fuente unica de lectura entre el campo
``saldo_flete_esperado`` y el texto de ``informativos``.

Disciplina: cada test crea sus propias filas y las borra por ID, en orden inverso
de FK. Ningun assert sobre conteos globales de la BD de desarrollo.
"""
from __future__ import annotations

import os
import re
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:admin@localhost:5433/celr_v6_db")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.auditoria import AuditoriaEvento  # noqa: E402
from app.models.financiero import FlypassTransaccion, Ingreso  # noqa: E402
from app.models.flota import Conductor, Vehiculo  # noqa: E402
from app.models.operaciones import Gasto, ViajeODT  # noqa: E402
from app.schemas.viaje import ViajeCreate  # noqa: E402
from app.services.operaciones import recalcular_viaje  # noqa: E402
from _test_helpers import capturar_token_ids, limpiar_tokens_nuevos  # noqa: E402

CLIENT = TestClient(app)

SNAPSHOT_NAMES = (
    "retefuente_valor",
    "reteica_valor",
    "comision_conductor",
    "saldo_flete_esperado",
    "gastos_totales_viaje",
    "utilidad_neta_odt",
)


def headers_admin() -> dict:
    r = CLIENT.post(
        "/api/v1/auth/login",
        json={"identificador": "test@celr.com", "contrasena": "admin123"},
    )
    assert r.status_code == 200, f"Login fallo: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def crear_viaje(db, veh_id: int, cond_id: int, fecha: date) -> ViajeODT:
    """Crea la ODT con el schema real, para que corra la misma validacion que la API."""
    data = ViajeCreate(
        vehiculo_id=veh_id,
        conductor_id=cond_id,
        origen="Prueba R1",
        destino="Prueba R1",
        fecha_salida=fecha,
        valor_flete_manifiesto=Decimal("1000000.00"),
        retefuente_porcentaje=Decimal("0"),
        reteica_porcentaje=Decimal("1"),
        otras_deducciones=Decimal("0"),
        anticipo_manifiesto=Decimal("0"),
        tipo_viaje="nacional",
    )
    viaje = ViajeODT(**data.model_dump())
    db.add(viaje)
    db.flush()
    db.refresh(viaje)
    viaje.numero_odt = f"ODT-R1-{uuid.uuid4().hex[:8].upper()}"
    recalcular_viaje(db, viaje)
    db.commit()
    db.refresh(viaje)
    return viaje


def crear_gasto(db, viaje: ViajeODT, valor: str = "1000.00", nota: str | None = None) -> Gasto:
    gasto = Gasto(
        viaje_id=viaje.id,
        vehiculo_id=viaje.vehiculo_id,
        categoria="mantenimiento",
        descripcion=nota or "Gasto de prueba R1",
        fecha_gasto=viaje.fecha_salida,
        valor_total=Decimal(valor),
        responsable_pago="empresa",
        asumido_por="empresa",
        metodo_pago="efectivo",
        estado_pago="pagado",
        tiene_num_factura=False,
        hash_comprobante=f"r1-{uuid.uuid4().hex}",
    )
    db.add(gasto)
    db.flush()
    return gasto


def crear_ingreso(db, viaje: ViajeODT, valor: str = "1000.00") -> Ingreso:
    ing = Ingreso(
        viaje_id=viaje.id,
        vehiculo_id=viaje.vehiculo_id,
        tipo_ingreso="anticipo_manifiesto",
        descripcion="Ingreso de prueba R1",
        fecha_ingreso=viaje.fecha_salida,
        valor=Decimal(valor),
        estado_pago="recibido",
    )
    db.add(ing)
    db.flush()
    return ing


def crear_peaje(db, viaje: ViajeODT) -> FlypassTransaccion:
    peaje = FlypassTransaccion(
        vehiculo_id=viaje.vehiculo_id,
        fecha_transaccion=viaje.fecha_salida,
        nombre_peaje="Peaje R1",
        ciudad_peaje="Bogota",
        valor=Decimal("50000.00"),
        num_transaccion_flypass=f"R1-{uuid.uuid4().hex[:12]}",
        viaje_id=viaje.id,
        gasto_id=None,
        estado="pendiente",
    )
    db.add(peaje)
    db.flush()
    return peaje


def numero_del_texto(texto: str) -> Decimal:
    """Extrae la cifra de un informativo sin depender del separador de miles.

    El ultimo separador es el decimal y los anteriores son de miles, asi que
    funciona con '4,414,000.00' y con '4.414.000,00'. A proposito: el test
    sobrevive al fix de ``number-format-locale`` en vez de romperse con el.
    """
    crudo = texto.split("faltan")[-1].strip()
    ultimo = max(crudo.rfind("."), crudo.rfind(","))
    if ultimo < 0:
        return Decimal(crudo)
    entero = re.sub(r"[.,]", "", crudo[:ultimo])
    return Decimal(f"{entero}.{crudo[ultimo + 1:]}")


def main() -> int:
    print("Iniciando pruebas R1 del endpoint de resumen CELR v6...")
    db = SessionLocal()
    tokens_antes = capturar_token_ids(db, "test@celr.com")
    viajes_creados: list[int] = []
    gastos_creados: list[int] = []
    ingresos_creados: list[int] = []
    peajes_creados: list[int] = []
    try:
        veh = db.query(Vehiculo).first()
        cond = db.query(Conductor).first()
        assert veh is not None and cond is not None, "Se requiere vehiculo y conductor"
        H = headers_admin()

        # --- TR-1: snapshots completos -----------------------------------
        print("\n=== TR-1: snapshots completos -> total_deducibles calculado ===")
        v1 = crear_viaje(db, veh.id, cond.id, date(2027, 1, 10))
        viajes_creados.append(v1.id)
        r = CLIENT.get(f"/api/v1/viajes/{v1.id}/resumen", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["snapshots_completos"] is True, d["snapshots_completos"]
        esperado = (v1.retefuente_valor or 0) + (v1.reteica_valor or 0) + v1.otras_deducciones
        assert Decimal(d["total_deducibles"]) == esperado, (
            f"total_deducibles {d['total_deducibles']} != {esperado}"
        )
        for campo in SNAPSHOT_NAMES:
            assert d["viaje"][campo] is not None, f"snapshot {campo} ausente en el payload"
        print(f"  snapshots_completos=True total_deducibles={d['total_deducibles']}: OK")

        # --- TR-2: snapshot NULL se propaga, no se rellena ---------------
        # Se anulan LOS 6, no dos. `snapshots_completos` declara una invariante
        # sobre los seis, asi que el escenario tiene que cubrirlos a todos: si
        # solo se anula un par, el test no puede afirmar nada sobre los otros
        # cuatro. Ver la nota de TR-11.
        print("\n=== TR-2: snapshots NULL -> snapshots_completos=False, total=null ===")
        v2 = crear_viaje(db, veh.id, cond.id, date(2027, 1, 11))
        viajes_creados.append(v2.id)
        for campo in SNAPSHOT_NAMES:
            setattr(v2, campo, None)
        db.commit()
        r = CLIENT.get(f"/api/v1/viajes/{v2.id}/resumen", headers=H)
        assert r.status_code == 200, r.text
        d2 = r.json()
        assert d2["snapshots_completos"] is False, "un snapshot NULL debe dar False"
        assert d2["total_deducibles"] is None, (
            f"total_deducibles debe ser null, no {d2['total_deducibles']!r}"
        )
        print("  snapshots_completos=False total_deducibles=null: OK")

        # --- TR-11: el payload expone el estado de la BD, no uno recalculado
        # Sin esto, `bloqueos_cierre_odt` recalcula en memoria, el objeto queda
        # mutado y el resumen devuelve cifras que la BD nunca guardo al lado de
        # un `snapshots_completos=false`. El modal se contradice a si mismo: avisa que
        # los valores son "—" y muestra el resultado del recalculo. Encontrado
        # por render en R1-frontend, no por un assert.
        #
        # Esta es la version corregida: la primera comprobaba 2 de los 6 snapshots
        # que la flag declara gobernar, y los otros 4 se colaban sin que nadie lo
        # notara. El alcance del assert tiene que ser el del contrato, no el del
        # bug que lo motivo.
        print("\n=== TR-11: con snapshots NULL, el payload NO trae cifras recalculadas ===")
        d11 = CLIENT.get(f"/api/v1/viajes/{v2.id}/resumen", headers=H).json()
        assert d11["snapshots_completos"] is False
        colados = [
            c for c in SNAPSHOT_NAMES if d11["viaje"][c] is not None
        ]
        assert not colados, (
            f"estos snapshots llegan calculados pese a estar NULL en la BD: {colados}. "
            f"El payload debe reflejar la BD, no el recalculo en memoria de "
            f"bloqueos_cierre_odt"
        )
        print(f"  los {len(SNAPSHOT_NAMES)} snapshots llegan en null pese al recalculo interno: OK")

        # --- TR-3: listas vacias ------------------------------------------
        print("\n=== TR-3: viaje sin gastos/ingresos/peajes ===")
        d3 = CLIENT.get(f"/api/v1/viajes/{v1.id}/resumen", headers=H).json()
        for clave in ("gastos", "ingresos", "peajes"):
            assert d3[clave]["items"] == [], f"{clave}.items deberia estar vacio"
            assert d3[clave]["total"] == 0, f"{clave}.total deberia ser 0"
            assert d3[clave]["truncado"] is False, f"{clave}.truncado deberia ser False"
        print("  las 3 listas: items=[] total=0 truncado=False: OK")

        # --- TR-5: solo saldo -> informativo, no bloqueo -----------------
        print("\n=== TR-5: solo saldo sin cubrir -> informativos, no bloqueos ===")
        assert d3["bloqueos"] == [], f"el saldo no debe bloquear: {d3['bloqueos']}"
        assert d3["informativos"], "el saldo sin cubrir debe informarse"
        assert "Saldo flete esperado sin cubrir" in d3["informativos"][0]
        print(f"  bloqueos=[] informativos={d3['informativos']}: OK")

        # --- TR-6: peaje pendiente -> bloquea, el saldo se informa -------
        print("\n=== TR-6: peaje Flypass pendiente -> bloqueos, no informativos ===")
        v6 = crear_viaje(db, veh.id, cond.id, date(2027, 1, 12))
        viajes_creados.append(v6.id)
        p6 = crear_peaje(db, v6)
        peajes_creados.append(p6.id)
        db.commit()
        d6 = CLIENT.get(f"/api/v1/viajes/{v6.id}/resumen", headers=H).json()
        assert d6["bloqueos"], "un peaje pendiente debe bloquear"
        assert "Flypass" in d6["bloqueos"][0]
        assert all("Flypass" not in m for m in d6["informativos"]), (
            "el peaje no debe aparecer tambien como informativo"
        )
        assert d6["peajes"]["total"] == 1
        assert d6["peajes"]["items"][0]["legalizado"] is False
        print(f"  bloqueos={d6['bloqueos']} peajes.total=1 legalizado=False: OK")

        # --- TR-7: fuente unica (campo y texto salen de la misma cifra) --
        # Ojo con la semantica: el campo es el saldo esperado TOTAL y el texto
        # dice "faltan X" = saldo menos lo recaudado. No son el mismo numero y
        # no deben serlo. Lo que debe cumplirse es que salen de la MISMA
        # lectura: shortfall + recaudado == saldo del campo. Si alguien leyera
        # el saldo de una parte y calculara el faltante con otra, esta suma
        # descuadraria.
        print("\n=== TR-7: el campo y el texto salen de la misma lectura ===")
        v7 = crear_viaje(db, veh.id, cond.id, date(2027, 1, 13))
        viajes_creados.append(v7.id)
        g7 = crear_gasto(db, v7, "77777.00")
        gastos_creados.append(g7.id)
        i7 = crear_ingreso(db, v7, "5000.00")
        ingresos_creados.append(i7.id)
        db.commit()
        d7 = CLIENT.get(f"/api/v1/viajes/{v7.id}/resumen", headers=H).json()
        campo = Decimal(d7["viaje"]["saldo_flete_esperado"])
        texto = next(
            (m for m in d7["informativos"] if "Saldo flete esperado sin cubrir" in m), None
        )
        assert texto, f"se esperaba un informativo de saldo, hubo: {d7['informativos']}"
        faltante = numero_del_texto(texto)
        # "recaudado" replica el filtro de bloqueos_cierre_odt: solo cuenta lo
        # recibido o conciliado.
        recaudado = sum(
            (
                Decimal(i["valor"])
                for i in d7["ingresos"]["items"]
                if i["estado_pago"] in ("recibido", "conciliado")
            ),
            Decimal(0),
        )
        assert campo == faltante + recaudado, (
            f"fuente unica rota: campo={campo}, faltante={faltante}, "
            f"recaudado={recaudado} -> {faltante} + {recaudado} != {campo}"
        )
        assert d7["gastos"]["total"] == 1
        assert d7["ingresos"]["total"] == 1
        assert d7["ingresos"]["items"][0]["valor"] == "5000.00"
        print(
            f"  campo={campo} = faltante {faltante} + recaudado {recaudado}: "
            f"misma lectura; gastos=1 ingresos=1: OK"
        )

        # --- TR-8: 404 ---------------------------------------------------
        print("\n=== TR-8: 404 inexistente y 404 soft-deleted ===")
        r = CLIENT.get("/api/v1/viajes/999999999/resumen", headers=H)
        assert r.status_code == 404, f"inexistente deberia ser 404, dio {r.status_code}"
        v8 = crear_viaje(db, veh.id, cond.id, date(2027, 1, 14))
        viajes_creados.append(v8.id)
        v8.eliminado_en = datetime.now(timezone.utc)
        db.commit()
        r = CLIENT.get(f"/api/v1/viajes/{v8.id}/resumen", headers=H)
        assert r.status_code == 404, f"soft-deleted deberia ser 404, dio {r.status_code}"
        print("  404 para inexistente y para soft-deleted: OK")

        # --- TR-9: truncado explicito -----------------------------------
        print("\n=== TR-9: 201 gastos -> truncado=true, tope 200 ===")
        v9 = crear_viaje(db, veh.id, cond.id, date(2027, 1, 15))
        viajes_creados.append(v9.id)
        for i in range(201):
            g = crear_gasto(db, v9, "10.00", nota=f"Gasto R1 {i:03d}")
            gastos_creados.append(g.id)
        db.commit()
        d9 = CLIENT.get(f"/api/v1/viajes/{v9.id}/resumen", headers=H).json()
        assert d9["gastos"]["total"] == 201, f"total {d9['gastos']['total']} != 201"
        assert d9["gastos"]["truncado"] is True, "truncado deberia ser True"
        assert len(d9["gastos"]["items"]) == 200, (
            f"items {len(d9['gastos']['items'])} != tope 200"
        )
        print("  total=201 items=200 truncado=True: OK")

        # --- TR-10: el GET no escribe -----------------------------------
        print("\n=== TR-10: el GET no escribe (snapshots, auditoria, filas) ===")
        db.refresh(v9)
        antes_snap = {c: getattr(v9, c) for c in SNAPSHOT_NAMES}
        antes_aud = db.query(AuditoriaEvento).count()
        antes_viajes = db.query(ViajeODT).count()
        CLIENT.get(f"/api/v1/viajes/{v9.id}/resumen", headers=H)
        CLIENT.get(f"/api/v1/viajes/{v1.id}/resumen", headers=H)
        CLIENT.get(f"/api/v1/viajes/{v2.id}/resumen", headers=H)
        db.expire_all()
        v9r = db.query(ViajeODT).filter(ViajeODT.id == v9.id).first()
        for c in SNAPSHOT_NAMES:
            assert getattr(v9r, c) == antes_snap[c], f"{c} cambio al hacer GET"
        assert db.query(AuditoriaEvento).count() == antes_aud, "el GET escribio en auditoria"
        assert db.query(ViajeODT).count() == antes_viajes, "el GET creo filas"
        print("  0 escrituras: snapshots, auditoria_evento y conteos intactos: OK")

        print("\n[TODOS LOS TESTS R1 DE RESUMEN PASARON]")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR EN TESTS]: {exc}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        if peajes_creados:
            db.query(FlypassTransaccion).filter(
                FlypassTransaccion.id.in_(peajes_creados)
            ).delete(synchronize_session=False)
        if ingresos_creados:
            db.query(Ingreso).filter(Ingreso.id.in_(ingresos_creados)).delete(
                synchronize_session=False
            )
        if gastos_creados:
            db.query(Gasto).filter(Gasto.id.in_(gastos_creados)).delete(
                synchronize_session=False
            )
        if viajes_creados:
            db.query(ViajeODT).filter(ViajeODT.id.in_(viajes_creados)).delete(
                synchronize_session=False
            )
        db.commit()
        print(
            f"[CLEANUP] peajes={len(peajes_creados)} ingresos={len(ingresos_creados)} "
            f"gastos={len(gastos_creados)} viajes={len(viajes_creados)}"
        )
        tokens = limpiar_tokens_nuevos(db, "test@celr.com", tokens_antes)
        # El commit va DESPUES del helper, no antes. `limpiar_tokens_nuevos` hace
        # un delete sin commit: sin esto, el borrado se descarta en el close() de
        # abajo y la suite REPORTA una limpieza que no ocurrio. Medido: +1 token
        # por corrida hasta que se corrigio.
        db.commit()
        print(f"[CLEANUP] Refresh tokens del login eliminados: {tokens}")
        db.close()


if __name__ == "__main__":
    sys.exit(main())
