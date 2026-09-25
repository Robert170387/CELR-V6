# CELR v6 — Backend (FastAPI)

## Requisitos
- Python 3.11+
- PostgreSQL (local: `celr_v6_db` en `localhost:5433`)

## Instalación
```
python -m venv venv
venv\Scripts\activate        # Windows
venv/bin/activate            # Linux/macOS
pip install -r requirements.txt
```

## Migraciones (Alembic) — mecanismo oficial
A partir de CELR v6 el esquema se gestiona con **Alembic**. La migración
`a5b6b344c873` (`baseline v6`) crea todo el esquema desde los modelos
(`app/models/`) mediante `Base.metadata.create_all`:

- **Base vacía** (deploy nuevo): `python -m alembic upgrade head` construye todas
  las tablas.
- **Base existente** (migrada antes con `scripts/migrate_*.py`): es un no-op y
  queda marcada en `head`.

Comandos útiles:
```
set DATABASE_URL=postgresql://postgres:admin@localhost:5433/celr_v6_db
python -m alembic upgrade head     # aplicar migraciones
python -m alembic current          # revisión actual
python -m alembic revision -m "desc"        # nueva migración
python -m alembic revision --autogenerate -m "desc"  # desde modelos (comparando con DB)
```

### Baseline dinámico y guards idempotentes

La migración baseline `a5b6b344c873` ejecuta `Base.metadata.create_all()` sobre los
modelos actuales. En una BD vacía construye todo el schema vigente; por eso las
migraciones posteriores deben ser idempotentes. Cada `add_column`, check, FK,
`alter_column`, drop y creación de vista debe consultar el estado real antes de
ejecutarse. Usar como referencia los guards de `f2e1d0c9b8a7` y
`a1b2c3d4e5f6` (`_columna_existe`, `_constraint_existe`, `_fk_existe`,
`_columna_es_nullable`, `_columna_es_generated`, `_vista_existe`).

`alembic.op` no expone `op.drop_view` ni `op.create_view`. Para vistas usar
`op.execute(text("DROP VIEW IF EXISTS ..."))` o
`op.execute(text("CREATE ... VIEW ..."))`.

Antes de commitear una migración, ejecutar desde `backend/`:

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql://postgres:admin@localhost:5433/celr_v6_db"
venv\Scripts\python.exe scripts\test_fresh_db.py
```

El test crea y destruye únicamente `celr_v6_fresh_test`; nunca modifica
`celr_v6_db`. Requiere PostgreSQL vivo en `:5433` y valida `upgrade head`,
`downgrade base` y el segundo `upgrade head` (TM1–TM9).

> ⚠️ **DEPRECADO**: `init_db.py` y `scripts/migrate_roles.py`,
> `scripts/migrate_gastos_valor.py`, `scripts/migrate_gastos_viaje_nullable.py`,
> `scripts/migrate_v6_hardening.py` quedan solo como referencia histórica.
> No usar en bases nuevas: `docker-compose.yml` y los deploys ejecutan
> `alembic upgrade head`. El archivo `schema_celr_v6.sql` es documentación del
> esquema, no un mecanismo de migración.

## Seed

La ejecución está particionada:

- `python seed_base.py` sincroniza el catálogo DIVIPOLA y puede crear un admin inicial
  create-only mediante `CELR_BOOTSTRAP_ADMIN_EMAIL` y `CELR_BOOTSTRAP_ADMIN_PASSWORD`.
  Nunca modifica cuentas existentes.
- `python seed.py` es un wrapper seguro: ejecuta siempre `seed_base.py` y ejecuta
  `seed_demo.py` solo con opt-in local:
  ```powershell
  $env:CELR_ALLOW_DEMO_SEED="1"
  python seed.py
  ```
- `seed_demo.py` es únicamente local. Rechaza `ENVIRONMENT=production` y exige
  `CELR_ALLOW_DEMO_SEED=1`; no tiene `--reset` en esta fase.
- En producción se debe ejecutar directamente `python seed_base.py`; nunca habilitar la demo.

### Docker

`docker compose up -d --force-recreate backend` no reconstruye la imagen. Después de cambiar
migraciones, seeds o `Dockerfile`, ejecutar primero:

```powershell
docker compose build backend
docker compose up -d --force-recreate backend
```

## Importación Flypass

El endpoint `POST /api/v1/flypass/import` recibe un archivo multipart `file` en formato
`.xlsx` (máximo 5 MB) y está protegido con los roles financieros de la API. La primera hoja
debe contener los encabezados `TRANSACCION`, `PLACA`, `FECHA_MVTO`, `MONTO` y
`PUNTO ATENCION`.

El importador conserva la fila completa en `flypass_transacciones.raw_data`, evita duplicados
por `TRANSACCION`, resuelve la placa, y hace matching de gastos `peajes` por vehículo, valor
y fecha ±1 día. Si no hay match, crea el gasto con `estado_pago=pendiente_por_pagar`,
`metodo_pago=tag` y proveedor `Flypass`; al setear `gasto_id` la transacción queda legalizada.
La asociación a una ODT es best-effort por vehículo y rango de fechas. La respuesta incluye
el reporte de insertados, duplicados, sin placa, ambiguos, gastos creados/matcheados, sin ODT
y errores.

## Listado Flypass

El endpoint `GET /api/v1/flypass` devuelve `{data, total}` con paginación offset-based:
`skip` (default `0`) y `limit` (default `50`, máximo `200`; un límite mayor responde `422`).
Los filtros disponibles son `fecha_desde`, `fecha_hasta`, `placa`, `sin_odt` y `sin_gasto`.
El filtro de placa resuelve `vehiculos.placa` mediante `LEFT JOIN`; la respuesta no expone
`raw_data`. Cada fila incluye `placa`, `viaje_id`, `gasto_id` y `legalizado_en_gastos`.

## Ejecutar el servidor
```
set DATABASE_URL=postgresql://postgres:admin@localhost:5433/celr_v6_db
venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

