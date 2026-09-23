# CELR v6 — Documento de entrega para Deepseek (nuevo consultor)

> **Para qué es este documento:** brief de **traspaso del proyecto** desde un consultor
> (Claude) hacia **Deepseek**, que tomará el control de la programación de ahora en adelante.
> Está **verificado con evidencia hoy** (2026-09-23). No dependas de conversaciones anteriores:
> todo lo necesario está aquí y en el código.
>
> **Regla #1 — PAUSA TOTAL:** el estado por defecto es **solo lectura/auditoría**. Ninguna
> mutación de código, BD, Docker, commits ni push **sin autorización explícita del usuario**.
> Antes de ejecutar algo que modifique el sistema: presenta el plan y espera el OK.
>
> **Regla #2 — IDIOMA:** todo el proyecto se escribe en **español**: identificadores,
> comentarios, campos JSON de API, mensajes de error, migraciones, seed y tests.

---

## 1. Qué es el proyecto

**CELR v6 ("TRUCK DRIVER")** — aplicación de **gestión de flota de carga pesada en Colombia**:
viajes/ODT, gastos, ingresos, liquidaciones de conductores, maestras (conductores, vehículos,
proveedores) y catálogo de municipios DIVIPOLA. Es un **monorepo**:

| Carpeta | Contenido |
|---|---|
| `backend/` | **FastAPI + SQLAlchemy 2 + PostgreSQL + Alembic** (Python). OCR local (Tesseract) para comprobantes. |
| `frontend/` | **React 18 + Vite + TypeScript + Tailwind + PWA** (vite-plugin-pwa) con sincronización **offline** (IndexedDB). |
| `scripts/` | Suite **E2E** (`e2e_flow_test.py`) contra el backend real en ejecución. |

### Stack exacto (verificado)

**Backend:** FastAPI, SQLAlchemy 2.x, Alembic, pydantic v2, python-jose (JWT), bcrypt,
pytesseract + tesseract `spa`, rate limiting en memoria. Config en
`backend/app/core/config.py` (Settings Pydantic + `.env`).

**Frontend** (`package.json` real):
- deps: `react@^18.3.1`, `react-dom@^18.3.1`, `react-router-dom@^6.26.0`, `axios@^1.7.2`,
  `lucide-react@^0.414.0`
- dev: `typescript@^5.5.3`, `vite@^5.4.0`, `@vitejs/plugin-react@^4.3.1`,
  `vite-plugin-pwa@^0.20.0`, `tailwindcss@^3.4.14`, `postcss@^8.4.38`, `autoprefixer@^10.4.19`
- `npm run build` = `tsc -b && vite build` → **el typecheck es parte del build** (TS estricto:
  `noUnusedLocals`, `noUnusedParameters`).

---

## 2. Arquitectura y puertos (deliberadamente no estándar)

La pila **coexiste con otra app** (`celr_app_v2` que usa 5432/8000/5173), por eso los puertos
propios son **5433 / 8001 / 5174**.

| Servicio | Docker (`docker compose up`) | Bare-metal dev |
|---|---|---|
| PostgreSQL | `localhost:5433` (db `celr_v6_db`, user `postgres`, pass `admin`) | igual |
| Backend | `localhost:8001` (container 8000) | `localhost:8000` |
| Frontend | `localhost:5174` (nginx que proxiya `/api/v1` → `backend:8000`) | Vite en `localhost:3000` (proxy `/api` → `:8000`) |

**DB URL (en todas partes):** `postgresql://postgres:admin@localhost:5433/celr_v6_db`
(Windows: `set DATABASE_URL=...`). `config.py` ya normaliza `postgres://` → `postgresql://`
(quirk de Aiven). El backend se corre con
`venv\Scripts\python.exe -m uvicorn app.main:app --port 8000` desde `backend/`.

> **Incidente reciente resuelto (2026-09-23):** las imágenes Docker estaban desactualizadas
> (previas a FASE A2) y el backend entraba en crash-loop por no encontrar la migración
> `a1b2c3d4e5f6`. Se reconstruyeron `truckdriver-backend` y `truckdriver-frontend` desde el
> repo actual y se levantó el stack: **login verificado OK** vía `:5174` y `:8001`.

---

## 3. Estructura del repo

