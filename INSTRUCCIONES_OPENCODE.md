# INSTRUCCIONES_OPENCODE.md — CELR v6

Guía operativa para el agente que trabaja en este repo (TRUCK DRIVER, CELR v6).
Complementa a `AGENTS.md` (convenciones del repo) y a `CONTEXTO_DEEPSEEK_CELR_v6.md`
(documento de traspaso oficial, grueso de la operación).

## 1. Idioma y estilo

- Todo en español: código, comentarios, mensajes API, commits, tests, docs.
- Un commit por fase, mensajes en español (ej. `fix(frontend): ...`).

## 2. PAUSA TOTAL

- Lectura/auditoría: siempre OK.
- Toda mutación (código, BD, Docker, migraciones, docs tracked, push) requiere **OK explícito
  del usuario por sub-fase**. Ante ambigüedad: detenerse y reportar, no improvisar.
- `CONTEXTO_CLAUDE_CELR_v6.md` y `CONTEXTO_PARA_CLAUDE.md` son del usuario (untracked):
  **NO tocarlos**.

## 3. Gates antes de commitear

1. **Backend:** las **9** suites `backend/scripts/test_*.py` en verde (desde `backend/`, con
   `PYTHONPATH=.` y `DATABASE_URL` → `:5433`), con el venv:
   `venv\Scripts\python.exe scripts\test_<suite>.py` — los scripts imprimen checks `✓`/`✗`;
   bajo pipe en Windows ejecutar con `$env:PYTHONIOENCODING="utf-8"` (cp1252 rompe esos
   caracteres). `test_cierre_mensual.py` es la suite de la FASE B2.
2. **Humo:** `venv\Scripts\python.exe scripts\smoke.py` → `[SMOKE OK]`.
3. **E2E** (servidor vivo, p. ej. Docker `:8001`):
   `$env:CELR_BASE_URL="http://localhost:8001"; $env:PYTHONUTF8="1";
   venv\Scripts\python.exe ..\scripts\e2e_flow_test.py` — si la salida se captura por pipe,
   añadir `$env:PYTHONIOENCODING="utf-8"` (el check `✓` revienta con cp1252 bajo pipe).
4. **Frontend:** `npm run build` en `frontend/` (incluye `tsc -b`, es el gate) → sin warnings.

## 4. Entorno y trampas

- Puertos no estándar: DB `:5433` (`celr_v6_db`), backend Docker `:8001`, backend local `:8000`,
  web Docker `:5174`, Vite local `:3000`.
- **Trampa:** `backend/.env` trae `DATABASE_URL=...:5432/...` (puerto de `celr_app_v2`). Ejecutar
  siempre con la variable de entorno al stack propio:
  `postgresql://postgres:admin@localhost:5433/celr_v6_db`.
- **Trampa — frontend Docker:** el `dist` va **horneado** en la imagen nginx (`build.context: ./frontend`,
  SIN bind mount). Cambios en `frontend/src/**` NO se reflejan en `:5174` hasta
  `docker compose build frontend && docker compose up -d frontend`. Para desarrollo con HMR usar
  `npm run dev` (Vite `:3000`, proxy `/api` → `:8000`). Verificado 2026-09-23 (el preview en `:5174`
  servía un build viejo hasta reconstruir).
- Migraciones: **Alembic es el mecanismo oficial** (`alembic upgrade head`). `init_db.py`,
  `schema_celr_v6.sql` y `backend/scripts/migrate_*.py`: históricos, NO usarlos en BD nuevas.
- Baseline estable (verificado): `usuarios=7, vehiculos=9, conductores=7, proveedores=6,
  viajes_odt=24, gastos=37, ingresos=8, liquidaciones_conductores=6, refresh_tokens=0`;
  `km_actual` SKN756 = `125000.00`; max ODT `ODT-2026-000030`.
- `secuencias_documento` **no se resetea** (nunca rewinds ni edits manuales).
- **Producción (Render):** cada entorno tiene su propia BD, así que `secuencias_documento`
  arranca en cero → los primeros ODT serán `ODT-2026-000001…`. **Es normal, no es un bug**;
  no comparar números ODT entre entornos.
