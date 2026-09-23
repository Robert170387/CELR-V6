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

## 4. FASE EN EJECUCIÓN — ODT frontend (única fase aprobada)

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

## 5. Fuera de alcance (documentado, no borrado — futuras fases candidatas)

| Fase candidata | Qué implica | Costo |
|---|---|---|
| **Gastos + Proveedor en UI** | Exponer `proveedor_id` (FK ya existe) + estados pago `<select>` | Frontend |
| **Liquidaciones — desglose completo** | Ampliar la UI COMPENSADO_RC existente | Frontend |
| **Flypass — import + pantalla** | Import CSV/API de `flypass_transacciones` + cruce con gastos peajes | Frontend + decisión de import |
| **Movimientos bancarios — pantalla** | UI de `movimientos_bancarios` + cruce anticipos | Frontend |
| **B2 — persistir cierre COMPENSADO_RC** | Tabla + endpoint + UI (decisión de negocio, alta) | Full-stack + **migración** |
| **B1 / B3 / B4 / B5** | Decisiones de negocio/seguridad en `INSTRUCCIONES_OPENCODE.md` §8 | varía |

---

## 6. Ejecución y gates

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

## 7. Trazabilidad (pendiente)

- El "prompt original del otro LLM" que motivó el briefing **no está en el repo**. Pegar aquí
  (apéndice) el texto del requerimiento para que esta alineación sea verificable.
- Fecha de verificación de los hechos de la sección 3: **2026-09-23** contra HEAD `d7048af`.

---

## 8. Apéndice

_(pendiente: pegar el prompt/requerimiento original del briefing)_