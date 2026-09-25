# Decisiones — Módulo de Usuarios

**Estado:** decisiones bloqueantes cerradas; A1 desbloqueada. Sin código en esta sub-fase.
**Fecha:** 2026-09-25.
**Contexto:** auditoría read-only completada en `adeb89c`; respuestas de negocio registradas en A0.1.
**Complementa:** `ALINEACION_MODELO_NEGOCIO.md`, `INSTRUCCIONES_OPENCODE.md §8`.

## Resumen

- 8 decisiones cerradas con voto (D1, D2, D3, D4, D5, D9, correo nullable, cardinalidad).
- 0 decisiones bloqueantes para A1.
- 3 decisiones diferidas para A3/A5 (D7, D8, auditoría).
- 1 tema separado (residuos `cli-*`/`cond-*`).
- A1 puede comenzar con migración nullable, sin backfill destructivo y con guards idempotentes.

## Decisiones cerradas (con voto)

| # | Decisión | Voto | Fundamento |
|---|---|---|---|
| D1 | Login por cédula/correo | Coexistencia: aceptar `identificador`, mantener `correo` como alias | Compatibilidad con clientes actuales + flexibilidad |
| D2 | Reset por email | Arquitectura email_mock local + proveedor real futuro, dividido en capas (token persistido → email → asistido admin → código offline) | No hay SMTP hoy; arquitectura correcta desde el inicio |
| D3 | Fuente canónica de cédula | Opción C simplificada: `usuarios.cedula UNIQUE NULL`, sin `identificador_fiscal` | No hay personas jurídicas; no todos los usuarios son conductores |
| D4 | Reset asistido por admin | Solo contraseña temporal (server-generated, mostrada una vez, `debe_cambiar_contrasena=True`) | El admin nunca conoce la contraseña final |
| D5 | Residuos `cli-*`/`cond-*` | No tocar en A1; resolver en fase separada | Cambio de dominio independiente |
| D9 | Invariantes de auditoría | Actores derivados del token (implementado en Track C, `adeb89c`) | Integridad de auditoría |
| Correo | `usuarios.correo` nullable | Sí | Coherente con login por cédula, reset sin email y reset asistido/offline |
| Cardinalidad | Usuario–Conductor | 1:1 opcional; `conductor_id UNIQUE NULL` | Una persona tiene una cuenta; el vínculo con Conductor es opcional |

## Decisiones cerradas para A1 (2026-09-25)

### D3 — Fuente canónica de la cédula → Opción C simplificada

**Respuestas del usuario:**

- ¿Personas jurídicas como cuentas de acceso? **No.**
- ¿Todos los usuarios son conductores? **No.**
- ¿Una persona puede tener varias cuentas? **No.**

**Diseño derivado:**

- `usuarios.cedula VARCHAR(20) UNIQUE NULL` — canónica, identifica a la persona.
- `usuarios.conductor_id INTEGER FK NULL UNIQUE` — vínculo 1:1 opcional.
- `usuarios.correo` pasa a **nullable**.
- **Sin** `identificador_fiscal` (no hay personas jurídicas).

**Regla de sincronización:** si `conductor_id IS NOT NULL` →
`usuarios.cedula` debe coincidir con `Conductor.cedula` (validación en
endpoints de creación/edición de usuario). Si `conductor_id IS NULL` (admin,
operador, contador) → la cédula vive solo en `usuarios`.

**Backfill de los 7 usuarios actuales:** `usuarios.cedula` nullable; los
existentes quedan en `NULL`. Los nuevos se crean con cédula obligatoria desde
la UI de gestión (A5).

### Correo nullable → sí

`usuarios.correo` pasa a nullable. Coherente con login por cédula, reset sin
email y reset asistido/offline.

### Cardinalidad Usuario–Conductor → 1:1 opcional

Un usuario puede estar vinculado a 0 o 1 conductor. `conductor_id` pasa a
UNIQUE (nullable) en la migración de A1.

## Decisiones diferidas

| # | Decisión | Fase |
|---|---|---|
| D7 | Permisos del operador para reset (¿resetear cualquier usuario, solo conductores, otros operadores, admins, sí mismo?) | A5 |
| D8 | Política del último admin (impedir deshabilitar/degradar al último activo) | A5 |
| Auditoría | Qué se loguea, IP detrás de Render (`X-Forwarded-For`), retención, quién consulta | A3 |

## Residuos `cli-*` / `cond-*`

**Estado:** 6 usuarios activos (IDs 13–16, 20–21). Sin `conductor_id`. Sin `cliente@celr.com`.
**Voto:** preservar en A1. Resolver en fase separada, sin inferir relaciones por sufijos.

## Plan A1–A5

| # | Alcance | Commit sugerido |
|---|---|---|
| A1 | Modelo de identidad + política de contraseñas + migración Alembic idempotente | `feat(auth): agrega cedula canonica y politica de contrasenas` |
| A2 | Login por identificador + corrección de `VITE_API_URL` en login | `feat(auth): login por identificador y compatibilidad de correo` |
| A3 | Reset (token persistido → email mock → asistido → offline) + auditoría base | `feat(auth): reset de contrasena con auditoria` |
| A4 | Enforcement real del primer login (backend + frontend) | `feat(auth): obliga cambio de contrasena en primer login` |
| A5 | Gestión de usuarios (CRUD + roles + desactivación + auditoría visible) | `feat(usuarios): gestion de usuarios con auditoria` |

**Nota A1:** la migración será nullable y sin backfill. `usuarios.cedula` tendrá
UNIQUE parcial (`WHERE cedula IS NOT NULL`) y `usuarios.conductor_id` será
UNIQUE nullable. La aplicación validará la correspondencia con
`Conductor.cedula` cuando exista vínculo.

## Riesgos mitigados / deuda de A1

- **Backfill de cédulas:** resuelto con columnas nullable; los usuarios actuales quedan en `NULL`.
- **Uniqueness:** UNIQUE parcial para cédulas no nulas y UNIQUE nullable para `conductor_id`.
- **Autenticación inconsistente:** D1 establece coexistencia cédula/correo.
- **Migración reversible:** cambios nullable, guards idempotentes y sin backfill de datos.
- **Tests:** queda como deuda de A1 revisar consumidores que asumen `correo` NOT NULL.

## Preguntas abiertas para el negocio/contador

1. ¿Cuánto tiempo se conservan los logs de login, reset y cambios sensibles?
2. ¿Quién puede consultar la auditoría: solo admin o también operador?
3. ¿Qué permisos exactos tendrá el operador para reset y cómo se protege al último administrador activo?
