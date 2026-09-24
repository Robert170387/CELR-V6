# ALINEACION_MODELO_NEGOCIO.md — CELR v6

Documento maestro de alineación entre el modelo de negocio pedido y la implementación real.
Complementa a `AGENTS.md` (convenciones) y a `INSTRUCCIONES_OPENCODE.md` (operativa del agente).
Escrito en español, como todo el repo.

> **Estado:** borrador base elaborado por el agente con la **realidad verificada contra el repo**
> (modelos ORM, schemas Pydantic, API y frontend). El consultor puede refinarlo; los hechos de
> esta sección 3 fueron contrastados con el código, no con capturas.

---

## 1. Objetivo

Cerrar la brecha entre lo que el briefing pedía para la ODT y lo que el usuario ve en la UI,
usando **solo lo que falta realmente** — sin rehacer backend que ya existe.

## 2. Decisiones registradas (aprobadas por el usuario)

| Decisión | Elección | Nota |
|---|---|---|
| **Alcance** | **A — Solo frontend ODT** | El backend ya cubre casi todo el modelo; el gap es exposición en el form + preview |
| **Preview en vivo** | **C — Cliente + servidor** | Preview aproximado en el form (JS) y fuente de verdad = servidor al crear/guardar |
| **Documentación** | **A — Este `.md` primero** | Luego ejecución de la fase ODT con gate y OK explícito |

## 3. Gap verificado (realidad del repo, corregida)

> El análisis previo del consultor (basado en capturas de pantalla) concluyó que varios campos
> "no existían". La verificación contra `backend/app/models/`, `backend/app/schemas/` y
> `frontend/src/` muestra que **casi todo existe a nivel backend+API**; el gap real es UI.

### 3.1 ODT (`viajes_odt` / `ViajeODT` / `schemas/viaje.py`)

| Campo del briefing | Backend | Schema | Form ODT | Veredicto |
|---|---|---|---|---|
| N° manifiesto (`num_manifiesto`) | ✅ existe + Regla 2 (`ux_viajes_odt_manifiesto_empresa`) | ✅ | ❌ | **Falta exponerlo** |
| Material (`tipo_carga`) | ✅ | ✅ | ❌ | **Falta exponerlo** |
| Peso declarado (`peso_declarado_ton`) | ✅ | ✅ | ❌ | **Falta exponerlo** |
| Peso báscula origen/destino | ✅ (2 cols) | ✅ | ❌ | **Falta exponerlos** |
| KMS tacómetro (`km_inicial`/`km_final`) | ✅ + `km_recorridos` computed | ✅ | ❌ | **Falta exponerlos** |
| Fecha llegada (`fecha_llegada`) | ✅ | ✅ | ❌ | **Falta exponerla** |
| Saldo flete esperado / gastos / utilidad | ✅ (3 cols calculadas) | ✅ | ⚠️ preview parcial | **Sumar a la tabla si se quiere** |
| Preview en vivo de calculados | — | — | ✅ **ya existe** (retefuente, reteica, flete neto, comisión, saldo, utilidad est.) | Verificado 2026-09-23 (`Viajes.tsx` 726–747) |
| Combustible total facturas / peajes / otros gastos **como columnas ODT** | ❌ no existen | ❌ | — | **Fuera de alcance** (se modelan vía `gastos` + `flypass`; derivable en reporte) |

**Conclusión ODT:** no hay migración ni cambio de schema. Son **8 inputs nuevos** en el form,
el wiring en el payload y (opcional) una columna de KMS en la tabla.

### 3.2 Gastos (`gastos`)

- `proveedor_id` **existe** en modelo (FK → `proveedores.id`) y en los 3 schemas → **falta exponerlo en `Gastos.tsx`** (form + tabla).
- `estado_pago` con los 3 estados (`pagado`, `pendiente_por_pagar`, `legalizado`) y `legalizado`
  (computed) **existen** → verificar que el form permita cambiarlos.
- **Fuera de alcance A** (se documenta, no se ejecuta ahora).

### 3.3 Flypass (`flypass_transacciones`)

- Entidad **existe**: `flypass_transacciones` con `legalizado_en_gastos` computed
  (`gasto_id IS NOT NULL`), `num_transaccion_flypass` unique, `viaje_id`, `gasto_id`,
  `ciudad_peaje_municipio_id`. El servicio `operaciones.py` **ya bloquea** el cierre de ODT con
  peajes sin legalizar.
