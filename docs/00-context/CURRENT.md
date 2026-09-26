# CURRENT.md — memoria operacional

> **Este es el primer archivo que debe leer cualquier agente.** Responde: ¿dónde estamos?
> Se actualiza al **cerrar cada sub-fase**, no durante. Si está más viejo que el último
> commit, desconfía de él y verificalo contra `git log`.
>
> **Última actualización:** 2026-09-26 · **HEAD al momento de escribir:** `3018c20`
> (la anotación anterior decía `315a788`; después salieron B1, R1 y la tanda de
> dependencias)

## Estado del working tree

**Limpio**, salvo trabajo del usuario que deliberadamente no se versiona:

| Qué | Estado | Por qué |
|---|---|---|
| `CONTEXTO_CLAUDE_CELR_v6.md`, `CONTEXTO_PARA_CLAUDE.md` | untracked | **Del usuario.** No van al repo: su banner no protege a nadie porque no están versionados. |
| `respuestas_agente/` | untracked | Bitácora de sesión del 2026-09-23. No es estado; la versión curada vive en `docs/`. Ver la nota en [`docs/README.md`](../README.md). |
| `.opencode/`, `SESSION-HANDOFF.md` | untracked | Infraestructura de agentes. **`AGENTS.md` los referencia y aún no están versionados** — pendiente de decisión. |

## Lo cerrado en la última tanda

| Commit | Qué |
|---|---|
| `9a576f4` | `fix(deps)` — SQLAlchemy pineado a `<2.1` (el rebuild tomó 2.1.1, que cambió el driver por defecto a psycopg3) y `httpx2` → `httpx` |
| `5a488da` | `feat(db)` — índice en `flypass_transacciones(viaje_id)` |
| `0768d6c` | `fix(liquidaciones)` — el GET y el POST de bloqueos dejaron de contradecirse; afectaba 2 de 2 viajes |
| `6c3bf38` | `docs` — B1: radar consolidado + normas 5–7 |
| `3012d81` / `6529819` | `feat(viajes)` / `feat(frontend)` — resumen de viaje end-to-end |
| `6e98b03` … `3018c20` | TR-11 de 2/6 a 6/6, norma 8, mensaje de `verify_seed`, fuga de tokens y su docstring |

**Al retomar: leer [`BACKLOG.md`](../05-tasks/BACKLOG.md) y
[`DECISIONS-PENDING.md`](../07-consulting/DECISIONS-PENDING.md).** El radar ya no
vive en conversaciones.

### Preguntas abiertas al negocio

**Ya no bloquean nada.** El glosario las dejó como `UNKNOWN`, que es un estado
válido y no una deuda: se resuelven cuando exista el caso real que las dispara.

- **#2** — ¿cómo se llama un gasto sin viaje?
- **#5** — ¿"compensado" es palabra del negocio? Si es así, ¿el módulo se llama
  "compensado" o "liquidación"? Las dos no pueden ser canónicas a la vez.
- **#6 / B1** — ¿el rol `cliente` existe? Depende de si hay un valor de
  `proveedores.tipo` que lo represente; hoy ninguno lo tiene.
- **B9 / D8** — ¿un gasto puede marcarse `legalizado` sin ser un cruce con peaje?
  Ver la sección siguiente: la respuesta **NO** no significa eliminar.

### Pregunta abierta (B9 / D8) — **UNKNOWN, no bloquea nada**

> ¿El negocio necesita marcar un gasto como `legalizado` por una vía que **no** sea el cruce
> con un peaje?
>
> **No** → migración de 3 partes que **reconcilia** las dos definiciones (CHECK único,
> validador coherente, columna GENERATED expuesta en `GastoResponse`).
> **Sí** → `gastos.legalizado` deja de derivarse de `estado_pago` y pasa a campo propio.
>
> ⚠️ **Corrección 2026-09-26 — este texto decía antes "eliminar `'legalizado'` de
> `gastos.estado_pago`". Eso era una lectura equivocada de la decisión, y era
> destructiva: `gastos.legalizado` es `GENERATED AS (estado_pago = 'legalizado')`
> (`operaciones.py:135`), así que **quitar el valor del CHECK hace caer la columna
> entera.** Reconciliar no es eliminar.
>
> **Evidencia medida (2026-09-26):** la única asignación de `estado_pago` en
> `backend/app` es `flypass_import.py:449` → `'pendiente_por_pagar'`. **Ningún flujo
> automático pone `'legalizado'`.** Pero `GastoCreate` **lo acepta sin mirar la
> `categoria`** (`schemas/gasto.py:53`), así que un gasto de mantenimiento con
> `estado_pago="legalizado"` es alcanzable por API — y el nombre miente, porque no
> implica que su peaje esté legalizado (`flypass_transacciones.legalizado_en_gastos`
> depende de `gasto_id`, no de `estado_pago`).

---

## Dónde estamos

**FACT.** El Módulo de Usuarios (identidad, autenticación, recuperación de credenciales,
enforcement, auditoría, CRUD y UI) está **cerrado end-to-end** (A1–A5.4 más dos
micro-fixes). No hay sub-fase en curso.

**FACT.** El proyecto tiene historia previa a ese módulo: FASE A2, FASE 2, alineación ODT,
FASE Gastos, FASE Liquidaciones, B2 (cierre mensual), Flypass, Alembic fresh-DB y
partición de seeds. Todo eso está cerrado y documentado en `INSTRUCCIONES_OPENCODE.md` §5.

