---
name: Domain ODT
description: Procedimiento para cambiar reglas del documento de transporte (ODT/viaje) sin inventar reglas de negocio. Usar al tocar viajes_odt, flete, comisiones, retenciones, liquidaciones o estados de viaje.
---

# Trabajar sobre la ODT sin inventar el negocio

## Lo primero, y no es opcional

> **Este skill no contiene las reglas de negocio de la ODT.** No están en el repositorio, y
> **no se adivinan**. Lo que sí hay son restricciones técnicas y los `UNKNOWN` conocidos.

Antes de proponer cualquier cambio, leer `docs/02-domain/GLOSSARY.md` y
`docs/00-context/BUSINESS.md`. Si la regla que necesitás no está ahí, es `UNKNOWN`:
**preguntá, no la inventes**.

## La ODT es la tabla central

`viajes_odt` (43 columnas) es el eje: **gastos, ingresos y liquidaciones se le enganchan**.
Un cambio acá tiene efecto en tres dominios. Verificá los tres.

## Estados

`programado` · `en_curso` · `completado` · `liquidado` · `cancelado`

**El enum vive en el frontend y en la lógica — NO hay CHECK constraint en la BD.** Consecuencia:
una llamada directa a la API puede escribir un estado arbitrario. No "arregles" eso sin ADR:
agregaría un CHECK y rompería cualquier estado que hoy funcione.

**Campos requeridos por estado** (definición en `frontend/src/pages/Viajes.tsx`):
- `programado` / `en_curso`: `valor_flete_manifiesto`, `km_inicial`
- `completado`: los anteriores + `km_final`, `fecha_llegada`
- `cancelado`: ninguno

Al agregar un estado, actualizá **las dos** definiciones: la del frontend y la de validación del
backend. Que divergan produce un estado que el backend acepta y la UI no muestra.

## Los derivados se calculan en el servidor

`flete_neto`, `gastos_totales_viaje`, `utilidad_neta_odt` y `comision_conductor` se calculan
en el endpoint. **Nunca en el cliente.** Si el cálculo vive en dos lados, divergen.

## Secuencia de `numero_odt`

UPSERT atómico sobre `secuencias_documento` (`app/services/secuencias.py`). Debe correr **en la
misma transacción** que el commit del endpoint, o se pierde la secuencia.

**La secuencia no se resetea** entre corridas de tests ni de E2E (decisión registrada).

## Liquidaciones

- `liquidado` es terminal: volver a liquidar da **400**.
- El cierre **mensual** marca los viajes del período como `liquidado` **en la misma transacción**.
- Cerrar un mes da **409** si ya hay liquidaciones del período en estado final.
- `bloqueos_cierre_odt` devuelve dos bloqueos (Flypass pendiente, saldo no cubierto) pero
  **solo se fuerza el de Flypass** (decisión B6, pendiente de negocio). No "arregles" el saldo.

## `saldo_neto` significa dos cosas — no lo resuelvas por tu cuenta

Saldo operativo de la ODT vs. neto del conductor. Es la decisión abierta **B8**. Está
documentada en `ALINEACION_MODELO_NEGOCIO.md` §6.1 con las opciones. **Esperá al usuario.**

## `UNKNOWN` conocidos en este dominio

- Tasas de retención (retefuente/reteica): los porcentajes **son columnas**, los valores no están.
- Si la comisión se calcula sobre el flete bruto o el neto: **no está documentado**.
- Días de corte del cierre mensual, y si el mes es calendario o de operación.
- Si nacional y urbano están ambos activos.
- Regla de `asumido_por='owner'` (**B7**).

## Procedimiento

1. Leer el glosario y `BUSINESS.md`. Anotar qué es `UNKNOWN`.
2. Verificar el esquema real: `docker exec celr_v6_db psql -U postgres -d celr_v6_db -c "\d viajes_odt"`.
3. **Preguntar al usuario** lo que sea `UNKNOWN` antes de diseñar.
4. Tocar backend **y** frontend juntos si el cambio afecta validación visible.
5. Si cambia el cálculo de un derivado: **suite que falle si cambia**, no un test de ejemplo.
6. Migración ⇒ skill `database-alembic`.
7. UI ⇒ skill `ux-patterns`, y **camino de error primero**.