- **Falta:** pantalla de import (CSV/API) + visual + legalización. **Esto NO requiere migración.**
- **Fuera de alcance A** (se documenta).

### 3.4 Movimientos de tarjeta (`movimientos_bancarios`)

- Entidad **existe**: `MovimientoBancario` con `cruzado` (SI/PENDIENTE, FASE A2) y
  `retiros_tarjeta_anticipos` en la fórmula del COMPENSADO_RC.
- **Falta:** pantalla con cruce automático vs anticipos del conductor.
- **Fuera de alcance A** (se documenta).

### 3.5 Liquidaciones (COMPENSADO_RC)

- La UI **ya tiene** la sección COMPENSADO_RC Mensual (`Liquidaciones.tsx` 329–389), incluidos
  retiros de tarjeta. Pendiente: desglose completo (viajes por tipo, comisiones, devengado,
  deducciones, neto).
- **Fuera de alcance A** (se documenta).

---

## 4. FASE ODT FRONTEND — ✅ HECHO (2026-09-23)

> **Ejecución:** sub-fase única autorizada y commiteada — `d075cca` (feat(frontend): expone inputs
> completos de ODT + KMS en preview y tabla). Gates: `npm run build` verde · **E2E verde**
> (`e2e_flow_test.py` contra :8001) · OpenAPI vivo confirma los 8 campos en
> `ViajeCreate`/`ViajeUpdate`. Sin cambios en backend (4.3 se cumplió al pie de la letra).

### 4.1 Inputs nuevos en el form (ya soportados por backend/schema)

| Campo | Etiqueta sugerida | Tipo / unidad |
|---|---|---|
| `num_manifiesto` | N° Manifiesto | text |
| `tipo_carga` | Material / carga | text |
| `peso_declarado_ton` | Peso declarado (ton) | number ≥ 0 |
| `peso_bascula_origen` | Peso báscula origen (ton) | number ≥ 0 |
| `peso_bascula_destino` | Peso báscula destino (ton) | number ≥ 0 |
| `km_inicial` | KMS inicial tacómetro | number ≥ 0 |
| `km_final` | KMS final tacómetro | number ≥ 0 |
| `fecha_llegada` | Fecha llegada | date |

### 4.2 Cambios concretos en `frontend/src/pages/Viajes.tsx`

1. **`initialForm`:** añadir los 8 campos como `''` (lines ~90–105).
2. **`camposViaje`** (offline/draft): añadir los 8 nombres (lines 107–124).
3. **Payload `crear`** (lines 229–247): agregar `if (form.num_manifiesto) payload.num_manifiesto = form.num_manifiesto` (ídem los 7 restantes, con `Number()` para pesos/kms).
4. **Payload `actualizar`** (lines ~287–310): ídem con los 8.
5. **Interfaz `Viaje`** (lines 36–62): añadir campos opcionales `num_manifiesto?`, `tipo_carga?`, `peso_declarado_ton?`, `peso_bascula_origen?`, `peso_bascula_destino?`, `km_inicial?`, `km_final?`, `km_recorridos?`, `fecha_llegada?`.
6. **JSX del form:** añadir los 8 inputs tras el bloque actual de deducciones/comisión, con la misma clase `input-truck` y `onChange={handleChange}`.
7. **Preview en vivo** (bloque 726–747): **extender**, no reemplazar:
   - Si hay `km_inicial`/`km_final` → `km_recorridos` estimado (badge read-only).
   - Mantener la línea "fuente: servidor" (el preview es aproximado; los valores definitivos los recalcula el backend — decisión C).
8. **Tabla** (opcional recomendado): añadir columna **KMS** ( `viaje.km_recorridos` ?? `'-'`) entre "Fecha Salida" y "Flete Neto".

### 4.3 Sin cambios en backend

- Ninguna migración. Ningún cambio en `schemas/viaje.py` (los 8 campos ya están en
  `ViajeCreate`/`ViajeUpdate`/`ViajeResponse`).
- El servidor ya recalcula `km_recorridos`, `flete_neto`, `retefuente_valor`, `reteica_valor`,
  `saldo_flete_esperado`, `comision_conductor`, `gastos_totales_viaje`, `utilidad_neta_odt`.

---

## 5. FASE B2 — Persistir el cierre mensual COMPENSADO_RC — ✅ HECHO (2026-09-23)