- **Deuda técnica IDBKeyRange — RESUELTA (2026-09-23, `172e38f`):** los `PAGEERROR
  Failed to execute 'only' on IDBKeyRange` (2 veces en el arranque post-login) tenían causa
  raíz confirmada empíricamente: **`boolean` no es una clave válida de índice en IndexedDB**
  (lo son `number | Date | DOMString | binary | Array`). `offlineStore.ts` indexaba el campo
  `synced` (booleano) y consultaba `IDBKeyRange.only(false/true)` → `DataError`, rompiendo
  silenciosamente `getUnsyncedTransactions()` / `clearSyncedTransactions()` (la sync offline
  del PWA fallaba siempre). Fix (**Opción B**, `getAll()` + `filter` en memoria): el índice
  `'synced'` queda **declarado pero sin uso**, sin bump de `DB_VERSION` ni reindexación, y es
  tolerante a registros antiguos con `synced` booleano. Verificado: `PAGEERROR` ausente en el
  dist nuevo post-login (build + E2E `--purge` + baseline `viajes_odt=24` verdes).
  Residuo opcional a futuro: borrar el índice `'synced'` del schema (no requiere migración si
  se hace al crear store, pero tocaría `DB_VERSION`).

## 5. Estado actual

- Rama `main` y backup: **conteo vivo** con `git rev-list --count origin/main..HEAD` (fases mezcladas: FASE A2 + FASE 2 + docs 2.G + alineación ODT + FASE Gastos + FASE Liquidaciones + docs). No se pinea el número exacto aquí para evitar el off-by-one autoreferencial (ver `e474022`).
- **Backup remoto:** `origin/fase-a2-fase-2-local` se mantiene **al día con `main` local** tras cada sesión. Verificar con `git rev-list --left-right --count origin/fase-a2-fase-2-local...main` → esperado `0 0`. El merge a `origin/main` sigue pendiente.
- Pendiente real: **merge/push a `main`** (PAT del usuario) + deploy manual en Render.
- **FASE 2 cerrada:**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | 2.0 | `165078e` | docs: corregida afirmación sobre `/municipios` (requiere auth) |
  | 2.A | `2e38ee4` | `requests` en venv del backend (E2E sin depender del Python del sistema) |
  | 2.B | `e0bf6bd` | suites con limpieza de datos al final (DELETE real, orden inverso de FK) |
  | 2.C | `a73c952` | `backend/scripts/smoke.py` (humo: conexión, migraciones head, seed, login, baseline) |
  | 2.D | `962ee79` | frontend: import de `offlineStore` unificado a estático (warning Vite eliminado) |
  | 2.F | `c6fb07f` | docs: §9/§10/§11 del contexto actualizados tras FASE 2 |
  | 2.E | — | **cancelada**: residuo de 6 usuarios `cli-*@celr.com`/`cond-*@celr.com`
    (ids 13–16, 20–21) documentado, **no borrado** (0 referencias FK) |
- **FASE ODT (alineación) cerrada:**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | doc base | `ce409ff` | `ALINEACION_MODELO_NEGOCIO.md` (§1–§8, gap verificado contra el repo) |
  | doc §8 | `141ace3` | apéndice con el requerimiento original (trazabilidad) |
  | ODT | `d075cca` | form ODT completo: 8 inputs (N° manifiesto, material, pesos, KMS, fecha llegada) + preview KMS + columna KMS; gates build+E2E verdes |
- **FASE Gastos (proveedor) cerrada:**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | Gastos | `b7e1cf5` | `Gastos.tsx`: proveedor en form crear, modal editar y columna en tabla; gates build+E2E `--purge`+OpenAPI verdes |
- **FASE Liquidaciones (desglose) cerrada:**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | Liquidaciones | `221ff2f` | `Liquidaciones.tsx`: conteos en 3 cards, desglose por línea de haberes/descuentos, DEVENGADO TOTAL / DEDUCCIONES TOTALES / NETO A PAGAR, inputs agrupados por sección; gates build+E2E `--purge` verdes |
- **FASE Fix offline IDBKeyRange cerrada:**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | Fix cola offline | `172e38f` | `offlineStore.ts`: `getUnsyncedTransactions()`/`clearSyncedTransactions()` pasan de `index('synced').getAll(only(false/true))` (DataError: booleans no son claves IDB) a `getAll()` + `filter`/`delete` en memoria; índice `'synced'` declarado sin uso; gates build+E2E `--purge`+baseline+PAGEERROR ausente verdes |
- **FASE B2 (cierre mensual COMPENSADO_RC) cerrada:**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | 1 migración+modelo | `1a11e18` | `f2e1d0c9b8a7_b2_cierre_mensual_compensado.py` (`es_cierre_mensual`, `periodo_ym` GENERATED STORED, `vehiculo_id` NULL, UNIQUE parcial) + modelo `LiquidacionConductor` |
  | 2 endpoints+tests | `61a56be` | `POST/GET /liquidaciones/cierre-mensual`, `GET /liquidaciones/cierres-mensuales`, `POST /{id}/reabrir`, `POST /{id}/cancelar`, 409 en `/cerrar/{viaje_id}`; schemas `CierreMensualCreate/Response`; suite nueva `test_cierre_mensual.py` |
  | 3 UI frontend | `2131127` | `Liquidaciones.tsx`: «Cerrar mes» + «Meses cerrados» (Detalle/Reabrir/Cancelar); `api/index.ts` (`CierreMensual` + métodos) |
  | 4 docs | *(este commit)* | Sección B2 en `ALINEACION_MODELO_NEGOCIO.md` §5 + pipeline/nota `PYTHONIOENCODING` aquí (§3) |

