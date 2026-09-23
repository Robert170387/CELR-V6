import apiClient from '@/api/client'

const DB_NAME = 'celr_v6_offline'
const DB_VERSION = 2
const STORE_NAME = 'pending_transactions'
const DISCARDED_STORE_NAME = 'discarded_transactions'

export type TransactionType = 'gasto' | 'viaje' | 'liquidacion'

export type TxEstado = 'pendiente' | 'pending_auth'

export interface PendingTransaction {
  id?: number
  type: TransactionType
  data: any
  timestamp: number
  synced: boolean
  estado?: TxEstado
}

export interface DiscardedTransaction {
  id?: number
  type: TransactionType
  data: any
  motivo: string
  timestamp: number
}

let db: IDBDatabase | null = null

function getStore(database: IDBDatabase, name: string, mode: IDBTransactionMode): IDBObjectStore {
  return database.transaction(name, mode).objectStore(name)
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (db) {
      resolve(db)
      return
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onerror = () => reject(request.error)
    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result
      if (database.objectStoreNames.contains(STORE_NAME) && !database.objectStoreNames.contains(DISCARDED_STORE_NAME)) {
        // El store de cola ya existe: solo se añade el de descartados en la v2.
        const disc = database.createObjectStore(DISCARDED_STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        })
        disc.createIndex('type', 'type', { unique: false })
        disc.createIndex('timestamp', 'timestamp', { unique: false })
        return
      }
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true })
        store.createIndex('type', 'type', { unique: false })
        store.createIndex('synced', 'synced', { unique: false })
        store.createIndex('timestamp', 'timestamp', { unique: false })
      }
      if (!database.objectStoreNames.contains(DISCARDED_STORE_NAME)) {
        const disc = database.createObjectStore(DISCARDED_STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        })
        disc.createIndex('type', 'type', { unique: false })
        disc.createIndex('timestamp', 'timestamp', { unique: false })
      }
    }
    request.onsuccess = () => {
      db = request.result
      resolve(db)
    }
  })
}

export async function addPendingTransaction(
  tx: Omit<PendingTransaction, 'id' | 'timestamp' | 'synced' | 'estado'>
): Promise<number> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readwrite')
    const request = store.add({ ...tx, timestamp: Date.now(), synced: false, estado: 'pendiente' })
    request.onsuccess = () => resolve(request.result as number)
    request.onerror = () => reject(request.error)
  })
}

export async function getPendingTransactions(): Promise<PendingTransaction[]> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readonly')
    const request = store.getAll()
    request.onsuccess = () => resolve(request.result as PendingTransaction[])
    request.onerror = () => reject(request.error)
  })
}

export async function markAsSynced(id: number): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readwrite')
    const getRequest = store.get(id)
    getRequest.onsuccess = () => {
      const record = getRequest.result
      if (record) {
        record.synced = true
        store.put(record)
      }
    }
    const tx = store.transaction
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function setTransactionEstado(id: number, estado: TxEstado): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readwrite')
    const getRequest = store.get(id)
    getRequest.onsuccess = () => {
      const record = getRequest.result
      if (record) {
        record.estado = estado
        store.put(record)
      }
    }
    const tx = store.transaction
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function removePendingTransaction(id: number): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readwrite')
    store.delete(id)
    const tx = store.transaction
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

// Los booleanos no son claves válidas de índice en IndexedDB (lo son number,
// Date, DOMString, binary y Array), por lo que el índice 'synced' no se puede
// consultar con IDBKeyRange.only(false/true): lanza DataError. Se filtra en
// memoria sobre getAll(); el índice queda declarado pero sin uso (ver §4 de
// INSTRUCCIONES_OPENCODE.md).
export async function getUnsyncedTransactions(): Promise<PendingTransaction[]> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readonly')
    const request = store.getAll()
    request.onsuccess = () => {
      const items = request.result as PendingTransaction[]
      resolve(items.filter((t) => !t.synced))
    }
    request.onerror = () => reject(request.error)
  })
}

export async function clearSyncedTransactions(): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readwrite')
    // Mismo motivo que getUnsyncedTransactions(): el índice 'synced' con claves
    // booleanas no es consultable; se borran los registros ya sincronizados
    // filtrando en memoria.
    const request = store.getAll()
    request.onsuccess = () => {
      const items = request.result as PendingTransaction[]
      for (const item of items) {
        if (item.synced && item.id !== undefined) {
          store.delete(item.id)
        }
      }
    }
    const tx = store.transaction
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

// ---------------------------------------------------------------------------
// Bitácora persistente de transacciones descartadas (nunca perder datos a ciegas)
// ---------------------------------------------------------------------------

