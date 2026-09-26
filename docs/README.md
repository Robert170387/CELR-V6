# docs/ — memoria persistente de CELR v6

Esta carpeta es la **fuente de verdad** para que cualquier agente o persona retome el
proyecto sin depender de una conversación anterior. El repositorio es la memoria;
si un dato solo existe en un chat, está perdido.

## Regla de oro

> **El repositorio es la fuente de verdad. La conversación no lo es.**
> Si un agente afirma algo que no está verificado contra el código o contra un documento
> de esta carpeta, es `UNKNOWN` hasta que se demuestre.

## Clasificación del conocimiento

Todo documento nuevo, y toda afirmación dentro de ellos, se etiqueta:

| Etiqueta | Significado |
|---|---|
| **FACT** | Verificado contra el código, la BD o un comando. Con referencia (`archivo:línea`). |
| **DECISION** | Elegido por el usuario y registrado en un ADR. No se cambia sin ADR nuevo. |
| **PROPOSAL** | Sugerencia de un agente o consultor. **No es una decisión.** |
| **ASSUMPTION** | Se cree cierto pero no verificado. Tratar como sospechosa. |
| **UNKNOWN** | No se pudo determinar. **Marcar, nunca inventar.** |

> **Una recomendación de un agente NO se convierte automáticamente en decisión.**
> Un PROPOSAL pasa a DECISION solo con aprobación del usuario + ADR.

## Mapa

| Carpeta | Contenido | Empieza por |
|---|---|---|
| `00-context/` | Qué es el proyecto, para quién, dónde estamos | [`CURRENT.md`](00-context/CURRENT.md) |
| `01-architecture/` | Cómo está construido el sistema | [`SYSTEM.md`](01-architecture/SYSTEM.md) |
| `02-domain/` | Las entidades y reglas del negocio | [`GLOSSARY.md`](02-domain/GLOSSARY.md) |
| `03-ux/` | Patrones de interfaz y verificación visual | [`UX-PATTERNS.md`](03-ux/UX-PATTERNS.md) |
| `04-decisions/` | ADRs: decisiones con contexto y consecuencias | [`README.md`](04-decisions/README.md) |
| `05-tasks/` | Qué falta, en orden | [`BACKLOG.md`](05-tasks/BACKLOG.md) |
| `06-quality/` | Gates, normas y otras reglas de calidad | [`GATES.md`](06-quality/GATES.md) |
| `07-consulting/` | Brief para el consultor externo | [`DEEPSEEK-BRIEF.md`](07-consulting/DEEPSEEK-BRIEF.md) |

## Orden de lectura para un agente nuevo

1. [`docs/00-context/CURRENT.md`](00-context/CURRENT.md) — dónde estamos y qué es el próximo paso
2. [`AGENTS.md`](../AGENTS.md) — las reglas que no se negocian
3. [`docs/00-context/PROJECT.md`](00-context/PROJECT.md) — qué es el proyecto
4. [`docs/02-domain/GLOSSARY.md`](02-domain/GLOSSARY.md) — qué significa cada cosa
5. La skill relevante (`.opencode/skills/`) cuando la tarea toque su territorio
6. [`INSTRUCCIONES_OPENCODE.md`](../INSTRUCCIONES_OPENCODE.md) §3–§4 para gates y trampas

## Documentos en la raíz (fuera de `docs/`)

Se conservan donde están porque tienen historia y referencias. **No son la entrada.**

| Documento | Estado |
|---|---|
| `AGENTS.md` | **VIGENTE.** Reglas operativas para agentes. |
| `INSTRUCCIONES_OPENCODE.md` | **VIGENTE.** Gates, trampas, deudas, estado. §3–§4 son operativos. |
| `ALINEACION_MODELO_NEGOCIO.md` | **VIGENTE.** Breviado de negocio y gaps. |
| `DECISIONES_MODULO_USUARIOS.md` | **VIGENTE.** Decisiones de diseño de identidad. |
| `AUDITORIA_CELR_v6.md` | ⛔ **HISTÓRICO.** Describe `b802d82`. Sus hallazgos S1–S4 ya se remediaron. |
| `CONTEXTO_PARA_CLAUDE.md` | ⛔ **OBSOLETO** (2026-09-22). |
| `CONTEXTO_CLAUDE_CELR_v6.md` | ⛔ **OBSOLETO** (2026-09-22). Duplica al anterior. |
| `CONTEXTO_DEEPSEEK_CELR_v6.md` | ⛔ **OBSOLETO** (2026-09-23). Reemplazado por `07-consulting/`. |
| `respuestas_agente/` | ⛔ **UNTRACKED, NO VERSIONAR.** Bitácora local: 17 respuestas, todas del 2026-09-23. Ver abajo. |
| `schema_celr_v6.sql` | **Referencia histórica.** Alembic es el mecanismo oficial. |
| `repomix-output.xml` | Generado, gitignorado. |

## `respuestas_agente/` — untracked a propósito

Directorio de trabajo local en la raíz del repo. **17 archivos markdown, todos del
2026-09-23.** Es bitácora de sesión: respuestas, no estado.

**No forma parte de la documentación durable.** La información curada vive en
`docs/`. Si la sesión local se limpia, se pierde y **no afecta al proyecto** — por
eso no se versiona: versionarlo crearía dos fuentes de verdad para la misma
información, y en un año divergirían sin que nadie sepa cuál manda.

**Regla para quien lea esto desde el repo:** un archivo de `respuestas_agente/` no
está en el clon, y no debería buscarse. Si un dato de ahí te resulta necesario,
llévalo a `docs/` curado y citándolo, o trátalo como `ASSUMPTION` hasta verificarlo.

> **Trampa conocida — mismo síntoma, distinto incidente.** El archivo
> `2026-09-23-subfase-3-bloqueada-imagen-stale.md` describe un **restart loop** con
> `Can't locate revision identified by 'f2e1d0c9b8a7'`, cuya causa real era una
> imagen construida antes de B2. El 2026-09-25 un rebuild distinto cayó en
> **restart loop** con `ModuleNotFoundError: No module named 'psycopg'`, por
> SQLAlchemy 2.1 sin pinear (corregido en `9a576f4`). Síntoma visible idéntico,
> causa opuesta. **No diagnostiques "imagen stale" por defecto: lee el traceback.**

## Convención de nombres

- ADR: `ADR-NNNN-slug-corto.md`, NNNN secuencial, nunca reutilizado.
- Un ADR = una decisión. Si tomaste dos, son dos ADR.
- Fechas en `YYYY-MM-DD`. Todo en **español**.
