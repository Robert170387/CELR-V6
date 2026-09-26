# Auditoría Técnica — CELR v6 "TRUCK DRIVER" (2026-09)

> ## ⛔ HISTÓRICO — DESCRIBE EL ESTADO EN `b802d82`, NO EL ESTADO ACTUAL
>
> **Fecha del análisis:** 2026-09-22 · **Base:** commit `b802d82` (97 commits atrás) · **Actual:** `git log --oneline -1`
>
> Los hallazgos S1–S4 **fueron remediados después**. Acting sobre ellos reintroduce trabajo
> ya hecho. Estado verificado contra el código:
>
> | Hallazgo | Decía | Estado actual (verificado) |
> |---|---|---|
> | **S1** | `debe_cambiar_contrasena` se valida SOLO en el frontend | **RESUELTO.** `deps.py:exigir_contrasena_actualizada` + `PROTEGIDOS` sobre 8 routers (`api.py:15-27`). 403 con header `X-CELR-Requiere-Cambio`. El router `auth` está exento **a propósito**: el flujo forzado necesita `/auth/me` y `/auth/cambio-contrasena`. |
> | **S2** | Falta `password_version` en el token | **RESUELTO.** Campo en `flota.py:74`, viaja en el JWT, `deps.py:52` lo compara contra el valor actual. Cambiar la contraseña invalida los access tokens al instante. |
> | **S3** | Recuperación de contraseña NO IMPLEMENTADA | **RESUELTO.** `POST /auth/forgot-password`, `/auth/reset-password`, `/auth/reset-codigo`, `/auth/cambio-contrasena`, más `/usuarios/{id}/reset-password` y `/reset-codigo`. Servicio `app/services/password_reset.py`. UI en `frontend/src/pages/{Recuperar,ResetPassword,ResetCodigo}.tsx`. |
> | **S4** | Rate limit in-memory y solo en login | **PARCIAL (abierta, = B4).** Ahora cubre login, `forgot-password` y `reset-codigo`. Sigue in-memory (`app/core/rate_limiter.py`) y **no** limita `/auth/refresh` ni `/auth/cambio-contrasena`. Ver `INSTRUCCIONES_OPENCODE.md` §4. |
>
> El texto original se conserva sin modificar, para trazabilidad. **No lo uses como estado
> vigente.** Estado actual: `docs/00-context/CURRENT.md` e `INSTRUCCIONES_OPENCODE.md` §4–§5.

> Documento de auditoría de nivel senior. **Reglas respetadas:** sin modificación de código, sin refactors,
> sin cambios de DB/Docker/endpoints, sin instalación de paquetes. Solo lectura + verificación contra el código real.
> Todo hallazgo cita archivo y línea. Lo que no se pudo verificar de forma concluyente se marca **NO VERIFICADO**;
> lo que no existe se marca **NO IMPLEMENTADO**.

---

## 1. Inventario del proyecto (FASE 1)