```
TRUCK DRIVER/
├── AGENTS.md                      # reglas de trabajo (léelo primero)
├── AUDITORIA_CELR_v6.md           # auditoría completa previa (referencia, 12 fases) — TRACKED
├── CONTEXTO_DEEPSEEK_CELR_v6.md   # ESTE documento (untracked)
├── CONTEXTO_CLAUDE_CELR_v6.md     # contexto viejo del consultor anterior (untracked, obsoleto en FASE A1)
├── CONTEXTO_PARA_CLAUDE.md        # contexto viejo del consultor anterior (untracked, obsoleto en FASE A1)
├── docker-compose.yml
├── backend/
│   ├── alembic/                   # migraciones (mecanismo OFICIAL)
│   ├── app/
│   │   ├── main.py                # FastAPI + CORS
│   │   ├── api/v1/
│   │   │   ├── api.py             # ensambla routers (prefix /api/v1)
│   │   │   ├── deps.py            # get_current_user, RoleChecker, exigir_contrasena_actualizada
│   │   │   └── endpoints/
│   │   │       ├── auth.py        # login/refresh/logout/me/cambio-contrasena
│   │   │       ├── vehiculos.py, conductores.py, proveedores.py
│   │   │       ├── viajes.py, gastos.py, ingresos.py, liquidaciones.py
│   │   │       └── municipios.py  # catálogo DIVIPOLA (requiere auth; consumido post-login)
│   │   ├── core/                  # config.py, security.py, roles.py, rate_limiter.py
│   │   ├── db/                    # session.py, base_class.py
│   │   ├── models/                # flota.py, operaciones.py, financiero.py, mantenimiento.py, ubicacion.py, secuencia.py
│   │   ├── schemas/               # pydantic
│   │   ├── services/              # secuencias.py (ODT), ocr_service.py, ocr_engines.py, operaciones.py, hashing.py
│   │   ├── seed.py                # idempotente (credenciales en §5)
│   │   └── db/session.py
│   ├── scripts/                   # seed_municipios.py + test_*.py + migrate_* (históricos)
│   └── README.md                  # setup, migraciones, trade-off de tokens
├── frontend/
│   ├── .env.production            # VITE_API_URL (versionado; ver §4)
│   ├── Dockerfile + nginx.conf    # nginx con proxy /api/v1 → backend
│   └── src/
│       ├── main.tsx, App.tsx
│       ├── api/                    # client.ts (axios + refresh), index.ts (endpoints)
│       ├── context/                # AuthContext.tsx, MunicipiosContext.tsx
│       ├── pages/                  # Login, CambioContrasena, Dashboard, Viajes, Gastos,
│       │                           #   Ingresos, Liquidaciones, Maestras, ScanReceipt
│       ├── components/             # Navbar, Sidebar, Layout, Pagination, SelectorCiudad
│       └── utils/                  # offlineStore.ts, useOfflineSync.ts, rbac.ts, format.ts
└── scripts/e2e_flow_test.py        # E2E contra servidor en ejecución
```

> ⚠️ Los dos `CONTEXTO_*` antiguos describen FASE A1 como "pendiente". **Ya no es así**: FASE A1
> y **FASE A2 están completas y verificadas** (ver §8–§10). No te guíes por ellos.

---

## 4. Comandos

### Backend (desde `backend/`)

```powershell
python -m alembic upgrade head                      # migraciones (OFICIAL)
python -m alembic current                           # revisión aplicada
python -m alembic revision --autogenerate -m "desc" # nueva migración desde modelos
python seed.py                                      # idempotente: admin/conductor/vehículo/proveedor
python scripts/seed_municipios.py                   # DIVIPOLA — REQUERIDO en DBs nuevas
venv\Scripts\python.exe -m uvicorn app.main:app --port 8000   # servidor bare-metal
```

- **Alembic es el mecanismo oficial de esquema.** `init_db.py`, `schema_celr_v6.sql` y
  `backend/scripts/migrate_*.py` son **históricos/deprecados** — no usarlos en DBs nuevas.
- Baseline `a5b6b344c873` = `create_all` desde modelos (no-op en DBs existentes). Los cambios
  reales van en **migraciones nuevas**.
- Orden de arranque de Docker (mantener): `alembic upgrade head && seed.py &&
  scripts/seed_municipios.py`.

