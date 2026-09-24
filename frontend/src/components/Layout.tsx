import React, { useEffect, useState } from 'react'
import {
  Menu,
  X,
  Truck,
  Package,
  Fuel,
  Receipt,
  Calculator,
  Wallet,
  Database,
  Shield,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  Wifi,
  WifiOff,
  AlertTriangle,
  FileSpreadsheet,
} from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useOfflineSync } from '@/utils/useOfflineSync'
import { menuPermitido, esRolFinanzas, esRolRecursos } from '@/utils/rbac'
import { PendingTransaction, DiscardedTransaction } from '@/utils/offlineStore'

interface LayoutProps {
  children: React.ReactNode
}

interface MenuItem {
  path: string
  label: string
  icon: React.ComponentType<{ size?: number | string; className?: string }>
  tab?: string
}

interface SidebarGroup {
  titulo: string
  visible: boolean
  items: MenuItem[]
}

const grupoOperacion: MenuItem[] = [
  { path: '/', label: 'Dashboard', icon: Truck },
  { path: '/viajes', label: 'Viajes / ODTs', icon: Package },
  { path: '/gastos', label: 'Registrar Gasto', icon: Fuel },
  { path: '/scan', label: 'Escanear Recibo (OCR)', icon: Receipt },
]

const grupoFinanzas: MenuItem[] = [
  { path: '/ingresos', label: 'Ingresos', icon: Wallet },
  { path: '/liquidaciones', label: 'Liquidaciones', icon: Calculator },
  { path: '/flypass', label: 'Flypass', icon: FileSpreadsheet },
]

const grupoRecursos: MenuItem[] = [
  { path: '/maestras', label: 'Flota & Mantenimiento', icon: Database, tab: 'vehiculos' },
  { path: '/maestras', label: 'Personal', icon: Shield, tab: 'conductores' },
  { path: '/maestras', label: 'Terceros', icon: Receipt, tab: 'proveedores' },
]

const etiquetaTipo: Record<string, { label: string; color: string }> = {
  gasto: { label: 'Gasto', color: 'bg-yellow-500/20 text-yellow-400' },
  viaje: { label: 'Viaje', color: 'bg-blue-500/20 text-blue-400' },
  liquidacion: { label: 'Liquidación', color: 'bg-purple-500/20 text-purple-400' },
}

const resumenItem = (tx: PendingTransaction): string => {
  const d = tx.data
  switch (tx.type) {
    case 'gasto':
      return d && (d.valor || d.num_factura || d.categoria)
        ? [d.valor ? `$${d.valor}` : '', d.categoria || ''].filter(Boolean).join(' · ')
        : 'Gasto por confirmar'
    case 'viaje':
      return d ? d.numero_odt || `Vehiculo ${d.vehiculo_id ?? ''}` : 'Viaje por confirmar'
    case 'liquidacion':
      return d && d.viaje_id ? `Viaje #${d.viaje_id}` : 'Liquidación por confirmar'
    default:
      return ''
  }
}