| Dimensión | Valor | Evidencia |
|---|---|---|
| Monorepo | `backend/`, `frontend/`, `scripts/`, `docker-compose.yml`, `render.yaml`, `AGENTS.md`, `schema_celr_v6.sql` | glob raíz |
| Backend framework | FastAPI (`app.main:app`) | `backend/main.py:10` |
| Backend lenguaje | Python 3.11 | `backend/Dockerfile` `FROM python:3.11-slim` |
| ORM | SQLAlchemy 2.0 (híbrido: `db.query()` legacy + `select()` core) | `viajes.py`, `auth.py` |
| Migraciones | Alembic (`python -m alembic upgrade head`) | `docker-compose.yml:37`, `backend/alembic/versions/` |
| Base de datos | PostgreSQL 16 (`postgres:16-alpine`) | `docker-compose.yml:5` |
| DB puerto host | 5433 (no-default, convive con `celr_app_v2` en 5432) | `docker-compose.yml:12` |
| Backend puerto host | 8001 (container →8000) | `docker-compose.yml:31` |
| Frontend puerto host | 5174 (nginx →80) | `docker-compose.yml:48` |
| Frontend framework | React 18 + Vite + TypeScript + PWA (workbox) | `frontend/package.json`, `dist/workbox*` |
| SPA router proxy | nginx `/api/v1/` → `http://backend:8000/api/v1/` | `frontend/nginx.conf:8-9` |
| Auth | JWT access (jose, HS256) + refresh tokens opacos hasheados (SHA-256) en DB | `backend/app/core/security.py` |
| Sesiones | Access+refresh en `localStorage` (claves `celr_token`/`celr_refresh`) | `frontend/src/api/client.ts:7-8` |
| RBAC | `RoleChecker` backend + `puedeAccederModulo/rbac.ts` frontend | `backend/app/api/v1/deps.py`, `frontend/src/utils/rbac.ts` |
| Rate limit | In-memory deque, 5 intentos/15 min, SOLO login | `backend/app/core/rate_limiter.py` |
| Testing | Scripts ad-hoc contra DB real; **no hay pytest ni vitest** | `backend/scripts/*.py`; frontend sin suite |

Estructura backend de endpoints (con prefijo `/api/v1`):
`api.py` monta `vehiculos, conductores, proveedores, viajes, gastos, ingresos, liquidaciones, municipios, auth`
además de `deps.py` (get_current_user, RefreshToken, hash/verify) y `RateLimiter` (`backend/app/core/rate_limiter.py`).

---

## 2. Auditoría de autenticación / ciclo de contraseñas (FASES 4 y 5)

### 2.1 Login normal — **OK con matices**
`auth.py` login:
- Normaliza clave `correo.strip().lower()` y aplica rate limit por usuario antes de la query (`auth.py:28-33`).
- Mensaje genérico `"Credenciales incorrectas"` en usuario inexistente **y** contraseña incorrecta → **no hay enumeración de usuarios a través del mensaje** (`auth.py:45-47`).
- Verifica `activo`, actualiza `ultimo_acceso`, emite access (`ACCESS_TOKEN_EXPIRE_MINUTES=30`) + refresh (`REFRESH_TOKEN_EXPIRE_DAYS=14`) (`auth.py:50-56`).
- SHA/rounds: `bcrypt.rounds=12` en hash (`security.py:18`).

**Hallazgo S1 (seguridad-op. media):** el **cambio obligatorio de contraseña (`debe_cambiar_contrasena=True`) se valida SOLO en el frontend**, no en el backend: el endpoint `/auth/login` emite token completo sin comprobar el flag, y `get_current_user` (`deps.py:13-42`) no niega el acceso. Un cliente que use la API directamente (Postman/curl) puede saltarse el flujo de cambio forzado. -> Corrección: forzar `403 must_change_password` en `get_current_user` para todo endpoint salvo `/auth/cambio-contrasena`, `/auth/me` y `/auth/refresh`.

### 2.2 Cambio voluntario — **OK**
`POST /auth/cambio-contrasena` verifica contraseña actual, hashea la nueva, `debe_cambiar_contrasena=False`, y **revoca todos los refresh tokens activos del usuario** (invalidación de sesiones) (`auth.py:109-132`). Buena práctica.

### 2.3 Cambio obligatorio (primer acceso) — **parcial**
Flag existe en modelo (`Usuario.debe_cambiar_contrasena`), seed lo fija en `True` (`seed.py:29`), frontend obliga vía `CambioContrasena.tsx`. **Falta enforcement en backend** (ver S1). El frontend solo muestra la página si detecta el flag/rol; un atacante puede consumir la API sin pasarlo.

