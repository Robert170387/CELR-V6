---
name: Backend FastAPI
description: Procedimiento para agregar o modificar endpoints, servicios, schemas y modelos en el backend FastAPI de CELR v6. Usar para cambios de backend que no sean migración ni decisión de seguridad.
---

# Agregar o modificar un endpoint

## Dónde va cada cosa

| Capa | Ubicación | Regla |
|---|---|---|
| HTTP | `app/api/v1/endpoints/` | Traduce HTTP ↔ dominio. **Sin lógica de negocio.** |
| Dominio | `app/services/` | Aquí vive la lógica. Hay 14 servicios. |
| Contrato | `app/schemas/` | Pydantic, en español |
| Persistencia | `app/models/` | Un tema por archivo: `flota`, `operaciones`, `financiero`, `mantenimiento`, `ubicacion`, `auditoria` |
| Transversal | `app/core/` | config, roles, seguridad, rate limiter |

**Si agregás lógica al endpoint, es el error más común.** Ya pasó: los endpoints de usuarios
necesitaron 3 servicios compartidos (`ROLES_OBJETIVO_POR_EJECUTOR` consumido por 4 operaciones).

## Procedimiento

1. **¿Existe ya?** Antes de escribir, buscá. La documentación vieja miente sobre ausencias.
2. **¿Toca auth, permisos o credenciales?** → skill `security-auth`. No lo hagas solo.
3. **¿Toca el esquema?** → skill `database-alembic`. No lo mezcles.
4. Definir el schema primero (contrato), después el endpoint, después el test.
5. **Un endpoint = una operación.** Si hacés dos cosas, son dos.
6. **Errores**: `HTTPException` con mensaje en español que la UI pueda mostrar.
   `422` validación · `409` conflicto de estado · `403` permiso · `404` no encontrado.
   **No inventes códigos.**
7. **Dinero es `Decimal`/`NUMERIC`, nunca `float`.**
8. **Todo campo y función nueva tiene consumidor**, o `reservado para fase X` en el código.

## Trampas del repo

- **`EmailStr` de pydantic rompe el arranque.** `email-validator` no está instalado, y
  `app.main` deja de importar ⇒ **tumba la API entera**. Usá el validador propio de
  `app/schemas/usuario.py` (`correo_valido`).
- **Listados: array plano + `X-Total-Count`** (ADR-0004). No `{data, total}`.
- **El total debe ser el del filtro aplicado**, no el de la tabla: con filtros, `skip`
  desalinea la paginación.
- **`extra="forbid"`** en schemas de alta/edición: rechaza campos desconocidos con 422 en vez
  de ignorarlos en silencio. Un 200 con el campo descartado hace creer al usuario que se guardó.
- **`response_model` siempre.** Sin él, un campo interno puede filtrarse.
- **No uses `scalar_one_or_none`** para algo que puede no ser único. Login resuelve cédula **o**
  correo: mismo texto en ambas columnas ⇒ `MultipleResultsFound`. Usá `OR` + `limit(2)`.
- **`municipios` es obligatorio**: los endpoints de autocomplete devuelven `municipio_id` y
  gastos/ingresos lo usan. Vacía ⇒ el alta se rompe.
- **`flete_neto` y los derivados se calculan en el servidor.** Nunca en el cliente.

## Secuencias

Los números de documento (`numero_odt`) salen de un **UPSERT atómico** sobre
`secuencias_documento` (`app/services/secuencias.py`). Deben correr **en la misma transacción**
que el commit del endpoint, o se pierde la secuencia.

## Verificación

```powershell
$env:PYTHONPATH="."; $env:DATABASE_URL="postgresql://postgres:admin@localhost:5433/celr_v6_db"
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
venv\Scripts\python.exe scripts\test_endpoints.py    # default: TODOS LOS TESTS PASARON
venv\Scripts\python.exe scripts\test_rbac.py
venv\Scripts\python.exe scripts\smoke.py
```

**Endpoint nuevo o modificado ⇒ `test_endpoints.py` y `/openapi.json` vivo.** Hoy son
**45 paths / 65 operaciones**. Si tu cambio altera ese número, es intencional y va en el reporte.

Contra el servidor: `$env:CELR_BASE_URL="http://localhost:8001"`.

Detalle: `docs/01-architecture/SYSTEM.md`.