> **Decisión de negocio aprobada:** **Opción 1** — reforzar `liquidaciones_conductores`, sin tabla
> nueva. El "mes" = la liquidación del conductor. El cierre se **persiste** con rastro
> (`es_cierre_mensual` + `periodo_ym`), se **bloquea** mientras existe, y se puede **reabrir** y
> **cancelar**; la UI expone «Cerrar mes» y «Meses cerrados».

### 5.1 Decisiones registradas B2

| Decisión | Elección | Nota |
|---|---|---|
| Modelo de cierre | **Opción 1** — fila en `liquidaciones_conductores` | Sin tabla nueva; mes = liquidación del conductor (`LiquidacionConductor`) |
| Vehículo en el cierre | `vehiculo_id = NULL` | Migración hace `DROP NOT NULL`; el cierre es del conductor, no de un vehículo |
| ODTs del rango ya liquidadas | **D5 = (c)** → HTTP 409 | El cierre mensual falla con 409 si hay ODTs del periodo ya liquidadas individualmente |
| Borrador de cierre | **También bloquea** `/cerrar/{viaje_id}` | `POST /liquidaciones/{id}/cancelar` (solo `borrador`) libera el rango |
| Comisión en el cierre | `comision_flete := comisiones_total` del mes | Fuente de verdad: `operaciones.consolidar_compensado` |
| Clave de periodo | `periodo_ym` **GENERATED STORED** inmutable | `EXTRACT` + `LPAD` (año-mes `YYYY-MM`); `to_char` lo rechaza PG (no es inmutable estable) |
| UNIQUE por periodo | `ux_liquidaciones_mes_cierre` parcial | `(conductor_id, periodo_ym) WHERE es_cierre_mensual AND eliminado_en IS NULL` |

### 5.2 Sub-fases ejecutadas

| Sub-fase | Commit | Qué cambió |
|---|---|---|
| 1 — Migración + modelo | `1a11e18` | `f2e1d0c9b8a7_b2_cierre_mensual_compensado.py` (columna `es_cierre_mensual`, `periodo_ym` GENERATED STORED, `vehiculo_id` nullable, UNIQUE parcial) + modelo `LiquidacionConductor` |
| 2 — Endpoints + tests | `61a56be` | `POST/GET /liquidaciones/cierre-mensual`, `POST /{id}/reabrir`, `POST /{id}/cancelar`; 409 en `/cerrar/{viaje_id}`; schemas `CierreMensualCreate/Response`; suite nueva `scripts/test_cierre_mensual.py` |
| 3 — UI frontend | `2131127` | `Liquidaciones.tsx`: botón «Cerrar mes» + sección «Meses cerrados» (Detalle / Reabrir / Cancelar); `api/index.ts` (interfaz `CierreMensual` + métodos). ⚠️ Nota de alcance: además del frontend, este commit (etiquetado `feat(frontend)`) arrastra el backend read-only `GET /liquidaciones/cierres-mensuales` que alimenta el listado |
| 4 — Docs | `8d72c3b` | Esta sección + pipeline/nota `PYTHONIOENCODING` en `INSTRUCCIONES_OPENCODE.md`. Posteriores ligados a B2: `f2e7591` (trazabilidad del listado) y `3f9a9d3` (tests de estados inválidos) |

### 5.3 Flujo del cierre mensual

1. **Crear:** `POST /api/v1/liquidaciones/cierre-mensual` con `{conductor_id, periodo, borrador}`.
   Falla con **409 (D5-c)** si en el rango del periodo hay ODTs ya liquidadas individualmente.
   Crea la fila `es_cierre_mensual=True` con `periodo_ym` derivado y copia los consolidados del
   COMPENSADO_RC mensual (`comision_flete := comisiones_total`, etc.).
2. **Bloqueo:** mientras el cierre exista (`borrador` o `cerrado`), `/cerrar/{viaje_id}` de
   cualquier ODT del rango responde **409** — el rango está reservado por el cierre mensual. El
   check del 409 va **antes** del 400 por estado `liquidado` (el cierre marca las ODT así; el
   orden original enmascaraba la causa real).
3. **Listar:** `GET /liquidaciones/cierres-mensuales?conductor_id=` devuelve los meses cerrados,
   más reciente primero — alimenta el listado «Meses cerrados» de la UI.
4. **Reabrir:** `POST /liquidaciones/{id}/reabrir` (solo estado `cerrado`; el rastro queda en el
   historial de estados).