### 2.4 Recuperación de contraseña — **NO IMPLEMENTADO**
- **No existe** endpoint de recuperación/olvido de contraseña (`forgot`/`reset`/`reset_password`): búsqueda en backend dio 0 resultados.
- **No existe** input de «olvidé mi contraseña» en el frontend (`Login` sin link de recuperación).
- **Impacto operativo ALTO:** la única vía de volver a entrar sin contraseña es que un admin levante el usuario en DB o que `seed.py` re-hashée. No hay token de un solo uso ni expiración de recuperación.

### 2.5 Sesiones / token lifecycle — **mayormente correcto**
- Refresh tokens: opacos, `secrets.token_urlsafe(48)`, hasheados SHA-256 en DB (`security.py:34-45`), rotación con revocación del usado y `jti` en access.
- Refresh endpoint: token inválido/revocado/expirado → 401 (`auth.py:60-74`); rota refresh al usarlo.
- Logout: `revoke_refresh_token` sobre el refresh enviado (`auth.py` logout). El refresh se revoca.
- **TO-DO de seguridad S2 (media):** el **access token NO se valida contra un registro en DB** (stateless JWT): un JWT firmado con `SECRET_KEY` y `usuario_id` en payload sigue siendo válido aunque el usuario se active/desactive. `get_current_user` solo chequea `payload.usuario_id` y `usuario.activo` — la desactivación se propaga (chequea `activo`), pero el **cambio de contraseña no invalida access tokens ya emitidos** (sólo revoca refresh). Ver 2.6.

### 2.6 Invalidación tras cambio de contraseña
- Revoca refresh tokens → la siguiente renovación falla (OK, sesión muere a los 30 min). Pero los **access tokens ya emitidos siguen válidos hasta expirar**, porque no hay `password_changed_at` en el JWT ni filtro. Corrección posible (menor): incluir `contrasena_version`/`contrasena_cambiada_en` en el token y validarlo.

### 2.7 Almacenamiento seguro — **OK**
bcrypt rounds=12, salt per-user, `contrasena_hash` (bcrypt estándar). Sin passwords en texto plano.
**Hallazgo incidental:** el endpoint de cambio vuelca `setattr`/`model_dump` de payload del cliente; se descarta (ver 5).

### 2.8 Rate limiting / fuerza bruta — **parcial**
- `rate_limiter.py`: in-memory `defaultdict(deque)`, `MAX_INTENTOS=5`, ventana 15 min, `excede_limite/registrar_fallo/limpiar_fallos`. **Solo cubre `/auth/login`** (se llama en `auth.py:29-33`).
- **No hay rate limit en:** refresh token, cambio de contraseña, ni en ningún endpoint de negocio. Un atacante puede hacer fuerza bruta sobre `/auth/refresh` o sobre N usuarios en paralelo (la clave es por-usuario, no por-IP **global**; `_fallidos` por usuario permite ataque distribuido multi-usuario).
- **In-memory:** se pierde al reiniciar el contenedor; sin Redis/Postgres (documentado en el propio archivo). Para multi-replica es insuficiente.

### 2.9 Protección contra enumeración — **masteria OK**
Login usa mensaje genérico. **Detalle:** el endpoint `/auth/me` y el `cambio-contrasena` devuelven `402/403` con respuestas que podrían diferir (usuario inactivo "Usuario inactivo" vs "Credenciales incorrectas") — leve señal de enumeración en contraste con login (`auth.py:45-49` diff). Riesgo bajo.

---

## 3. Auditoría de autorización / RBAC (FASE 7)

