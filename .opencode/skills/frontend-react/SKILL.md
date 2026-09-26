---
name: Frontend React
description: Procedimiento para crear o modificar páginas, componentes, estado y rutas del frontend React+Vite+TS. Usar para cambios de UI que no sean específicamente de la cola offline PWA.
---

# Agregar o modificar una pantalla

## El gate

```powershell
npm.cmd run build      # incluye tsc -b — ES el gate, no solo el build
```

TS estricto: `noUnusedLocals` y `noUnusedParameters`. **Un import sin usar rompe el build**, y
eso es intencional.

## Antes de escribir

1. `docs/03-ux/UX-PATTERNS.md` — el sistema visual completo.
2. Skill `ux-patterns` si la tarea es evaluar cómo se ve. **Verificá el flujo de error primero.**
3. ¿Existe ya un patrón? **Copiá el de otra página** antes de inventar.

## Sistema visual (resumen)

`card-truck` · `input-truck` (`pl-10` con ícono) · `btn-celr` ·
`py-2 px-4 rounded-lg bg-slate-800` secundario · `space-y-4` de página.
Tabla: `overflow-x-auto` + `table w-full text-sm` + `th py-2 px-3` + `tr hover:bg-slate-800/40`.
Caja de error: `bg-danger-500/10 border border-danger-500/30 text-danger-500`.

**No hay librería de componentes.** No agregues una.

## Reglas que se rompen seguido

### `conTotal` necesita tipo explícito

```ts
listar: (params) => apiClient.get<X[]>('/x', {params}).then((r) => conTotal<X>(r))
```

Su parámetro es `any`, así que `.then(conTotal)` deja `data` como `unknown[]` (ADR-0004).

### Ruta nueva ⇒ registrala en `ACCESO_POR_MODULO`

`puedeAccederModulo` devuelve **`true` para paths no registrados**. Sin registrar,
`RequireRole` deja pasar a cualquiera y el 403 llega tarde, con la pantalla a medias.

### Rutas públicas antes del catch-all

El `/*` vive **dentro** de `ProtectedRoute`. `/recuperar`, `/reset-password`, `/reset-codigo`
van **antes** o nunca se ven sin sesión.

### Todo estado necesita UI que lo lea

Un `setX` sin nada que lo muestre es un bug esperando. En `GestionUsuarios.tsx` el check de
"Copiado" leía un campo que solo se escribía en `false`: **código muerto**, la copia funcionaba
y nunca confirmaba nada.

### El error va donde el usuario puede verlo

Si la acción **no abrió** modal, el error va en una caja a nivel de página. Ponerlo en
`errorModal` sin modal abierto = **error invisible**. Pasó con `generarCodigo` y `activar`.

### Cédula nunca con `type="email"`

El navegador rechazaba cédulas antes de enviar el formulario (A2).

### No reimplementar reglas del backend

Mostrá el `detail` del servidor vía `extraerMensajeError`, que lo prefiere sobre el status.
Duplicar reglas es cómo se desincronizan.

## Formularios

Label siempre. `text-sm font-medium text-slate-300 mb-1`. Requerido: `<span className="text-red-400"> *</span>`.
`inputMode` correcto en móvil. Submit con `disabled` + spinner.

## Paginación y filtros

```tsx
<Pagination total={total} page={pagina} pageSize={PAGE_SIZE} onPage={setPagina} />
// skip: (pagina - 1) * PAGE_SIZE
```

`Pagination` devuelve `null` si hay una sola página. Filtros: **no** se aplican en cada
keystroke; con botón "Aplicar", porque cada cambio dispara una petición.

## Antes de concluir que tu fix no funcionó

**Ctrl+Shift+R**, o desregistrar el service worker (DevTools → Application → Service Workers).
El SW sirve el bundle viejo y produce un falso negativo. Ya mordió dos veces.

## Orden de verificación

```powershell
npm.cmd run build
docker compose build frontend && docker compose up -d --force-recreate frontend
# el dist va horneado en la imagen nginx: sin bind mount
# después: abrir la pantalla y recorrer el CAMINO DE ERROR primero
```

**No verificado:** rutas en `frontend/src/api/index.ts` que consumen las pantallas nuevas.

Detalle: `docs/03-ux/UX-PATTERNS.md`, `docs/01-architecture/SYSTEM.md`.