export async function addDiscardedTransaction(discarded: Omit<DiscardedTransaction, 'id'>): Promise<number> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, DISCARDED_STORE_NAME, 'readwrite')
    const tx = store.transaction
    const request = store.add({
      ...discarded,
      timestamp: discarded.timestamp || Date.now(),
    })
    request.onsuccess = () => resolve(request.result as number)
    request.onerror = () => reject(request.error)
    tx.onabort = () => reject(tx.error)
  })
}

export async function getDiscardedTransactions(): Promise<DiscardedTransaction[]> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, DISCARDED_STORE_NAME, 'readonly')
    const request = store.index('timestamp').getAll()
    request.onsuccess = () => {
      const items = request.result as DiscardedTransaction[]
      items.sort((a, b) => a.timestamp - b.timestamp)
      resolve(items)
    }
    request.onerror = () => reject(request.error)
  })
}

export async function removeDiscardedTransaction(id: number): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, DISCARDED_STORE_NAME, 'readwrite')
    store.delete(id)
    const tx = store.transaction
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function clearDiscardedTransactions(): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, DISCARDED_STORE_NAME, 'readwrite')
    store.clear()
    const tx = store.transaction
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

// ---------------------------------------------------------------------------
// Sincronización
// ---------------------------------------------------------------------------

export interface SyncResult {
  synced: number
  failed: number
  pending: number
}

export async function encolarOffline(type: TransactionType, data: any): Promise<number> {
  const id = await addPendingTransaction({ type, data })
  window.dispatchEvent(new Event('celr:queued'))
  if (navigator.onLine) {
    void syncPendingTransactions().finally(() => window.dispatchEvent(new Event('celr:queued')))
  }
  return id
}

function extraerDetail(err: any): string {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d: any) => (typeof d === 'string' ? d : d?.msg || '')).join('; ')
  return ''
}

async function enviarTransaccion(tx: PendingTransaction): Promise<void> {
  const opts: any = { _celrOffline: true, _celrTxId: tx.id }
  if (tx.type === 'gasto') {
    await apiClient.post('/gastos', tx.data, opts)
  } else if (tx.type === 'viaje') {
    await apiClient.post('/viajes', tx.data, opts)
  } else if (tx.type === 'liquidacion') {
    await apiClient.post(`/liquidaciones/cerrar/${tx.data?.viaje_id}`, tx.data, opts)
  }
}

async function descartarConLog(
  tx: PendingTransaction,
  motivo: string
): Promise<void> {
  await addDiscardedTransaction({
    type: tx.type,
    data: tx.data,
    motivo,
    timestamp: Date.now(),
  })
  await removePendingTransaction(tx.id!)
  window.dispatchEvent(new Event('celr:discarded'))
}

export async function syncPendingTransactions(): Promise<SyncResult> {
  if (!navigator.onLine) {
    return { synced: 0, failed: 0, pending: (await getUnsyncedTransactions()).length }
  }

  const unsynced = await getUnsyncedTransactions()
  let synced = 0
  let failed = 0

  for (const tx of unsynced) {
    const id = tx.id!
    try {
      await enviarTransaccion(tx)
      // ÉXITO: el servidor confirmó (2xx). La transacción sale de la cola.
      await removePendingTransaction(id)
      synced++
    } catch (err: any) {
      if (!err?.response) {
        // Error de red / servidor inalcanzable: se abandona el intento por ahora.
        // Los pendientes conservan su lugar para reintentos posteriores.
        break
      }
      const status = err?.response?.status ?? 0
      if (status === 401) {
        // Token expirado: el interceptor ya intentó /auth/refresh y reintentó.
        // Si llegó aquí sin éxito, NO se marca como sincronizada. Queda
        // 'pending_auth' y la UI le pide al usuario volver a iniciar sesión.
        await setTransactionEstado(id, 'pending_auth')
        failed++
        continue
      }
      const detail = extraerDetail(err)
      if (status === 400 && /duplicado/i.test(detail)) {
        // Error inequívocamente permanente y no recuperable: se descarta pero
        // queda una bitácora visible en la UI con el motivo.
        await descartarConLog(tx, `Duplicado detectado por el servidor: ${detail}`)
        failed++
        continue
      }
      if (status >= 500) {
        // 5xx: servidor inestable -> misma conducta que un error de red.
        break
      }
      // Otros 4xx (422, 404...): se mantienen en la cola para revisión manual;
      // no se descartan ni se marcan como sincronizados.
      failed++
    }
  }

  // Limpieza de registros legacy marcados como 'synced'.
  await clearSyncedTransactions()

  return { synced, failed, pending: (await getUnsyncedTransactions()).length }
}