# DECISIONS-PENDING.md — decisiones que requieren aprobación del propietario

> **Nada de este documento está aprobado.** Cada fila es una decisión abierta. Ninguna se
> implementa hasta que el propietario la apruebe explícitamente.
>
> Cuando se aprueba: (1) ADR en `docs/04-decisions/`, (2) `CURRENT.md`, (3) planificación,
> (4) implementación, (5) gates, (6) revisión de seguridad/UX si aplica, (7) diff.
>
> **La columna "Estado verificado" se midió contra el código**, no contra documentación.
> Es la línea base contra la que se evalúa cualquier propuesta de un consultor.

## Estado de la revisión de DeepSeek

**No hay revisión de DeepSeek en el repositorio.** Verificado en cuatro fuentes al
2026-09-25:

| Fuente | Qué contiene |
|---|---|
| `docs/07-consulting/` | Solo `DEEPSEEK-BRIEF.md` — el brief **de salida**, no respuesta |
| `CONTEXTO_DEEPSEEK_CELR_v6.md` | El brief **entregado** a DeepSeek (2026-09-23) |
| `respuestas_agente/` | 17 respuestas del **agente**, no de DeepSeek |
| `git log` / `git status` | Sin commits ni archivos nuevos que traigan la respuesta |

**Consecuencia:** la comparación ADOPT/REJECT/MODIFY/DEFER/UNKNOWN **no se puede hacer**
y no se inventó. Lo que sí se dejó es el arnés de comparación (más abajo) y la línea base
medida de cada decisión, para que la clasificación sea mecánica cuando la revisión llegue.

---

## D1 — `cliente@celr.com` no existe (**B1**)

| | |
|---|---|
| **Pregunta** | ¿Existe la cuenta `cliente@celr.com`? |
| **Estado verificado** | **FACT** — `SELECT count(*) FROM usuarios WHERE correo='cliente@celr.com'` → **0 filas**. `seed_demo.py` no la crea. |
| **Por qué importa** | El rol `cliente` existe en `RolUsuario` y en el CHECK de la BD, pero **no tiene ninguna instancia**. |
| **Agravante** | **No existe tabla `clientes`.** `ingresos.cliente_origen_id` es FK a **`proveedores.id`**, y `proveedores.tipo` es texto libre **sin CHECK** cuyos únicos valores vivos son `combustible` y `pasarela_pagos`. **Ningún dato representa a un cliente hoy.** |
| **Opciones** | (a) Crear la cuenta con rol `cliente`. (b) Modelar `clientes` como tabla propia — **refactor de datos con migración**. (c) Definir el valor de `proveedores.tipo` que significa "cliente". (d) Dejarlo: `cliente` es un rol de acceso, no una entidad de negocio. |
| **Bloquea** | Todo trabajo sobre ingresos por cliente. |
| **Riesgo de (b)** | Toca `ingresos` y su FK. Migración con datos existentes. |
| **Decisión** | — |

## D2 — Refresh token en cookie HttpOnly (**B3**)

| | |
|---|---|
| **Pregunta** | ¿Mover el refresh token a cookie HttpOnly? |
| **Estado verificado** | **FACT** — `client.ts:8-9`: `TOKEN_KEY='celr_token'`, `REFRESH_KEY='celr_refresh'`, en `localStorage`. |
| **Por qué importa** | `localStorage` es legible por JS: un XSS se lleva la sesión. Cookie HttpOnly no. |
| **Contra** | **Rompe el sync offline del PWA.** El interceptor lee el token en runtime; una cookie HttpOnly requiere leer `/auth/refresh` para saber si hay sesión, lo que agrega un round-trip al arranque sin conexión. |
| **Opciones** | (a) Cookie HttpOnly + endpoint de "¿tengo sesión?". (b) Access token corto en memoria + refresh en cookie. (c) Mantener `localStorage` y agregar CSP estricta. (d) Mantener y aceptar el riesgo. |
| **Decisión** | — |
| **Nota** | Es seguridad **contra** una decisión de producto (offline). Ninguna opción es gratis. |

## D3 — Rate limiter distribuido (**B4**)

| | |
|---|---|
| **Pregunta** | ¿Sustituir el limiter en memoria por uno compartido? |
| **Estado verificado** | **FACT** — `rate_limiter.py:15`: `_fallos: Dict[str, Deque[float]] = defaultdict(deque)`. Proceso local. Hoy cubre login, `forgot-password` y `reset-codigo`; **no** `/auth/refresh` ni `/auth/cambio-contrasena`. |
| **Por qué importa** | Con >1 worker, cada uno tiene su cubeta ⇒ el límite efectivo es `5 × workers`. En Render el backend corre **single worker** hoy, así que **no es urgente**. |
| **Agravante relacionado** | `Dockerfile:40` sin `--proxy-headers` ⇒ `client.host` es la IP del proxy. Hoy el límite por IP es global. **Son dos problemas distintos**; arreglar el headers **no** arregla el store. |
| **Opciones** | (a) Redis. (b) Tabla Postgres con `INSERT ... ON CONFLICT`. (c) Dejarlo mientras sea single worker y documentar el límite. |
| **Riesgo de (a)/(b)** | Nueva dependencia o nueva tabla ⇒ migración, y (a) servicio nuevo en Render. |
| **Decisión** | — |