const SyncQueueDrawer: React.FC<{ abierto: boolean; onClose: () => void }> = ({ abierto, onClose }) => {
  const {
    isOnline,
    isSyncing,
    pendientes,
    descartados,
    discardedCount,
    sync,
    limpiarDescartados,
  } = useOfflineSync()

  if (!abierto) return null

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <aside className="absolute right-0 top-0 h-full w-full max-w-md bg-slate-900 border-l border-slate-700 flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 bg-slate-800">
          <div className="flex items-center gap-2">
            <Clock size={20} className="text-primary-400" />
            <h3 className="font-semibold text-white">Cola de Sincronización</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div
          className={`flex items-center gap-2 px-5 py-3 text-sm border-b border-slate-700 ${
            isOnline ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          }`}
        >
          {isOnline ? <Wifi size={16} /> : <WifiOff size={16} />}
          <span>
            {isOnline
              ? 'En línea — puedes sincronizar'
              : 'Sin conexión — los cambios se guardan en este dispositivo'}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {pendientes.length === 0 ? (
            <div className="text-slate-500 text-center py-12">
              <div className="flex justify-center">
                <div className="p-3 rounded-full bg-green-500/15 text-green-500">
                  <RefreshCw size={28} />
                </div>
              </div>
              <p className="mt-3 text-sm">No hay elementos pendientes por sincronizar</p>
            </div>
          ) : (
            pendientes.map((tx) => (
              <div key={tx.id} className="p-3 bg-slate-800 border border-slate-700 rounded-lg">
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                      etiquetaTipo[tx.type]?.color || 'bg-slate-500/20 text-slate-400'
                    }`}
                  >
                    {etiquetaTipo[tx.type]?.label || tx.type}
                  </span>
                  {tx.estado === 'pending_auth' ? (
                    <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400">
                      requiere iniciar sesión
                    </span>
                  ) : (
                    <span className="text-xs text-slate-500">
                      {new Date(tx.timestamp).toLocaleString('es-CO', {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      })}
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-300 mt-2">{resumenItem(tx)}</p>
              </div>
            ))
          )}

          {descartados.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-semibold tracking-widest text-slate-400 uppercase flex items-center gap-1">
                  <AlertTriangle size={12} />
                  Descartados ({discardedCount})
                </h4>
                <button
                  type="button"
                  onClick={() => void limpiarDescartados()}
                  className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                  Limpiar bitácora
                </button>
              </div>
              <div className="space-y-2">
                {descartados.map((d) => (
                  <div key={d.id} className="p-3 bg-red-950/40 border border-red-900/40 rounded-lg">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                          etiquetaTipo[d.type]?.color || 'bg-slate-500/20 text-slate-400'
                        }`}
                      >
                        {etiquetaTipo[d.type]?.label || d.type}
                      </span>
                      <span className="text-xs text-slate-500">
                        {new Date(d.timestamp).toLocaleString('es-CO', {
                          dateStyle: 'short',
                          timeStyle: 'short',
                        })}
                      </span>
                    </div>
                    <p className="text-sm text-slate-300 mt-2">{resumenDiscartado(d)}</p>
                    <p className="text-xs text-red-400 mt-1">{d.motivo}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-slate-700 p-4">
          <button
            type="button"
            onClick={() => void sync()}
            disabled={!isOnline || isSyncing || pendientes.length === 0}
            className="btn-celr w-full flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <RefreshCw size={18} className={isSyncing ? 'animate-spin' : ''} />
            {isSyncing ? 'Sincronizando...' : `Reintentar sincronización (${pendientes.length})`}
          </button>
        </div>
      </aside>
    </div>
  )
}

const resumenDiscartado = (d: DiscardedTransaction): string => {
  const base = resumenItem(d as unknown as PendingTransaction)
  return base || 'Registro sin resumen'
}

const StatusIndicator: React.FC = () => {
  const { isOnline, isSyncing, pendingCount, pendingAuthCount, sync } = useOfflineSync()
  const [drawerAbierto, setDrawerAbierto] = useState(false)

  const statusColor = isOnline ? 'bg-green-500' : 'bg-red-500'
  const statusText = isOnline ? (isSyncing ? 'Sincronizando' : 'En línea') : 'Sin conexión'

  return (
    <>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className={`w-2.5 h-2.5 rounded-full ${statusColor} ${isSyncing ? 'animate-pulse' : ''}`} />
          <span className={`text-xs font-medium ${isOnline ? 'text-green-400' : 'text-red-400'}`}>
            {statusText}
          </span>
        </div>
        {pendingAuthCount > 0 && (
          <button
            onClick={() => setDrawerAbierto(true)}
            className="flex items-center gap-1 px-2 py-1 bg-amber-500/20 hover:bg-amber-500/40 text-amber-400 rounded-md text-xs transition-colors"
            title="Estos envíos requieren que vuelvas a iniciar sesión"
          >
            <AlertTriangle size={12} />
            {pendingAuthCount} requieren iniciar sesión
          </button>
        )}
        {pendingCount > 0 ? (
          <button
            onClick={() => setDrawerAbierto(true)}
            className="flex items-center gap-1 px-2 py-1 bg-primary-600/20 hover:bg-primary-600/40 text-primary-400 rounded-md text-xs transition-colors"
          >
            <RefreshCw size={12} className={isSyncing ? 'animate-spin' : ''} />
            {pendingCount} pendientes
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setDrawerAbierto(true)}
            title="Ver cola de sincronización"
            className="flex items-center gap-1 px-2 py-1 bg-slate-700/50 hover:bg-slate-700 text-slate-400 rounded-md text-xs transition-colors"
          >
            <Clock size={12} />
            Cola
          </button>
        )}
        {!isOnline && (
          <button
            onClick={() => void sync()}
            disabled={isSyncing}
            className="flex items-center gap-1 px-2 py-1 bg-red-500/15 hover:bg-red-500/30 text-red-400 rounded-md text-xs transition-colors disabled:opacity-50"
            title="Reintentar sincronización"
          >
            <AlertTriangle size={12} className={isSyncing ? 'animate-pulse' : ''} />
            Reintentar
          </button>
        )}
      </div>
      <SyncQueueDrawer abierto={drawerAbierto} onClose={() => setDrawerAbierto(false)} />
    </>
  )
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [gruposColapsados, setGruposColapsados] = useState<Record<string, boolean>>({})
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, user } = useAuth()

  const tabActual = new URLSearchParams(location.search).get('tab') || 'vehiculos'

  const itemActivo = (item: MenuItem): boolean => {
    if (location.pathname !== item.path) return false
    if (item.tab) return tabActual === item.tab
    return true
  }

  const irA = (item: MenuItem) => {
    navigate(item.tab ? `${item.path}?tab=${item.tab}` : item.path)
  }

  const grupos: SidebarGroup[] = [
    { titulo: 'OPERACIÓN', visible: true, items: menuPermitido(grupoOperacion, user?.rol) },
    { titulo: 'FINANZAS Y CIERRE', visible: esRolFinanzas(user?.rol), items: grupoFinanzas },
    { titulo: 'RECURSOS Y FLOTA', visible: esRolRecursos(user?.rol), items: grupoRecursos },
  ]

  const itemActivoGlobal = grupos.flatMap((g) => g.items).find(itemActivo)

  useEffect(() => {
    const grupoActivo = grupos.find((g) => g.items.some(itemActivo))
    if (grupoActivo) {
      setGruposColapsados((prev) => ({ ...prev, [grupoActivo.titulo]: false }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search])

  return (
    <div className="flex h-screen bg-slate-900 text-slate-200">
      <aside
        className={`${
          sidebarOpen ? 'w-64' : 'w-16'
        } bg-slate-900 border-r border-slate-700 flex flex-col transition-all duration-300`}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <Truck className="w-8 h-8 text-blue-500" />
            {sidebarOpen && <span className="font-bold text-lg text-white">CELR v6</span>}
          </div>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        <nav className="flex-1 p-2 overflow-y-auto">
          {grupos
            .filter((g) => g.visible && g.items.length > 0)
            .map((grupo) => {
              const colapsado = !!gruposColapsados[grupo.titulo]
              return (
                <div key={grupo.titulo} className="mb-3">
                  {sidebarOpen && (
                    <button
                      type="button"
                      onClick={() =>
                        setGruposColapsados((prev) => ({ ...prev, [grupo.titulo]: !prev[grupo.titulo] }))
                      }
                      className="w-full flex items-center justify-between px-3 py-1.5 text-[10px] font-semibold tracking-widest text-slate-500 hover:text-slate-300 uppercase transition-colors"
                    >
                      <span>{grupo.titulo}</span>
                      {colapsado ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                    </button>
                  )}
                  {!colapsado &&
                    grupo.items.map((item) => {
                      const isActive = itemActivo(item)
                      return (
                        <button
                          key={`${item.path}-${item.tab || ''}`}
                          onClick={() => irA(item)}
                          title={sidebarOpen ? undefined : item.label}
                          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                            isActive
                              ? 'bg-primary-600 text-white glow-blue'
                              : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                          }`}
                        >
                          <item.icon size={20} />
                          {sidebarOpen && <span className="text-sm">{item.label}</span>}
                        </button>
                      )
                    })}
                </div>
              )
            })}
        </nav>

        <div className="p-3 border-t border-slate-700">
          {sidebarOpen && <div className="text-xs text-slate-500 mb-2">{user?.correo}</div>}
          <button
            onClick={logout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-slate-400 hover:bg-danger-600/20 hover:text-danger-500 transition-colors"
          >
            <Shield size={20} />
            {sidebarOpen && <span>Cerrar Sesión</span>}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <header className="bg-slate-800 border-b border-slate-700 px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-white">{itemActivoGlobal?.label || 'CELR v6'}</h1>
          <StatusIndicator />
        </header>
        <div className="p-6">{children}</div>
      </main>
    </div>
  )
}

export default Layout