## 6. Pendientes (GitHub / Render)

1. **Hecho:** todo `main` local está respaldado en `origin/fase-a2-fase-2-local` (conteo vivo:
   `git rev-list --count origin/fase-a2-fase-2-local...main` → `0 0` tras cada sesión).
   Pendiente: **merge a `main`** — vía PR en GitHub o
   `git checkout main && git merge fase-a2-fase-2-local`, luego
   `git push origin main` con **PAT del usuario** (Credential Manager, Opción A).
2. **Actualizar los deploys de Render** a FASE A2 (backend + frontend estático con
   `VITE_API_URL=https://celr-backend.onrender.com/api/v1`). Orden de boot en Render:
   `alembic upgrade head && seed.py && scripts/seed_municipios.py`. No hacer sin credenciales.
3. **Decidir el usuario `cliente@celr.com`:** no existe en la BD y `seed.py` no lo crea. Si el
   negocio lo requiere, registrar rol `cliente` o extender el seed (con autorización).
4. ~~COMPENSADO_RC mensual: GET solo lectura, sin persistir~~ → **HECHO (FASE B2, 2026-09-23):**
   el cierre mensual se **persiste** en `liquidaciones_conductores` (`es_cierre_mensual` +
   `periodo_ym`) vía `POST/GET /liquidaciones/cierre-mensual`, con reapertura/cancelación y
   bloqueo 409. Ver `ALINEACION_MODELO_NEGOCIO.md` §5.
5. **Residuo 2.E:** los 6 usuarios históricos pueden borrarse si el negocio lo pide (con OK).

## 7. Decisiones registradas en FASE 2

1. Suites backend con **limpieza propia** (2.B): DELETE real en orden inverso de FK; baseline
   idéntico al inicio/fin de cada corrida; excluir siempre el seed.
2. `secuencias_documento` **no se resetea** tras corridas de tests/E2E.
3. `smoke.py` es el humo estándar post-migración (2.C), junto a suites + E2E + `npm run build`.
4. Import de `offlineStore` unificado a **estático** (2.D): el módulo no es pesado y ya estaba
   en el bundle inicial vía Layout/Viajes/Gastos/useOfflineSync.
5. **2.E cancelada** (decisión de FASE 2): los 6 usuarios residuo quedan documentados, no se
   borran sin nuevo OK.

## 8. Decisiones B1–B5 — preguntas al próximo consultor/agente

Decisiones de negocio/arquitectura que quedan **abiertas**; no son decidibles por el agente. El
consultor previo dejó el marco; quien retome el proyecto debe cerrarlas con el usuario:

| # | Pregunta | Implica si se acepta |
|---|---|---|
| **B1** | ¿Rol `cliente` en seed? | Lógica de seed + credencial de prueba documentada. Riesgo mínimo. |
| **B3** | ¿Refresh token a cookie `HttpOnly`? | **Rompe el offline del PWA.** Trade-off explícito. |
| **B4** | ¿Rate limiter distribuido? | Redis o tabla DB → **migración** + infra. Solo multi-instancia. |
| **B5** | ¿OCR Google Vision o Tesseract local? | Código comentado; activar = dependencia cloud + credenciales. |

> **B2 quedó resuelta (2026-09-23):** persiste el cierre mensual COMPENSADO_RC con **Opción 1**
> (reforzar `liquidaciones_conductores`, D5-c → 409 preventivo, reabrir/cancelar con rastro). Ver
> FASE B2 en §5 y `ALINEACION_MODELO_NEGOCIO.md` §5.

Prioridad actual: de las restantes, **B3 y B4** son deuda de seguridad/arquitectura al escalar;
**B1** y **B5** cuando surja la necesidad.