# DEEPSEEK-BRIEF.md — brief para el consultor externo

> **DeepSeek es CONSULTOR.** Propone, argumenta y señala riesgos. **No tiene autoridad sobre el
> código.** Nada de lo que diga se convierte en decisión sin aprobación del usuario **y** un ADR
> en `docs/04-decisions/`.
>
> Este documento es una **plantilla**. Copiar, llenar los corchetes, enviar.
> Es **compacto a propósito**: un brief de 2000 líneas no lo lee nadie, y un brief de 30 líneas
> sin evidencia hace que el consultor especule.

---

## 1. Objetivo

> `[QUÉ QUEREMOS DECIDIR O RESOLVER. Una pregunta concreta, no "revisá el proyecto".]`

## 2. Contexto de negocio (5 líneas máximo)

CELR v6 gestiona una flota de trucks de carga en Colombia: ODTs, gastos, ingresos, liquidaciones
a conductores, mantenimiento y peajes. Control de acceso por rol (6 roles) y soporte de trabajo
sin conexión (PWA).

- Transportista con N tractocamiones. **UNKNOWN**: número exacto, cobertura y si opera propio o
  como operador. No está en el repositorio.
- El eje del modelo es la **ODT**. Gastos, ingresos y liquidaciones se le enganchan.

## 3. Estado actual

- Módulo de Usuarios (identidad, auth, recuperación, enforcement, auditoría, CRUD, UI) cerrado.
- Fases previas cerradas: ODT, Gastos, Liquidaciones, cierre mensual B2, Flypass, seeds.
- **No hay funcionalidad en curso.** Lo abierto son decisiones de negocio y deuda técnica.
- 21 suites backend en verde + humo + E2E + `tsc -b`.

**Commits del módulo:** `2b7f784` (A1) · `e7d57b2` (A2) · `dc6421d` (A3.1) · `0e6d2b3` (A3.2) ·
`e8fd8bd` (A3.3) · `6eaba0c`+`282540f` (A3.4) · `4c5ba07` (A4) · `06c0b1a` (A5.1) ·
`a08fdfa` (A5.2) · `b4b1426`+`99cfb4d` (A5.3) · `f514341` (A5.4) · `3b6367e` · `3a2046d` ·
`bdd14e1`.

## 4. Arquitectura relevante (lo que afecta la pregunta)

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL. 11 routers, 45 paths, 65 operaciones.
  Alembic oficial. 21 tablas.
- **Frontend:** React 18 + Vite + TypeScript estricto. Sin librería de componentes.
  PWA con service worker + cola en IndexedDB. **JWT en `localStorage`** (trade-off deliberado
  por el sync offline).
- **Auth:** 3 capas — JWT con `password_version` (invalida sesiones al rotar credencial),
  enforcement de primer login a nivel de router, `RoleChecker` por rol.
- **Despliegue:** Render, backend container + sitio estático, single worker.

**Detalle completo:** `docs/01-architecture/SYSTEM.md` y `DATABASE.md`.

## 5. Restricciones

1. **No se inventa una regla de negocio.** Si no se puede confirmar, es `UNKNOWN`.
2. **Alembic es el mecanismo de esquema.** Las migraciones nuevas llevan guards de existencia.
3. **Identidad:** una persona = una cuenta. `cedula` es canónica y nullable; `correo` es alias
   legacy. Sin personas jurídicas.
4. **El frontend funciona sin conexión.** Cualquier cambio que rompa el sync offline es
   inaceptable sin decisión explícita.
5. **No hay pytest, ni linter, ni CI.** Las suites son scripts contra la BD real.
6. Todo en **español**, incluidos identificadores.

## 6. Hechos confirmados (con evidencia)

Solo esto. **Nada de lo que sigue se pone en duda.**

| Hecho | Evidencia |
|---|---|
| El rate limiter es un `deque` en RAM: 5 intentos / 15 min, por `usuario:{id}` | `backend/app/core/rate_limiter.py` |
| Con >1 worker, cada uno tiene su cubeta independiente | Consecuencia directa del `deque` |
| `request.client.host` es la IP del proxy en Render | `Dockerfile:40` corre uvicorn sin `--proxy-headers` |
| `password_reset_token.token_hash` es sha256; el token nunca se guarda en claro | `app/services/password_reset.py` |
| `usuarios.correo` es nullable; hay 7 cuentas con `correo=NULL` | modelo `flota.py` + `d4e5f6a7b8c9` |
| `refresh_tokens.usuario_id` es FK **sin** `ON DELETE CASCADE` | `pg_constraint` |
| **No existe tabla `clientes`.** `ingresos.cliente_origen_id` → `proveedores.id`, y `proveedores.tipo` es texto libre sin CHECK | `pg_constraint` + valores vivos |
| `viajes_odt.estado` no tiene CHECK; el enum vive en el frontend y la lógica | `Viajes.tsx:83` |
| `auditoria_evento` es append-only por convención, sin restricción | sin trigger en `pg_constraint` |
| La UI de gestión tuvo 4 bugs que ninguna prueba de endpoint podía ver | `docs/03-ux/UX-PATTERNS.md` |

