# AGENTS.md

CELR v6 — Colombian heavy-truck fleet management app ("gestión de flota de carga pesada"). Monorepo: `backend/` (FastAPI + SQLAlchemy + PostgreSQL), `frontend/` (React 18 + Vite + TS + PWA), `scripts/` (E2E test), deployed to Render.

## Fuente de verdad

> **El repositorio es la fuente de verdad. La conversación no lo es.**

- **`docs/00-context/CURRENT.md` es lo primero que se lee.** Dónde estamos, qué está
  bloqueado, cuál es el próximo paso autorizado. Si está más viejo que el último commit,
  verificalo contra `git log` y no confíes en él.
- **`docs/README.md` es el índice.** Mapa de las carpetas, orden de lectura para un agente nuevo,
  y estado de cada documento de la raíz. Cada afirmación se clasifica **FACT / DECISION /
  PROPOSAL / ASSUMPTION / UNKNOWN** (ver abajo).
- **`docs/07-consulting/DECISIONS-PENDING.md` es la fuente de las decisiones abiertas.** D1–D8
  con el estado verificado de cada una contra el código. **Nada de lo que está ahí está
  aprobado.**
- `docs/` es la memoria persistente. `INSTRUCCIONES_OPENCODE.md` tiene las reglas operativas
  (gates §3, trampas §4, estado §5, decisiones abiertas §8).
- **Antes de afirmar que algo "no existe", buscá en el código.** La documentación histórica de
  este repo miente sobre ausencias: `AUDITORIA_CELR_v6.md` afirma que no hay recuperación de
  contraseña. **Sí hay** — lleva 97 commits desfasada. Los documentos vencidos llevan banner ⛔
  en la raíz; no los uses como estado.
- `docs/00-context/CURRENT.md` (versionado) es el estado de salida de la sesión. Se
  actualiza al cerrar cada sub-fase, no durante. `CURRENT.md` > `git log` si divergen.

## Clasificación del conocimiento

Toda afirmación nueva se etiqueta. Sin etiqueta, se asume no verificada.

| Etiqueta | Significado |
|---|---|
| **FACT** | Verificado contra código, BD o comando. Cita `archivo:línea`. |
| **DECISION** | La eligió el usuario. Vive en un ADR de `docs/04-decisions/`. |
| **PROPOSAL** | Sugerencia de un agente o consultor. **No es una decisión.** |
| **ASSUMPTION** | Se cree cierto pero no verificado. |
| **UNKNOWN** | No se puede determinar. **Se marca, nunca se inventa.** |

> **Una recomendación de un agente NO se convierte automáticamente en decisión.** PROPOSAL
> pasa a DECISION solo con aprobación del usuario **y** un ADR. Sin ambas dos, queda en
> `docs/05-tasks/BACKLOG.md` marcado como PROPOSAL.

**Nunca inventar una regla de negocio.** Si el repositorio no la dice, es `UNKNOWN` y se
pregunta. `docs/02-domain/GLOSSARY.md` separa lo confirmado de lo desconocido.

## Agentes y skills

`.opencode/agents/` — 8 agentes especializados. `.opencode/skills/` — 12 skills de procedimiento.

**Estos archivos son parte del repo y hay que mantenerlos.** Un clon los trae; si el
flujo de trabajo cambia, se actualizan **en el mismo commit que el cambio**. Versionados
pero sin mantenimiento se convierten en una fuente de verdad parcial: 20 archivos que
prometen cosas que ya no son ciertas — el mismo patrón que `verify_seed`, que existía y
nadie llamaba.

**Ruta por territorio:** auth/permisos/secretos → `security` + `backend`. Esquema/migraciones/
datos → `database`. React/UI/PWA → `frontend`. Cómo se ve y qué ve el usuario al fallar →
`ux`. Gates/suites/regresión → `qa`. Decisiones previas a implementar → `planner`.

Cada skill enseña un **procedimiento**, no repite la arquitectura. El agente carga la que
corresponde en vez de llevar todo en el prompt.

## Protocolo de trabajo por feature

```
Petición → Especificación → Revisión de arquitectura → ADR → Planificación
  → Implementación → QA → Revisión de seguridad → Revisión UX → Regresión
  → CURRENT.md → Commit
```