- Backend: `RoleChecker`/`RoleChecker(roles)` como `depends` en router/endpoint; `roles.py` centraliza `ROLES_*`. **Bien: autorización backend REAL, no solo ocultar botones.** Encontrado el patrón en `proveedores.py:19-98`, `gastos.py:190`, etc.
- Frontend: `rbac.ts` filtra menú por rol (`puedeAccederModulo`), pero **es solo ocultación de UI** (esperable; la fuente de verdad es el backend).
- **IDOR / ownership:** en `viajes.py` el GET de un viaje por `{viaje_id}` **no valida que el viaje pertenezca al conductor/vehículo del usuario**; `listar_viajes` filtra por `eliminado_en` pero no por `conductor_id`. Un conductor autenticado con rol `conductor` podría **leer** viajes de otros conductores (solo lectura; escritura está restringida por rol `ROLES_LIQUIDACIONES` → `gastos.py:190`, `put` en `viajes` con RoleChecker). **Confirmar en datos/rol**: verificar si existe endpoint que exponga `viaje_id` sensible para role `conductor` (el `GET /viajes/{id}` solo requiere `get_current_user`).

Datos de roles concretos en `backend/app/core/roles.py`:
ROLES_ESCRITURA_MAESTROS, ROLES_LIQUIDACIONES, ROLES_INGRESOS, ROLES_MUNICIPIOS. Acceso lectura maestras abierto a cualquier autenticado (lista = lectura), escritura restringida a admin/operador/supervisor según módulo.

---

## 4. Auditoría de la base de datos (FASE 6)

- `usuarios`: `correo` UNIQUE indexado, `contrasena_hash` bcrypt, `rol` (check), `debe_cambiar_contrasena`, `activo`, `ultimo_acceso`. Columnas necesarias para password lifecycle presentes. Aurora: no hay `contrasena_version`, `contrasena_cambiada_en`, `failed_login_attempts` en tabla (rate limit es en memoria, no en DB) — evaluar si se necesita persistencia para auditoría (ver S4).
- Refresh tokens en tabla `refresh_tokens` con `token_hash` SHA-256, `revocacion`, `expira_en`, `usado_en`. Rotación OK.
- Alemlbic baseline `create_all` + migraciones idempotentes (guards). **Estado DB actual** (verificado vía psql): 20 tablas presentes, `alembic_version = b7c8d9e0f1a2` (head). Sin `DuplicateTable`.

---

## 5. Auditoría de manejo de errores / código (FASE 10) — ejemplos concretos

- `gastos.py:324-329`: `except Exception: logger.exception(...)` re-lanza 503 — aceptable pero captura demasiado amplia (traga errores de programación como 500 legítimos).
- `ingresos.py:86-93`: al actualizar usa `setattr` sobre `model_dump` del cliente sin filtrar campos no permitidos (`creado_por`, `eliminado_en`) → **potencial mass-assignment** por `model_dump()` de `exclude_unset` pero sin whitelist. Verificar si el schema `IngresoUpdate` excluye campos sensibles.
- `viajes.tsx` (front): uso de `String(viaje.id)`/`as any` y accesos sin tipo — **refactor de tipado recomendado**, sin impacto funcional.
- `console.log`/`console.error` en producción: presencia en `useOfflineSync.ts:52`, `index.ts` variado; **no crítico** si es PWA local, pero se recomienda guard.
- No hay `TODO/FIXME` diseminados ni `SECRET_KEY` por defecto hardcodeado en `config.py` (usa `Settings` con env). Se detectó `.env` **NO ignorable (sin git)** → ver Docker.

---

## 6. Auditoría Docker / deploy (FASE 8)

- Stack: db (healthy), backend, frontend nginx. `depends_on: db service_healthy`. **OK**.
- Orden de boot backend: `alembic upgrade head && seed.py && seed_municipios.py && uvicorn` (`docker-compose.yml:36-40`).
- **Secretos expuestos (se recomienda vag);** NO se replica valor de claves en este informe. Se observó: `SECRET_KEY` y DATABASE credenciales como variables de entorno en `docker-compose.yml` para dev local (`celr-local-dev-secret`, `postgres:admin`) — **NO es secreto real** (valores de desaarrollo), pero deben moverse a secretos/`.env` si se lleva a Render/productivo.
- `backend/app/core/config.py`: `DATABASE_URL` obligatoria sin default (*settings* pydantic), buena. `SECRET_KEY` obligatoria.
- `.env`: existe `backend/.env` con `SECRET_KEY` de desarrollo. **NO hay `.env.example`** (se solicitó `include *.example` pero no existe) → falta plantilla documentada.
- nginx sirve SPA + proxy. Sin healthcheck propio de frontend (depende de Ports). `docker compose ps`: backend Up tras rebuild (resuelto el crash-loop de `DuplicateTable` con migración idempotente).

