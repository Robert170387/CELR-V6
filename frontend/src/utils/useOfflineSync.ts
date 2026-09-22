import { useState, useEffect, useCallback } from 'react'
import {
  getUnsyncedTransactions,
  getDiscardedTransactions,
  syncPendingTransactions,
  clearDiscardedTransactions,
  PendingTransaction,
  DiscardedTransaction,
} from '@/utils/offlineStore'

interface UseOfflineSyncReturn {
  isOnline: boolean
  isSyncing: boolean
  pendingCount: number
  pendingAuthCount: number
  discardedCount: number
  pendientes: PendingTransaction[]
  descartados: DiscardedTransaction[]
  sync: () => Promise<void>
  refresh: () => Promise<void>
  limpiarDescartados: () => Promise<void>
}

export function useOfflineSync(): UseOfflineSyncReturn {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [isSyncing, setIsSyncing] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [pendingAuthCount, setPendingAuthCount] = useState(0)
  const [discardedCount, setDiscardedCount] = useState(0)
  const [pendientes, setPendientes] = useState<PendingTransaction[]>([])
  const [descartados, setDescartados] = useState<DiscardedTransaction[]>([])

  const refresh = useCallback(async () => {
    const [unsynced, desc] = await Promise.all([
      getUnsyncedTransactions(),
      getDiscardedTransactions(),
    ])
    setPendientes(unsynced)
    setPendingCount(unsynced.length)
    setPendingAuthCount(unsynced.filter((tx) => tx.estado === 'pending_auth').length)
    setDescartados(desc)
    setDiscardedCount(desc.length)
  }, [])

  const sync = useCallback(async () => {
    if (!navigator.onLine || isSyncing) return
    setIsSyncing(true)
    try {
      const result = await syncPendingTransactions()
      setPendingCount(result.pending)
    } catch (err) {
      console.error('Error sincronizando cola offline:', err)
    } finally {
      setIsSyncing(false)
      void refresh()
    }
  }, [isSyncing, refresh])

  const limpiarDescartados = useCallback(async () => {
    await clearDiscardedTransactions()
    void refresh()
  }, [refresh])

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      sync()
    }
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('celr:sync', sync)
    window.addEventListener('celr:queued', refresh)
    window.addEventListener('celr:discarded', refresh)

    void refresh()

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('celr:sync', sync)
      window.removeEventListener('celr:queued', refresh)
      window.removeEventListener('celr:discarded', refresh)
    }
  }, [sync, refresh])

  return {
    isOnline,
    isSyncing,
    pendingCount,
    pendingAuthCount,
    discardedCount,
    pendientes,
    descartados,
    sync,
    refresh,
    limpiarDescartados,
  }
}