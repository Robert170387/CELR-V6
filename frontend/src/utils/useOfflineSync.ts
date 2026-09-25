import { useState, useEffect, useCallback } from 'react'
import {
  getUnsyncedTransactions,
  getQuarantinedTransactions,
  getForeignPendingCount,
  getDiscardedTransactions,
  syncPendingTransactions,
  clearDiscardedTransactions,
  PendingTransaction,
  DiscardedTransaction,
} from '@/utils/offlineStore'
import { useAuth } from '@/context/AuthContext'

interface UseOfflineSyncReturn {
  isOnline: boolean
  isSyncing: boolean
  pendingCount: number
  pendingAuthCount: number
  discardedCount: number
  quarantinedCount: number
  foreignPendingCount: number
  pendientes: PendingTransaction[]
  quarantined: PendingTransaction[]
  descartados: DiscardedTransaction[]
  sync: () => Promise<void>
  refresh: () => Promise<void>
  limpiarDescartados: () => Promise<void>
}

export function useOfflineSync(): UseOfflineSyncReturn {
  const { user } = useAuth()
  const usuarioId = user?.id ?? null
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [isSyncing, setIsSyncing] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [pendingAuthCount, setPendingAuthCount] = useState(0)
  const [discardedCount, setDiscardedCount] = useState(0)
  const [quarantinedCount, setQuarantinedCount] = useState(0)
  const [foreignPendingCount, setForeignPendingCount] = useState(0)
  const [pendientes, setPendientes] = useState<PendingTransaction[]>([])
  const [quarantined, setQuarantined] = useState<PendingTransaction[]>([])
  const [descartados, setDescartados] = useState<DiscardedTransaction[]>([])

  const refresh = useCallback(async () => {
    const [unsynced, desc, legacyQuarantined, foreign] = await Promise.all([
      usuarioId ? getUnsyncedTransactions(usuarioId) : Promise.resolve([]),
      getDiscardedTransactions(),
      getQuarantinedTransactions(),
      usuarioId ? getForeignPendingCount(usuarioId) : Promise.resolve(0),
    ])
    setPendientes(unsynced)
    setPendingCount(unsynced.length)
    setPendingAuthCount(unsynced.filter((tx) => tx.estado === 'pending_auth').length)
    setDescartados(desc)
    setDiscardedCount(desc.length)
    setQuarantined(legacyQuarantined)
    setQuarantinedCount(legacyQuarantined.length)
    setForeignPendingCount(foreign)
  }, [usuarioId])

  const sync = useCallback(async () => {
    if (!usuarioId || !navigator.onLine || isSyncing) return
    setIsSyncing(true)
    try {
      const result = await syncPendingTransactions(usuarioId)
      setPendingCount(result.pending)
      setQuarantinedCount(result.quarantined)
      setForeignPendingCount(result.foreignPending)
    } catch (err) {
      console.error('Error sincronizando cola offline:', err)
    } finally {
      setIsSyncing(false)
      void refresh()
    }
  }, [isSyncing, refresh, usuarioId])

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

    // Al cambiar de cuenta se vacía la vista anterior antes de consultar la
    // cola del usuario nuevo; nunca se muestran pendientes de otra sesión.
    setPendientes([])
    setPendingCount(0)
    setPendingAuthCount(0)
    setQuarantined([])
    setQuarantinedCount(0)
    setForeignPendingCount(0)
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
    quarantinedCount,
    foreignPendingCount,
    pendientes,
    quarantined,
    descartados,
    sync,
    refresh,
    limpiarDescartados,
  }
}