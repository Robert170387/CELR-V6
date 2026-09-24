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

1. **Backend:** las **11** suites `backend/scripts/test_*.py` en verde (desde `backend/`, con
   `PYTHONPATH=.` y `DATABASE_URL` → `:5433`), con el venv:
   `venv\Scripts\python.exe scripts\test_<suite>.py` — los scripts imprimen checks `✓`/`✗`;
   bajo pipe en Windows ejecutar con `$env:PYTHONIOENCODING="utf-8"` (cp1252 rompe esos
   caracteres). `test_cierre_mensual.py` es la suite de la FASE B2;
   `test_flypass_import.py` cubre TF1–TF8 y `test_flypass_list.py` cubre TL1–TL9.
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
- **Trampa — rebuild Docker:** `docker compose up -d --force-recreate backend` recrea el contenedor,
  pero **no reconstruye la imagen**. Cuando cambien migraciones, seeds o `Dockerfile`, ejecutar primero:
  `docker compose build backend` y después `docker compose up -d --force-recreate backend`.
  Síntoma de una imagen stale: el contenedor entra en restart loop y los logs muestran
  `Can't locate revision identified by '...'` durante Alembic.
- Migraciones: **Alembic es el mecanismo oficial** (`alembic upgrade head`). `init_db.py`,
  `schema_celr_v6.sql` y `backend/scripts/migrate_*.py`: históricos, NO usarlos en BD nuevas.

### Partición de seeds

- `seed_base.py` es el entrypoint seguro y siempre presente: sincroniza el catálogo DIVIPOLA y
  puede crear un admin inicial mediante variables de entorno, sin modificar cuentas existentes.
- `seed_demo.py` contiene únicamente fixtures locales. Requiere `CELR_ALLOW_DEMO_SEED=1` y
  rechaza `ENVIRONMENT=production`.
- `seed.py` es un wrapper seguro: ejecuta base siempre y demo solo con el opt-in local.
- `--reset` no está implementado; queda para una fase posterior con guardas y OK propio.
- En producción se debe ejecutar `seed_base.py`; nunca habilitar la seed demo.

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

- **Regla 4 — componente saldo no forzado (B6, 2026-09-23).** `bloqueos_cierre_odt`
  devuelve dos bloqueos: Flypass pendiente y saldo no cubierto. Solo el Flypass se fuerza
  en `POST /liquidaciones/cerrar/{viaje_id}` y `POST /liquidaciones/cierre-mensual`
  desde `9e07857`. Forzar el saldo hoy rompería la operación: 15/18 ODTs activas
  quedarían bloqueadas, incluidas 9 ya `liquidado`. La ambigüedad semántica entre
  “Finalizada” del brief y `liquidado` queda pendiente de decisión de negocio; ver B6 en
  `ALINEACION_MODELO_NEGOCIO.md` §6.

- **Trampa — startup Docker:** después de `docker compose up -d --force-recreate backend`,
  esperar 5–10 s o verificar que el health endpoint responda `200` antes de correr el E2E.
  Sin esa espera, el primer intento puede fallar con `Connection refused` por la race de startup.
- **Dependencia Excel:** `openpyxl==3.1.5` es la dependencia compartida para importadores
  `.xlsx`; queda disponible para el importador Flypass y para futuros importadores bancarios.

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
  | 2 endpoints+tests | `61a56be` | `POST/GET /liquidaciones/cierre-mensual`, `POST /{id}/reabrir`, `POST /{id}/cancelar`, 409 en `/cerrar/{viaje_id}`; schemas `CierreMensualCreate/Response`; suite nueva `test_cierre_mensual.py` |
  | 3 UI frontend | `2131127` | `Liquidaciones.tsx`: «Cerrar mes» + «Meses cerrados» (Detalle/Reabrir/Cancelar); `api/index.ts` (`CierreMensual` + métodos). ⚠️ El commit (etiquetado `feat(frontend)`) arrastra el backend read-only `GET /cierres-mensuales` (soporte del listado) |
  | 4 docs | `8d72c3b` | Sección B2 en `ALINEACION_MODELO_NEGOCIO.md` §5 + pipeline/nota `PYTHONIOENCODING` aquí (§3) |

- **FASE Flypass completa cerrada (2026-09-23):**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | 1 — enforcement de cierre | `9e07857` | El cierre ODT bloquea Flypass pendiente; el componente saldo queda diferido como B6. |
  | 2 — importador Excel | `d4736b7` | `openpyxl`, `raw_data` JSONB, matching/creación de gastos, auto-asociación ODT y suite TF1–TF8. |
  | 3 — listado backend | `cae6b1a` | `GET /api/v1/flypass` con filtros, paginación, JOIN de placa y suite TL1–TL9. |
  | 4 — UI de consulta/importación | `4aaedc8` | Página Flypass, importación, reporte, tabla, filtros, paginación y menú financiero. |

