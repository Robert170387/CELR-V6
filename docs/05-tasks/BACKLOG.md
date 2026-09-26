# BACKLOG.md — qué falta

> Nada arranca sin que el usuario lo pida. Clasificado por **quién puede resolverlo**.
> Estados: `DECISION` (espera al usuario) · `PROPOSAL` (sugerencia no aprobada) ·
> `DEUDA` (defecto conocido sin decisión pendiente).

## 🔴 Decisiones de negocio — **bloquean** funcionalidad

No son del agente. Requieren al usuario.

| # | Decisión | Qué implica | Dónde |
|---|---|---|---|
| **B1** | ¿Existe `cliente@celr.com`? | No existe en la BD y `seed_demo.py` no la crea. Sin eso, el rol `cliente` no tiene instancia. | `INSTRUCCIONES §6.3` |
| **B3** | Refresh token a cookie HttpOnly | **Rompe el sync offline del PWA.** Los JWT viven en `localStorage` a propósito. Hay que elegir: seguridad o offline. | `INSTRUCCIONES §8` |
| **B4** | Rate limiter distribuido | Hoy es `deque` en RAM. Con >1 worker cada uno tiene su cubeta. Necesita Redis o tabla. | `INSTRUCCIONES §8` |
| **B5** | OCR: Google Vision vs Tesseract | Tesseract local es el default. Vision requiere habilitar la dependencia comentada y trae costo. | `INSTRUCCIONES §8` |
| **B6** | Regla 4 — componente saldo | Hoy solo se fuerza el bloqueo de Flypass. Forzar el saldo bloquearía 15/18 ODTs. **R1-pre-2 (`0768d6c`) hizo que GET y POST affirmen lo mismo, pero no cerró la decisión:** el saldo es informativo por convención documentada en el código, no por acuerdo del negocio. | `ALINEACION §6` |
| **B7** | `asumido_por='owner'` | Permitido por schema y UI, sin regla contable. | `ALINEACION §6.1` |
| **B8** | `saldo_neto` con dos significados | **DIRECCIÓN DECIDIDA (2026-09-26): renombrar la columna GENERATED.** `RENAME COLUMN` conserva la expresión, no rompe la API y es reversible — 0 cambios en frontend y 0 asserts tocados. La medición corrigió el planteo: no es "columna vs campo" sino **campo vs campo dentro de la misma API** (`/calcular/{id}` y `/cerrar/{id}`). **Pendiente: el nombre exacto** de la columna nueva. | `GLOSSARY.md` L20 |
| **B9** | `legalizado` significa dos cosas | **UNKNOWN (2026-09-26):** ¿el negocio necesita marcar un gasto `legalizado` por una vía que no sea el cruce con peaje? No se encontró caso de uso. **Aviso — `legalizado` no lo escribe ningún flujo automático, pero NO se puede eliminar:** la única asignación de `estado_pago` en `backend/app` es `flypass_import.py:449` → `'pendiente_por_pagar'`, pero `GastoCreate` acepta `'legalizado'` sin mirar la `categoria`, así que es alcanzable por API; y `gastos.legalizado` es GENERATED sobre ese valor, de modo que quitarlo del CHECK hace caer la columna. Si algún día es NO, la migración de 3 partes **reconcilia** las dos definiciones; no borra. | `DECISIONS-PENDING.md` D8 · `GLOSSARY.md` §colisión |
| **A–F** | Refactor Nacional/Urbano | `tipo_viaje` ya distingue; el refactor no está diseñado. | `INSTRUCCIONES §8` |

> **Fuente de verdad de esta tabla:** [`DECISIONS-PENDING.md`](../07-consulting/DECISIONS-PENDING.md)
> lleva el estado medido contra el código de cada decisión (D1–D8) y es **más
> reciente que esta tabla**. Si divergen, el otro manda: esta es el índice, aquel
> el detalle. Actualizar ambos cuando una se cierre.

## 🟡 Deuda técnica — **no requiere decisión**, el agente puede tomarla

Ordenadas por relación costo/riesgo.