### Frontend (desde `frontend/`)

```powershell
npm run dev       # Vite en :3000 (proxya /api → :8000)
npm run build     # tsc -b && vite build — typecheck incluido
```

- `VITE_API_URL` se inyecta en **build-time** (ARG del Dockerfile / Render). En dev cae al proxy.
  Para producción en Render el valor debe ser la URL absoluta del backend:
  `https://celr-backend.onrender.com/api/v1`.
- Alias `@/` → `src/`. No hay ESLint/Prettier configurados.

### Docker (desde la raíz)

```powershell
docker compose up -d --build      # reconstruye y levanta db + backend + frontend
docker compose logs -f backend    # seguimiento
```

---

## 5. Seed y credenciales (verificadas en `backend/seed.py`)

| Qué | Valor | Rol |
|---|---|---|
| Admin | `test@celr.com` / `admin123` | admin |
| Conductor | cédula `1234567890` ("Juan Perez", correo `juan.perez@celr.com`) | — |
| Vehículo | placa `SKN756` (Kenworth 2020) | — |
| Proveedor | NIT `900123456` (Terpel) | — |

- El seed es **idempotente** (UPSERT; re-hashea la clave si cambió la constante y reactiva si
  quedó inactivo). **NO crea ningún usuario `cliente@celr.com`** (en esta BD no existe).
- En DBs nuevas es **obligatorio** `scripts/seed_municipios.py` (DIVIPOLA, 1122 municipios) o
  el autocompletado ciudad→municipio se rompe.
- El admin arranca con `debe_cambiar_contrasena=True` → el primer login fuerza el cambio. Hoy,
  tras las corridas de tests, la cuenta `test@celr.com` está **activa y sin cambio forzado**
  (verificado en BD).

---

## 6. Esquema, migraciones y modelo contable (contrato FASE A2)

### Migraciones aplicadas (BD viva, verificado hoy)

```
a5b6b344c873  (baseline v6 — create_all, no-op en DBs existentes)
26c38982f253  (agrega columna password_version)
b7c8d9e0f1a2  (viajes_municipios_secuencias)
a1b2c3d4e5f6  (head) — FASE A2: modelo contable/operativo
```

### 🟢 Contrato de negocio VIGENTE (FASE A2) — crítico

1. **El cliente NUNCA envía los campos calculados; el servidor los deriva.** El backend
   recalcula con `recalcular_viaje` (ODT) y `consolidar_compensado` (mensual). El frontend envía
   **solo inputs manuales**: `%` retención, `empresa_manifiesto_id`, `fecha_manifiesto`,
   `otras_deducciones`, `anticipo_manifiesto`, `porcentaje_comision`, y los enums nuevos.
2. **Enums de ingreso actualizados:** incluye `anticipo_manifiesto`. ⚠️ Un bug corregido: el
   literal viejo dejaba `total_anticipos` en `0` — ya está el literal correcto en
   `liquidaciones.py`.
3. **Enums de gasto actualizados** (`estado_pago`: `pagado` / `pendiente_por_pagar` /
   `legalizado`; `tipo_gasto`; `estado_validacion`: `pendiente` / `observado` / etc.).
4. **Anti-duplicados de gastos:** solo cuentan los gastos **vivos** (`eliminado_en IS NULL`) al
   crear/editar y en OCR. El `hash_comprobante` (foto + metadata) es server-side; re-submit del
   mismo hash → `400 "Gasto duplicado"`. En OCR el hash es **lógico** (MD5 de proveedor+fecha+
   monto), independiente de la imagen.
5. **ODT (`numero_odt` = `ODT-…`):** se generan con **UPSERT atómico** sobre
   `secuencias_documento` (`app/services/secuencias.py`), **en la misma transacción** que el
   commit del endpoint. No reemplazar por otra lógica.
6. **Bloqueos de cierre de ODT** (`GET /viajes/{id}/bloqueos-cierre`): lista de razones (peajes
   Flypass pendientes de legalizar, etc.). Lista vacía = la ODT es cerrable.
