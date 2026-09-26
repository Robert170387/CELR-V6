# UX-PATTERNS.md — patrones de interfaz

Todo **FACT** por observación del código. La lesson más importante de este documento está
al final y no es un patrón visual.

## Sistema visual

### Layout base

| Elemento | Clase | Uso |
|---|---|---|
| Contenedor de página | `space-y-4` | Vertical rhythm entre bloques |
| Card | `card-truck` | Fondo de card/tabla/modal |
| Input / select | `input-truck` | **Con `pl-10` si lleva ícono a la izquierda** |
| Botón primario | `btn-celr` | Acción principal |
| Botón secundario | `py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700` | Cancelar |
| Tabla | `overflow-x-auto` + `table w-full text-sm` | Wrapper **obligatorio** |
| Encabezado de tabla | `text-left text-slate-400 border-b border-slate-700` + `th py-2 px-3` | |
| Fila | `border-b border-slate-800 last:border-0 hover:bg-slate-800/40` | |
| Celda | `py-3 px-3` | |
| Caja de error | `bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg` | |
| Caja de éxito | `bg-green-500/10 border border-green-500/30 text-green-400 ...` | |
| Caja de aviso | `bg-amber-500/10 border border-amber-500/30 text-amber-400 ...` | |
| Badge | `{color}-500/20 text-{color}-400` + `px-2 py-1 rounded text-xs font-medium` | |
| Página pública | `PublicShell` | Fondo centrado + card `glass rounded-xl p-8` |

**No hay librería de componentes.** No hay shadcn, MUI ni similar. Tailwind con clases
compuestas a mano. `frontend/src/components/ui/` existe pero no es un design system.

### Paleta por significado

| Color | Significado | Usado en |
|---|---|---|
| `green-400` | Activo, pagado, legalizado, éxito | Estado de cuenta, pago |
| `slate-400` | Inactivo, neutro, texto secundario | |
| `blue-400` | `en_curso`, primario de datos | |
| `yellow-400` | `programado`, pendiente | |
| `purple-400` | `liquidado`, administrador | |
| `cyan-400` | `contador` | |
| `amber-400` | `supervisor`, avisos | |
| `red-400` / `danger-500` | `cancelado`, error | |

## Modales

**FACT** — No hay componente `Modal` compartido. **Cada página inlinea**:

```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
  <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
    {/* header con título + X */}
    {/* cuerpo */}
  </div>
</div>
```

**Excepción documentada:** `components/PublicShell.tsx` sí es compartido, y está justifiable
porque son **tres pantallas completas** con el mismo chrome público (fondo, marca, card), no
tres modales.

### Reglas de un modal

1. `max-h-[90vh] overflow-y-auto` — obligatorio si el contenido puede crecer.
2. Botón de cerrar `X` en el header. Siempre.
3. El error va **dentro** del modal, arriba del body. Si el error corresponde a una acción
   que **no abrió** modal, no puede ir dentro: va en una caja a nivel de página.
4. While enviando: `disabled` + spinner. Nunca dejar doble submit.

## Tablas y paginación

```tsx
<Pagination total={total} page={pagina} pageSize={PAGE_SIZE} onPage={setPagina} />
// skip: (pagina - 1) * PAGE_SIZE
```

**FACT** — `Pagination` devuelve `null` si hay una sola página. No hay que ocultarlo a mano.

**FACT** — El total viene del header `X-Total-Count`, leído por `conTotal<T>(r)`. El listado
devuelve **array plano**, no `{data, total}`. Con body, la UI muestra 0 elementos con el array
lleno. Detalle en `SYSTEM.md`.

**FACT** — `conTotal` necesita **tipo explícito**: su parámetro es `any`, así que
`.then(conTotal)` deja `data` como `unknown[]`. El repo ya lo hace así en `viajesAPI`.

## Filtros

**Convención del repo:** select de estado + botón "Aplicar" + botón "Limpiar". Los filtros
**no** se aplican en cada keystroke: se aplican con un botón, porque cada cambio dispara una
petición.

## Formularios

- Label siempre. `text-sm font-medium text-slate-300 mb-1`.
- Campo requerido: `<span className="text-red-400"> *</span>`.
- `inputMode` para teclado móvil correcto: `numeric` en códigos, `text` en cédula.
- **Cédula nunca con `type="email"`** — el navegador rechazaba cédulas antes de enviar (A2).
- Los mensajes de validación del backend se muestran **textuales**, no genéricos:
  `extraerMensajeError(err)` prefiere `response.data.detail` sobre el status.

## Paginación de filtros vs. búsqueda

**FACT** — El backend no expone búsqueda de texto. El filtro de texto de `GestionUsuarios.tsx`
opera **sobre la página visible**, y la UI lo dice explícitamente en pantalla. No prometer
búsqueda global si el endpoint no existe.

---

## La lección: verificar el flujo de ERROR primero

**FACT** — En la pantalla de gestión de usuarios pasaron **4 bugs que ninguna verificación de
endpoint podía detectar**, porque el backend respondía correctamente y la UI descartaba la
respuesta:

| Bug | Qué veía el usuario |
|---|---|
| El `catch` de reset abría el modal de **crear usuario** | Un formulario de alta con un error de contraseña adentro |
| `setErrorModal` se pintaba sin modal abierto | **Nada.** 403 totalmente silencioso |
| El check de "Copiado" leía un campo que solo se escribía en `false` | La copia funcionaba y **no confirmaba nada** |
| `catch` mudo en `navigator.clipboard.writeText` | Clic y ninguna señal de si copió |

**Y uno más, en otra capa:** el interceptor de 401 de `apiClient` veía el 401 de
"token inválido" de `/auth/reset-password` como "sesión expirada", intentaba refrescar, fallaba
y **expulsaba al usuario a `/login` sin mostrar el error**. Eso era invisible a las pruebas de
endpoint **y** a las pruebas de UI del camino feliz.

### Regla

> **Cuando agregues una pantalla, ejercita PRIMERO los caminos de error, después el feliz.**
> 403 · 409 · 422 · 401 · timeout · y **qué ve el usuario si el portapapeles falla**.

El camino feliz es el que ya funciona y el ojo lo detecta. El camino de error es el que
funciona hasta que nadie lo prueba.

### Herramienta

**FACT** — Se verificó con Chrome headless por CDP (sin dependencias: `node` con el `WebSocket`
nativo), accionable: navegar, escribir, hacer clic, leer el DOM, capturar pantalla y **leer el
portapapeles real** para compararlo contra lo que la pantalla muestra.

Dos trampas que ya costaron tiempo:

1. **El service worker sirve el bundle viejo.** Antes de concluir que un fix no surtió efecto:
   `Ctrl+Shift+R` o desregistrar el SW en DevTools → Application → Service Workers.
2. **`GET /usuarios` responde array plano con `X-Total-Count`.** Si esperabas `{data, total}`,
   la tabla queda vacía sin error visible.

## Accesibilidad — estado actual

**UNKNOWN / no implementado.** No haylabels asociados con `htmlFor` de forma consistente, ni
`aria-*`, ni navegación por teclado para modales, ni foco atrapado. **No prometer accesibilidad.**
Si es requisito, es trabajo nuevo con su propio ADR.
