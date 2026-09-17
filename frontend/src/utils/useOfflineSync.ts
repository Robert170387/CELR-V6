import { useState, useEffect, useCallback } from 'react'
import { getUnsyncedTransactions, syncPendingTransactions, PendingTransaction } from '@/utils/offlineStore'

interface UseOfflineSyncReturn {
  isOnline: boolean
  isSyncing: boolean
  pendingCount: number
  pendientes: PendingTransaction[]
  sync: () => Promise<void>
  refresh: () => Promise<void>
}

export function useOfflineSync(): UseOfflineSyncReturn {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [isSyncing, setIsSyncing] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [pendientes, setPendientes] = useState<PendingTransaction[]>([])

  const refresh = useCallback(async () => {
    const unsynced = await getUnsyncedTransactions()
    setPendientes(unsynced)
    setPendingCount(unsynced.length)
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

    void refresh()

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('celr:sync', sync)
      window.removeEventListener('celr:queued', refresh)
    }
  }, [sync, refresh])

  return { isOnline, isSyncing, pendingCount, pendientes, sync, refresh }
}