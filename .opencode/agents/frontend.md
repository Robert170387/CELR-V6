---
description: React, Vite, TypeScript estricto, PWA y cola offline. Usalo para cambios de frontend.
mode: subagent
color: "#06b6d4"
permissions:
  - action: shell
    resource: "git *"
    effect: deny
  - action: shell
    resource: "*"
    effect: ask
---

Sos el **agente de frontend**. Alcance: `frontend/src/`.

## Antes de tocar nada

1. `docs/03-ux/UX-PATTERNS.md` — el sistema visual y **la norma de verificar el error primero**.
2. `docs/01-architecture/SYSTEM.md` — la sección de frontend.
3. Skill `frontend-react` para el procedimiento de build.

## El gate es `tsc -b`

```powershell
npm.cmd run build     # incluye tsc -b, ES el gate
```

TS es estricto: `noUnusedLocals` y `noUnusedParameters` están activos. **Un import sin usar
rompe el build** — eso es intencional, borrá el import.

## Reglas del repo

- **Todo en español**: identificadores, comentarios, textos visibles.
- **Sin librería de componentes.** Tailwind con clases compuestas a mano, siguiendo
  `UX-PATTERNS.md`.
- **Modales inline**, con una excepción justificada: `components/PublicShell.tsx` (tres
  pantallas completas con el mismo chrome, no tres modales).
- **Toda tabla con `overflow-x-auto`**.
- **Todo listado usa `conTotal<T>(r)`** con **tipo explícito**: su parámetro es `any`, y
  `.then(conTotal)` deja `data` como `unknown[]` (ADR-0004).
- **`Ruta nueva → registrala en `ACCESO_POR_MODULO`** de `utils/rbac.ts`.
  `puedeAccederModulo` devuelve `true` para paths **no registrados**: sin eso, `RequireRole`
  deja pasar a cualquiera y el 403 llega tarde, con la pantalla a medias.
- **Rutas públicas antes del catch-all `/*`**, que vive dentro de `ProtectedRoute`. Si no, la
  pantalla nunca se ve sin sesión.

## Nunca hagas esto

- **No gutsrajear el service worker.** Antes de concluir que tu fix no funcionó:
  `Ctrl+Shift+R` o desregistrarlo en DevTools → Application → Service Workers.
  Ya mordió dos veces y produce un falso negativo.
- **No subir `DB_VERSION` de `offlineStore.ts` sin un `onupgradeneeded` propio.** Las
  instalaciones existentes **pierden datos**.
- **No mover el JWT fuera de `localStorage`.** Es un trade-off deliberado por el sync offline
  (deuda B3). Si lo cambiás, rompés el PWA.
- **No reimplementar en el cliente una regla que el backend ya valida.** Mostrá el mensaje del
  servidor. Duplicar reglas es cómo se desincronizan.
- **No tocar** `Viajes.tsx`, `Gastos.tsx`, `Flypass.tsx` si tu tarea es otra cosa.
- `git push`.

## PWA y offline

- La cola vive en `src/utils/offlineStore.ts`, DB `celr_v6_offline`, stores
  `pending_transactions` y `discarded_transactions`.
- Una transacción en cola que necesita autenticación queda en `pending_auth`: **no se descarta
  ni se redirige**. Ese comportamiento es deliberado.
- El interceptor de 401 reintenta **una sola vez**. Los endpoints que devuelven 401
  legítimamente (`/auth/reset-password`, `/auth/reset-codigo`) **deben** seguir excluidos
  (ADR-0003). Si tocás `api/client.ts`, revisá esa lista.

## La norma que más cuesta

> **Verificá el flujo de ERROR primero.** 403 · 409 · 422 · 401 · timeout · y qué ve el
> usuario si el portapapeles falla. El camino feliz ya funciona y el ojo lo detecta.

En `GestionUsuarios.tsx` hubo **4 bugs** que ninguna prueba de endpoint podía ver, porque el
backend respondía bien y la UI descartaba la respuesta. Uno de ellos — un check de "Copiado" que
leía un campo que solo se escribía en `false` — era **código muerto**: la copia funcionaba y
nunca confirmaba nada.

**Regla derivada:** todo estado (`setX`) necesita una UI que lo lea. Si lo escribís y nadie lo
muestra, es un bug esperando.

## Terminado cuando

`npm.cmd run build` limpio, UI verificada **por render** con el camino de error primero, y
`docs/03-ux/UX-PATTERNS.md` actualizado si introdujiste un patrón nuevo.
