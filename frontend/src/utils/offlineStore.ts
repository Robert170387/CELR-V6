import apiClient, { getAccessToken } from '@/api/client'

const DB_NAME = 'celr_v6_offline'
const DB_VERSION = 3
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
  /** Dueño de la transacción. null significa registro legacy en cuarentena. */
  usuario_id: number | null
  estado?: TxEstado
}

export type NewPendingTransaction = Omit<
  PendingTransaction,
  'id' | 'timestamp' | 'synced' | 'estado' | 'usuario_id'
> & {
  usuario_id: number
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
    request.onblocked = () =>
      reject(new Error('La cola offline está bloqueada por otra pestaña; ciérrala y reintenta'))
    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result
      const transaction = request.transaction
      if (!transaction) {
        throw new Error('No se pudo iniciar la actualización de IndexedDB')
      }

      let pendingStore: IDBObjectStore
      if (database.objectStoreNames.contains(STORE_NAME)) {
        pendingStore = transaction.objectStore(STORE_NAME)
      } else {
        pendingStore = database.createObjectStore(STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        })
        pendingStore.createIndex('type', 'type', { unique: false })
        // Se conserva el índice histórico 'synced', aunque no se consulta con
        // IDBKeyRange.only() porque booleanos no son claves válidas.
        pendingStore.createIndex('synced', 'synced', { unique: false })
        pendingStore.createIndex('timestamp', 'timestamp', { unique: false })
      }

      // Índice numérico válido para ownership. No se usa para migrar ni para
      // reemplazar el filtrado en memoria de los booleanos.
      if (!pendingStore.indexNames.contains('usuario_id')) {
        pendingStore.createIndex('usuario_id', 'usuario_id', { unique: false })
      }

      if (!database.objectStoreNames.contains(DISCARDED_STORE_NAME)) {
        const discardedStore = database.createObjectStore(DISCARDED_STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        })
        discardedStore.createIndex('type', 'type', { unique: false })
        discardedStore.createIndex('timestamp', 'timestamp', { unique: false })
      }

      // Los registros anteriores a v3 no tienen dueño. Se conservan y se
      // marcan como cuarentena; nunca se reasignan ni se sincronizan.
      const cursorRequest = pendingStore.openCursor()
      cursorRequest.onsuccess = () => {
        const cursor = cursorRequest.result
        if (!cursor) return
        const record = cursor.value as PendingTransaction
        const owner = record.usuario_id
        if (typeof owner !== 'number' || !Number.isInteger(owner) || owner <= 0) {
          cursor.update({ ...record, usuario_id: null })
        }
        cursor.continue()
      }
    }
    request.onsuccess = () => {
      db = request.result
      resolve(db)
    }
  })
}

export async function addPendingTransaction(tx: NewPendingTransaction): Promise<number> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readwrite')
    const request = store.add({ ...tx, timestamp: Date.now(), synced: false, estado: 'pendiente' })
    request.onsuccess = () => resolve(request.result as number)
    request.onerror = () => reject(request.error)
  })
}

export async function getPendingTransactions(usuarioId: number): Promise<PendingTransaction[]> {
  validarUsuarioId(usuarioId)
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readonly')
    const request = store.getAll()
    request.onsuccess = () => {
      const items = request.result as PendingTransaction[]
      resolve(items.filter((t) => t.usuario_id === usuarioId))
    }
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
function validarUsuarioId(usuarioId: number): void {
  if (!Number.isInteger(usuarioId) || usuarioId <= 0) {
    throw new Error('Se requiere un usuario autenticado para gestionar la cola offline')
  }
}

// El filtro por dueño evita enviar una cola ajena; esta segunda comprobación
// cubre el caso en que la cuenta cambia mientras una sincronización está en
// vuelo. No es una frontera de seguridad: solo evita una carrera del cliente.
function usuarioIdDeSesion(): number | null {
  const token = getAccessToken()
  if (!token) return null
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    const claims = JSON.parse(atob(padded)) as { usuario_id?: unknown }
    const id = Number(claims.usuario_id)
    return Number.isInteger(id) && id > 0 ? id : null
  } catch {
    return null
  }
}