| # | Deuda | Riesgo si no se hace | Dónde |
|---|---|---|---|
| 1 | **`IP-real-detras-de-proxy`** — `Dockerfile:40` sin `--proxy-headers --forwarded-allow-ips=*` | En Render `client.host` es el proxy. El rate limit por IP se vuelve global y la columna `ip` de auditoría **no identifica a nadie**. **No saques conclusiones de esa columna.** | `INSTRUCCIONES §4` |
| 2 | **`verify_seed` mensaje claro** (3 líneas) | Falla con 10 baselines absolutos y el mensaje no dice que la BD no es recién sembrada. No es una suite. | `INSTRUCCIONES §4` |
| 3 | **`conteo-admins-cache`** — índice parcial `WHERE rol='admin' AND activo` | `es_ultimo_admin_activo` hace COUNT por llamada. Hoy es barato. **No cachear entre requests.** | `INSTRUCCIONES §4` |
| 4 | **A2.1 índices funcionales** `lower(cedula)`/`lower(correo)` | `func.lower()` no usa los índices actuales. La búsqueda se va a full scan. | `INSTRUCCIONES §4` |
| 5 | **`usuario_objetivo_id` es FK a `usuarios`** | Impide auditar entidades que no sean usuario. Alternativa futura: `objetivo_tipo + objetivo_id` sin FK. | `INSTRUCCIONES §4` |
| 6 | **`refresh_tokens` FK sin CASCADE** | Es el guardrail correcto (el producto no borra usuarios). Solo los tests lo sufren. Ver GATES. | `INSTRUCCIONES §4` |
| 7 | **Backfill de ADR** — 7 decisiones de `INSTRUCCIONES §7` a ADR | Deuda de proceso, no de producto. | `docs/04-decisions/README.md` |
| 8 | **`CONTRATO_PARA_UN_SOFTWARE.md`** — buenas prácticas de arquitectura de software | PROPOSAL, no aprobado. | este archivo |
| 9 | **`requirements-sin-pinear`** — 6 paquetes libres: `fastapi`, `alembic`, `pydantic-settings`, `python-jose`, `passlib`, `uvicorn` | Ya rompió una vez: `sqlalchemy` sin pinear tomó 2.1.1, cambió el driver por defecto de `postgresql://` a psycopg3 y dejó el contenedor en restart loop. **El mismo mecanismo puede romper con cualquiera de los otros 6 en el próximo rebuild.** | `9a576f4` · `requirements.txt` |
| 10 | **`sqlalchemy-2.1-psycopg3`** — adoptar el driver v3 | Hoy pineado a `<2.1` para desbloquear. El salto a 2.1 + `psycopg[binary]` es una fase consciente, no un efecto colateral de un rebuild. | `requirements.txt` |
| 11 | **`margen-est-formula`** — `Margen Est.` en la tabla no descuenta comisión | La columna nunca coincide con `Utilidad` y el ojo no lo detecta porque las dos parecen lo mismo. Preexistente. | `frontend/src/pages/Viajes.tsx` `margenDe` |
| 12 | **`gastos-listar-limit-100`** — `gastosAPI.listar()` sin filtro | Con más de 100 gastos, el margen se calcula sobre un subconjunto **sin avisar**. | `frontend/src/api/index.ts` |
| 13 | **`v_odt_resumen-sin-mapeo`** — vista de 20 columnas, 0 lectores, sin mapeo SQLAlchemy | Atrajo un cambio estructural: su `COALESCE` recalcula `saldo_flete_esperado` y **oculta el staleness** (un snapshot NULL se ve como número). Por eso R1 lee `viajes_odt`, no la vista. | `docs/01-architecture/DATABASE.md` |
| 14 | **`coalesce-oculta-staleness`** — la vista no distingue "0 calculado" de "nunca calculado" | Un resumen que sale de la vista puede mostrar un saldo que el servidor nunca calculó, indistinguible de uno real. Se cierra junto con 13. | `v_odt_resumen` |
| 15 | **`number-format-locale`** — `operaciones.py:161` formatea dinero en inglés dentro de una frase de servidor | Único outlier del proyecto: el frontend usa `toLocaleString('es-CO')`. **El fix durable NO es cambiar el separador**, es devolver `{codigo, monto}` y que el frontend arme la frase con su formateador. Cambiar el string perpetúa el smell. **Subió de prioridad (2026-09-26): el modal de resumen muestra `$4.414.000,00` en es-CO y, dos líneas más abajo, el texto del servidor dice `4,414,000.00` — la incoherencia se ve de lado a lado en la misma pantalla.** Cosmética, no rompe nada. | `R1-pre-2` `0768d6c` |
| 16 | **`formatearMoneda-dual`** — conviven `formatearMoneda` (0 decimales) y `formatearMonedaExacta` (2 decimales) | `formatearMoneda` redondea y está en **40+ lugares de 10 archivos**: en una vista donde se comparan cifras produce un número DISTINTO al real, que es la misma clase de problema que inventar un `total_deducibles`. La próxima vez que alguien formatee un monto tiene que elegir entre las dos sin criterio. **Consolidar en una cuando se decida si el redondeo a 0 decimales era intencional** — esa es la pregunta que bloquea el fix, y es de negocio. | `R1-frontend` `6529819` |
| 17 | **`resumen-sin-paginacion`** — `/viajes/{id}/resumen` topa las 3 listas en 200 y no pagina | Un viaje con más de 200 gastos muestra solo los primeros y **no hay forma de ver el resto desde la UI**. El truncado se declara (`truncado: true`) en vez de cortar en silencio, que es la mitad de la solución; la otra mitad es `?offset=` en el contrato. Hoy no hay caso observable: las tablas 1:N están vacías en la BD de desarrollo. | `R1-backend` `3012d81` |
| 18 | **`liquidaciones-calcular-sin-ruta`** — el backend expone `GET /liquidaciones/calcular/{viaje_id}` pero no hay pantalla | La ruta `/liquidaciones/calcular/:id` **no existe** en el frontend. El cálculo por viaje es un formulario donde se escribe el id a mano. El modal de resumen lo dice con texto en vez de link. Deep-linkearlo exige tocar `Liquidaciones.tsx`. | `frontend/src/App.tsx` |
| 19 | **`refresh_tokens-acumulados`** — 36 filas en la BD de desarrollo | **Parcialmente respondida (2026-09-26).** Se sospechaba que fueran residuos de suites que no limpian. **Medido: una suite sí fugaba** — `test_viajes_resumen` hacía `db.commit()` → `limpiar_tokens_nuevos()` → `db.close()`, así que el borrado se descartaba al cerrar y la suite **reportaba una limpieza que no había hecho**. +1 token por corrida, verificado en 3 corridas. Corregido. **Ahora las 22 suites corren sin mover el conteo**, así que las 36 restantes no se acumulan desde las suites: son anteriores a la corrección o de uso real. **Queda abierto solo el barrido**, cosmético y opcional. **No borrar a ciegas:** son FK de `usuarios` y borrarlos expulsa sesiones vivas. | medido vía `verify_seed` |

