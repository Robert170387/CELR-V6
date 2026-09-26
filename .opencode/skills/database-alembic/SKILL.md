---
name: Database Alembic
description: Procedimiento para cambiar el esquema PostgreSQL con Alembic de forma segura e idempotente. Usar al agregar o modificar columnas, constraints, índices, seeds o datos. Incluye el gate obligatorio.
---

# Migraciones Alembic seguras

## Por qué los guards existen

La baseline `a5b6b344c873` ejecuta `create_all` con los **modelos vigentes**. Una BD "vacía" y
una ya migrada arrancan en **estados distintos**. Sin guards, la misma migración puede fallar
en una y no en la otra — y el fallo aparece en el deploy, no en desarrollo.

## Procedimiento

1. **Verificar el estado real antes de proponer nada**
   ```powershell
   docker exec celr_v6_db psql -U postgres -d celr_v6_db -P pager=off -c "\dt"
   docker exec celr_v6_db psql -U postgres -d celr_v6_db -P pager=off -c "\d <tabla>"
   ```
   Nunca asumas el esquema. Cambió.

2. **Crear la revisión**
   ```powershell
   $env:DATABASE_URL="postgresql://postgres:admin@localhost:5433/celr_v6_db"
   venv\Scripts\python.exe -m alembic revision --autogenerate -m "desc"
   ```
   El autogenerate es un punto de partida, **no** el resultado final. Revisalo.

3. **Escribir guards de existencia** para cada `add_column`, check, FK, `alter_column`, drop y
   vista. Referencias: `_columna_existe`, `_constraint_existe`, `_fk_existe`,
   `_columna_es_nullable`, `_columna_es_generated`, `_vista_existe` (en la baseline y en
   `f2e1d0c9b8a7` / `a1b2c3d4e5f6`).

   ```python
   if not _columna_existe("usuarios", "cedula"):
       op.add_column(...)
   ```

4. **Vistas**: `alembic.op` no expone `drop_view`/`create_view`.
   ```python
   op.execute(text("DROP VIEW IF EXISTS ..."))
   op.execute(text("CREATE ... VIEW ..."))
   ```

5. **`downgrade()` con guard** si la revertir pierde datos. Precedente: `d4e5f6a7b8c9` aborta si
   hay `usuarios.correo IS NULL`. Sin ese abort, un `downgrade` destructivo es un accidente
   esperando.

6. **Destinos absolutos, nunca `-1`.**
   `downgrade <revision_objetivo>`, y validá contra el head leído en el momento. Ya rompió dos
   veces: `test_a1_guard_downgrade` bajó un paso de más y terminó verificando otra cosa.

7. **Gate obligatorio**
   ```powershell
   $env:PYTHONPATH="."; $env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
   venv\Scripts\python.exe scripts\test_fresh_db.py
   ```
   Crea y destruye **únicamente** `celr_v6_fresh_test`. Nunca toca `celr_v6_db`.

8. **Actualizar `test_fresh_db.HEAD_REVISION`.** Es una constante. Si no, la precondición
   aborta antes de empezar y oculta el resto.

9. **Si tocaste una migración con guard**, correr también `test_a1_guard_downgrade.py`.

## Prohibido

- `init_db.py`, `scripts/migrate_*.py`, `schema_celr_v6.sql` como mecanismo. Son históricos.
- `alembic upgrade` contra `celr_v6_db` sin pedido explícito.
- `DROP COLUMN` o `DELETE` sin ADR. El producto usa soft delete.
- Índice sobre `func.lower()` sin el índice funcional correspondiente (deuda A2.1).

## Seeds

- `seed_base.py` — siempre presente. DIVIPOLA + admin create-only. **Nunca** modifica cuentas
  existentes.
- `seed_demo.py` — **solo local**. Rechaza `ENVIRONMENT=production`.
- Orden de boot: `alembic upgrade head && seed.py && seed_municipios.py`.

> `municipios` es **obligatorio**: los endpoints de autocomplete devuelven `municipio_id` y
> gastos e ingresos lo usan. **Vacía ⇒ el alta de gastos y viajes se rompe.**

## Limpiar datos de test

`refresh_tokens.usuario_id` es FK a `usuarios.id` **sin CASCADE** (guardrail correcto). Por eso:

```sql
BEGIN;
DELETE FROM password_reset_token WHERE usuario_id = :id;
DELETE FROM refresh_tokens        WHERE usuario_id = :id;
DELETE FROM usuarios              WHERE id = :id;
COMMIT;
-- y DESPUÉS verificá. Un DELETE rechazado deja los contadores como falsos positivos.
```

Rastrear temporales por **`id`**, nunca por `correo`: con `correo` nullable, `correo IS NULL`
no se encuentra nunca y deja la `cedula` (UNIQUE parcial) plantada.

Detalle: `docs/01-architecture/DATABASE.md`.
