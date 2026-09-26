---
name: Workflow Feature
description: Procedimiento de extremo a extremo para tomar una feature desde la petición hasta el cierre, con la revisión de arquitectura y el ADR en el lugar correcto. Usar al arrancar una feature no trivial o cuando no esté claro por dónde empezar.
---

# Ciclo de vida de una feature

```
Business Request
  → Specification        qué entra, qué NO entra
  → Architecture Review  ¿cambia dominio, persistencia o seguridad?
  → ADR                  si sí, y si tiene alternativas plausibles
  → Planning             sub-fases verificables
  → Implementation
  → QA                   los 4 gates
  → Security Review      si tocó auth
  → UX Review            si tocó UI — CAMINO DE ERROR PRIMERO
  → Regression           las suites completas, con datos reales presentes
  → CURRENT.md
  → Commit
```

## Cuándo se puede condensar

| Cambio | Flujo |
|---|---|
| Solo texto / estilos | Condensar: implementación + QA + commit. |
| UI sin cambio de contrato | Implementación + UX review + QA. |
| **Dominio, persistencia o seguridad** | **Flujo completo. Sin excepción.** |

## Cuándo hace falta ADR

**Sí** si la decisión afecta dominio/persistencia/seguridad **y** tiene alternativas
plausibles que alguien va a volver a proponer.

Ejemplos reales quevigilan: el shape de un listado (ADR-0004), la clave del rate limit
(ADR-0001), la forma del mensaje de recuperación (ADR-0003).

**No** si: es una convención de estilo, un refactor sin consecuencia externa, o **es una idea
tuya sin aprobación** — eso es `PROPOSAL` y va a `docs/05-tasks/BACKLOG.md`.

## Regla que más se ha salted

> **El camino de error se verifica antes que el camino feliz.**

En la UI de gestión de usuarios pasaron 4 bugs invisibles a toda prueba de endpoint. Y un quinto,
en el interceptor de 401, invisible incluso a las pruebas de UI del camino feliz.

## Procedimiento

1. **Leer `docs/00-context/CURRENT.md`.** Dónde estamos y qué está autorizado.
2. **Verificar el estado real** antes de creer a la documentación. `AUDITORIA_CELR_v6.md` dice
   que no hay recuperación de contraseña. **Sí hay.** Lleva 97 commits desfasada.
3. **Clasificar el riesgo.** Dominio / persistencia / seguridad / solo UI.
4. **Delegar** al agente adecuado. El orquestador decide, no implementa.
5. **Por sub-fase:** un commit, un gate, un criterio de terminado.
6. **Gates completos** antes de cerrar, con los datos reales presentes.
7. **Documentación en el mismo commit.** ADR, `CURRENT.md` o `GLOSSARY.md` según corresponda.
8. **`SESSION-HANDOFF.md`** con qué se hizo, qué **no**, y las trampas de la sesión.

## El filtro de definición de terminado

- [ ] Los 4 gates verdes: 21 suites + humo + E2E + `npm.cmd run build`.
- [ ] `git diff --check` limpio y **diff leído**.
- [ ] UI verificada **por render**, camino de error primero.
- [ ] Migraciones: `test_fresh_db.py` + `HEAD_REVISION` al día.
- [ ] Documentación actualizada en el mismo commit.
- [ ] `SESSION-HANDOFF.md` actualizado.
- [ ] Ningún `UNKNOWN` introducido sin marcar.
- [ ] Backup `0 0`.

## Anti-patrones que ya pasaron

| Anti-patrón | Qué pasó |
|---|---|
| Maquetar el gate | Suite verde porque se relajó el assert. Peor que rojo. |
| Confiar en la doc vieja | Se "implementó" algo que ya existía. |
| Verificar solo el camino feliz | 4 bugs vivos, todos en el camino de error. |
| Limpiar la BD para cuadrar | Rompió `auditoria_evento`, que es append-only. |
| Asumir el baseline | Se borró una cuenta real del usuario. |
| Un commit con varios temas | Difícil de revisar y de revertir. |
