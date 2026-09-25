# AGENTS.md

CELR v6 — Colombian heavy-truck fleet management app ("gestión de flota de carga pesada"). Monorepo: `backend/` (FastAPI + SQLAlchemy + PostgreSQL), `frontend/` (React 18 + Vite + TS + PWA), `scripts/` (E2E test), deployed to Render.

## Language convention

The entire codebase is in **Spanish**: identifiers, comments, API JSON fields, error messages, migration messages, seed/test credentials. Write new code in Spanish to match (e.g. `valor_total`, `numero_odt`, `hash_comprobante`).

## Local stack

Ports are deliberately non-default so the stack coexists with `celr_app_v2` (another app on 5432/8000/5173):

| Service | Docker (`docker compose up`) | Bare-metal dev |
|---|---|---|
| PostgreSQL | `localhost:5433` (db `celr_v6_db`, user `postgres`, pass `admin`) | same |
| Backend | `localhost:8001` (container 8000) | `localhost:8000` |
| Frontend | `localhost:5174` (nginx) | Vite on `localhost:3000` (proxies `/api` → `:8000`) |

DB URL everywhere: `postgresql://postgres:admin@localhost:5433/celr_v6_db` (Windows: `set DATABASE_URL=...`). `config.py` already normalizes `postgres://` → `postgresql://` (Aiven quirk). Run backend with `venv\Scripts\python.exe -m uvicorn app.main:app --port 8000` from `backend/`.

## Backend commands (from `backend/`)

```
python -m alembic upgrade head      # migrations
python -m alembic revision --autogenerate -m "desc"
python seed.py                      # wrapper seguro: base siempre; demo requiere CELR_ALLOW_DEMO_SEED=1
python scripts/seed_municipios.py   # wrapper compatible del catálogo DIVIPOLA — REQUIRED on fresh DBs
```

- **Alembic is the official schema mechanism.** `init_db.py`, `schema_celr_v6.sql`, and `backend/scripts/migrate_*.py` are deprecated/historical — do not use them on new DBs. Baseline migration `a5b6b344c873` is `create_all` from models (no-op on existing DBs); real schema changes go in new migrations.
- **Patrón y validación:** el baseline es dinámico; las migraciones nuevas deben usar guards de existencia y validarse con `backend/scripts/test_fresh_db.py`. La referencia completa está en `INSTRUCCIONES_OPENCODE.md` §4.
- Endpoints autocomplete free-text city → municipio FK, so an empty `municipios` table breaks gastos/viajes. `docker compose` runs `alembic upgrade head && seed.py && scripts/seed_municipios.py` in that order — keep this boot order in mind.

## Frontend commands (from `frontend/`)

```
npm run dev       # Vite on :3000
npm run build     # tsc -b && vite build — typecheck is part of build
```

- `VITE_API_URL` is injected at **build time** (Render static site / Dockerfile ARG); dev falls back to the `/api` Vite proxy. No `.env` files are committed except `frontend/.env.production` (public URL only, intentionally versioned).
- Alias `@/` → `src/`. Strict TS (`noUnusedLocals`, `noUnusedParameters`). No ESLint/Prettier config exists.

## Tests

No pytest. Las suites backend usan la BD real; `test_fresh_db.py` es la excepción
aislada y usa una BD desechable. Las demás suites tienen limpieza propia al final.

- `backend/scripts/test_*.py` — hit the real `celr_v6_db`. Run with `set PYTHONPATH=.` and `DATABASE_URL` set, from `backend/`:
  `venv\Scripts\python.exe scripts/test_auth.py` (also: `test_rbac`, `test_liquidaciones`, `test_gasto_sin_odt`, `test_gasto_combustible`, `test_put_delete`, `test_ocr`, `test_endpoints`, `verify_models`)
- `backend/scripts/test_fresh_db.py` — crea y destruye únicamente `celr_v6_fresh_test`; requiere PostgreSQL vivo en `:5433` y valida la cadena Alembic sin tocar `celr_v6_db`.
- `backend/scripts/test_a1_guard_downgrade.py` — crea y destruye únicamente `celr_v6_a1_guard_test`; verifica que el `downgrade()` de `d4e5f6a7b8c9` aborte si hay usuarios con `correo=NULL` (protección contra pérdida de datos) sin tocar `celr_v6_db`.
- `backend/scripts/test_password_reset.py` — reset de contraseña por token de enlace (A3.1), TR-1..TR-13; usa la BD real con limpieza propia.
- `backend/scripts/test_primer_login.py` — enforcement del primer login (A4), TA-FL1..TA-FL9; usa la BD real con limpieza propia.
- `backend/scripts/test_reset_asistido.py` — reset admin con contraseña temporal (A3.2), TRA-1..TRA-16; usa la BD real con limpieza propia.
- `backend/scripts/test_reset_codigo.py` — reset por código offline de 6 dígitos (A3.3), TRC-1..TRC-16; usa la BD real con limpieza propia.
- `backend/scripts/test_auditoria.py` — auditoría de eventos sensibles (A3.4), TAUD-1..TAUD-12; usa la BD real y limpia solo sus propias filas.
- `scripts/e2e_flow_test.py` — against a **running server**; set `CELR_BASE_URL` (default `http://localhost:8000`; use `http://localhost:8001` for the Docker backend).
- La lista completa de **18 suites** y gates está centralizada en `INSTRUCCIONES_OPENCODE.md` §3.

Credentials: `test@celr.com` / `admin123` (admin), `cliente@celr.com` / `cliente123` (cliente). Seed admin starts with `debe_cambiar_contrasena=True` (first login is forced through `/cambiar-contrasena`).

## Gates operativos

Los comandos, variables de entorno y gates exactos están centralizados en
`INSTRUCCIONES_OPENCODE.md §3`; no duplicarlos aquí. En Windows, usar `npm.cmd` cuando
PowerShell bloquee `npm` por ExecutionPolicy.

## Auth, RBAC, offline

- JWT access+refresh stored in **localStorage** (`celr_token`, `celr_refresh`) — a documented trade-off for offline PWA sync (see `backend/README.md`). Refresh uses rotation (non-reusable) + `jti`; the axios client retries 401 once with a single in-flight refresh.
- Backend RBAC: `RoleChecker([...])` dependency (see `deps.py`). Frontend role gating: `puedeAccederModulo(path, rol)` in `src/utils/rbac.ts` — keep the frontend module map **in sync** with backend role constants (`app/core/roles.py`).
- Offline sync: IndexedDB queue in `src/utils/offlineStore.ts` (`celr_v6_offline`, stores `pending_transactions` / `discarded_transactions`). Bumping `DB_VERSION` requires a proper `onupgradeneeded` handler or existing installs lose data.

## OCR & domain quirks

- OCR runs Tesseract locally (`OCR_ENGINE=tesseract`, needs the binary + `spa` language; Dockerfile installs it). Switching to `OCR_ENGINE=google` requires enabling the commented `google-cloud-vision` dep.
- Receipt duplicate detection is server-side: gastos get a `hash_comprobante` (foto + metadata); a re-submitted hash → 400 "Gasto duplicado".
- ODT numbers (`numero_odt`, e.g. `ODT-…`) come from atomic UPSERTs on `secuencias_documento` (`app/services/secuencias.py`) — they must run in the same transaction as the endpoint commit.
- Monetary fields are `Decimal`; `flete_neto` is computed server-side.