import { useState, useEffect, useCallback } from 'react'
import { getUnsyncedTransactions, syncPendingTransactions } from '@/utils/offlineStore'

interface UseOfflineSyncReturn {
  isOnline: boolean
  isSyncing: boolean
  pendingCount: number
  sync: () => Promise<void>
}

export function useOfflineSync(): UseOfflineSyncReturn {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [isSyncing, setIsSyncing] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)

  const updatePendingCount = useCallback(async () => {
    const unsynced = await getUnsyncedTransactions()
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
    }
  }, [isSyncing])

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      sync()
    }
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('celr:sync', sync)
    window.addEventListener('celr:queued', updatePendingCount)

    updatePendingCount()

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('celr:sync', sync)
      window.removeEventListener('celr:queued', updatePendingCount)
    }
  }, [sync, updatePendingCount])

  return { isOnline, isSyncing, pendingCount, sync }
}