> **Lo que NO va en esta tabla, y por qué.** `fallo-silencioso`, `campo-sin-consumidor`,
> `baseline-absoluto`, `PWA-service-worker`, `commit-F` y `backtick-PowerShell` no son
> deudas: son **normas y trampas ya documentadas** en `docs/06-quality/GATES.md` §1–§4 e
> `INSTRUCCIONES_OPENCODE.md` §4. Copiarlas acá las convertiría en trabajo pendiente que
> ya está hecho. Una deuda es algo que **falta hacer**; una norma es algo que **hay que
> cumplir**.

## 🟢 Brechas de prueba declaradas

Cada una es una garantía que **no** tiene suite propia.

| # | Brecha | Por qué importa | Dónde |
|---|---|---|---|
| 1 | **No hay test de frontend.** No hay framework. | Un listado nuevo que devuelva `{data,total}` rompe la UI en silencio y **solo se ve mirando la pantalla**. | `docs/03-ux/UX-PATTERNS.md` |
| 2 | **No hay CI.** Los gates se corren localmente. Si nadie los corre, nada lo detecta. | — | — |
| 3 | **`ADR-0001`: no hay test de que rotar el identificador no limpia la cubeta** | Es la razón de ser de ese ADR. | `docs/04-decisions/` |
| 4 | **No hay test de que la UI muestre el error de un 403** | Los 4 bugs de A5.3 eran exactamente eso. | `docs/03-ux/UX-PATTERNS.md` |
| 5 | **`verificar que un log no filtra secretos`** solo existe en 2 suites del módulo de Usuarios | `rate_limiter` y `password_reset` sí. El resto de la app, no. | `test_auth.py`, `test_password_reset.py` |

### Cerradas

Se registran aquí para que quede la evidencia de que el proceso funciona, y para que
nadie las vuelva a contar como faltantes.

| Brecha | Cerrada en | Cómo |
|---|---|---|
| **`GET /viajes/{id}/bloqueos-cierre` sin ninguna cobertura** — ni suite ni E2E | `0768d6c` | TC-1 en `test_liquidaciones.py` cruza GET y POST sobre el mismo viaje en los tres escenarios. Probado con mutación: reintroducir el bug lo hace fallar. |
| **T1/T4 asertaban texto** (`"Flypass" in mensaje`), el mismo acoplamiento que el fix eliminaba del código | `0768d6c` | Ahora asertan estructura: el viaje está en la lista de bloqueos y trae al menos un bloqueo. |
| **`verify_seed.py` sin alcance documentado** | — | Ya estaba cubierto en `GATES.md` §"Lo que nunca es un gate". No se agregó deuda duplicada. |

## ⚪ Candidato a decisión, sin pedido

**PROPOSAL**, no implementado, no en el backlog activo hasta que alguien lo pida:

- Rotar a OpenTelemetry / structured logging (hoy `logger.info` con formato simple).
- Extraer los roles a un `.sql` generado desde el enum, para que CHECK y enum no puedan divergir.
- Tests de contrato contra `/openapi.json` para congelar la forma de los listados (cierra la brecha 1).

## Lo que **no** está en el backlog

- Refactors de estilo. El repo no tiene linter ni formateador; agregar uno es decisión aparte.
- Migrar de `JWT en localStorage` a cookie: es **B3** y rompe offline.
- Cambiar el modelo de `proveedores` para separar `cliente`: requiere decisión de negocio, no
  solo técnica. Ver la advertencia en `docs/02-domain/GLOSSARY.md`.
