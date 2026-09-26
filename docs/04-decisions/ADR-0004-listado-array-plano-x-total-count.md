# ADR-0004 — Listados: array plano + `X-Total-Count`

**Estado:** ACEPTADA
**Fecha:** 2026-09-25
**Decide:** usuario
**Ámbito:** frontend, persistencia (contrato HTTP)

## Contexto

El listado de usuarios se diseñó mientras se escribía el cliente. La propuesta inicial fue
`{data, total}` en el body.

El frontend tiene un helper `conTotal<T>(r)` en `src/api/index.ts` que lee el total del header
HTTP `x-total-count` y devuelve `{data, total}` en el cliente. Ya era la convención de los
módulos anteriores.

**Evidencia:** `src/api/index.ts:20-25` (`leerTotal`, `conTotal`), usado por `viajesAPI`,
`vehiculosAPI`, `gastosAPI` y compañía.

## Problema

Devolver `{data, total}` en el body **duplica** el total que el header ya transporta, y obliga a
que cada módulo implemente su propia forma. Peor: el helper `conTotal` existe y lee el header,
así que un endpoint con body sobrediseñado obliga a elegir — y elegir mal rompe la UI en
silencio.

## Opciones

1. **Array plano + `X-Total-Count`** (elegida).
2. `{data, total}` en el body.
3. Solo array plano, sin total (el cliente cuenta lo que recibió).
4. Envelope con metadata de paginación completa (`page`, `pages`, `next`).

## Decisión

`GET /usuarios` devuelve un **array plano**. El total viaja en el header `X-Total-Count`, y
toda la aplicación consume `conTotal<T>`.

Es la convención **ya existente** en el repo. El criterio: no se introduce una segunda forma
para un endpoint nuevo cuando el resto de la API ya tiene una.

## Consecuencias

**Positivas**

- Una sola convención de listado en toda la API.
- El total puede cachearse en CDN/proxy por separado del body.
- La UI no puede desincronizarse: total y filas vienen del mismo request.

**Negativas / costo aceptado**

- Sin total, el cliente no puede paginar. Irrelevante: el listado **sí** manda `X-Total-Count`.
- **Fricción de implementación:** `conTotal` exige **tipo explícito**
  (`.then((r) => conTotal<UsuarioListItem>(r))`). Su parámetro es `any`, así que TypeScript no
  puede inferirlo y `.then(conTotal)` deja `data` como `unknown[]`. Es una trampa que ya
  costó un build fallido.
- El error es **invisible**: si el frontend espera `{data,total}` y recibe un array, la tabla
  queda vacía sin ningún error en consola.

**Fuera de alcance**

- Paginación por cursor. Hoy es `skip`/`limit`.
- Ordenamiento en el servidor (no hay parámetro de sort).

## Alternativas descartadas

| Opción | Por qué no |
|---|---|
| `{data, total}` en body | Duplica el header y crea una segunda convención. Rompe `conTotal` y deja la UI vacía en silencio. |
| Solo array, sin total | Rompe la paginación: el cliente no sabe cuántas páginas hay. |
| Envelope con `page`/`pages`/`next` | Útil a escala; hoy `skip`/`limit` + total es suficiente. Añade complexity sin caso. |

## Restricciones de implementación

- **Todo listado nuevo** devuelve array plano y setea `X-Total-Count`. No inventar otra forma.
- El total **debe** ser el total del **filtro aplicado**, no el total de la tabla. Con
  filtros, `skip` desalinea la paginación.
- Si el listado no está paginado, puede omitir el header; `conTotal` devuelve 0 y la UI no
  muestra paginación (que es lo correcto si cabe en una página).
- El cliente **siempre** pasa el tipo: `conTotal<T>(r)`.
- Verificar contra `/openapi.json` vivo cuando se agrega un endpoint: el conteo de paths y
  operaciones es un gate informal del proyecto (hoy 45 paths / 65 operaciones).

## Pruebas requeridas

- `test_usuarios_crud.py` (TUC-2) — el operador ve lo que le corresponde y `X-Total-Count`
  concuerda con el largo del array.
- `npm run build` (`tsc -b`) — es el gate que detecta el `unknown[]` del `conTotal` sin tipo.

**Brecha declarada:** no hay test de frontend que falle si un listado nuevo devuelve
`{data, total}`. El síntoma (tabla vacía) solo aparece mirando la pantalla.
Ver `docs/03-ux/UX-PATTERNS.md`.