7. **Pantalla mensual `COMPENSADO_RC`:** el endpoint **`GET /liquidaciones/compensado`** es
   **solo lectura**: consolida el mes (haberes − descuentos) con la fórmula de la DB:
   - haberes = comision_flete + bonificaciones + viaticos + otros_haberes + salario_basico +
     auxilio_transporte + papeleria
   - descuentos = anticipos_entregados + gastos_a_cargo_conductor + prestamos +
     otros_descuentos + descuento_salud_pension + retiros_tarjeta_anticipos
   - saldo = haberes − descuentos
   El cierre **formal sigue por ODT** (no hay cierre mensual en la DB todavía; ver pendientes §11).
8. **Montos monetarios:** `Decimal`; `flete_neto` se calcula server-side.

### Modelos/entidades principales

`Usuario`, `RefreshToken`, `Vehiculo`, `Conductor`, `ConductorVehiculo`, `Viaje`, `Gasto`,
`Ingreso`, `Liquidacion`, `Movimiento`, `Proveedor`, `Municipio`, `SecuenciaDocumento`
(+ columnas nuevas A2 en `operaciones.py`/`financiero.py`: enums, `anticipo_manifiesto`,
`porcentaje_comision`, campos de compensado, etc.).

---

## 7. Autenticación, RBAC y offline (estado actual)

- **JWT access + refresh** en `localStorage` (`celr_token`, `celr_refresh`) — **trade-off
  documentado** para el PWA offline (ver `backend/README.md`). El refresh usa **rotación
  (no reutilizable) + `jti`**; el cliente axios reintenta 401 **una vez** con un único refresh en
  vuelo (single in-flight).
- **FASE A1 (completa):** el JWT lleva `password_version`; `cambio-contrasena` devuelve
  **200 + par de tokens nuevos**, incrementa `password_version` (revoca access previos),
  revoca refresh tokens y pone `debe_cambiar_contrasena=False`. `deps.py` valida
  `password_version` y bloquea endpoints de negocio con **403 + cabecera
  `X-Celr-Requiere-Cambio`** cuando `debe_cambiar_contrasena=True`. El frontend lee ese header y
  redirige a `/cambiar-contrasena`.
- **Rate limit login:** en memoria (`rate_limiter.py`): máx. **5 fallos por correo en 15 min** →
  6.º intento = **429**; un login exitoso limpia los fallos.
- **RBAC backend:** `RoleChecker([...])` en `deps.py`. Roles (`app/core/roles.py`):
  `admin`, `operador`, `contador`, `supervisor`, `cliente`, `conductor`.
- **RBAC frontend:** `puedeAccederModulo(path, rol)` en `src/utils/rbac.ts` — **mantener en
  sincronía con el backend**. Hoy los módulos restringidos son `/scan`, `/liquidaciones`,
  `/ingresos`, `/maestras`.
- **Offline:** IndexedDB `celr_v6_offline` (stores `pending_transactions` /
  `discarded_transactions`) en `offlineStore.ts`. **Bump de `DB_VERSION` exige un
  `onupgradeneeded` correcto** o los installs existentes pierden datos.
- **Cambio forzado de contraseña:** funcional de punta a punta (verificado en E2E).

---

## 8. Endpoints principales (`/api/v1`)

| Recurso | Notas |
|---|---|
| `/auth/login`, `/refresh`, `/logout`, `/me`, `/cambio-contrasena` | JWT rotativo + `password_version` |
| `/vehiculos`, `/conductores`, `/proveedores` | CRUD maestras |
| `/viajes` (+ `/viajes/{id}/bloqueos-cierre`) | ODT con cálculo server-side |
| `/gastos` (incl. OCR `/scan-receipt` vía `/gastos` o similar) | anti-duplicado por hash |
| `/ingresos` | con enums nuevos (incl. `anticipo_manifiesto`) |
| `/liquidaciones` (+ **`/liquidaciones/compensado`** GET) | cierre por ODT + consolidado mensual |
| `/municipios` | catálogo DIVIPOLA — **requiere auth** (consumido post-login por `MunicipiosContext`/`SelectorCiudad`; NO se usa pre-login) |

> Detalles de contrato exactos (schemas pydantic): `backend/app/schemas/`.

---

## 9. Estado REAL verificada hoy (2026-09-23)

### Git

