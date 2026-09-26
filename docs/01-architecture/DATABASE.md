# DATABASE.md — persistencia

**FACT** — PostgreSQL. 21 tablas. **Alembic es el mecanismo oficial de esquema.**

> `init_db.py`, `schema_celr_v6.sql` y `backend/scripts/migrate_*.py` son **históricos**.
> No usarlos en BD nuevas. `schema_celr_v6.sql` sirve como documentación del esquema.

## Conexión

```
postgresql://postgres:admin@localhost:5433/celr_v6_db
```

**FACT** — `core/config.py` normaliza `postgres://` → `postgresql://` (quirk de Aiven).
`backend/.env` apunta a `:5432` (otro proyecto): **siempre** exportar la variable de entorno.

## Cadena de migraciones

**FACT** — Baseline `a5b6b344c873` (`create_all` desde los modelos). En BD vacía construye todo;
en BD existente es no-op. Head actual: `f6a7b8c9d0e1`.

| Revisión | Qué |
|---|---|
| `a5b6b344c873` | Baseline `create_all`. |
| `f2e1d0c9b8a7` | Cierre mensual B2. |
| `a1b2c3d4e5f6` | Guardas simples (`password_version`, `raw_data`). |
| `d4e5f6a7b8c9` | A1: `cedula`, `correo` nullable, `conductor_id` UNIQUE parcial. |
| `e5f6a7b8c9d0` | A3.1: `password_reset_token`. |
| `f6a7b8c9d0e1` | A3.4: `auditoria_evento`. |

## Tablas

**FACT** — Extraído del metadata de SQLAlchemy. Columnas exactas.

### Identidad

| Tabla | Col | Notas |
|---|---|---|
| `usuarios` | 12 | `cedula` UNIQUE NULL, `correo` nullable, `rol` CHECK, `conductor_id` UNIQUE **parcial**, `activo`, `debe_cambiar_contrasena`, `password_version`, `ultimo_acceso`. |
| `refresh_tokens` | 7 | `token_hash` (sha256, nunca el token en claro), rotación con `revocado` + `usado_en`. |
| `password_reset_token` | 10 | `tipo` `enlace`\|`codigo`, `token_hash`, `expira_en`, `usado_en`, `revocado`, `intentos`, `intentos_max`. |
| `auditoria_evento` | 8 | `evento`, `usuario_actor_id`, `usuario_objetivo_id`, `ip`, `user_agent`, `detalle` JSONB, `creado_en`. |

### Flota y personal

| Tabla | Col | Notas |
|---|---|---|
| `vehiculos` | 16 | `placa`, `tipo_carroceria`, `capacidad_ton`, `km_actual`, `km_inicial_sistema`. |
| `conductores` | 13 | `porcentaje_comision_default`, licencia + vencimiento. |
| `conductor_vehiculo` | 8 | Asignación con `es_principal` y vigencia. |
| `tarjetas_bancarias` | 9 | Solo `ultimos_4_digitos`. |
| `proveedores` | 13 | `nit`, banco y cuenta para anticipos. |

### Operación

| Tabla | Col | Notas |
|---|---|---|
| `viajes_odt` | 43 | La tabla central. `numero_odt` por secuencia atómica. `flete_neto` **calculado en el servidor**. `eliminado_en`/`eliminado_por` ⇒ soft delete. |
| `gastos` | 33 | `hash_comprobante` para duplicados. `datos_ocr_json`. `eliminado_*` ⇒ soft delete. |
| `ingresos` | 17 | Siempre con `viaje_id`. `eliminado_*` ⇒ soft delete. |
| `liquidaciones_conductores` | 40 | `periodo_ym` GENERATED STORED con UNIQUE parcial cuando `es_cierre_mensual`. `viajes_ids` (array). `eliminado_*` ⇒ soft delete. |

### Soporte

`municipios` (4, catálogo DIVIPOLA) · `mantenimientos_reglas` (15) · `mantenimientos_registros` (13) ·
`documentos_vencimientos` (18) · `flypass_transacciones` (14, con `raw_data` JSONB) ·
`movimientos_bancarios` (12) · `configuracion_sistema` (4) · `secuencias_documento` (2).

## Vistas

### `v_odt_resumen` — 20 columnas, **0 lectores**

**FACT** (verificado 2026-09-26 contra `information_schema` y contra `backend/app`):
existe en la BD, tiene 20 columnas, y **nada en el código la lee ni la mapea en
SQLAlchemy**. La única mención en el código es un comentario que la sugiere como
fuente posible (`app/services/operaciones.py:223`).