## D4 — Motor OCR (**B5**)

| | |
|---|---|
| **Pregunta** | ¿Tesseract local o Google Vision? |
| **Estado verificado** | **FACT** — `config.py`: `OCR_ENGINE: str = "tesseract"`. `google-cloud-vision` está **comentado** en `requirements.txt`. |
| **Por qué importa** | Calidad de lectura de recibos vs. costo por llamada. |
| **Opciones** | (a) Tesseract (actual). (b) Vision. (c) Híbrido: Tesseract primero, Vision si la confianza es baja. |
| **Riesgo de (c)** | El path de confianza no existe: `gastos.estado_validacion` **no tiene CHECK y está vacía en todas las filas**. (c) requiere trabajo previo. |
| **Decisión** | — |

## D5 — Regla 4, componente saldo (**B6**)

| | |
|---|---|
| **Pregunta** | ¿Se fuerza el bloqueo por saldo no cubierto al cerrar una liquidación? |
| **Estado verificado** | **FACT** — `bloqueos_cierre_odt` devuelve **dos** bloqueos (Flypass pendiente, saldo no cubierto) y **solo el de Flypass se fuerza**. |
| **Por qué no se forzaba** | Forzarlo bloquearía **15/18 ODTs activas**, incluidas 9 ya liquidadas. Es inaccionable hoy. |
| **Opciones** | (a) Mantener solo Flypass. (b) Forzar ambos, con un umbral configurable. (c) Advertir sin bloquear. |
| **Riesgo de (b)** | Inmoviliza la operación. El umbral correcto es **regla de negocio**: **UNKNOWN**. |
| **Decisión** | — |

## D6 — `asumido_por='owner'` (**B7**)

| | |
|---|---|
| **Pregunta** | ¿Qué significa que un gasto u ODT lo asuma el dueño? |
| **Estado verificado** | **FACT** — `operaciones.py`: `asumido_por = Column(String(50), nullable=False, default='empresa')`. Permitido por schema y UI, **sin regla contable**. |
| **Por qué importa** | Dinero sin dueño contable. |
| **UNKNOWN** | Si `'owner'` es un valor válido hoy, qué reglas lo gobiernan, y cómo afecta la liquidación del conductor. **No está en el repositorio.** |
| **Decisión** | — |

## D7 — `saldo_neto` con dos fórmulas (**B8**)

| | |
|---|---|
| **Pregunta** | ¿Se renombra uno de los dos? |
| **Estado verificado** | **FACT** — dos cálculos con el mismo nombre:<br>• **Columna GENERATED** en `liquidaciones_conductores` (`financiero.py:77`): `comision_flete + bonificaciones + viaticos + otros_haberes − descuentos`.<br>• **Clave del payload de API** del detalle de liquidación de una ODT (`liquidaciones.py:96`): `flete_neto − gastos_empresa − anticipos − comision_flete`.<br>`viajes_odt` **no** tiene columna `saldo_neto`; tiene `saldo_flete_esperado`. |
| **Riesgo real** | Un consumidor que lea `saldo_neto` del endpoint de ODT y lo compare con el de la liquidación está comparando **dos cosas distintas** y obtiene un número plausible y equivocado. |
| **Opciones** | (a) Renombrar la clave del payload. (b) Renombrar la columna. (c) Renombrar ambas. (d) Documentar y no tocar. |
| **Riesgo** | Renombrar la columna ⇒ migración sobre una **GENERATED**. Renombrar la clave ⇒ **rompe clientes de la API**; requiere coordinación. |
| **Decisión** | — |

## D8 — `legalizado` significa dos cosas (**B9**)

| | |
|---|---|
| **Pregunta** | ¿Se renombra uno de los dos, o se documenta la diferencia y se dejan los nombres? |
| **Estado verificado** | **FACT** — dos columnas GENERATED en tablas distintas, leídas de `information_schema.columns`:<br>• `gastos.legalizado` = `estado_pago = 'legalizado'` — depende del **estado de pago**.<br>• `flypass_transacciones.legalizado_en_gastos` = `gasto_id IS NOT NULL` — depende de la **existencia del vínculo**.<br>**Ninguna implica la otra.** No existe campo de "quién legalizó" ni de cuándo. |
| **Riesgo real** | Un `gastos.legalizado = true` **no** significa que su peaje esté legalizado, ni al revés. Una consulta que una los dos por nombre produce un número plausible y equivocado. Es el **mismo patrón que D7/B8**: mismo nombre, fórmulas distintas. |
| **Opciones** | (a) Renombrar `gastos.legalizado` → `pagado_como_legalizado`, o `legalizado_por_estado`. (b) Renombrar `flypass_transacciones.legalizado_en_gastos` → `vinculado_a_gasto`. (c) Renombrar ambos. (d) Dejar los nombres y documentar explícitamente que no son el mismo concepto. |
| **Riesgo de (a)/(b)** | Renombrar `gastos.legalizado` ⇒ migración sobre una **GENERATED** (hay que drop y re-add; en Postgres se puede con `ALTER TABLE ... DROP COLUMN` + `ADD COLUMN ... GENERATED`, verificando que no se pierde dato porque es derivada). Renombrar `flypass_transacciones.legalizado_en_gastos` ⇒ también GENERATED, mismo procedimiento. |
| **Riesgo de (c)** | Toca las dos tablas y cualquier consumidor de `/api/v1/flypass` que lea ese campo. |
| **Bloquea** | Nada. Es deuda de vocabulario, no un defecto funcional. |
| **Depende de** | Si el negocio usa "legalizado" para **una sola cosa** o para **dos**. Con una sola, (c). Con dos conceptos reales, (a) o (b) según cuál sea el nombre canónico. |
| **Decisión** | — |