```
rama local  = main
HEAD local  = 962ee79  (FASE 2.D - fix frontend offlineStore)
origin/main = 317fbe2  (feat: gastos sin ODT, página de ingresos, ...)
local adelante = 20 commits — SIN PUSH aun
                 (FASE A2:  9 commits, b802d82 → … → 5738e51)
                 (FASE 2.0-2.D: 165078e → 2e38ee4 → e0bf6bd → a73c952 → 962ee79)   [5]
                 (docs/higiene 2.G: 3fdbb32 → c6fb07f → 62ca791 → d722f94 → d3b9557 → +1 sincronización) [6]
working tree = limpio (solo los CONTEXTO_*.md untracked, no modificados)
```

Historial reciente relevante:

| Commit | Contenido |
|---|---|
| `b802d82` | Base tras auditoría (beanstack hardening: secuencias ODT, municipios DIVIPOLA, rate limiter, auth, liquidaciones/ingresos con ODT, fixes TS) |
| `e45adb7`, `dcd03b5` | **FASE A1** — `password_version` en JWT + revocación; frontend guarda tokens nuevos del cambio de contraseña |
| `baa2933`, `64a2fa9` | **FASE A2 modelo** — migración `a1b2c3d4e5f6` + modelos ORM alineados |
| `1da3b0b`, `8b36f17` | **FASE A2 backend** — enums nuevos, recálculo server-side, `GET /liquidaciones/compensado` |
| `b9e665e` | **FASE A2 frontend** — ODT con inputs/calculados, enums ingreso/gasto, pantalla COMPENSADO_RC |
| `5738e51` | **FASE A2 pruebas** — suites realineadas + fixes (literal `anticipo_manifiesto`, FK viaje→404, duplicados sin soft-delete, `test_rbac`/`test_auth` idempotentes) |
| `165078e` | **FASE 2.0** — doc: corregida afirmación sobre `/municipios` (requiere auth, no es público ni pre-login) |
| `2e38ee4` | **FASE 2.A** — `requests` en el venv del backend (E2E sin depender del Python del sistema) |
| `e0bf6bd` | **FASE 2.B** — suites: limpieza de datos al final (DELETE real en orden inverso de FK) |
| `a73c952` | **FASE 2.C** — `backend/scripts/smoke.py` (humo: conexión, migraciones head, seed, login, conteos baseline) |
| `962ee79` | **FASE 2.D** — frontend: import de `offlineStore` unificado a estático (warning Vite eliminado) |

### BD / Docker / tests

- BD viva: migraciones **hasta `a1b2c3d4e5f6` (head)**; municipios DIVIPOLA sembrados (1122).
- Baseline estable verificada (2.B/2.C y hoy): `usuarios=7, vehiculos=9, conductores=7,
  proveedores=6, viajes_odt=24, gastos=37, ingresos=8, liquidaciones_conductores=6,
  refresh_tokens=0`; `km_actual` SKN756 = `125000.00`; max ODT = `ODT-2026-000030`.
  **Residuo documentado (2.E cancelada):** 6 usuarios históricos `cli-*`/`cond-*@celr.com`
  (ids 13–16, 20–21), 0 referencias FK — no borrados por decisión de FASE 2.
- Stack Docker: **operativo** (backend `:8001`, web `:5174`, DB `:5433`).
  Login verificado: `test@celr.com`/`admin123` → 200 con access+refresh, vía `:5174` y `:8001`.
- **Tests backend: 8/8 en verde con limpieza propia** (2.B): cada suite borra los datos que crea
  (DELETE real, orden inverso de FK) y la BD vuelve al baseline; gate 3×3 verdes.
- **Smoke `[SMOKE OK]`** (2.C): conexión, migraciones en head, seed, login, conteos baseline.
- **E2E completo en verde** (2.A, re-verificado con el venv, `requests` 2.34.2):
  Auth → ODT `flete_neto=850000` → anti-duplicado 400 → balance 415000 → cierre `liquidado`.
- `npm run build` (tsc + vite) **en verde y sin warnings de chunking** (2.D: `offlineStore`
  unificado a import estático).

---

## 10. Cómo correr las suites (referencia rápida)

