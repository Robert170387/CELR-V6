# BUSINESS.md — el negocio

> Todo en este documento está marcado. Lo que no pude confirmar contra el código o contra una
> decisión registrada está como **UNKNOWN** y **no debe completarse por inferencia**.

## Qué vende la empresa

**FACT** — El sistema gestiona transporte de carga. La unidad de negocio central es la **ODT**
(Orden de Transporte): un documento de/manifiesto de carga con un vehículo, un conductor, una
ruta origen→destino, un flete y deducciones.

**FACT** — El modelo de ingresos es una operación: se factura un flete, se descuentan
retenciones (retefuente, reteica), se calculan comisiones al conductor y se liquida por período.

**UNKNOWN** — Modelo de negocio específico (cantidad de trucks, cobertura geográfica, si opera
propio o como operador, esquema de tarifas). No está en el repositorio. Requiere al usuario.

## Glosario de negocio

El detalle técnico de cada entidad está en [`../02-domain/GLOSSARY.md`](../02-domain/GLOSSARY.md).
Acá va el significado de negocio.

| Término | Significado | Estado |
|---|---|---|
| **ODT** | Orden de Transporte. El documento que formaliza un viaje de carga. Es el eje del modelo: gastos, ingresos y liquidaciones se le enganchan. | **FACT** (`viajes_odt`, 43 columnas) |
| **Flete** | Lo que se cobra por el transporte. `valor_flete_manifiesto` es el bruto declarado; `flete_neto` se calcula en el servidor. | **FACT** |
| **Tractocamión** | El vehículo de carga. En el modelo es `vehiculos` con `tipo_carroceria`, `capacidad_ton`. | **FACT** |
| **Conductor** | Persona que opera. Tiene licencia, categoría, comisiones. `porcentaje_comision_default` individual. | **FACT** |
| **Cliente** | Quien paga el flete. En `ingresos` aparece como `cliente_origen_id`. | **PARTIAL** — no hay tabla de clientes; ver GLOSSARY |
| **Proveedor** | Quien cobra un gasto: taller, combustible, peaje. Con NIT, banco y cuenta para anticipos. | **FACT** |
| **Gasto** | Egreso. Puede belong a un viaje, a un vehículo, o ser fijo (mantenimiento sin ODT). | **FACT** |
| **Ingreso** | Entrada de caja. Siempre ligado a un viaje. | **FACT** |
| **Liquidación** | settlement al conductor: comisiones − deducciones. | **FACT** (`liquidaciones_conductores`, 40 columnas) |
| **Municipio** | División territorial. Alimenta el autocomplete de ciudades y respalda la geometría. | **FACT** (`municipios`, catálogo DIVIPOLA) |
| **Peaje** | Transacción de peaje, importada desde el archivo de Flypass. | **FACT** (`flypass_transacciones`) |
| **Documento** | Factura, comprobante, licencia. Con vencimiento y alertas. | **FACT** (`documentos_vencimientos`) |
| **OCR** | Lectura automática de recibos en foto → datos del gasto. | **FACT** (`datos_ocr_json`) |
| **Anticipo** | Adelanto entregado al conductor o pagador a un proveedor. Se descuenta en liquidación. | **FACT** (`retiros_tarjeta_anticipos`, `anticipo_manifiesto`) |
| **Comisión** | Porcentaje del flete que gana el conductor. Configurable por ODT. | **FACT** (`porcentaje_comision`) |
| **Compensado** | | **UNKNOWN** — `saldo_neto` designa tanto el saldo operativo de la ODT como el neto del conductor. Colisión documentada como B8 en `ALINEACION_MODELO_NEGOCIO.md` §6.1. **No desambiguar por inferencia.** |

## Cierre mensual

**FACT** — `liquidaciones_conductores` soporta dos modos:
- **Quincenal / por viaje:** se liquida un conjunto de ODTs.
- **Mensual:** `es_cierre_mensual` + `periodo_ym` (GENERATED STORED, UNIQUE parcial).
  Persistido vía `POST/GET /api/v1/liquidaciones/cierre-mensual`, con reapertura y cancelación.

**FACT** — El cierre mensual marca los viajes del período como `liquidado` en la misma
transacción. Volver a liquidarlos da 400.

**FACT** — Cerrar un mes exige que no queden liquidaciones del período en estado final, y da
409 si ya existen viajes del período liquidados.

**UNKNOWN** — Días de corte, si el mes es calendario o de operación, y quién autoriza el
cierre. No está en el código.

## Comisiones y deducciones

**FACT** — La comisión del conductor se puede fijar por ODT (`porcentaje_comision`) o tener
un valor por defecto en el conductor (`porcentaje_comision_default`).

**FACT** — La ODT guarda retenciones como par porcentaje/valor: `retefuente_porcentaje` /
`retefuente_valor`, `reteica_porcentaje` / `reteica_valor`. Y `anticipo_manifiesto` +
`saldo_flete_esperado`.

**UNKNOWN** — Tasas de retención, si cambian por año, y quién las carga al conductor. No
consta. No hardcodear.

## Regla 4 (componente saldo)

**FACT** — `bloqueos_cierre_odt` devuelve dos bloqueos: Flypass pendiente y saldo no cubierto.
**Solo el Flypass se fuerza** en el cierre. Forzar el saldo bloquearía 15/18 ODTs activas,
incluidas 9 ya liquidadas.

**DECISION** — B6, pendiente de negocio. Ver `INSTRUCCIONES_OPENCODE.md` §8.

## Reglas que NO se pueden confirmar con el repositorio

- Tarifas, listas de precios, contratos con clientes.
- Política de comisiones por tipo de ruta o cliente.
- Quién puede aprobar un gasto, y el flujo de aprobación (`aprobado_por`, `fecha_aprobacion`
  existen como columnas; **el flujo no está implementado** — **UNKNOWN**).
- treatment de `asumido_por='owner'`. **UNKNOWN** — es una de las columnas sin regla
  documentada (B7).
- Si el negocio es nacional, urbano, o ambos. `tipo_viaje` acepta `urbano`, `nacional`,
  `internacional`, `vacio`, y la liquidación distingue `viajes_nacionales` / `viajes_urbanos`.
  **UNKNOWN** si ambos están activos.

## Cómo agregar una regla de negocio

1. No la escribas en código sin registrarla.
2. Si viene del usuario → es **DECISION**: necesita un ADR en [`../04-decisions/`](../04-decisions/).
3. Si se te ocurre a ti → es **PROPOSAL**. Pregunta. No la implementes.
4. Si no se puede determinar → **UNKNOWN**, y déjalo marcado.
