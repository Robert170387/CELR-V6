---
name: Domain Transport
description: Procedimiento para trabajar sobre la flota física (vehículos, conductores, proveedores, tarjetas, mantenimiento) sin inventar reglas. Usar al tocar vehiculos, conductores, proveedores, tarjetas o mantenimiento.
---

# Trabajar sobre la flota sin inventar el negocio

> Este skill **no contiene las reglas de la flota**: no están en el repositorio. Contiene las
> restricciones técnicas, las trampas de modelado y los `UNKNOWN` conocidos. Para el
> significado de cada entidad: `docs/02-domain/GLOSSARY.md`.

## ⚠️ La trampa de "cliente"

**No existe una tabla `clientes`.** `ingresos.cliente_origen_id` es FK a **`proveedores.id`**.

Lo que distingue a un "cliente" de un taller o un proveedor de combustible es
`proveedores.tipo`, que es **texto libre sin CHECK constraint**. En los datos actuales solo
existen los valores `combustible` y `pasarela_pagos`: **no hay ningún valor que represente a
un cliente**.

**Consecuencia práctica:** un cambio que "agregue soporte de cliente" tiene que decidir primero
cómo se modela. Crear una tabla `clientes` es un **refactor de datos** con migración, y tocar
`cliente_origen_id` afecta ingresos. **Es decisión de negocio, no técnica.**

## Un conductor no tiene `vehiculo_id`

La relación conductor↔vehículo vive en la tabla aparte `conductor_vehiculo` (8 columnas), con
`es_principal` y vigencia (`fecha_inicio`, `fecha_fin`).

Un vehículo **tampoco** tiene `conductor_id`. Si necesitás "el conductor actual de este
vehículo", consultá `conductor_vehiculo` con la vigencia y `es_principal`. **No lo asumas.**

## Un usuario puede o no tener conductor

`usuarios.conductor_id` es nullable con **UNIQUE parcial** (solo entre valores presentes).
Refuerza la cardinalidad 1:1 del módulo de identidad (ADR-0002).

`usuarios.correo` es nullable. **Consecuencia para tests:** un temporal sin correo tiene
`correo IS NULL` y **no se encuentra buscando por correo**. Rastrear por `id`.

## `veiculos.km_actual` y el mantenimiento

`km_actual`, `km_inicial_sistema`, y las reglas de mantenimiento con
`km_proximo_servicio` / `fecha_proximo_servicio` / `alerta_activa` conviven. Los kilometrajes
salen del ODTS, del gasto de combustible (`km_registro`) y de los servicios registrados.

**UNKNOWN**: cómo se reconcilian cuando las fuentes no coinciden. No lo implementes sin que se
pida.

## Tarjetas bancarias

`tarjetas_bancarias` guarda **solo `ultimos_4_digitos`**, jamás el número completo. No es una
omisión: es una garantía. No la "completes".

## `UNKNOWN` conocidos

- Valores válidos de `vehiculos.estado` y `vehiculos.tipo_carroceria`. **No hay CHECK.**
- Valores válidos de `conductores.estado`. **No hay CHECK.**
- `mantenimientos_reglas.tipo_servicio`. **No hay CHECK.**
- Si hay un job que escriba las alertas de `documentos_vencimientos` (`alerta_30/15/5_enviada`).
  Las columnas existen; **no hay evidencia de que algo las escriba**.
- Si `conductor_vehiculo` tiene más de un conductor principal por vehículo y cómo se resuelve.

## Procedimiento

1. Leer el glosario. Separar lo `FACT` de lo `UNKNOWN`.
2. Verificar el esquema real: `docker exec celr_v6_db psql -U postgres -d celr_v6_db -c "\d vehiculos"`.
3. **Preguntar al usuario** lo que sea `UNKNOWN` antes de diseñar.
4. Si agregás un campo con dominio cerrado: usar **CHECK constraint** o `Enum`, y documentar los
   valores. No repetir el patrón de `vehiculos.estado`.
5. Migración ⇒ skill `database-alembic`.
6. Si toca el CRUD de cuentas ⇒ `backend/app/api/v1/endpoints/usuarios.py` y la matriz
   `ROLES_OBJETIVO_POR_EJECUTOR` (4 consumidores). Cambiarla afecta a 4 operaciones.
7. UI ⇒ skill `ux-patterns`, **camino de error primero**.