export async function getUnsyncedTransactions(usuarioId: number): Promise<PendingTransaction[]> {
  validarUsuarioId(usuarioId)
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readonly')
    const request = store.getAll()
    request.onsuccess = () => {
      const items = request.result as PendingTransaction[]
      resolve(items.filter((t) => !t.synced && t.usuario_id === usuarioId))
    }
    request.onerror = () => reject(request.error)
  })
}

export async function getQuarantinedTransactions(): Promise<PendingTransaction[]> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readonly')
    const request = store.getAll()
    request.onsuccess = () => {
      const items = request.result as PendingTransaction[]
      const quarantined = items.filter((t) => t.usuario_id === null)
      quarantined.sort((a, b) => a.timestamp - b.timestamp)
      resolve(quarantined)
    }
    request.onerror = () => reject(request.error)
  })
}

// Solo devuelve un conteo: las transacciones de otra cuenta no se exponen a
// la UI ni se pueden sincronizar con la sesión actual.
export async function getForeignPendingCount(usuarioId: number): Promise<number> {
  validarUsuarioId(usuarioId)
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readonly')
    const request = store.getAll()
    request.onsuccess = () => {
      const items = request.result as PendingTransaction[]
      resolve(
        items.filter(
          (t) => !t.synced && typeof t.usuario_id === 'number' && t.usuario_id !== usuarioId
        ).length
      )
    }
    request.onerror = () => reject(request.error)
  })
}

export async function clearSyncedTransactions(usuarioId: number): Promise<void> {
  validarUsuarioId(usuarioId)
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const store = getStore(database, STORE_NAME, 'readwrite')
    // Mismo motivo que getUnsyncedTransactions(): el índice 'synced' con claves
    // booleanas no es consultable; se borran en memoria. El filtro de dueño
    // evita tocar registros de otra cuenta o de la cuarentena legacy.
    const request = store.getAll()
    request.onsuccess = () => {
      const items = request.result as PendingTransaction[]
      for (const item of items) {
        if (item.synced && item.usuario_id === usuarioId && item.id !== undefined) {
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
  /** Registros legacy sin usuario_id; se conservan para revisión. */
  quarantined: number
  /** Registros pendientes que pertenecen a otra cuenta; solo se expone el conteo. */
  foreignPending: number
}

export async function encolarOffline(
  type: TransactionType,
  data: any,
  usuarioId: number
): Promise<number> {
  validarUsuarioId(usuarioId)
  const id = await addPendingTransaction({ type, data, usuario_id: usuarioId })
  window.dispatchEvent(new Event('celr:queued'))
  if (navigator.onLine) {
    void syncPendingTransactions(usuarioId).finally(() => window.dispatchEvent(new Event('celr:queued')))
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

export async function syncPendingTransactions(usuarioId: number): Promise<SyncResult> {
  validarUsuarioId(usuarioId)
  const [unsynced, quarantined, foreignPending] = await Promise.all([
    getUnsyncedTransactions(usuarioId),
    getQuarantinedTransactions(),
    getForeignPendingCount(usuarioId),
  ])
  const baseResult: SyncResult = {
    synced: 0,
    failed: 0,
    pending: unsynced.length,
    quarantined: quarantined.length,
    foreignPending,
  }

  // Si el token actual ya no pertenece al dueño solicitado, no se intenta
  // enviar nada. La cola queda intacta para la sesión correcta.
  if (usuarioIdDeSesion() !== usuarioId) {
    return baseResult
  }

  if (!navigator.onLine) {
    return baseResult
  }

  let synced = 0
  let failed = 0

  for (const tx of unsynced) {
    // Defensa adicional: aunque getUnsynced ya filtró, no enviar nunca una
    // transacción cuyo dueño no coincida con la sesión activa.
    if (tx.usuario_id !== usuarioId || tx.id === undefined) continue
    if (usuarioIdDeSesion() !== usuarioId) break
    const id = tx.id
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

  // Solo se limpian los registros ya sincronizados del usuario activo. Las
  // cuentas ajenas y la cuarentena legacy permanecen intactas.
  await clearSyncedTransactions(usuarioId)

  const [remaining, remainingQuarantined, remainingForeign] = await Promise.all([
    getUnsyncedTransactions(usuarioId),
    getQuarantinedTransactions(),
    getForeignPendingCount(usuarioId),
  ])
  return {
    synced,
    failed,
    pending: remaining.length,
    quarantined: remainingQuarantined.length,
    foreignPending: remainingForeign,
  }
}