---
name: PWA Offline
description: Procedimiento para trabajar con el service worker, la cola de transacciones en IndexedDB y la sincronización sin conexión. Usar al tocar offlineStore, el service worker, los tokens en localStorage o cualquier flujo que deba sobrevivir sin red.
---

# Cola offline y service worker

## Dónde vive

| Pieza | Ubicación |
|---|---|
| Cola de transacciones | `frontend/src/utils/offlineStore.ts` |
| Hook de sync | `frontend/src/utils/useOfflineSync.ts` |
| Drawer en la UI | `frontend/src/components/Layout.tsx` |
| Config del SW | `vite.config.ts` (vite-plugin-pwa) |
| Interceptores | `frontend/src/api/client.ts` |

**IndexedDB:** DB `celr_v6_offline`, stores `pending_transactions` y `discarded_transactions`.

## La regla que más caro sale

> **Subir `DB_VERSION` sin un `onupgradeneeded` propio hace perder datos** en las
> instalaciones existentes. No es un bug de desarrollo: es pérdida de datos en campo.

Cada bump de versión necesita su handler que migre o preserva los stores.

## Trampa: el SW sirve el bundle viejo

Antes de concluir que un fix de frontend no surtió efecto: **Ctrl+Shift+R**, o desregistrar el
service worker en DevTools → Application → Service Workers.

El `dist` va **horneado** en la imagen nginx (`build.context: ./frontend`, **sin** bind mount):
cambios en `frontend/src/**` no se reflejan en `:5174` hasta
`docker compose build frontend && docker compose up -d --force-recreate frontend`.

**Este combo (SW viejo + dist nuevo) produce dos falsos negativos distintos.** Costo real: una
tarea completa de debugging sobre un fix que ya funcionaba.

## JWT en `localStorage` — trade-off deliberado

`celr_token` y `celr_refresh` viven en `localStorage`. Es una **decisión consciente a favor del
sync offline**, documentada en `backend/README.md`.

Moverlos a cookie HttpOnly es la deuda **B3** y **rompe el offline**. Si te lo piden, es
decisión de negocio, no refactor.

## Estados de una transacción en cola

| Estado | Significado |
|---|---|
| `pending` | En cola, esperando red |
| `pending_auth` | Necesita autenticación. **No se descarta ni redirige** — la UI muestra el contador "requieren iniciar sesión". |
| `discarded` | Descartada, en `discarded_transactions` |

**Cuidado al tocar el interceptor de 401.** Si el refresh falla y la transacción es `_celrOffline`,
`setTransactionEstado(txId, 'pending_auth')` **en vez de** redirigir a `/login`. Redirigir
descartaría trabajo del usuario. Ese comportamiento es deliberado y está testeado.

## Procedimiento para tocar la cola

1. Leer `offlineStore.ts` **completo** antes de cambiar. El manejo de `IDBKeyRange` ya tuvo un
   bug: `index('synced').getAll(only(false))` falla porque los booleanos no son claves de
   índice. La corrección usa `getAll()` + `filter` en memoria.
2. Si agregás un store: actualizar `onupgradeneeded` y el tipo del store.
3. Si agregás un tipo de transacción: registrar su serializer/deserializer y el handler de sync.
4. **Probar los dos caminos**: con red y sin red. Y con la sesión expirada.
5. Verificar que el contador del drawer y el estado en la UI coinciden con IndexedDB.

## Reconstruir y probar

```powershell
npm.cmd run build
docker compose build frontend
docker compose up -d --force-recreate frontend
# 1. DevTools → Application → Service Workers → Unregister
# 2. Ctrl+Shift+R
# 3. Probar offline: DevTools → Network → Offline
```

Detalle: `docs/01-architecture/SYSTEM.md`, sección PWA.