## 7. Decisiones ya tomadas — **no las reviertas sin discutir**

Cada una tiene ADR o documento. Cambiarlas es una decisión, no una mejora.

| Decisión | Dónde |
|---|---|
| Rate limit keyeado por `usuario:{id}` canónico | `ADR-0001` |
| `cedula` canónica nullable, `correo` alias, sin backfill | `ADR-0002` |
| Recuperación que **no** revela existencia de cuentas | `ADR-0003` |
| Listados: array plano + `X-Total-Count` | `ADR-0004` |
| Último admin: garantía estructural + confirmación humana | `ADR-0005` |
| Alembic oficial con guards de idempotencia | `INSTRUCCIONES §4` |
| `flete_neto` se calcula en el servidor, nunca en el cliente | `INSTRUCCIONES §4` |

## 8. Riesgos

| Riesgo | Impacto |
|---|---|
| Rate limiter in-memory | Con >1 worker, el límite de fuerza bruta es 5× workers. |
| IP de proxy en la columna `ip` | La auditoría **no identifica** al usuario. Cualquier análisis de esa columna es inválido. |
| `saldo_neto` con dos significados | Riesgo de cálculo contable incorrecto. **B8.** |
| `asumido_por='owner'` sin regla | Dinero sin dueño contable. **B7.** |
| Enumeración de cuentas vía `forgot-password` | Ya mitigada (ADR-0003). **No revertir.** |
| Documentación histórica miente sobre ausencias | `AUDITORIA_CELR_v6.md` dice que no hay recuperación de contraseña. **Sí hay.** Lleva 97 commits desfasada. |

## 9. Preguntas abiertas (las que decides tú)

| # | Pregunta | Bloquea |
|---|---|---|
| B1 | ¿Existe `cliente@celr.com`? | Instancia del rol `cliente`. |
| B3 | ¿Refresh token a cookie HttpOnly? | **Rompe el sync offline.** Hay que elegir. |
| B4 | ¿Rate limiter distribuido? | Seguridad real con >1 worker. |
| B5 | ¿OCR Vision o Tesseract? | Costo y dependencia. |
| B6 | Regla 4 — ¿se fuerza el saldo? | Hoy solo se fuerza Flypass. |
| B7 | Regla de `asumido_por='owner'` | Contabilidad. |
| B8 | Desambiguar `saldo_neto` | Contabilidad. |

## 10. Archivos relevantes

```
AGENTS.md                             Reglas operativas, no negociables
INSTRUCCIONES_OPENCODE.md             §3 gates · §4 trampas y deudas · §5 estado · §8 B1-B8
docs/00-context/CURRENT.md            Dónde estamos
docs/01-architecture/SYSTEM.md        Arquitectura
docs/01-architecture/DATABASE.md      21 tablas, reglas de migración
docs/02-domain/GLOSSARY.md            Entidades (con sus UNKNOWN)
docs/04-decisions/ADR-*.md           Decisiones con alternativas descartadas
docs/06-quality/GATES.md              Los 4 gates + las 4 normas
backend/app/core/rate_limiter.py      B4
backend/app/api/v1/deps.py           Las 3 capas de auth
backend/Dockerfile:40                 Falta --proxy-headers
```

## 11. Solicitud concreta

> `[QUÉ QUEREMOS DE VUELTA. Sé específico: "revisá si el esquema de rate limiting aguanta
> multi-worker y proponé una opción con costo estimado", no "danos tu opinión sobre el proyecto".]`

**Formato de respuesta que pedimos:**

1. **Hallazgos** — cada uno con `archivo:línea` y un caso concreto que lo dispare. Si no lo
   pudiste verificar, decilo: `UNKNOWN` es una respuesta válida y valiosa.
2. **Opciones** — al menos dos, con el costo y el riesgo de cada una.
3. **Recomendación** — una, y qué haría distinto si la decisión fuera distinta.
4. **Lo que no verificaste** — explícito.

**Lo que NO vamos a aceptar:**

- Afirmaciones sin evidencia. "Debería" no es un hecho.
- Reglas de negocio inventadas. El repositorio no las tiene y no se adivinan.
- Propuestas presentadas como decisiones. Vos proponés; el usuario decide.
- Ignorar los ADRs existentes y re-litigar decisiones ya tomadas sin conocerlas.
