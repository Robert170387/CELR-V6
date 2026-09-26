# Sistema ADR — Architecture Decision Records

## Propósito

Un ADR captura **por qué** algo se hizo así. El código dice *qué*; el ADR dice *qué se consideró
y se descartó*. Sin eso, un agente futuro "optimiza" algo deliberado y rompe una garantía.

## Cuándo escribir un ADR

**SÍ** cuando la decisión:

- afecta dominio, persistencia o seguridad;
- tiene alternativas plausibles que alguien va a proponer de nuevo;
- es difícil de inferir leyendo el código.

**NO** cuando:

- es una convención de estilo (va en `AGENTS.md`);
- es un refactor interno sin consequence externas;
- **la tomaste tú sin que el usuario la aprobara** — eso es **PROPOSAL**, no decisión.

## Regla de oro

> **Una propuesta de un agente NO es una decisión.**
> Un PROPOSAL se vuelve DECISION únicamente con aprobación explícita del usuario **y** un ADR.
> Sin ambas dos cosas, queda en `BACKLOG.md` marcado como PROPOSAL.

## Estados

| Estado | Significado |
|---|---|
| `PROPUESTA` | Escrita, no aprobada. **No la implementes.** |
| `ACEPTADA` | Vigente. Cambiarla exige un ADR nuevo que la reemplace. |
| `SUPERADA` | Reemplazada por otro ADR. Se marca con `Sustituida por: ADR-NNNN`. |
| `DESCARTADA` | Se consideró y se rechazó. **Se conserva**: evita re-litigar. |

## Plantilla

```markdown
# ADR-NNNN — Título en imperativo

**Estado:** PROPUESTA | ACEPTADA | SUPERADA | DESCARTADA
**Fecha:** YYYY-MM-DD
**Decide:** <usuario>            # NUNCA un agente
**Ámbito:** dominio | persistencia | seguridad | proceso | frontend

## Contexto
Qué restricciones y hechos existen. Con evidencia (archivo:línea, comando).

## Problema
Qué no se puede hacer con el estado actual.

## Opciones
1. Opción A — descripción
2. Opción B — descripción

## Decisión
Qué se eligió, y por qué.

## Consecuencias
- Positivas
- Negativas / costo aceptado
- Qué queda explícitamente fuera de alcance

## Alternativas descartadas
Por qué NO. Con el argumento que las eliminó.

## Restricciones de implementación
Lo que la decisión obliga en el código. Con a dónde mirar.

## Pruebas requeridas
Qué suite cubre la decisión. Si no hay suite, decirlo: es una brecha.
```

## Regla de numeración

Secuencial, **nunca se reutiliza**. Si cancelas un ADR, queda como `DESCARTADA` con su número.

## Registro

| ADR | Título | Estado |
|---|---|---|
| [ADR-0001](ADR-0001-rate-limit-por-usuario.md) | Rate limit de login keyeado por `usuario:{id}` | ACEPTADA |
| [ADR-0002](ADR-0002-identidad-canonica-cedula.md) | Cédula como identidad canónica, correo nullable, sin backfill | ACEPTADA |
| [ADR-0003](ADR-0003-recuperacion-sin-enumeracion.md) | Recuperación de contraseña que no revela existencia de cuentas | ACEPTADA |
| [ADR-0004](ADR-0004-listado-array-plano-x-total-count.md) | Listados: array plano + `X-Total-Count` | ACEPTADA |
| [ADR-0005](ADR-0005-proteccion-ultimo-admin-estructural.md) | Protección del último admin como garantía estructural | ACEPTADA |

## Decisiones anteriores al sistema ADR

No todas las decisiones del proyecto tienen ADR. Las previas están en:

- `INSTRUCCIONES_OPENCODE.md` §7 (decisiones registradas)
- `INSTRUCCIONES_OPENCODE.md` §8 (B1–B8, abiertas)
- `DECISIONES_MODULO_USUARIOS.md` (diseño de identidad)
- `ALINEACION_MODELO_NEGOCIO.md` §2 y §6.1

**Backfill pendiente** (PROPOSAL, no autorizado): convertir las decisiones de §7 en ADR.
Son 7 y no son urgentes: ninguna es de dominio, persistencia ni seguridad.
