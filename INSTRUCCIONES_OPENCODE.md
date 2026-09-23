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

1. **Backend:** las 8 suites `backend/scripts/test_*.py` en verde (desde `backend/`, con
   `PYTHONPATH=.` y `DATABASE_URL` → `:5433`), con el venv:
   `venv\Scripts\python.exe scripts\test_<suite>.py`
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
- **Deuda técnica detectada (2026-09-23):** en el arranque de la app salen
  `PAGEERROR Failed to execute 'only' on IDBKeyRange` (2 veces, IndexedDB). No bloquea la app
  (el error se atrapa), pero puede **romper silenciosamente la sincronización offline del PWA**:
  algo pasa una key inválida (`undefined`/`NaN`/tipo incorrecto) en una consulta indexada de
  `frontend/src/utils/offlineStore.ts`. Candidato a fase futura (investigación read-only
  primero, ~15 min); sin urgencia.

## 5. Estado actual

- Rama `main` = **33 commits por delante de `origin/main`** (FASE A2 + FASE 2 + docs 2.G + alineación ODT + FASE Gastos + FASE Liquidaciones + docs).
- **Backup remoto:** `origin/fase-a2-fase-2-local` actualizado a **32 commits** (`0bd5d31` — ODT + Gastos + Liquidaciones + docs ya respaldados). El commit de esta sección (hallazgos de sesión) queda **solo local** hasta el merge.
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

## 6. Pendientes (GitHub / Render)

1. **Hecho:** los 22 commits de FASE A2+FASE 2 ya están respaldados en `origin/fase-a2-fase-2-local` (`e474022`).
   Tras las fases de alineación (ODT + Gastos + Liquidaciones), `main` local quedó en **31 commits** (los 9 nuevos
   solo locales).
   Pendiente: **merge a `main`** — vía PR en GitHub o
   `git checkout main && git merge fase-a2-fase-2-local`, luego
   `git push origin main` con **PAT del usuario** (Credential Manager, Opción A).
2. **Actualizar los deploys de Render** a FASE A2 (backend + frontend estático con
   `VITE_API_URL=https://celr-backend.onrender.com/api/v1`). Orden de boot en Render:
   `alembic upgrade head && seed.py && scripts/seed_municipios.py`. No hacer sin credenciales.
3. **Decidir el usuario `cliente@celr.com`:** no existe en la BD y `seed.py` no lo crea. Si el
   negocio lo requiere, registrar rol `cliente` o extender el seed (con autorización).
4. **COMPENSADO_RC mensual:** hoy es GET solo lectura; falta decidir si se persiste el cierre
   mensual (preguntar al usuario antes de diseñarlo).
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
| **B2** | ¿Persistir cierre mensual COMPENSADO_RC? | **Migración nueva** + tabla + endpoint POST + UI. Proyecto pequeño. |
| **B3** | ¿Refresh token a cookie `HttpOnly`? | **Rompe el offline del PWA.** Trade-off explícito. |
| **B4** | ¿Rate limiter distribuido? | Redis o tabla DB → **migración** + infra. Solo multi-instancia. |
| **B5** | ¿OCR Google Vision o Tesseract local? | Código comentado; activar = dependencia cloud + credenciales. |

Prioridad sugerida por el consultor previo: **B2 primero** (única con impacto funcional real hoy);
B3 y B4 como deuda de seguridad/arquitectura al escalar; B1 y B5 cuando surja la necesidad.