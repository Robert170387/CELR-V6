---
name: OCR Documents
description: Procedimiento para trabajar con lectura de recibos por OCR, el importador de Flypass y los documentos con vencimiento. Usar al tocar reconocimiento de texto, carga de comprobantes o importación de archivos.
---

# OCR, comprobantes y documentos

## Piezas

| Pieza | Ubicación |
|---|---|
| Servicio de OCR | `backend/app/services/ocr_service.py` |
| Motores | `backend/app/services/ocr_engines.py` |
| Parser | `backend/app/services/ocr_parser.py` |
| Importador Flypass | `backend/app/services/flypass_import.py` |
| Vencimientos | tabla `documentos_vencimientos` |
| Suite OCR | `backend/scripts/test_ocr.py` |

## Motor OCR

- **Tesseract local** es el default (`OCR_ENGINE=tesseract`). Necesita el binario **y** el
  idioma `spa`; el `Dockerfile` los instala.
- **Google Vision** requiere **descomentar** la dependencia `google-cloud-vision` en
  `requirements.txt`. Trae costo. Es la decisión de negocio **B5** — no la tomes por tu cuenta.

## Detección de duplicados

`gastos.hash_comprobante` se calcula con la foto + metadata. Un hash reenviado ⇒ **400
"Gasto duplicado"**, en el servidor. Es la defensa contra la doble carga del mismo recibo.

**No lo degrades a una comparación en el cliente.** Es una garantía de integridad contable.

## Flag `estado_validacion`

La columna existe en `gastos`. **UNKNOWN**: no hay CHECK, no hay valores que la usen, y en la
BD está vacía. No asumas que hay un flujo de aprobación debajo: `aprobado_por` y
`fecha_aprobacion` existen como columnas **sin lógica que las escriba**.

## Importador Flypass

`POST /api/v1/flypass/import` acepta `.xlsx` (máx. 5 MB), protegido por roles financieros.
Primera hoja con encabezados: `TRANSACCION`, `PLACA`, `FECHA_MVTO`, `MONTO`, `PUNTO ATENCION`.

- Conserva la fila original en `flypass_transacciones.raw_data` (JSONB).
- Deduplica por `num_transaccion_flypass`.
- Resuelve la placa con `LEFT JOIN`.
- Matching de gastos `peajes` por vehículo, valor y fecha ±1 día.
- Sin match ⇒ crea el gasto con `estado_pago='pendiente_por_pagar'`, `metodo_pago='tag'`,
  proveedor `Flypass`.
- Al setear `gasto_id`, la transacción queda **legalizada**.

**La asociación a una ODT es best-effort** por vehículo y rango de fechas. No es determinista:
puede fallar sin que nada se rompa, y por eso el reporte incluye "sin ODT" y "ambiguos".

## Alertas de vencimiento

`documentos_vencimientos` tiene tres flags: `alerta_30_enviada`, `alerta_15_enviada`,
`alerta_5_enviada`. Las columnas existen; **no hay evidencia de un job que las escriba**.

**UNKNOWN**: si deben dispararse automáticamente. No implementes un cron sin que se pida.

## Procedimiento

1. ¿El motor es el correcto? Tesseract local **o** Vision (**B5**).
2. Para importadores: **la fila cruda se conserva siempre**. Es la única forma de re-procesar
   sin volver a pedir el archivo.
3. Para duplicados: el hash se calcula en el **servidor**. El cliente solo muestra.
4. Probá con un archivo real: los parsers fallan con datos raros, no con los limpios.
5. Verificá que el reporte de importación lista los casos no resueltos. Un importador que
   "siempre funciona" está escondiendo losses.

```powershell
venv\Scripts\python.exe scripts\test_ocr.py
venv\Scripts\python.exe scripts\test_flypass_import.py   # TF1–TF8
venv\Scripts\python.exe scripts\test_flypass_list.py      # TL1–TL9
```

Detalle: `docs/02-domain/GLOSSARY.md`.