5. **Cancelar:** `POST /liquidaciones/{id}/cancelar` (solo estado `borrador`) libera el rango y
   deja liquidar las ODT individualmente de nuevo.

### 5.4 Gates verdes por sub-fase

- **1:** `alembic upgrade head` aplicada y **reversa probada** sobre `celr_v6_db`; baseline intacto (`viajes_odt=24`, `liquidaciones_conductores=6`).
- **2:** suite nueva `test_cierre_mensual.py` 8/8 + `test_liquidaciones` sin regresión + E2E 5/5 `--purge` + baseline intacto.
- **3:** `npm run build` OK + suite B2 9/9 (incluye listado) + E2E 5/5 `--purge` + baseline `24/6/0` + **validación HTTP en vivo** (crear → listar → detalle → 409 duplicado → cancelar → vacío; datos purgados al final).

---

## 6. Fases cerradas y fuera de alcance

> ✅ **Cerrada (2026-09-23):** **Gastos + Proveedor en UI** — commit `b7e1cf5`
> (`feat(frontend): expone proveedor en gastos`). Solo frontend (`Gastos.tsx`); gates verdes:
> `npm run build` + E2E `--purge` + OpenAPI vivo (`proveedor_id` presente en
> `GastoCreate`/`GastoUpdate`).

> ✅ **Cerrada (2026-09-23):** **Liquidaciones — desglose completo** — commit `221ff2f`
> (`feat(liquidaciones): desglose completo del COMPENSADO_RC mensual`). Solo frontend
> (`Liquidaciones.tsx`); gates verdes: `npm run build` + E2E `--purge`. Sin backend y sin
> migración (el servidor ya devuelve los consolidados del compensado). El input `Vehículo`
> del COMPENSADO_RC del brief queda como pendiente menor (por ODT el vehículo ya se asocia).

> ✅ **Cerrada (2026-09-23):** **B2 — cierre mensual COMPENSADO_RC persistido** — ver **§5**
> (sub-fases 1–3: `1a11e18`, `61a56be` y `2131127`; docs en este commit). Full-stack + migración; gates
> verdes por sub-fase y baseline `24/6/0` intacto.

> ✅ **Cerrada (2026-09-23):** **Flypass completo — Excel, matching, legalización y UI** — commits
> `9e07857`, `d4736b7`, `cae6b1a` y `4aaedc8`. El importador acepta `.xlsx`, conserva la fila
> original en `flypass_transacciones.raw_data`, resuelve placa, matchea o crea gastos `peajes`,
> y asocia una ODT única por vehículo/fecha. El backend agrega listado paginado con filtros;
> la UI permite consultar, filtrar e importar con reporte. Comportamiento D híbrido:
> duplicados, sin placa, ambiguos y filas sin ODT quedan en el reporte. P4:
> `pendiente_por_pagar`; P5: proveedor único `Flypass` (se crea una sola vez con NIT nullable).
> La legalización es automática al setear `gasto_id`; el gasto creado usa
> `metodo_pago="tag"`. TF1–TF8, TL1–TL9, 11 suites backend, smoke, E2E `--purge`, build frontend,
> Alembic y baseline quedaron verdes.

> ✅ **Cerrada (2026-09-23):** **Seeds — partición base/demo** — commits `7a1a384`, `d74fac5`,
> `5e86fda`, `4c117a9` y `ee86d05`. `seed_base.py` es seguro y siempre presente;
> `seed_demo.py` es opt-in local con guard de producción; `seed.py` es wrapper; Docker local
> habilita la demo mediante `CELR_ALLOW_DEMO_SEED=1`. El rebuild explícito de la imagen es
> obligatorio cuando cambian seeds, migraciones o Dockerfile. Gates de build, startup, health,
> B2, E2E 5/5 y baseline quedaron verdes.

**Fases candidatas restantes:**
| Fase candidata | Qué implica | Costo |
|---|---|---|
| **Movimientos bancarios — pantalla** | UI de `movimientos_bancarios` + cruce anticipos | Frontend |
| **B1 / B3 / B4 / B5 / B6** | Decisiones de negocio/seguridad en `INSTRUCCIONES_OPENCODE.md` §8 | varía |

### B6 — Regla 4 (componente saldo): no forzable hoy

