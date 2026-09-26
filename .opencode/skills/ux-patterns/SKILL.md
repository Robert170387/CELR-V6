---
name: UX Patterns
description: Procedimiento para construir o revisar pantallas: estados obligatorios, modales, tablas, formularios y verificación visual por render. Usar al crear una pantalla nueva o al evaluar cómo se ve y qué ve el usuario cuando algo falla.
---

# Construir y revisar pantallas

## La norma que define este trabajo

> **Verificá el flujo de ERROR primero. El feliz después.**

El camino feliz ya funciona y el ojo lo detecta. El de error funciona **hasta que alguien lo
prueba**. En `GestionUsuarios.tsx` hubo **4 bugs que ninguna prueba de endpoint podía ver**,
porque el backend respondía bien y la UI descartaba la respuesta.

| Bug | Qué veía el usuario |
|---|---|
| El `catch` de reset abría el modal de **crear usuario** | Formulario de alta con un error de contraseña |
| `setErrorModal` pintado sin modal abierto | **Nada** |
| Check de "Copiado" leyendo un campo escrito solo en `false` | Copiaba y no confirmaba |
| `catch` mudo en `writeText` | Clic sin señal |

## Checklist de estados de una pantalla

| Estado | Qué se ve |
|---|---|
| Cargando | Spinner. **No** una tabla vacía. |
| Vacío | Mensaje + qué hacer. No solo "no hay datos". |
| Con datos | — |
| Error de lista | Caja a nivel de página con el motivo del servidor |
| Error dentro de modal | Caja **dentro**, el modal sigue abierto |
| **Acción sin modal** (reset, activar) | Su error va a **nivel de página** |
| Éxito | Confirmación visible + camino a lo que sigue |
| Destructivo | type-to-confirm: escribir el identificador del objetivo |
| Fallo del navegador | Aviso explícito. Nunca clic mudo. |

## Sistema visual

`card-truck` · `input-truck` · `btn-celr` · `space-y-4` · badges `{color}-500/20 text-{color}-400`.
Cajas: `bg-danger-500/10` (error), `bg-green-500/10` (éxito), `bg-amber-500/10` (aviso).

Colores con significado fijo: verde activo/pagado, azul `en_curso`, amarillo `programado`,
púrpura `liquidado`, rojo `cancelado`.

## Modales

```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
  <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
```

`max-h-[90vh] overflow-y-auto` si puede crecer. Botón `X` siempre. `disabled` + spinner
mientras envía.

**Excepción justificada:** `components/PublicShell.tsx` es compartido porque son **tres
pantallas completas** con el mismo chrome, no tres modales. El repo no tiene componente Modal.

## Verificación visual

Un build verde **no** significa que la pantalla se vea bien.

**Con el usuario:** abrir la pantalla y **describir qué se ve**. Pedir captura si algo no
cuadra. Es la única forma de validar si el layout le resulta cómodo a una persona.

**Sin el usuario:** Chrome headless por CDP, **sin dependencias** — `node` con el `WebSocket`
nativo. Permite navegar, escribir, hacer clic, leer el DOM, capturar pantalla y **leer el
portapapeles real** para compararlo contra lo que la pantalla muestra.

Comprobaciones que esa técnica sí permite y una prueba HTTP no:
- ¿la tabla renderiza con datos?
- ¿el modal aparece donde corresponde?
- ¿el botón "Copiar" pone el valor correcto en el portapapeles?
- ¿el error se ve, o es invisible?
- ¿la fila propia ofrece acciones que el backend va a rechazar con 403?

**Trampa antes de todo:** `Ctrl+Shift+R` o desregistrar el service worker.

## No prometas accesibilidad

Hoy no hay `aria-*` consistente, ni foco atrapado en modales, ni navegación por teclado, ni
labels asociados de forma uniforme. Si es requisito, es trabajo nuevo con su propio ADR.

Detalle: `docs/03-ux/UX-PATTERNS.md`.
