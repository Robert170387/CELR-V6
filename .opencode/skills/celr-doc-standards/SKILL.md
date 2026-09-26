---
name: Docs Standards
description: Procedimiento para escribir o actualizar documentación en CELR v6: qué clasificar cada afirmación, dónde va cada tipo de documento y qué no se documenta. Usar al crear docs, responder preguntas de negocio o registrar una decisión.
---

# Escribir documentación que no miente

## La clasificación — en **cada** afirmación

| Etiqueta | Significado | Cómo se verifica |
|---|---|---|
| **FACT** | Verdad verificada | Cita `archivo:línea` o el comando |
| **DECISION** | La eligió el usuario | Vive en un ADR |
| **PROPOSAL** | Sugerencia no aprobada | **No la implementes** |
| **ASSUMPTION** | Creés que es cierto, sin verificar | Verificá o marcá |
| **UNKNOWN** | No se puede determinar | **Se escribe. No se inventa.** |

> **Una recomendación de un agente NO se convierte en decisión.** PROPOSAL → DECISION
> requiere aprobación del usuario **y** un ADR. Con una de las dos, no es decisión.

## Dónde va cada cosa

| Documento | Contenido | No va acá |
|---|---|---|
| `docs/00-context/CURRENT.md` | Dónde estamos. **Breve.** | Bitácora histórica |
| `docs/00-context/PROJECT.md` | Qué es el proyecto, stack, estructura | Reglas de gates |
| `docs/00-context/BUSINESS.md` | El negocio, en palabras del negocio | Esquema técnico |
| `docs/01-architecture/` | Cómo está construido | Qué significa cada entidad |
| `docs/02-domain/GLOSSARY.md` | Entidades, con evidencia | Reglas de proceso |
| `docs/04-decisions/` | Decisiones con alternativas descartadas | Estado actual |
| `docs/05-tasks/BACKLOG.md` | Lo que falta, por quién lo resuelve | Decisiones tomadas |
| `docs/06-quality/GATES.md` | Gates y normas | Estado de una tarea |
| `INSTRUCCIONES_OPENCODE.md` | Operación: gates, trampas, deudas | Arquitectura |
| `AGENTS.md` | Reglas que no se negocian | Cualquier otra cosa |

**No dupliques.** Si algo ya está en un documento, en el otro se enlaza.

## Cómo escribir un `UNKNOWN`

Mal:

> El conductor cobra por porcentaje del flete.

Bien:

> **UNKNOWN** — el conductor cobra por porcentaje del flete. `porcentaje_comision` existe en
> `conductores` y `viajes_odt`, y hay un `porcentaje_comision_default` individual, pero **la tasa
> y su base de cálculo no están documentadas en el repo**. Requiere al usuario.

La diferencia es que uno se puede integrar por error y el otro no.

## Documentos históricos

**No los borres.** Ponles un banner al principio:

```markdown
> ## ⛔ OBSOLETO — YYYY-MM-DD. No usar como estado vigente.
> Snapshot tomado antes de <qué>. Ver <documento actual>.
```

Eso ya se hizo con 4 documentos de la raíz, y es la razón por la que
`AUDITORIA_CELR_v6.md` no hizo que alguien reimplemente lo que ya existía.

## Al responder una pregunta de negocio

1. ¿Está en `docs/02-domain/GLOSSARY.md`? Respondé con la referencia.
2. ¿Está en un ADR? Respondé con la decisión y su porqué.
3. ¿Está en el código? Verificá y citá `archivo:línea`.
4. **¿No está en ninguno de los tres? → `UNKNOWN`. No completes por inferencia.**

## Anti-patrones

| Anti-patrón | Por qué falla |
|---|---|
| Documentar una aspiración como hecho | Un agente la implementa. |
| "Probablemente" / "debería" sin marcar | Se lee como verificado. |
| Bitácora en `CURRENT.md` | Se vuelve ilegible y nadie lo actualiza. |
| Duplicar entre documentos | Se desincronizan; se lee la versión vieja. |
| Documentar sin verificar | `AUDITORIA_CELR_v6.md`-existió97commits. |
| Borrar el histórico | Se pierde por qué se descartó algo. |

## Español

Todo en español, incluidos identificadores, comentarios y mensajes visibles. Es convención
dura del proyecto, no preferencia.
