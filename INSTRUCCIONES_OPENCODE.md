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
- Migraciones: **Alembic es el mecanismo oficial** (`alembic upgrade head`). `init_db.py`,
  `schema_celr_v6.sql` y `backend/scripts/migrate_*.py`: históricos, NO usarlos en BD nuevas.
- Baseline estable (verificado): `usuarios=7, vehiculos=9, conductores=7, proveedores=6,
  viajes_odt=24, gastos=37, ingresos=8, liquidaciones_conductores=6, refresh_tokens=0`;
  `km_actual` SKN756 = `125000.00`; max ODT `ODT-2026-000030`.
- `secuencias_documento` **no se resetea** (nunca rewinds ni edits manuales).
- **Producción (Render):** cada entorno tiene su propia BD, así que `secuencias_documento`
  arranca en cero → los primeros ODT serán `ODT-2026-000001…`. **Es normal, no es un bug**;
  no comparar números ODT entre entornos.

## 5. Estado actual

- `HEAD = c6fb07f` · **15 commits de `main` sin push** (requiere PAT del usuario).
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

## 6. Pendientes (GitHub / Render)

1. **Push** de los 15 commits a `origin` (`https://github.com/Robert170387/CELR-V6.git`, rama
   `main`) con **PAT del usuario**: `git push origin main`.
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

## 8. Decisiones B1–B5 — PENDIENTES de definición por el consultor

> Texto pendiente: el consultor aún no entregó el detalle de estas decisiones; no están en el
> repo ni en el historial. Se completarán cuando llegue el texto exacto.

- B1: _(pendiente)_
- B2: _(pendiente)_
- B3: _(pendiente)_
- B4: _(pendiente)_
- B5: _(pendiente)_