## Pruebas de la suite backend

Las suites backend usan la BD real (`celr_v6_db`) y tienen limpieza propia al
final. `test_fresh_db.py` y `test_a1_guard_downgrade.py` son la excepción: cada
una crea y destruye su propia BD desechable, sin tocar `celr_v6_db`.
```
set PYTHONPATH=.
set DATABASE_URL=postgresql://postgres:admin@localhost:5433/celr_v6_db
venv\Scripts\python.exe scripts/test_auth.py
venv\Scripts\python.exe scripts/test_rbac.py
venv\Scripts\python.exe scripts/test_liquidaciones.py
venv\Scripts\python.exe scripts/test_gasto_sin_odt.py
venv\Scripts\python.exe scripts/test_put_delete.py
venv\Scripts\python.exe scripts/test_ocr.py
```

Son **21 suites** (`test_*.py`). La lista completa, con qué cubre cada una y qué
gate exige cada una, está en `INSTRUCCIONES_OPENCODE.md` §3 — ese es el documento
que hay que leer, no este resumen.

> **Ningún test puede afirmar conteos globales de la app DB** (`usuarios=7`,
> `gastos=37`, `ConductorModel.id == 2`). La BD de desarrollo acumula datos reales
> y otras suites borran lo que crean, así que un assert absoluto pasa en una BD
> limpia y falla con el uso diario. Los tests miden delta, filtran por sus propias
> filas, o construyen un escenario controlado y lo restauran. Ocurrió en
> `test_reset_asistido` (TRA-13), `test_ultimo_admin` (TUA-2) y `test_usuarios_crud`
> (TUC-9); ver la norma en `INSTRUCCIONES_OPENCODE.md` §4.

> **`scripts/verify_seed.py` NO es una suite y no está en el gate.** Verifica que un
> seed se aplicó completo (espera 24 viajes, 37 gastos, 6 proveedores), así que
> **solo es válido en una BD recién sembrada**. Contra la BD de desarrollo falla a
> propósito. No convertirlo a delta: su valor es detectar un seed a medias.

### Credenciales de prueba — SOLO desarrollo local

