# GLOSSARY.md — entidades y términos del dominio

**FACT** salvo que se marque. "Evidencia" = archivo, tabla o comando del que sale el hecho.
Si no se pudo confirmar: **UNKNOWN**. No completar por inferencia.

## Cómo se verificó

Las tablas y columnas de abajo se extrajeron del **metadata de SQLAlchemy** y de
`pg_constraint` sobre la BD, no de documentación. Los CHECK constraints son los que
existen **de verdad** en la BD.

## ⚠️ El dominio no coincide con el vocabulario

Tres hallazgos que hacen que un agente assuma mal si no los lee:

| Hallazgo | Consecuencia |
|---|---|
| **No existe tabla `clientes`.** `ingresos.cliente_origen_id` es FK a **`proveedores.id`**. | "Cliente" y "proveedor" son la misma tabla. Lo que los distingue es una columna de texto libre `proveedores.tipo` **sin CHECK constraint**. |
| **En la BD actual `proveedores.tipo` solo tiene** `combustible` (6) y `pasarela_pagos` (1). | **UNKNOWN** — qué valor representa a un cliente. No hay dato vivo que lo demuestre. No lo asumas. |
| **`saldo_neto` significa dos cosas** con fórmulas distintas. | **FACT** — la API lo expone en **dos endpoints del mismo módulo**, no en una columna y un campo: <br>• `GET /liquidaciones/calcular/{viaje_id}` (`liquidaciones.py:96`) → `flete_neto − gastos_empresa − anticipos − comision_flete`. Magnitud **de la ODT**.<br>• `POST /liquidaciones/cerrar/{viaje_id}` (`liquidaciones.py:296`) → la **columna GENERATED** de la fila: 7 haberes − 6 deducciones (ver "Qué es una liquidación", lectura #1, para la fórmula completa). Magnitud **del conductor**.<br>El frontend usa las dos con rótulos distintos y **cada rótulo muestra la magnitud correcta**: no hay bug de valor, hay **mismo nombre para dos magnitudes**. `viajes_odt` **no** tiene columna `saldo_neto`; tiene `saldo_flete_esperado`. **Decisión B8: renombrar la columna GENERATED** — `RENAME COLUMN` conserva la expresión, no rompe la API y es reversible. El nombre exacto sigue abierto. |

---

## Entidades

### ODT / viaje — `viajes_odt` (43 col)

**FACT.** La tabla central. Un viaje de carga.

| Grupo | Columnas |
|---|---|
| Identidad | `numero_odt` (secuencia atómica), `num_manifiesto`, `empresa_manifiesto` + `empresa_manifiesto_id` |
| Ruta | `origen` / `destino` (texto) + `origen_municipio_id` / `destino_municipio_id` (FK) |
| Flete | `valor_flete_manifiesto`, `flete_neto` (**calculado en el servidor**), `anticipo_manifiesto`, `saldo_flete_esperado` |
| Retenciones | `retefuente_porcentaje`/`_valor`, `reteica_porcentaje`/`_valor`, `otras_deducciones` |
| Carga | `tipo_carga`, `peso_declarado_ton`, `peso_bascula_origen`, `peso_bascula_destino` |
| Km | `km_inicial`, `km_final`, `km_recorridos` |
| Comisión | `porcentaje_comision`, `comision_conductor` |
| Derivados | `gastos_totales_viaje`, `utilidad_neta_odt` |
| Ciclo de vida | `estado`, `fecha_manifiesto`, `fecha_salida`, `fecha_llegada`, `eliminado_en`/`eliminado_por` |

**Estados** (`Viajes.tsx:83`, `liquidaciones.py:208`): `programado`, `en_curso`, `completado`,
`liquidado`, `cancelado`. **Sin CHECK constraint en la BD** — el enum vive en el frontend y en
la lógica. **UNKNOWN** si la BD debe aceptarlos todos.

**Campos requeridos por estado** (`Viajes.tsx:97`):
- `programado` / `en_curso`: `valor_flete_manifiesto`, `km_inicial`
- `completado`: los anteriores + `km_final`, `fecha_llegada`
- `cancelado`: ninguno

**`tipo_viaje`** — CHECK real: `urbano`, `nacional`, `internacional`, `vacio`.

**CHECK reales:** `km_final >= km_inicial`; valores no negativos (con `COALESCE` a 0).

### Tractocamión / vehículo — `vehiculos` (16 col)

**FACT.** `placa`, `marca`, `modelo`, `anio`, `tipo_carroceria`, `capacidad_ton`, `estado`,
`km_actual`, `km_inicial_sistema`, `numero_motor`, `numero_chasis`, `propietario_nombre`,
`propietario_nit`.

**UNKNOWN** — no hay CHECK sobre `estado` ni `tipo_carroceria`. Los valores no están
documentados en el repo.

### Conductor — `conductores` (13 col)

**FACT.** `nombre_completo`, `cedula`, `telefono`, `correo`, `direccion`, `num_licencia`,
`categoria_licencia`, `vencimiento_licencia`, `estado`, **`porcentaje_comision_default`**.

La comisión tiene un valor por defecto individual que la ODT puede sobreescribir con
`porcentaje_comision`.

**FACT.** Relación con vehículo: tabla `conductor_vehiculo` (8 col) con `es_principal` y
vigencia. `conductores` **no** tiene `vehiculo_id`.

**UNKNOWN** — valores válidos de `conductores.estado`.

### Cliente — **no existe como entidad**

**FACT.** `ingresos.cliente_origen_id` → `proveedores.id`. Un cliente es un proveedor.

**UNKNOWN** — cómo se distingue un proveedor que es cliente de uno que es taller o proveedor de
combustible. La columna `proveedores.tipo` es texto libre sin CHECK y no tiene el valor
"cliente" en los datos actuales.

### Proveedor — `proveedores` (13 col)

**FACT.** `nit`, `razon_social`, `nombre_comercial`, `tipo`, `telefono`, `correo`, `ciudad` +
`ciudad_municipio_id`, y datos bancarios: `banco`, `tipo_cuenta`, `numero_cuenta`.

**FACT.** `tipo` **no tiene CHECK**. Valores observados: `combustible`, `pasarela_pagos`.

### Gasto — `gastos` (33 col)

**FACT.** Pertenece a un viaje, a un vehículo, o a ninguno (gasto fijo / mantenimiento).

| Concepto | Columnas |
|---|---|
| Vínculo | `viaje_id`, `vehiculo_id`, `proveveedor_id` → `proveedores.id` |
| Clasificación | `categoria`, `descripcion` |
| Comprobante | `num_factura`, `tiene_num_factura`, `hash_comprobante` (**detecta duplicados**), `url_imagen` |
| Dinero | `valor_total` (NUMERIC), `responsable_pago`, `asumido_por`, `metodo_pago` |
| Combustible | `km_registro`, `cantidad_galones`, `precio_por_galon` |
| OCR | `datos_ocr_json`, `estado_validacion`, `aprobado_por`, `fecha_aprobacion`, `motivo_rechazo`, `reportado_por` |
| Legalización | `legalizado` |
| Soft delete | `eliminado_en`, `eliminado_por` |

**CHECK reales:**
- `estado_pago` ∈ {`pagado`, `pendiente_por_pagar`, `legalizado`}
- `metodo_pago` ∈ {`efectivo`, `tarjeta`, `transferencia`, `tag`}
- `valor_total >= 0`

**UNKNOWN** — valores de `categoria` y de `estado_validacion`. En la BD de desarrollo
`gastos` está **vacía**, así que no hay valores que observar: no es que estén vacíos en
las filas, es que **no hay filas**. No hay CHECK sobre ninguna de las dos columnas. El
flujo de aprobación `aprobado_por`/`fecha_aprobacion` tiene columnas pero **no hay lógica
que las use**.

### Ingreso — `ingresos` (17 col)

**FACT.** Siempre con `viaje_id`.

| Concepto | Columnas |
|---|---|
| Vínculo | `viaje_id`, `vehiculo_id`, **`cliente_origen_id` → `proveedores.id`** |
| Clasificación | `tipo_ingreso`, `descripcion`, `receptor_destino` |
| Dinero | `valor`, `forma_pago`, `num_referencia`, `estado_pago` |
| Control | `creado_por`, `eliminado_en`, `eliminado_por` |

**CHECK reales:**
- `tipo_ingreso` ∈ {`anticipo_manifiesto`, `saldo_flete`, `ajuste_flete`, `aporte_capital`, `otro`}
- `estado_pago` ∈ {`por_cobrar`, `recibido`, `conciliado`}
- `valor >= 0`

### Liquidación — `liquidaciones_conductores` (40 col)

**FACT.** Settlement al conductor. Soporta cierre quincenal y **mensual**.

| Concepto | Columnas |
|---|---|
| Sujeto | `conductor_id`, `vehiculo_id`, `viajes_ids` (array) |
| Período | `periodo_inicio`, `periodo_fin`, `periodo_ym` (GENERATED STORED), `es_cierre_mensual` |
| Haberes | `comision_flete`, `porcentaje_comision`, `comisiones_total`, `bonificaciones`, `viaticos_reconocidos`, `otros_haberes`, `salario_basico`, `auxilio_transporte`, `total_haberes` |
| Deducciones | `descuento_salud_pension`, `retiros_tarjeta_anticipos`, `gastos_a_cargo_conductor`, `prestamos`, `otros_descuentos`, `total_descuentos` |
| Resultado | **`saldo_neto`** |
| Conteo | `viajes_nacionales`, `viajes_urbanos`, `total_viajes` |
| Pago | `estado`, `fecha_pago`, `forma_pago_liquidacion`, `num_comprobante_pago` |

**CHECK real:** los cinco campos de deducción y los tres de haberes fijos son `>= 0`.
**`saldo_neto` NO tiene CHECK** — puede quedar negativo.

**UNKNOWN** — valores de `liquidaciones_conductores.estado`. En la BD actual está **vacía**.

### Municipio — `municipios` (4 col)

**FACT.** `codigo_dane`, `departamento`, `municipio`. Catálogo DIVIPOLA, cargado por
`backend/scripts/seed_municipios.py`.

**FACT** — **Obligatorio**: los endpoints de autocomplete de ciudad devuelven el `municipio_id`,
y gastos e ingresos lo usan. **Una tabla `municipios` vacía rompe el alta de gastos y viajes.**
Por eso el orden de boot en Docker y Render es `alembic upgrade head && seed.py && seed_municipios.py`.

### Documento — `documentos_vencimientos` (18 col)

**FACT.** `vehiculo_id`, `conductor_id`, `tipo_documento`, `nombre_documento`, `entidad_emisora`,
`num_documento`, `fecha_expedicion`, `fecha_vencimiento`, tres flags de alerta
(`alerta_30_enviada`, `alerta_15_enviada`, `alerta_5_enviada`), `url_documento`, `activo`.

**UNKNOWN** — valores de `tipo_documento`, y si las alertas se disparan automáticamente
(las columnas existen; **no hay evidencia de un job que las escriba**).

### OCR — `gastos.datos_ocr_json`

**FACT** — Tesseract local (`OCR_ENGINE=tesseract`), necesita binario + idioma `spa`.
Módulo `app/services/ocr_service.py` + `ocr_engines.py` + `ocr_parser.py`.

**FACT** — Cambiar a Google Vision requiere habilitar la dependencia comentada
`google-cloud-vision`. **Decisión de negocio pendiente: B5.**

**UNKNOWN** — qué se hace con el resultado cuando la confianza del OCR es baja. La columna
`estado_validacion` existe pero no hay CHECK ni valores que la usen.

### Peaje / Flypass — `flypass_transacciones` (14 col)

**FACT.** `vehiculo_id`, `fecha_transaccion`, `nombre_peaje`, `ciudad_peaje` (+ FK municipio),
`valor`, `num_transaccion_flypass` (dedupe), `viaje_id`, `gasto_id`, `legalizado_en_gastos`,
`raw_data` JSONB (fila original del Excel), `estado`, `importado_en`.

### Mantenimiento

**FACT.** `mantenimientos_reglas` (15 col): intervalos de servicio por vehículo en km y días,
`km_proximo_servicio`, `fecha_proximo_servicio`, `alerta_activa`, avisos previos.
`mantenimientos_registros` (13 col): servicios ejecutados, con `gasto_id` y `taller_proveedor`.

### Tarjeta y banco

**FACT.** `tarjetas_bancarias` — solo guarda `ultimos_4_digitos`, **nunca el número completo**.
`movimientos_bancarios` — movimientos con `estado_conciliacion` y `cruzado` (CHECK: `si`/`pendiente`).

### Otros términos

| Término | Significado | Estado |
|---|---|---|
| **Compensado** | — | **UNKNOWN** — no es un término del código de dominio: `consolidar_compensado()` es una función interna de liquidación. El nombre del módulo en el negocio sigue sin confirmar. Colisión con `saldo_neto` (B8). |
| **Flete neto** | Se calcula en el servidor, nunca en el cliente. | **FACT** (dónde se calcula) / **LECTURA** (qué resta exactamente) |
| **Legalizar** | Asociar una transacción de peaje a un gasto. | **LECTURA** — ver tabla de abajo. |
| **Anticipo** | Adelanto. Aparece en **tres** lugares distintos del modelo. | **LECTURA** — ver tabla de abajo. |
| **Secuencia** | `secuencias_documento`: contador atómico para números de ODT. No se resetea entre corridas de test. | **DECISION** (§7 de INSTRUCCIONES) |
| **Cierre de mes** | Liquidación mensual persistida; marca los viajes del período como `liquidado`. | **FACT** |

---

## Qué de este documento necesita confirmación del propietario

Este archivo mezcla **dos cosas distintas**:

| Tipo | Qué es | Estado |
|---|---|---|
| **FACT** (verificado) | Nombres de tabla y columna, FK, CHECK constraints, **expresiones GENERATED**, enums del código, valores observados. Todo sale del metadata de SQLAlchemy y de `information_schema.columns`. | **Verificado. Se puede commitear.** |
| **LECTURA** (interpretación) | Qué *significa* cada cosa en el negocio. | **Separado según la tabla de abajo.** |

### Estado de las lecturas, tras la revisión del 2026-09-26

Las expresiones GENERATED se leyeron **de la base**, no del código Python. Eso convirtió
tres de las seis en hechos y dejó tres realmente abiertas. Las tres abiertas **no son
deuda**: son preguntas con contexto medido, y quedan respondidas el día que exista el
caso real que las dispara.

| # | Lectura | Verificación | Estado |
|---|---|---|---|
| 1 | Qué es una liquidación | `saldo_neto` = `total_haberes` − 6 deducciones. **Haberes:** `comision_flete + bonificaciones + viaticos_reconocidos + otros_haberes + salario_basico + auxilio_transporte + papeleria`. **Deducciones:** `anticipos_entregados + gastos_a_cargo_conductor + prestamos + otros_descuentos + descuento_salud_pension + retiros_tarjeta_anticipos`. **FACT verificado contra `pg_get_expr`.** | **Cerrada** como hecho. |
| 2 | Gasto "fijo" | No existe el concepto en el código. `viaje_id` y `vehiculo_id` son ambos nullable, y eso **no implica** ninguna categoría. `gastos` está vacía: no hay evidencia de uso. | **UNKNOWN.** Se responde cuando exista el primer gasto sin viaje y el negocio le ponga nombre. |
| 3 | Legalizar | **Confirmado:** `flypass_transacciones.legalizado_en_gastos` es `GENERATED AS (gasto_id IS NOT NULL)`. **No existe campo de "quién legalizó" ni cuándo.** | **Cerrada**: es un link, no un acto administrativo. Si el negocio necesita responsable, es cambio de modelo. |
| 4 | Anticipo | **Confirmado como tres conceptos distintos:** `viajes_odt.anticipo_manifiesto` (componente contractual del flete) · `ingresos.tipo_ingreso='anticipo_manifiesto'` (movimiento de caja) · `liquidaciones_conductores.retiros_tarjeta_anticipos` (deducción en la liquidación). | **Cerrada**: no es uno, son tres. Documentarlos por separado. |
| 5 | Compensado | Confirmado que **no es un término del código de dominio**: existe `consolidar_compensado()` (`operaciones.py:161`) como función *interna*, y `COMPENSADO_RC` aparece en comentarios y nombres de migración. El nombre del módulo en el negocio sigue sin confirmar. | **UNKNOWN.** Si el negocio usa la palabra, se documenta; si no, se descarta del glosario. |
| 6 | Cliente | Confirmado: FK a `proveedores.id`, `tipo` sin CHECK, y **ningún valor vivo** representa a un cliente (`combustible` 6, `pasarela_pagos` 1, recontado 2026-09-26). | **UNKNOWN**, bloqueada por **B1** (`DECISIONS-PENDING.md` D1). |

> **Por qué 3, 5 y 6 siguen UNKNOWN.** No se promovieron a hecho porque no hay evidencia
> para hacerlo, y **"UNKNOWN" es el estado correcto**: la alternativa sería inventar
> vocabulario. Se resuelven con el dato del negocio, no con más análisis del código —
> el código ya se leyó completo y no dice qué palabras usa la operación.

### Una tercera colisión, que no estaba en la lista

`legalizado` aparece en **dos tablas con definiciones distintas**, y ninguna implica la otra:

| Columna | Definición real |
|---|---|
| `gastos.legalizado` | `GENERATED AS (estado_pago = 'legalizado')` — depende del **estado de pago** |
| `flypass_transacciones.legalizado_en_gastos` | `GENERATED AS (gasto_id IS NOT NULL)` — depende de la **existencia del vínculo** |

Un `gasto.legalizado = true` **no implica** que su peaje esté legalizado, ni al revés. Es el
mismo patrón que `saldo_neto` (B8): **mismo nombre, fórmulas distintas, números plausibles y
equivocados.**

> **`legalizado` no lo escribe ningún flujo automático, pero no se puede eliminar.**
> Verificado 2026-09-26: la única asignación de `estado_pago` en `backend/app` es
> `flypass_import.py:449` → `'pendiente_por_pagar'`. **Nadie pone `'legalizado'` solo.**
> Sin embargo `GastoCreate` **lo acepta sin mirar la `categoria`** (`schemas/gasto.py:53`),
> así que un gasto de mantenimiento con `estado_pago="legalizado"` es alcanzable por API
> — y `gastos.legalizado` es `GENERATED` sobre ese valor (`operaciones.py:135`).
> **Quitar `'legalizado'` del CHECK haría caer la columna entera.** Por eso la migración
> de reconciliación **no elimina el valor**: unifica las dos definiciones.

**Pregunta abierta (B9/D8):** ¿el negocio necesita marcar un gasto `legalizado` por una
vía que **no** sea el cruce con un peaje? **UNKNOWN** — no hay caso de uso identificado.
Si la respuesta alguna vez es NO, la migración es de **3 partes y reconcilia**, no elimina:
unificar las dos definiciones en una, con CHECK único, validador coherente y la columna
GENERATED expuesta en `GastoResponse`. Si es SÍ, `gastos.legalizado` deja de poder derivarse
de `estado_pago` y pasa a ser campo propio.

**Cómo resolver lo que queda:** #2, #5 y #6 necesitan vocabulario del negocio, no código.
Si no se responden quedan como `UNKNOWN`, que es una respuesta válida; lo que no
es válido es promoverlas a hecho sin confirmarlas.

### La fórmula se documenta literal, y `pg_get_expr` es la fuente

La fórmula de `saldo_neto` se escribe **completa y literal** en este documento, con
`pg_get_expr` como fuente de verdad declarada. Se eligió literal y no "referencia +
link a la migración" por un criterio de detección: **una fórmula abreviada se nota
al leer** — un humano ve que falta un término — mientras que con una referencia el
error no aparece hasta que alguien pregunta. *(Este documento tuvo exactamente ese
error: la misma columna aparecía con dos fórmulas distintas en dos lugares.)*

Cuando cambien los haberes o las deducciones, se actualiza esta línea **y** se
verifica contra `pg_get_expr`. La base manda, no este documento.

---

## Regla de este documento

Si un agente necesita agregar una entidad, una columna o una regla: **no la escriba aquí
directamente**. O es **DECISION** (ADR) o es **PROPOSAL** (preguntar) o queda **UNKNOWN**.
Este glosario refleja el código; no lo adelanta.