> **Decisión registrada (2026-09-23):** no forzar el componente de saldo de la Regla 4.
> El commit `9e07857` mantiene forzado únicamente el componente Flypass en el cierre individual
> y mensual. La auditoría sobre 18 ODTs activos encontró 15/18 con saldo no cubierto, incluidas
> 9 ya `liquidado`; 13/18 no tienen ningún ingreso calificable y las 3 ODTs restantes aparecen
> limpias solo porque sus snapshots (`saldo_flete_esperado` y `gastos_totales_viaje`) están en
> `NULL`. La ambigüedad semántica entre “Finalizada” del brief y `liquidado` (estado real del
> backend) sigue pendiente de decisión de negocio. También queda por confirmar si la fórmula
> `saldo_flete_esperado` —que no descuenta gastos— representa el saldo operativo que debe exigir
> la Regla 4. El cierre Flypass continúa vigente desde `9e07857`; B6 no habilita su forzado.

**Preguntas de negocio abiertas:** qué significa cerrar una ODT operativamente, cuándo es
aceptable cerrar sin saldo cubierto y si los ingresos se cargarán sistemáticamente en el futuro.

---

## 7. Ejecución y gates

Reglas que aplican a la ejecución de la fase ODT (y a cualquier fase futura):

1. **PAUSA TOTAL:** cada sub-fase requiere OK explícito del usuario antes de mutar.
2. **Un commit por sub-fase**, mensajes en español.
3. **Gates verdes antes de commitear** (ver `INSTRUCCIONES_OPENCODE.md` §3):
   - `npm run build` en `frontend/` (incluye `tsc -b`) sin warnings.
   - smoke `[SMOKE OK]` si el backend se toca (aquí no se toca).
   - E2E si aplica.
4. **Sin migraciones** en esta fase. Si algún día cambia el modelo, solo a través de Alembic.
5. Los 2 archivos `CONTEXTO_CLAUDE_CELR_v6.md` / `CONTEXTO_PARA_CLAUDE.md` siguen **prohibidos de tocar**.

---

## 8. Trazabilidad

- ✅ El texto del briefing está en §9 (commit `141ace3`, pegado 2026-09-23).
- ✅ **FASE B2 documentada (2026-09-23, §5):** sub-fases `1a11e18` (migración+modelo),
  `61a56be` (endpoints+tests), `2131127` (UI) y docs de esta sub-fase.
- ✅ Hechos de la sección 3 verificados **2026-09-23** contra HEAD `d7048af` y **re-cruzados**
  contra el brief original en §9: solo 4 inputs ODT están genuinamente ausentes del modelo
  (`combustible_total_facturas`, `peajes_efectivo`, `peajes_tag`, `otros_gastos_ruta` — §3.1,
  fuera de alcance, se modelan vía `gastos` + `flypass`).

---

## 9. Apéndice — requerimiento original (briefing)

Texto literal del prompt/briefing de arquitectura que motivó la alineación (pego traza 2026-09-23).

---

> **Instrucción del brief:** Actúa como un Arquitecto de Software Senior y Lead Full-Stack Developer. Tengo
> un proyecto en desarrollo con su base de datos, backend y frontend ya definidos e iniciados. Necesito
> acoplar, expandir y refactorizar mi código actual para que se alinee al 100% con el modelo de negocio y
> flujo contable/operativo real de mi empresa de transporte de carga (Tractocamiones / Flota).

### A. ENTIDAD "ODT" (Órdenes de Transporte / Viajes)

**Inputs manuales:** FECHA CARGA, FECHA DESCARGA, VEHICULO (FK→Vehículos.Placa), CONDUCTOR (FK→Personal.Documento),
TIPO DE VIAJE (Urbano, Nacional, Internacional, Vacío), ORIGEN/DESTINO, KMS INICIAL TACOMETRO / KMS FINAL TACOMETRO,
MATERIAL A TRANSPORTAR, FECHA MANIFIESTO, EMPRESA MANIFIESTO / CLIENTE (FK→Proveedores/Clientes), MANIFIESTO
(número único), PESO DECLARADO MANIFIESTO TON, PESO BASCULA ORIGEN/DESTINO TON, VALOR FLETE MANIFIESTO,
% RETENCION EN LA FUENTE, % RETENCION ICA, OTRAS DEDUCCIONES, ANTICIPO MANIFIESTO, COMBUSTIBLE TOTAL FACTURAS,
PEAJES EFECTIVO / PEAJES TAG, OTROS GASTOS RUTA (Cargue, Descargue, Carrozada, Hotel, Parqueadero).