```powershell
# Tests backend (desde backend/, PYTHONPATH=. y DATABASE_URL a :5433)
venv\Scripts\python.exe scripts/test_auth.py
venv\Scripts\python.exe scripts/test_liquidaciones.py
# ... (test_rbac, test_gasto_sin_odt, test_gasto_combustible, test_put_delete,
#      test_ocr, test_endpoints, verify_models)

# Smoke post-migración (2.C): conexión, migraciones head, seed, login, conteos baseline
venv\Scripts\python.exe scripts\smoke.py

# E2E (requiere servidor corriendo, p. ej. Docker :8001; venv ya incluye `requests` desde 2.A)
$env:PYTHONUTF8="1"
$env:CELR_BASE_URL="http://localhost:8001"
venv\Scripts\python.exe ..\scripts\e2e_flow_test.py  # desde backend/
# Si se captura la salida por pipe (Tee), añadir además: $env:PYTHONIOENCODING="utf-8"
# (el check ✓ del E2E revienta con cp1252 bajo pipe).
```

> Desde **2.B**, cada suite backend borra los datos que crea (DELETE real en orden inverso de FK):
> la BD queda con el mismo baseline al inicio y al final de cada corrida. El **E2E sí deja datos**
> de demostración en la BD real (viaje liquidado + liquidación) — limpiar manualmente si se
> requiere (purge de `viajes_odt` con `numero_odt > 'ODT-2026-000030'` y sus hijos).

---

## 11. 🟠 PENDIENTE POR EJECUTAR (checklist priorizado)

### P1 — Operativo / entrega (requiere autorización + credenciales del usuario)

1. **Push a GitHub de los 15 commits.** `origin = https://github.com/Robert170387/CELR-V6.git`,
   rama `main`, hoy **sin upstream de push** y **sin credencial de escritura** (se requiere un
   **PAT** del usuario). Comando (cuando el usuario lo autorice):
   ```powershell
   git push origin main
   ```
2. **Actualizar los deploys de Render** a FASE A2 (backend desplegado y frontend estático). El
   frontend de Render debe inyectar `VITE_API_URL=https://celr-backend.onrender.com/api/v1`.
   Recordar el orden de boot en Render: `alembic upgrade head && seed.py &&
   scripts/seed_municipios.py`. **No hacer sin confirmar acceso/credenciales del deploy.**
3. **Decidir el usuario `cliente`:** no existe `cliente@celr.com` en la BD y `seed.py` no lo
   crea (el README lo documenta como credencial de prueba). Si hace falta para el negocio:
   registrar rol `cliente` o extender seed (con autorización).
4. **Verificar si los inputs manuales del mensual COMPENSADO_RC persisten.** Hoy
   `/liquidaciones/compensado` es **GET solo lectura** y el cierre formal es **por ODT**. Si el
   negocio requiere *guardar* la conciliación mensual (retención, comisión, anticipo manifiesto,
   otras deducciones), falta una tabla/endpoint de cierre mensual. **Preguntar al usuario antes
   de diseñarlo.**
5. **Actualizar los `CONTEXTO_*.md` antiguos** (opcional, son del usuario y están obsoletos en
   las secciones de FASE A1). No borrarlos sin que el usuario lo pida.
6. **Residuo 2.E (cancelada, documentado):** 6 usuarios históricos `cli-*@celr.com` /
   `cond-*@celr.com` (ids 13, 14, 15, 16, 20, 21) siguen en la BD con **0 referencias FK**.
   FASE 2 decidió **no borrarlos** (2.E cancelada); si el negocio lo pide, borrarlos con OK explícito.

### P2 — Deuda técnica / optimizaciones sugeridas

1. ~~**Tests:** implementar **limpieza de datos al final**…~~ → ✅ **HECHO en FASE 2 (2.B):**
   `e0bf6bd` — las 8 suites borran los datos que crean (DELETE real, orden inverso de FK);
   la BD vuelve al baseline al final de cada corrida.
2. ~~**E2E:** el venv del backend **no tiene `requests`**…~~ → ✅ **HECHO en FASE 2 (2.A):**
   `2e38ee4` — `requests>=2.31` en `requirements.txt` e instalado en el venv (2.34.2).
3. **Seguridad de tokens:** mover el `refresh_token` de `localStorage` a **cookie
   `HttpOnly; Secure; SameSite=Lax`** (alternativa documentada en `backend/README.md`, no
   aplicada porque rompería el flujo offline). Valorar con el usuario si la compensación XSS
   importa más que el offline.
