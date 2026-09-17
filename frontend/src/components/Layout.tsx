import React from 'react'
import { Menu, X, Truck, Package, Fuel, Receipt, Calculator, Shield, RefreshCw, Database } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useOfflineSync } from '@/utils/useOfflineSync'
import { menuPermitido } from '@/utils/rbac'

interface LayoutProps {
  children: React.ReactNode
}

const menuItems = [
  { path: '/', label: 'Dashboard', icon: Truck },
  { path: '/viajes', label: 'Viajes', icon: Package },
  { path: '/gastos', label: 'Gastos', icon: Fuel },
  { path: '/scan', label: 'Scan Receipt', icon: Receipt },
  { path: '/liquidaciones', label: 'Liquidaciones', icon: Calculator },
  { path: '/maestras', label: 'Maestras', icon: Database },
]

const StatusIndicator: React.FC = () => {
  const { isOnline, isSyncing, pendingCount, sync } = useOfflineSync()

  const statusColor = isOnline ? 'bg-green-500' : 'bg-red-500'
  const statusText = isOnline ? (isSyncing ? 'Sincronizando' : 'En línea') : 'Sin conexión'

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5">
        <div className={`w-2.5 h-2.5 rounded-full ${statusColor} ${isSyncing ? 'animate-pulse' : ''}`} />
        <span className={`text-xs font-medium ${isOnline ? 'text-green-400' : 'text-red-400'}`}>
          {statusText}
        </span>
      </div>
      {pendingCount > 0 && (
        <button
          onClick={sync}
          disabled={!isOnline || isSyncing}
          className="flex items-center gap-1 px-2 py-1 bg-primary-600/20 hover:bg-primary-600/40 text-primary-400 rounded-md text-xs transition-colors disabled:opacity-50"
        >
          <RefreshCw size={12} className={isSyncing ? 'animate-spin' : ''} />
          {pendingCount} pendientes
        </button>
      )}
    </div>
  )
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = React.useState(true)
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, user } = useAuth()
  const items = menuPermitido(menuItems, user?.rol)

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

        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {items.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-primary-600 text-white glow-blue'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <item.icon size={20} />
                {sidebarOpen && <span>{item.label}</span>}
              </button>
            )
          })}
        </nav>

        <div className="p-3 border-t border-slate-700">
          {sidebarOpen && (
            <div className="text-xs text-slate-500 mb-2">{user?.correo}</div>
          )}
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
          <h1 className="text-xl font-bold text-white">
            {menuItems.find(m => m.path === location.pathname)?.label || 'CELR v6'}
          </h1>
          <StatusIndicator />
        </header>
        <div className="p-6">{children}</div>
      </main>
    </div>
  )
}

export default Layout
