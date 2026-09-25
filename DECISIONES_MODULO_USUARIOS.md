# Decisiones — Módulo de Usuarios

**Estado:** borrador previo a implementación. Sin código.
**Fecha:** 2026-09-25.
**Contexto:** auditoría read-only completada en `adeb89c`.
**Complementa:** `ALINEACION_MODELO_NEGOCIO.md`, `INSTRUCCIONES_OPENCODE.md §8`.

## Resumen

- 5 decisiones cerradas con voto provisional (D1, D2, D4, D5, D9).
- 3 decisiones bloqueantes que requieren input del usuario/negocio (D3,
  correo nullable, cardinalidad Usuario–Conductor).
- 1 pregunta bloqueante que define D3: ¿existen personas jurídicas como
  cuentas de acceso?
- 3 decisiones diferidas para A3/A5 (D7, D8, auditoría).
- 1 tema separado (residuos `cli-*`/`cond-*`).

## Decisiones cerradas (con voto)

| # | Decisión | Voto | Fundamento |
|---|---|---|---|
| D1 | Login por cédula/correo | Coexistencia: aceptar `identificador`, mantener `correo` como alias | Compatibilidad con clientes actuales + flexibilidad |
| D2 | Reset por email | Arquitectura email_mock local + proveedor real futuro, dividido en capas (token persistido → email → asistido admin → código offline) | No hay SMTP hoy; arquitectura correcta desde el inicio |
| D4 | Reset asistido por admin | Solo contraseña temporal (server-generated, mostrada una vez, `debe_cambiar_contrasena=True`) | El admin nunca conoce la contraseña final |
| D5 | Residuos `cli-*`/`cond-*` | No tocar en A1; resolver en fase separada | Cambio de dominio independiente |
| D9 | Invariantes de auditoría | Actores derivados del token (implementado en Track C, `adeb89c`) | Integridad de auditoría |

## Decisiones bloqueantes para A1

### D3 — Fuente canónica de la cédula

**Opciones:**

- **A** — Derivar de `Conductor.cedula`. Cero duplicación, pero usuarios no-conductores no pueden loguear por cédula.
- **B** — Entidad `Persona` separada. Limpia a largo plazo; refactor grande (Conductor + Usuario + más).
- **C** — `usuarios.cedula UNIQUE` canónica + regla de sincronización con `Conductor.cedula`.

**Voto provisional:** C **condicionada** a la respuesta de la pregunta bloqueante. Si existen personas jurídicas, C necesita además decisión sobre `identificador_fiscal`.

**Pregunta bloqueante:** ¿Todas las cuentas de acceso representan personas naturales con cédula, o también existen cuentas de empresas/personas jurídicas?

### Correo nullable

**Voto:** sí, `usuarios.correo` pasa a nullable.
**Fundamento:** coherente con D1 (login por cédula) + D2 (reset sin email) + reset asistido/offline para cuentas sin correo.
**Riesgo:** rompe contratos que asumen correo obligatorio (scripts, tests, respuestas). Mitigación: revisar consumidores en A1.

### Cardinalidad Usuario–Conductor

**Opciones:**

- 1 usuario ↔ 1 conductor.
- 1 conductor ↔ 0..N usuarios.
- Una persona puede tener cuenta de operador + cuenta de conductor.

**Voto:** pendiente de input del usuario.

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

## Riesgos si se ejecuta A1 sin resolver D3 y correo nullable

- Backfill incorrecto de cédulas en usuarios existentes.
- Uniqueness mal definida → conflictos con `Conductor.cedula`.
- Autenticación inconsistente (algunos usuarios por correo, otros por cédula).
- Migración difícil de revertir si la decisión final difiere.
- Tests existentes pueden fallar por correo NOT NULL.

## Preguntas abiertas para el negocio/contador

1. **¿Existen cuentas de acceso para personas jurídicas (empresas/clientes)?** (bloqueante para D3)
2. ¿Todos los usuarios son conductores, o hay operadores/admin/contador/clientes sin cédula de conductor?
3. ¿Un conductor puede tener múltiples cuentas? ¿Una persona puede tener varias cuentas con roles distintos?
4. Si hay personas jurídicas: ¿se identifican con NIT (`identificador_fiscal`) o con la cédula del representante legal?
5. Retención de auditoría: ¿cuánto tiempo se conservan logs de login/reset/cambios sensibles?
6. ¿Quién puede consultar la auditoría? ¿Admin solo, o también operador?