4. **Rate limiter:** en memoria no escala a **multi-instancia**/Render workers. Futuro: almacén
   compartido (Redis o tabla DB).
5. **OCR:** local con Tesseract (`spa`). El motor **Google Vision** queda comentado en
   `requirements.txt` (`OCR_ENGINE=google` + `google-cloud-vision`) para cuando se quiera calidad
   cloud. El hash anti-duplicado ya es lógico (no depende de la imagen).
6. ~~**Build de frontend:** warning de Vite (`offlineStore.ts` dynamic y static-imported…)~~ →
   ✅ **HECHO en FASE 2 (2.D):** `962ee79` — import unificado a estático; `npm run build` verde
   y sin warnings de chunking.
7. **Herramientas de calidad:** no hay ESLint/Prettier. Opcional estandarizar (los `noUnused*`
   del TS ya actúan como guardarraíl).
8. **Backups:** conviene un `pg_dump` programado de `celr_v6_db` (5433) antes de migraciones
   grandes (hoy no hay mecanismo automático).
9. **Fases de seguridad futuras** (de la auditoría, NO autorizadas aun): S3 refresh-rotate
   hardening adicional, S4 rate limit escalado/distribuido, envío SMTP de restablecimiento de
   contraseña obligatorio. **Solo con autorización explícita.**
10. **Pruebas de humo post-migración:** correr `scripts/smoke.py` (humo formalizado en 2.C) +
    la suite backend + E2E (rutina estándar ya adoptada en FASE A2, ver §10).

---

## 12. Reglas de trabajo NO negociables

1. **PAUSA TOTAL por defecto** — sin autorización explícita no tocar código, DB, Docker, ni
   ejecutar comandos mutadores. Lectura/auditoría siempre OK.
2. **Anunciar el plan antes de cada fase** que toque otro sistema (migración, Docker, push).
3. **Un commit por fase**, en español; **push solo al final** con el PAT del usuario.
4. **Todo en español**: código, comentarios, mensajes API, tests, migraciones.
5. **Cero migraciones/Docker sin autorización** — si un cambio exige una migración no autorizada,
   detente y pide OK.
6. **No rompas el catálogo de municipios** consumido post-login por `SelectorCiudad` (no se usa
   pre-login; el endpoint requiere auth).
7. **Mantener RBAC en sync** frontend (`rbac.ts`) ↔ backend (`roles.py`).
8. **Respetar el contrato A2**: el cliente nunca envía los campos calculados; el servidor los
   deriva (`recalcular_viaje`, `consolidar_compensado`).
9. Validar cada contrato con la suite de `backend/scripts/` y `npm run build` **antes** de
   commitear. `npm run build` incluye el typecheck — es el gate del frontend.
10. **Ante ambigüedad del entorno**, usa `git` read-only (`git status --porcelain`, `git diff`)
    como fuente fiable; no edites a ciegas.

---

## 13. Glosario y quirks del proyecto

| Término | Significado |
|---|---|
| ODT | Orden de trabajo/documento del viaje. Número `ODT-…` generado server-side (secuencias atómicas) |
| COMPENSADO_RC | Pantalla mensual consolidada (haberes − descuentos = saldo) |
| Flypass | Peajes por pasada; si hay pendientes de legalizar, la ODT no se cierra |
| `eliminado_en` | Soft-delete (los gastos eliminados NO cuentan para anti-duplicados ni totales) |
| `debe_cambiar_contrasena` | Flag de primer login → fuerza cambio (403 + `X-Celr-Requiere-Cambio`) |
| `password_version` | Versión del password en el JWT; cambiarla revoca access tokens previos |
| `hash_comprobante` | Hash anti-duplicado de recibos (OCR) — server-side, `400 Gasto duplicado` |
| `celr_v6_offline` | IndexedDB de cola offline (`pending_transactions` / `discarded_transactions`) |
| `VITE_API_URL` | URL del backend inyectada en build-time (Render/ARG Docker) |
| `postgres://` vs `postgresql://` | `config.py` normaliza el esquema (quirk Aiven) |

---

*Documento generado para el traspaso de consultor (Claude → Deepseek). Verificado contra repo,
BD y stack local el 2026-09-23. Si Deepseek modifica el proyecto, conviene actualizar §9–§11 al
cierre de cada fase.*