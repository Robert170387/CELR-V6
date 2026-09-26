# ADR-0002 — Cédula como identidad canónica, correo nullable, sin backfill

**Estado:** ACEPTADA
**Fecha:** 2026-09-25
**Decide:** usuario
**Ámbito:** dominio, persistencia

## Contexto

El módulo de Usuarios arranca sin una definición de identidad. Las decisiones previas
(`DECISIONES_MODULO_USUARIOS.md`) resolvieron: **no hay personas jurídicas**, **no todos son
conductores**, **una persona = una cuenta**.

Lo que faltaba era el esquema de columnas y, sobre todo, **qué pasa con las 7 cuentas
existentes que no tienen cédula**.

**Evidencia:** migración `d4e5f6a7b8c9`; modelo en `app/models/flota.py:Usuario`;
`deployments` con `correo=NULL` y `cedula=NULL` conviven hoy.

## Problema

Tres molds de identidad eran posibles: correo, cédula, o un documento fiscal nuevo. Y había que
decidir qué se hace con los datos que no tienen el identificador elegido.

## Opciones

1. **Cédula canónica, `correo` nullable, sin backfill** (elegida).
2. Correo canónico, cédula nullable.
3. Agregar `identificador_fiscal` nuevo y backfillear.
4. Cédula NOT NULL y obligar a completarla en la primera entrada.

## Decisión

```sql
usuarios.cedula   VARCHAR(20) UNIQUE NULL   -- identidad canónica
usuarios.correo   nullable                  -- alias legacy, no identidad
usuarios.conductor_id  UNIQUE PARCIAL       -- un conductor ↔ una cuenta
```

**Sin personas jurídica ⇒ no hay `identificador_fiscal`.**
**Sin backfill:** las 7 cuentas existentes quedan con `cedula=NULL`, que es un estado
legítimo ("todavía no se le ha pedido la cédula"), no un dato roto.

**`correo` queda como alias legacy** para no romper el login por correo, que era el único
método antes de A2.

## Consecuencias

**Positivas**

- Identidad que no depende de tener correo (muchos conductores no lo tienen).
- `NULL` en `cedula` no es error: no hay que distinguir "no tiene" de "no cargado".
- El login acepta ambos, y el canónico es el que va a la base de datos.

**Negativas / costo aceptado**

- `usuarios.correo` es nullable ⇒ **los tests no pueden buscar temporales por correo**: un
  temporal sin correo tiene `correo IS NULL` y no se encuentra nunca. Deuda `cleanup-ID`.
- **Una cuenta sin cédula no puede usar la recuperación por buzón** si tampoco tiene correo, y
  la UI no puede avisárselo sin convertirse en oráculo de enumeración (ADR-0003). Es el hueco
  operativo documentado en `ALINEACION_MODELO_NEGOCIO.md` §6.
- `cedula VARCHAR(20)`: suficiente para cédula colombiana, pero no para otros documentos
  sin una decisión nueva.

**Fuera de alcance**

- Verificación de la cédula contra un registro externo.
- `NIT` para personas jurídicas (descartado en la decisión de diseño).

## Alternativas descartadas

| Opción | Por qué no |
|---|---|
| Correo canónico | Muchos conductores no tienen correo. La identidad quedaría atada a un canal opcional. |
| `identificador_fiscal` | El negocio confirmó que no hay personas jurídicas. Agregar una columna sin caso de uso es deuda. |
| `cedula NOT NULL` | Obliga a un backfill de datos que **no existen** en 7 cuentas, o a bloquear el login de esas cuentas. |

## Restricciones de implementación

- **`correo` nunca puede volver a ser NOT NULL** sin ADR.
- **`cedula UNIQUE` en NULL es válido en Postgres** (múltiples NULL). No agregar un índice
  parcial que lo rompa: la unicidad real es entre valores presentes.
- `conductor_id` tiene **UNIQUE parcial** (solo donde no es NULL). Un conductor sin cuenta no
  bloquea el UNIQUE.
- El login resuelve por `cedula` **o** `correo` con `OR` + `limit(2)`, no `scalar_one_or_none`:
  un mismo texto podría existir en ambas columnas.
- **No usar `pydantic.EmailStr`**: `email-validator` no está instalado y rompe la importación
  de `app.main`, tumbando el arranque completo. El validador propio está en
  `app/schemas/usuario.py`.

## Pruebas requeridas

- `test_usuarios_crud.py` (TUC-1..TUC-18) — CRUD, cédula duplicada → 409, coherencia cédula↔conductor.
- `test_auth.py` (TA-ID-1..TA-ID-10) — login por cédula y por correo.
- `test_fresh_db.py` — la cadena Alembic completa sobre BD desechable.
- `test_a1_guard_downgrade.py` — el `downgrade()` de `d4e5f6a7b8c9` **aborta** si hay usuarios
  con `correo=NULL`. Es la protección contra pérdida de datos al revertir.