**Calculados:** ID_ODT (autogenerado, ej: ODT-0294); TOTAL KMS RECORRIDOS = KMS_final − KMS_inicial;
VALOR RETENCION FUENTE = flete × (%retefuente/100); VALOR RETENCION ICA = flete × (%reteica/100);
TOTAL DEDUCIBLES = retefuente + reteica + otras_deducciones; FLETE NETO = flete − total_deducibles;
COMISION CONDUCTOR CALCULADA = flete_neto × %comisión; SALDO FLETE ESPERADO = flete_neto − anticipo;
GASTOS TOTALES VIAJE = Σ(Combustible + Peajes + Cargues/Descargues + Viáticos);
UTILIDAD NETA ODT = flete_neto − comision − gastos_totales_viaje; AÑO = ExtractYear(FECHA CARGA).

### B. ENTIDAD "DB_INGRESOS" (flujo de caja positivo)

**Inputs:** FECHA, ID_VIAJE (FK opcional→ODT), VEHICULO (FK), CATEGORIA (Anticipo Manifiesto, Saldo Flete,
Ajuste Flete, Aporte Capital), VALOR, CLIENTE_ORIGEN, MEDIO_PAGO, RECEPTOR_DESTINO, ESTADO (Por cobrar,
Recibido, Conciliado), CONCEPTO.
**Calculados:** ID_INGRESO, FECHA MANIFIESTO (heredado de ODT), AÑO.

### C. ENTIDAD "DB_GASTOS" (flujo de caja negativo)

**Inputs:** FECHA, ID_VIAJE (FK opcional→ODT), VEHICULO (FK), CATEGORIA (Combustible, Peajes, Mantenimiento,
etc.), PROVEEDOR (FK), METODO_PAGO, VALOR, ESTADO (Pagado, Pendiente Por Pagar, Legalizado), CONCEPTO.
**Calculados:** ID_GASTO, LEGALIZADO (Boolean), AÑO.

### D. INTEGRACIONES Y CONCILIACIONES AUTOMÁTICAS

- **FLYPASS (peajes TAG):** importación/lectura de consumos; LEGALIZADO_EN_GASTOS (Boolean) al vincularse a
  una ODT/Gasto.
- **MOV_TARJETA (tarjeta débito conductor):** retiros/compras; CRUZADO (SI/PENDIENTE). Todo retiro en cajero o
  compra en EDS debe cruzarse automáticamente como ANTICIPO para la liquidación del conductor.

### E. ENTIDAD "COMPENSADO_RC" (liquidación mensual del conductor)

**Inputs:** PERIODO FACTURADO, CONDUCTOR (FK), VEHICULO (FK), SALARIO BASICO, AUXILIO TRANSPORTE, PAPELERIA,
DESCUENTO SALUD PENSION.
**Calculados (consolidados del mes):** VIAJES NACIONALES/URBANOS/TOTAL (conteos de ODT del periodo);
COMISIONES CONDUCTOR TOTAL (Σ comisiones ODT del mes); RETIROS TARJETA DEBITO/ANTICIPOS
(Σ MOV_TARJETA con CRUZADO='SI' del mes); DEVENGADO TOTAL = comisiones + salario + auxilio + papelería;
DEDUCCIONES TOTALES = descuento_salud_pension + retiros_tarjeta + gastos_asumidos;
NETO A PAGAR = devengado − deducciones.

### Reglas de negocio e integridad

1. Relación 1:N: una ODT ↔ N filas DB_INGRESOS y N filas DB_GASTOS.
2. Unicidad de manifiesto por empresa.
3. Cruce de tarjeta a anticipos: los retiros de la tarjeta asignada al conductor restan directo en su
   COMPENSADO_RC mensual.
4. Cierre operativo ODT: no marcar 'Finalizada' si el saldo flete esperado no concuerda con los ingresos
   confirmados o si hay peajes Flypass pendientes de legalizar en la ruta.

---

**Nota de trazabilidad:** al cruzar este brief con el repo (2026-09-23, HEAD `ce409ff`), los únicos campos
de ODT **genuinamente ausentes** del modelo son `combustible_total_facturas`, `peajes_efectivo`,
`peajes_tag` y `otros_gastos_ruta` (hoy modelados vía `gastos` + `flypass_transacciones`, no como columnas
de `viajes_odt`). El resto ya existe en backend+schema y el gap es exposición en el form (ver §3).