- **FASE Seeds (partición segura) cerrada (2026-09-23):**
  | Sub-fase | Commit | Qué cambió |
  |---|---|---|
  | 1 | `7a1a384` | `seed_base.py`, wrapper municipal compatible y `verify_seed.py`; bootstrap create-only |
  | 1b | `d74fac5` | documentación de la decisión N=2 y trigger N=3 |
  | 2 | `5e86fda` | `seed_demo.py`, wrapper seguro de `seed.py` y verificador base+demo |
  | 3 | `4c117a9` | `docker-compose.yml` habilita demo local mediante `CELR_ALLOW_DEMO_SEED=1` |
  | 3b | `ee86d05` | cleanup automático de refresh tokens en B2 y E2E |

## 6. Pendientes (GitHub / Render)

1. **Hecho:** todo `main` local está respaldado en `origin/fase-a2-fase-2-local` (conteo vivo:
   `git rev-list --count origin/fase-a2-fase-2-local...main` → `0 0` tras cada sesión).
   Pendiente: **merge a `main`** — vía PR en GitHub o
   `git checkout main && git merge fase-a2-fase-2-local`, luego
   `git push origin main` con **PAT del usuario** (Credential Manager, Opción A).
2. **Actualizar los deploys de Render** a FASE A2 (backend + frontend estático con
   `VITE_API_URL=https://celr-backend.onrender.com/api/v1`). Orden de boot en Render:
   `alembic upgrade head && python seed_base.py && python scripts/seed_municipios.py`.
   En producción no ejecutar `seed.py`, porque rechaza la demo; no hacer este paso sin credenciales.
3. **Decidir el usuario `cliente@celr.com`:** no existe en la BD y `seed.py` no lo crea. Si el
   negocio lo requiere, registrar rol `cliente` o extender el seed (con autorización).
4. ~~COMPENSADO_RC mensual: GET solo lectura, sin persistir~~ → **HECHO (FASE B2, 2026-09-23):**
   el cierre mensual se **persiste** en `liquidaciones_conductores` (`es_cierre_mensual` +
   `periodo_ym`) vía `POST/GET /liquidaciones/cierre-mensual`, con reapertura/cancelación y
   bloqueo 409. Ver `ALINEACION_MODELO_NEGOCIO.md` §5.
5. **Residuo 2.E:** los 6 usuarios históricos pueden borrarse si el negocio lo pide (con OK).

## 7. Decisiones registradas

1. Suites backend con **limpieza propia** (2.B): DELETE real en orden inverso de FK; baseline
   idéntico al inicio/fin de cada corrida; excluir siempre el seed. Las suites también purgan
   sus **propios `refresh_tokens` de login** (no forman parte del baseline: `refresh_tokens=0`).
2. `secuencias_documento` **no se resetea** tras corridas de tests/E2E.
3. `smoke.py` es el humo estándar post-migración (2.C), junto a suites + E2E + `npm run build`.
4. Import de `offlineStore` unificado a **estático** (2.D): el módulo no es pesado y ya estaba
   en el bundle inicial vía Layout/Viajes/Gastos/useOfflineSync.
5. **2.E cancelada** (decisión de FASE 2): los 6 usuarios residuo quedan documentados, no se
   borran sin nuevo OK.
6. **Verificación de seeds — N=2:** la idempotencia operativa se define como
   `estado_post-N == estado_post-(N+1)`. El contrato actual no tiene no-determinismo; si un seed
   incorpora `now()`, aleatoriedad u orden no estable, el verificador debe subir a N=3 y comparar
   `estado_post-2 == estado_post-3`.

## 8. Decisiones B1–B6 — preguntas al próximo consultor/agente

Decisiones de negocio/arquitectura que quedan **abiertas**; no son decidibles por el agente. El
consultor previo dejó el marco; quien retome el proyecto debe cerrarlas con el usuario:

| # | Pregunta | Implica si se acepta |
|---|---|---|
| **B1** | ¿Rol `cliente` en seed? | Lógica de seed + credencial de prueba documentada. Riesgo mínimo. |
| **B3** | ¿Refresh token a cookie `HttpOnly`? | **Rompe el offline del PWA.** Trade-off explícito. |
| **B4** | ¿Rate limiter distribuido? | Redis o tabla DB → **migración** + infra. Solo multi-instancia. |
| **B5** | ¿OCR Google Vision o Tesseract local? | Código comentado; activar = dependencia cloud + credenciales. |
| **B6** | ¿Qué significa cerrar operativamente una ODT y cuándo puede hacerse sin saldo cubierto? | Regla 4: no forzar saldo; Flypass sí. Ver `ALINEACION_MODELO_NEGOCIO.md` §6. |

> **B2 quedó resuelta (2026-09-23):** persiste el cierre mensual COMPENSADO_RC con **Opción 1**
> (reforzar `liquidaciones_conductores`, D5-c → 409 preventivo, reabrir/cancelar con rastro). Ver
> FASE B2 en §5 y `ALINEACION_MODELO_NEGOCIO.md` §5.

Prioridad actual: de las restantes, **B3 y B4** son deuda de seguridad/arquitectura al escalar;
**B1** y **B5** cuando surja la necesidad. **B6** requiere decisión de negocio antes de
forzar el componente saldo de la Regla 4.