Estas cuentas las crea `seed_demo.py`, que **rechaza `ENVIRONMENT=production`** y
exige `CELR_ALLOW_DEMO_SEED=1`. En Render nunca existen. No usarlas ni
documentarlas como credenciales de despliegue.

- `test@celr.com` / `admin123` (admin de la demo)
- `admin2@celr.com` / `admin123` (lo crea `test_liquidaciones.py`)

**No existe `cliente@celr.com`**: `seed_demo.py` no lo crea y su creación sigue
pendiente de la decisión de negocio B1. Cualquier doc que lo liste como
credencial válida está equivocada.

## Módulo de Usuarios (cerrado 2026-09-25)

Identidad, recuperación de credenciales, enforcement, auditoría, CRUD y UI.
Diseño y decisiones en `DECISIONES_MODULO_USUARIOS.md`; rastro de commits en
`INSTRUCCIONES_OPENCODE.md` §5.

**Modelo.** Una persona = una cuenta. `usuarios.cedula VARCHAR(20) UNIQUE NULL` es
la identidad canónica, `conductor_id` lleva UNIQUE parcial, y `correo` es nullable
(A1 no hace backfill: hay cuentas sin cédula). Sin personas jurídicas.

**Login.** `POST /auth/login` acepta `identificador` = cédula **o** correo
(A2). `correo` se conserva como alias legacy en el schema.

**Tres vías de recuperación, todas públicas** (A3.1 / A3.2 / A3.3):

| Vía | Quién la dispara | Prueba de identidad |
|---|---|---|
| Enlace por email — `POST /auth/forgot-password` | el usuario | el buzón (exige `correo`) |
| Temporal assistida — `POST /usuarios/{id}/reset-password` | un admin | la matriz de roles `ROLES_OBJETIVO_POR_EJECUTOR` |
| Código offline — `POST /usuarios/{id}/reset-codigo` + `POST /auth/reset-codigo` | un admin | un código de 6 dígitos con TTL e `intentos_max` |

`forgot-password` responde **200 con el mismo texto exista o no la cuenta**: un
404 o un mensaje distinto sería un oráculo de enumeración. En desarrollo el email
sale por `LogEmailBackend` con `logger.info` (por eso `main.py` configura
`basicConfig`); en producción ese backend lanza 503 y el log no se emite.

**Enforcement (A4).** Toda cuenta bornada con `debe_cambiar_contrasena=True`
—incluidas las creadas desde la pantalla de gestión— queda bloqueada en todos los
endpoints de negocio hasta que cambie la contraseña.

**Auditoría (A3.4).** `auditoria_evento` registra eventos sensibles con actor,
objetivo, IP y user-agent, y **nunca** la credencial. La tabla es append-only por
convención y **no entra en el baseline del gate**: es un log, no un estado.

**UI.** `/gestion-usuarios` (CRUD con filtros y paginación, reset, código,
activar/desactivar, degradar) y las tres pantallas públicas de recuperación.
Las cuentas con `correo` pueden usar el enlace; las que no, el código offline o el
reset asistido — la UI no puede decírselo, porque hacerlo confirmaría si la cuenta
existe.

## Autenticación: almacenamiento de tokens (trade-off)
- `access_token` y `refresh_token` viven en **localStorage** (claves `celr_token`,
  `celr_refresh`), lo que permite uso offline y sincronización de cola sin
  cookies. Riesgo: accesibles a XSS; mitigado sin transpilación de terceros
  (Vite/React puro) y con CSP.
- Alternativa más segura: cookie `HttpOnly; Secure; SameSite=Lax` para el
  `refresh_token` (+ cookie de `access_token` o header). No aplicado porque
  rompe el flujo offline/refresh del PWA sin red y complica el CORS del stack.
- El `refresh_token` se emite con **rotación** (no reutilizable) y `jti`; el
  `access_token` es corto (configurable) y el cliente reintenta 401 con un solo
  refresh en vuelo.

## OCR
Motor local Tesseract (`OCR_ENGINE=tesseract`, binario `TESSERACT_CMD`).
Opción cloud: `OCR_ENGINE=google` + `google-cloud-vision` (comentar desactivado
en `requirements.txt`).