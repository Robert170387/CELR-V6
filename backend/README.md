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

## Ejecutar el servidor
```
set DATABASE_URL=postgresql://postgres:admin@localhost:5433/celr_v6_db
venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

## Pruebas de la suite backend
Cada script usa la BD real (`celr_v6_db`) y deja datos de prueba al final
(borrado en lote no implementado):
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

### Credenciales de prueba
- `test@celr.com` / `admin123` (admin)
- `cliente@celr.com` / `cliente123` (cliente)
- `admin2@celr.com` / `admin123` (admin — creado por el test de liquidaciones)

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