## Qué estaba haciendo el equipo

**FACT.** Lo último fue cerrar el Módulo de Usuarios y consolidar la documentación:
normas explícitas (`INSTRUCCIONES_OPENCODE.md` §4), deudas inventariadas, conteo de
suites corregido a 21 y verificado contra el disco.

## Qué terminó

| Frente | Estado |
|---|---|
| Módulo de Usuarios A1–A5.4 | ✅ Cerrado. Rastro de commits en `INSTRUCCIONES_OPENCODE.md` §5. |
| Documentación del módulo | ✅ `INSTRUCCIONES_OPENCODE.md` §4–§5, `ALINEACION_MODELO_NEGOCIO.md` §6/§8. |
| Infraestructura de agentes | ✅ (esta fase) `.opencode/agents/`, `.opencode/skills/`, `docs/`. |

## Qué falta

Nada bloqueante. Todo lo abierto está en [`BACKLOG.md`](../05-tasks/BACKLOG.md), clasificado entre
decisiones de negocio (esperan al usuario) y deuda técnica (no requiere decisión).

## Qué está bloqueado

Nada.

> **ASSUMPTION a verificar en la próxima sesión:** el usuario puede haber seguido probando
> la app a mano. La última verificación de baseline Give `usuarios=8` (7 del seed + 1
> cuenta real creada manualmente). **Releé la BD antes de asumir cualquier conteo.**

## Próximo paso autorizado

**No hay un próximo paso técnico definido.** Los puntos de entrada, todos esperando
decisión del usuario:

1. **Decisiones de negocio** (B1, B3–B8, bloques A–F) — son del usuario, no del agente.
2. **Deuda técnica** (`docs/05-tasks/BACKLOG.md`) — el agente puede tomar la que no
   requiera decisión, empezando por `IP-real-detras-de-proxy`, que es una línea en el
   `Dockerfile` con efecto de seguridad.
3. **Micro-fix de `verify_seed.py`** — 3 líneas para que falle con un mensaje claro
   en vez de 10 baselines.

**No se autoriza** arrancar funcionalidad nueva sin una decisión de negocio registrada.

## Estado de Git

**FACT al momento de esta escritura:**

- Rama de trabajo: `main`
- Backup: `origin/fase-a2-fase-2-local` — verificar con
  `git rev-list --left-right --count origin/fase-a2-fase-2-local...main` → esperado `0 0`
- Merge a `origin/main`: **pendiente** (requiere PAT del usuario)
- Deploy en Render: **pendiente** (requiere acción del usuario)

```powershell
git log --oneline -5                    # qué hay
git status --short                      # qué está sin commitear
git rev-list --left-right --count origin/fase-a2-fase-2-local...main   # esperado 0 0
```

**Regla del proyecto:** un commit por sub-fase, mensaje en español preparado con la
herramienta de escritura (**nunca** `git commit -F` con redirección de PowerShell: corrompe
acentos y mete BOM). Detalle en la skill `release-git`.

## Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| **Documentación obsoleta da confianza falsa** | Los documentos vencidos llevan banner ⛔. `AUDITORIA_CELR_v6.md` describe `b802d82` (97 commits atrás) y sus hallazgos S1–S4 **ya están remediados**. |
| **El service worker del PWA sirve el bundle viejo** | Antes de concluir que un cambio de frontend no surtió efecto: **Ctrl+Shift+R** o desregistrar el SW. Ya mordió dos veces. |
| **El rate limiter es in-memory** | `app/core/rate_limiter.py` es un `deque` en RAM. Con más de un worker cada uno tiene su cubeta. Deuda **B4**. |
| **`request.client.host` es la IP del proxy en Render** | `Dockerfile:40` corre uvicorn sin `--proxy-headers`. Afecta el rate limit por IP y la columna `ip` de auditoría. **No saques conclusiones de esa columna.** |
| **Cuentas sin correo no tienen recuperación propia** | No es un bug: es la consecuencia de no revelar existencia de cuentas. Su salida es el código offline o el reset asistido. Documentado en `ALINEACION_MODELO_NEGOCIO.md` §6. |
| **`auditoria_evento` crece sin parar** | Es un log, no un estado. **Nunca la limpies para cuadrar un gate.** |

## Documentación que hay que leer antes de continuar

| Si tu tarea es… | Lee |
|---|---|
| Cualquier cosa | Este archivo, luego [`../AGENTS.md`](../../AGENTS.md) |
| Entender el negocio | [`PROJECT.md`](PROJECT.md), [`BUSINESS.md`](BUSINESS.md), [`../02-domain/GLOSSARY.md`](../02-domain/GLOSSARY.md) |
| Tocar backend | [`../01-architecture/SYSTEM.md`](../01-architecture/SYSTEM.md), skill `backend-fastapi` |
| Tocar la BD / migraciones | [`../01-architecture/DATABASE.md`](../01-architecture/DATABASE.md), skill `database-alembic` |
| Tocar frontend | skill `frontend-react`, y `pwa-offline` si es la cola offline |
| Cambiar auth o permisos | skill `security-auth` |
| Cambiar pantallas | skill `ux-patterns` — **error primero** |
| Correr los gates | [`../06-quality/GATES.md`](../06-quality/GATES.md) |

## Formato de handoff

Al terminar una sesión, escribir [`../SESSION-HANDOFF.md`](../../SESSION-HANDOFF.md) con la
plantilla de ahí. Es lo que permite retomar sin reconstruir la conversación.