Columnas, en orden: `id` · `numero_odt` · `anio` · `tipo_viaje` · `fecha_salida` ·
`vehiculo_id` · `conductor_id` · `empresa_manifiesto_id` · `num_manifiesto` ·
`valor_flete_manifiesto` · `retencion_fuente` · `retencion_ica` · `otras_deducciones` ·
`total_deducibles` · `flete_neto` · `comision_conductor` · `saldo_flete_esperado` ·
`gastos_totales_viaje` · `utilidad_neta_odt` · `km_recorridos`.

> **Fórmula verificada (2026-09-26, datos reales, diferencia 0.00 en ambos viajes):**
> `total_deducibles = retencion_fuente + retencion_ica + otras_deducciones`, y
> `saldo_flete_esperado = flete_neto - anticipo_manifiesto`.

> **Trampa — la vista no distingue "0 calculado" de "nunca calculado".**
> Son **7 `COALESCE`** en la definición. El caso grave no es `total_deducibles` sino
> `saldo_flete_esperado`: la vista **no lo toma de la tabla, lo recalcula** como
> `COALESCE(flete_neto,0) - COALESCE(anticipo_manifiesto,0)`. O sea que un snapshot
> que el servidor **nunca calculó** se ve como un saldo válido. Un resumen construido
> sobre la vista puede mostrar una cifra inventada, indistinguible de una real.

**Por eso R1 lee `viajes_odt` y no la vista.** Los snapshots se toman de la tabla, donde
un `NULL` sí significa "no calculado". Deuda registrada en
[`docs/05-tasks/BACKLOG.md`](../05-tasks/BACKLOG.md) (`v_odt_resumen-sin-mapeo`,
`coalesce-oculta-staleness`).

## Reglas de migración

**DECISION** — 1. Alembic es oficial. 2. Toda migración nueva usa **guards de existencia**.
3. Se valida con `test_fresh_db.py` antes de commitear.

**Motivo de los guards:** el baseline ejecuta `create_all` con los modelos vigentes, así que una
BD "vacía" y una ya migrada arrancan en estados distintos. Sin guards, la misma migración puede
fallar en una y no en la otra.

```python
if not _columna_existe("usuarios", "cedula"):
    op.add_column(...)
```

Helpers de referencia: `_columna_existe`, `_constraint_existe`, `_fk_existe`,
`_columna_es_nullable`, `_columna_es_generated`, `_vista_existe`.

`alembic.op` **no** expone `drop_view`/`create_view`: usar `op.execute(text("DROP VIEW IF EXISTS ..."))`.

### Revisiones absolutas, nunca `-1`

**FACT** — Ya rompió dos veces. `test_a1_guard_downgrade` usaba `downgrade -1` y, al agregar A3.1
encima, bajó **un paso** y nunca alcanzó el guard que decía verificar: fallaba por la razón
equivocada, que es peor que un fallo honesto porque entrena a ignorar el test.

**Regla:** `downgrade <revision_objetivo>`, y validar contra el head leído en el momento.

### `HEAD_REVISION` hardcodeado

**Deuda.** `test_fresh_db.HEAD_REVISION` es una constante. Al agregar una revisión hay que
actualizarla, o la precondición aborta la suite antes de empezar (síntoma:
`Precondición fallida: alembic_version=...`).

## Soft delete

**FACT** — `viajes_odt`, `gastos`, `ingresos` y `liquidaciones_conductores` tienen
`eliminado_en`/`eliminado_por`. **No hay borrado físico** en el flujo normal.

**Consecuencia:** los borrados de `usuarios` de los tests chocan con
`refresh_tokens.usuario_id`, que es FK **sin `ON DELETE CASCADE`**. Es el guardrail correcto
(el producto no borra usuarios), pero en tests significa: **borrar en orden inverso de FK y
dentro de una transacción, y verificar después.**

## `auditoria_evento` es append-only

**FACT** — Por **convención**, no por restricción: nada impide `UPDATE`/`DELETE`.

**FACT** — Crece con cada login. **No se limpia para cuadrar un gate.** Es un log, no un estado.
Lo único que se limpia es lo que genera `test_auditoria.py`, y solo lo suyo.

**Límite conocido:** `usuario_objetivo_id` es FK a `usuarios`, así que auditar una entidad que no
sea usuario no es posible con este esquema. Alternativa futura: `objetivo_tipo + objetivo_id`
sin FK. **Deuda documentada, no resuelta.**

## Índices que faltan

- **A2.1** — índices funcionales sobre `lower(cedula)` / `lower(correo)`. `func.lower()` **no**
  usa los índices actuales.
- `conteo-admins-cache` — `es_ultimo_admin_activo` hace COUNT por llamada. Candidato a índice
  parcial `WHERE rol='admin' AND activo`. Hoy es correcto y barato.

## Ver la BD

```powershell
docker exec celr_v6_db psql -U postgres -d celr_v6_db -P pager=off -c "\dt"
```

**Conteo de tablas** para los 21 nombres exactos está en el paso 3 de la skill
`database-alembic`.
