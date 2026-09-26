# SYSTEM.md — arquitectura

Todo verificado contra el código el 2026-09-25. Cita `archivo:línea` donde importa.

## Vista general

```
┌─────────────────────────────┐
│  Frontend (React 18 + Vite)  │   PWA: service worker + cola IndexedDB
│  pages/ components/ utils/   │   JWT en localStorage
└──────────────┬──────────────┘
               │ /api/v1 (nginx → :8000/:8001)
┌──────────────▼──────────────┐
│  FastAPI                     │   11 routers · 45 paths · 65 operaciones
│  api/v1/endpoints/           │
│  services/  ← lógica de dominio │
│  core/      ← config, roles, seguridad, rate limiter
└──────────────┬──────────────┘
               │ SQLAlchemy
┌──────────────▼──────────────┐
│  PostgreSQL (:5433)          │   21 tablas · Alembic oficial
└─────────────────────────────┘
```

## Backend

### Endpoints

**FACT** — 11 routers en `app/api/v1/endpoints/`: `auth`, `usuarios`, `viajes`, `gastos`,
`ingresos`, `liquidaciones`, `conductores`, `vehiculos`, `proveedores`, `municipios`, `flypass`.
45 paths / 65 operaciones (verificado contra `/openapi.json` vivo).

### Frontera de la lógica

**DECISION** — La lógica de negocio va en `app/services/`, no en los endpoints. Los endpoints
traducen HTTP ↔ dominio. Hay 14 servicios; los de identidad son `usuarios.py`,
`password_reset.py`, `auditoria.py`, `email.py`, `auth.py`, `secuencias.py`.

**Motivo:** los endpoints de usuarios lo necesitaba para 3 servicios compartidos
(`ROLES_OBJETIVO_POR_EJECUTOR` consumido por 4 operaciones distintas). No es un capricho
estético.

### Modelo de datos

**FACT** — 21 tablas en 6 módulos: `flota` (vehículos, conductores, usuarios, tokens),
`operaciones` (viajes), `financiero` (gastos, ingresos, liquidaciones), `flota` proveedores,
`mantenimiento`, `ubicacion`, `auditoria`, `secuencia`.

Detalle de columnas en [`DATABASE.md`](DATABASE.md) y en el glosario.

### Core

| Módulo | Responsabilidad |
|---|---|
| `core/config.py` | Settings por env. `DATABASE_URL` normaliza `postgres://` → `postgresql://`. |
| `core/roles.py` | `RolUsuario` enum canónico + `ROLES_LIQUIDACIONES` + `SQL_CHECK_ROL`. |
| `core/security.py` | Hash, verify, `validar_politica_contrasena`, JWT. |
| `core/rate_limiter.py` | In-memory `deque`. **Deuda B4.** |
| `api/v1/deps.py` | `get_current_user`, `exigir_contrasena_actualizada`, `RoleChecker`. |

### Autenticación y autorización

**FACT** — Tres capas, en este orden:

1. **Autenticación** — `get_current_user` valida el JWT, comprueba `activo`, y compara
   `password_version` del token contra el de la BD (`deps.py:52`). Un token emitido antes de un
   cambio de contraseña queda inválido al instante.
2. **Enforcement de primer login** — `exigir_contrasena_actualizada` como dependencia de router
   vía `PROTEGIDOS` (`api.py:15-27`) sobre 8 routers. Devuelve 403 + header
   `X-Celr-Requiere-Cambio`. **Exentos: `auth` y `municipios`** — el flujo de cambio forzado
   necesita `/auth/me` y `/auth/cambio-contrasena`, y `municipios` por un loop de recarga.
3. **Autorización por rol** — `RoleChecker([...])` como dependencia.

**FACT** — El frontend tiene un interceptor que detecta el 403 + header y redirige. Es un
**backstop**, no el mecanismo: la API sola bloquea.

## Frontend

### Estado

**FACT** — Contextos: `AuthContext` (sesión, `login(identificador, contrasena)`),
`MunicipiosContext`. No hay Redux ni otra librería de estado.

### Cliente HTTP

**FACT** — `src/api/client.ts`: axios con `baseURL` = `VITE_API_URL` o `/api/v1`.
- Request: inyecta `Authorization` si hay token.
- Response: en 401 intenta refresh **una sola vez**; si falla, limpia sesión y manda a `/login`.
- 403 + `x-celr-requiere-cambio` → redirige a `/cambiar-contrasena`.

**FACT** — `conTotal<T>(r)` lee el total del header `X-Total-Count`. El listado **no** devuelve
`{data,total}` en el body: devuelve un array plano. Hay que pasarle el tipo explícito porque su
parámetro es `any`.

**FACT** — El rate limit de login se keyea por `usuario:{id}` (canónico), no por cédula o correo
identificador. Un atacante no puede limpiar la cubeta cambiando el identificador.

### Rutas

**FACT** — `ProtectedRoute` + `RequiereCambioContrasena` + `RequireRole(path)`.
`RequireRole` consulta `utils/rbac.ts::puedeAccederModulo`, que devuelve **`true` para paths no
registrados**: una ruta nueva sin registrar en `ACCESO_POR_MODULO` queda abierta.

**FACT** — El catch-all `/*` vive **dentro** de `ProtectedRoute`. Las rutas públicas
(`/recuperar`, `/reset-password`, `/reset-codigo`, `/login`) van **antes** de él o nunca se ven
sin sesión.

### PWA / offline

**FACT** — Service worker (vite-plugin-pwa) + cola de transacciones en IndexedDB
(`utils/offlineStore.ts`, DB `celr_v6_offline`, stores `pending_transactions` y
`discarded_transactions`).

**FACT** — Los JWT viven en `localStorage` (`celr_token`, `celr_refresh`). Es un trade-off
documentado a favor del sync offline. **Deuda B3** (cookie HttpOnly) rompe ese tradeoff.

**FACT** — Bump de `DB_VERSION` sin `onupgradeneeded` propio **pierde datos** en instalaciones
existentes.

## Despliegue

**FACT** — Render: backend container + sitio estático. `render.yaml` define `ENVIRONMENT=production`,
`SECRET_KEY` autogenerado, y el orden de boot `alembic upgrade head && seed_base.py &&
seed_municipios.py`. `seed.py` **rechaza** producción.

**FACT** — `VITE_API_URL` se inyecta en **build time**. Cambiarlo exige rebuild del frontend.

**FACT** — `docker compose up -d --force-recreate X` **no** reconstruye la imagen. Con migraciones,
seeds o `Dockerfile` primero `docker compose build X`.

## Límites conocidos

| Límite | Detalle |
|---|---|
| Single worker | El rate limiter es in-memory. Más de un worker ⇒ cubetas independientes. **B4**. |
| IP detrás de proxy | `Dockerfile:40` sin `--proxy-headers` ⇒ `client.host` es el proxy. Afecta rate limit por IP y `auditoria_evento.ip`. |
| Semántica de `saldo_neto` | Colisión entre saldo operativo de ODT y neto del conductor. **B8**. |
| `asumido_por='owner'` | Permitido por schema y UI, sin regla contable. **B7**. |