**No se salta arquitectura ni documentación** cuando la feature cambia **dominio,
persistencia o seguridad**. Solo-UI o solo-texto puede condensar; el ADR no se negocia.

Procedimiento completo y anti-patrones: skill `celr-workflow`.

## Las cuatro normas

No son consejos: cada una costó un incidente. Detalle y evidencia en
`docs/06-quality/GATES.md` e `INSTRUCCIONES_OPENCODE.md` §4.

1. **Fallo silencioso prohibido.** Todo `catch` registra **e** informa. Nunca cerrar un camino de
   error sin rastro visible. La subclase peligrosa: el **403 descartado en la UI** — el
   endpoint se comportó bien, la presentación lo tira, y **ningún test de endpoint lo ve**.
2. **Campo o función sin consumidor, prohibido.** Todo campo tiene lector, toda función un
   caller, todo `setX` una UI que lo lea. Si es "reservado para fase X", se marca en el código.
   Un valor escrito y nunca leído es **seguridad decorativa**.
3. **Baseline absoluto en app DB, prohibido.** Ningún test afirma `usuarios=7` ni
   `ConductorModel.id == 2`. Miden delta, filtran por sus filas, o construyen un escenario
   controlado y lo restauran.
4. **Trampa del service worker.** Antes de concluir que un fix de frontend no surtió efecto:
   `Ctrl+Shift+R` o desregistrar el SW. Ya mordió dos veces.

## Obligación de pruebas

**4 gates:** 21 suites + humo + E2E + `npm.cmd run build` (incluye `tsc -b`).
Comandos exactos: `INSTRUCCIONES_OPENCODE.md` §3. Resumen accionable: `docs/06-quality/GATES.md`.

- **El conteo se verifica contra el disco**, no contra la documentación:
  `(Get-ChildItem backend\scripts\test_*.py).Count` → **21**.
- En Windows: `npm.cmd`, y `$env:PYTHONIOENCODING="utf-8"` bajo pipe (cp1252 rompe `✓`/`✗`).
- **Nunca relajar un assert para que el gate pase.** Arreglá el test o reportá el problema.
  Un gate verde con un assert que no prueba lo que dice es **peor que uno rojo**.
- **Nunca borrar filas de `auditoria_evento`** para cuadrar un gate. Es append-only.
- **UI: verificar por render, y el camino de ERROR primero.** El feliz ya funciona y el ojo lo
  detecta; el de error funciona hasta que alguien lo prueba. En `GestionUsuarios.tsx` hubo 4
  bugs invisibles a toda prueba de endpoint.

## Obligación de revisión del diff

- `git diff --check` limpio **y** el diff **leído**, no solo el exit code.
- Actualizar la documentación afectada **en el mismo commit**: ADR si hubo decisión,
  `CURRENT.md` si cambió el estado, `GLOSSARY.md` si cambió el dominio.
- Un commit por sub-fase. Mensaje en español, preparado con la herramienta de escritura —
  **nunca** `git commit -F` con redirección de PowerShell (corrompe acentos y mete BOM).
- Backup: `git rev-list --left-right --count origin/fase-a2-fase-2-local...main` → `0 0`.
- **Nunca** `git push` sin que lo pidan.
- Si algo no se pudo hacer, **decir cuál y por qué**. Un "OK las 3" cuando solo se hicieron 2
  es el peor resultado posible.

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
- `backend/scripts/test_ultimo_admin.py` — protección del último admin (A5.2), TUA-1..TUA-12; el CLI break-glass se prueba por subprocess. Neutraliza los admins ajenos al test y los restaura al terminar.
- `backend/scripts/test_usuarios_crud.py` — CRUD de usuarios (A5.1), TUC-1..TUC-18; crea su propio conductor de flota y lo borra al terminar.
- `scripts/e2e_flow_test.py` — against a **running server**; set `CELR_BASE_URL` (default `http://localhost:8000`; use `http://localhost:8001` for the Docker backend).
- La lista completa de **21 suites** y gates está centralizada en `INSTRUCCIONES_OPENCODE.md` §3.
  El conteo se verifica contra el disco (`(Get-ChildItem backend\scripts\test_*.py).Count`),
  no contra el documento: la etiqueta "suite N" es histórica y no cubre todos los archivos.

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