> **Nota de discovery:** B9 no estaba en el radar. Apareció al verificar las columnas
> GENERATED de `GLOSSARY.md`. No es un cambio de modelo, es un nombre que significa dos cosas.
> Conviene tratarlo junto con B8: son el mismo tipo de defecto y la misma clase de riesgo.

---

## Arnés de comparación — para cuando llegue la revisión

Para cada recomendación de DeepSeek, clasificar **contra el código**, no contra este
documento:

| Clasificación | Significado |
|---|---|
| **ADOPT** | Es correcta, es consistente con los ADR vigentes y no contradice código. Procede a ADR. |
| **MODIFY** | La observación es correcta; la solución propuesta no. Se reescribe la propuesta. |
| **REJECT** | Contradice un ADR vigente, un CHECK en la BD o un principio del proyecto, **y no aporta contexto nuevo** que lo revierta. Se documenta el motivo. Si el contexto es nuevo, no es REJECT: es un ADR a reemplazar. |
| **DEFER** | Correcta pero su momento no es ahora. Se anota con la condición que la activa. |
| **UNKNOWN** | No se puede determinar sin información que el repositorio no tiene. **Se pregunta, no se adivina.** |

### Checks obligatorios por recomendación

1. ¿Contradice algún ADR de `docs/04-decisions/`?
2. ¿Choca con un CHECK constraint real de la BD? (consultar `pg_constraint`, no el código)
3. ¿Asume una regla de negocio que no está confirmada? ⇒ **UNKNOWN**.
4. ¿Requiere tecnología nueva? Justificar **problema, beneficio, coste, migración, mantenimiento, riesgo**. Sin las seis, no se adoptan.
5. ¿Es reescritura masiva? El proyecto prefiere **evolución incremental**. Si toca más de ~5 archivos sin contexto, probablemente está mal planteada.
6. ¿Tiene test que la cubra? Si no, es una brecha que se declara, no un detalle.

### Decisiones ya tomadas — contexto, no cerco

**Esto no es una lista de propuestas que se rechazan.** Es el registro de decisiones que
**ya se tomaron con su motivo**, para que quien proponga algo las revise y decida.

Una propuesta sobre cualquiera de estos temas **es legítima** si aporta contexto que no
teníamos: una amenaza nueva, un requisito que cambió, una restricción que apareció. En ese
caso no se rechaza: se **cambia el ADR** y se documenta por qué cambió lo que se creía.

Lo único que no corresponde es proponerlas **sin conocerlas** y tratarlas como Inovacion.

| Tema | Por que se decidio asi | ADR | Como se revoca |
|---|---|---|---|
| "Devolver 404 cuando el usuario no existe en el reset" | Seria un oraculo de enumeracion de cuentas: cualquiera barria el padron de cedulas y correos. | 0003 | Solo con un cambio en el modelo de amenaza, **y** ADR nuevo. |
| "Confirmar en la UI si se envio el email" | La UI es parte del mismo sistema: si la UI confirma, la garantia del backend no sirve de nada. | 0003 | Separar los sistemas, o cambiar la garantia completa. |
| "Key del rate limit = lo que envia el cliente" | Es rotable por diseno: cambiar como se escribe la cedula limpia la cubeta. | 0001 | Con un limite global complementario, no reemplazando el canonico. |
| "Hacer cedula NOT NULL y backfillear" | 7 cuentas no tienen cedula, y **no hay de donde sacarla**: no es una migracion, es una carga de datos que requiere gente. | 0002 | Con el dato real disponible. |
| "Cambiar listados a {data, total}" | Duplica el total que ya viaja en el header y rompe conTotal; la tabla queda vacia sin error visible. | 0004 | Migracion de todos los modulos a la vez, con su propio ADR. |
| "Bloquear duro al ultimo admin" | Vuelve irrecuperable un error operativo: el unico camino restante es la consola. | 0005 | Si aparece una forma verificada de recuperar el acceso sin consola. |
| "Exponer si se envio el enlace de reset" | Revertiria 0003 por completo. | 0003 | Solo con un ADR nuevo que documente el modelo de amenaza asumido. |