---

## 7. Pruebas (FASE 9)

- Backend: scripts `test_*.py` contra DB real (`viajes`, `gastos`, `auth`, `rbac`, `ocr`, `liquidaciones`, `endpoints`) — **cubren auth básica y RBAC** pero sin framework de pruebas (no pytest). Se ejecutan de forma manual.
- Frontend: **NO hay** tests unitarios/componentes/E2E (no vitest/playwright/cypress). PWA offline probada solo de forma manual vía `useOfflineSync`.
- No hay pruebas de: enumeración de usuarios, rotación de refresh, change-password invalida sesiones, rate limit. (No automatizadas).

---

## 8. Resumen de hallazgos prioritarios

Hallazgos marcados con riesgo y archivo/línea:

**S1** (MEDIA) — Cambio obligatorio de contraseña solo en frontend. `auth.py:27-56`, `deps.py:13-42`.
**S2** (MEDIA) — JWT stateless: cambio de contraseña no invalida access tokens vigentes; falta `password_version` en token. `security.py:27-31`, `deps.py`.
**S3** (ALTA) — **Recuperación de contraseña NO IMPLEMENTADA** (backend ni frontend). Bloques recuperación/olvido.
**S4** (MEDIA) — Rate limit in-memory y solo en login; sin límite en refresh/cambio-contraseña; sin persistencia multi-worker. `rate_limiter.py`.
**S5** (MEDIA) — Posible mass-assignment en `update` de ingresos/gastos por `model_dump` sin whitelist. `ingresos.py:86-108`, `gastos.py:205-248`.
**S6** (BAJA-MEDIA) — Posible acceso IDOR de lectura en `GET /viajes/{id}` (sin ownership check). `viajes.py`.
**S7** (BAJA) — Errores 503 excesivamente genéricos (`gastos.py:324`) y `console` en producción frontend.
**S8** (BAJA) — Secretos de desarrollo en `docker-compose.yml`/`.env` + sin `.env.example` + sin git. Recomendar secrets de Render.

---

## 9. Plan de implementación propuesto (por fases, a aprobar ANTES de tocar código)

1. **FASE A — Auth backend hardening:** exception Handler unificado, forzar change-password en `get_current_user`, `password_version` + validación de expiración de refresh, mensajes genéricos en me/cambio-contrasena.
2. **FASE B — Recuperación de contraseña:** endpoint `POST /auth/forgot` (token de un solo uso hasheado, expiración corta, respuesta genérica anti-enumeración) + `POST /auth/reset` + flujo de correo (plantilla). Frontend: página OlvidéContrasena + Reset.
3. **FASE C — Rate limiting extensible:** mover a Redis/Postgres, límites por IP en todos los endpoints sensibles (refresh, cambio, login) + backoff logarítmico por usuario/IP.
4. **FASE D — RBAC/IDOR:** ownership checks en viajes/gastos/ingresos por `conductor_id`/`creado_por`, whitelist de campos en update (Pydantic `Field` explícitos), tests de rol por endpoint.
5. **FASE E — Framework de pruebas:** pytest + httpx TestClient (auth, RBAC, rotación, rate limit, IDOR) y vitest+RTL en frontend.
6. **FASE F — Docker/prod:** mover secretos a `.env`/secretos Render, `.env.example`, healthchecks de frontend, escaneo de imágenes (trivy), multi-stage más fino, quitar `-slim` innecesario si procede.

---

*Fin del documento. No se modificó código. Pendiente: aprobación del usuario para implementar las fases.*
