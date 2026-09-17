import apiClient from '@/api/client'

const DB_NAME = 'celr_v6_offline'
const DB_VERSION = 1
const STORE_NAME = 'pending_transactions'

export type TransactionType = 'gasto' | 'viaje' | 'liquidacion'

export interface PendingTransaction {
  id?: number
  type: TransactionType
  data: any
  timestamp: number
  synced: boolean
}

let db: IDBDatabase | null = null

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
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true })
        store.createIndex('type', 'type', { unique: false })
        store.createIndex('synced', 'synced', { unique: false })
        store.createIndex('timestamp', 'timestamp', { unique: false })
      }
    }
    request.onsuccess = () => {
      db = request.result
      resolve(db)
    }
  })
}

export async function addPendingTransaction(
  tx: Omit<PendingTransaction, 'id' | 'timestamp' | 'synced'>
): Promise<number> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const dbTx = database.transaction(STORE_NAME, 'readwrite')
    const store = dbTx.objectStore(STORE_NAME)
    const request = store.add({ ...tx, timestamp: Date.now(), synced: false })
    request.onsuccess = () => resolve(request.result as number)
    request.onerror = () => reject(request.error)
  })
}

export async function getPendingTransactions(): Promise<PendingTransaction[]> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.getAll()
    request.onsuccess = () => resolve(request.result as PendingTransaction[])
    request.onerror = () => reject(request.error)
  })
}

export async function markAsSynced(id: number): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const getRequest = store.get(id)
    getRequest.onsuccess = () => {
      const record = getRequest.result
      if (record) {
        record.synced = true
        store.put(record)
      }
    }
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
}

export async function removePendingTransaction(id: number): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    store.delete(id)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
}

export async function getUnsyncedTransactions(): Promise<PendingTransaction[]> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const index = store.index('synced')
    const request = index.getAll(IDBKeyRange.only(false))
    request.onsuccess = () => resolve(request.result as PendingTransaction[])
    request.onerror = () => reject(request.error)
  })
}

export async function clearSyncedTransactions(): Promise<void> {
  const database = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const index = store.index('synced')
    const request = index.openCursor(IDBKeyRange.only(true))
    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result
      if (cursor) {
        cursor.delete()
        cursor.continue()
      }
    }
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
}

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

export async function syncPendingTransactions(): Promise<SyncResult> {
  if (!navigator.onLine) {
    return { synced: 0, failed: 0, pending: (await getUnsyncedTransactions()).length }
  }

  const unsynced = await getUnsyncedTransactions()
  let synced = 0
  let failed = 0

  for (const tx of unsynced) {
    try {
      if (tx.type === 'gasto') {
        await apiClient.post('/gastos', tx.data)
      } else if (tx.type === 'viaje') {
        await apiClient.post('/viajes', tx.data)
      } else if (tx.type === 'liquidacion') {
        await apiClient.post(`/liquidaciones/cerrar/${tx.data?.viaje_id}`, tx.data)
      }
      await markAsSynced(tx.id!)
      synced++
    } catch (err: any) {
      if (!err?.response) {
        break
      }
      await markAsSynced(tx.id!)
      failed++
    }
  }

  return { synced, failed, pending: (await getUnsyncedTransactions()).length }
}
