import React, { useState, useEffect } from 'react'
import { useAuth } from '@/context/AuthContext'
import { Package, Fuel, Calculator, Receipt, Activity, Loader2, XCircle } from 'lucide-react'
import { viajesAPI, gastosAPI } from '@/api'

interface Viaje {
  id: number
  numero_odt: string
  origen: string
  destino: string
  estado: string
  fecha_salida: string
}

interface Gasto {
  id: number
  valor_total: string
  cantidad_galones: string | null
  fecha_gasto: string
  url_imagen: string | null
}

interface Stats {
  viajesActivos: number
  gastosMes: number
  liquidaciones: number
  receipts: number
}

const estadoStyles: Record<string, string> = {
  en_curso: 'bg-blue-500/20 text-blue-400',
  programado: 'bg-yellow-500/20 text-yellow-400',
  completado: 'bg-green-500/20 text-green-400',
  liquidado: 'bg-purple-500/20 text-purple-400',
  cancelado: 'bg-red-500/20 text-red-400',
}

export const formatearMoneda = (valor: number) =>
  `$${valor.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`

const Dashboard: React.FC = () => {
  const { user } = useAuth()
  const [stats, setStats] = useState<Stats>({ viajesActivos: 0, gastosMes: 0, liquidaciones: 0, receipts: 0 })
  const [recientes, setRecientes] = useState<Viaje[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const cargar = async () => {
      setLoading(true)
      setError('')
      try {
        const viajesRequest =
          user?.rol === 'conductor' && user.conductor_id
            ? viajesAPI.porConductor(user.conductor_id)
            : viajesAPI.listar(false)
        const [viajesRes, gastosRes] = await Promise.all([viajesRequest, gastosAPI.listar()])
        const viajes: Viaje[] = viajesRes.data
        const gastos: Gasto[] = gastosRes.data

        if (!active) return

        const hoy = new Date()
        const gastosMes = gastos
          .filter((g) => {
            const fecha = new Date(g.fecha_gasto)
            return fecha.getMonth() === hoy.getMonth() && fecha.getFullYear() === hoy.getFullYear()
          })
          .reduce((acc, g) => acc + Number(g.valor_total || 0), 0)

        const conImagen = gastos.filter((g) => g.url_imagen).length
        setStats({
          viajesActivos: viajes.filter((v) => v.estado === 'en_curso' || v.estado === 'programado').length,
          gastosMes,
          liquidaciones: viajes.filter((v) => v.estado === 'liquidado').length,
          receipts: conImagen > 0 ? conImagen : gastos.length,
        })
        setRecientes([...viajes].sort((a, b) => b.id - a.id).slice(0, 5))
      } catch (err: any) {
        if (active) setError(err?.response?.data?.detail || 'No se pudieron cargar los datos del dashboard')
      } finally {
        if (active) setLoading(false)
      }
    }
    cargar()
    return () => {
      active = false
    }
  }, [user?.id])

  const statCards = [
    { label: 'Viajes Activos', value: String(stats.viajesActivos), icon: Package, color: 'text-blue-400' },
    { label: 'Gastos del Mes', value: formatearMoneda(stats.gastosMes), icon: Fuel, color: 'text-orange-400' },
    { label: 'Liquidaciones', value: String(stats.liquidaciones), icon: Calculator, color: 'text-green-400' },
    { label: 'Receipts Scaneados', value: String(stats.receipts), icon: Receipt, color: 'text-purple-400' },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Dashboard</h2>
        <p className="text-slate-400">Bienvenido, {user?.correo || 'Usuario'}</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-slate-400">
          <Loader2 className="animate-spin mr-2" size={20} />
          Cargando datos...
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg">
          <XCircle size={18} />
          <span>{error}</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {statCards.map((stat) => (
              <div key={stat.label} className="card-truck">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-slate-400 text-sm">{stat.label}</p>
                    <p className="text-3xl font-bold text-white mt-1">{stat.value}</p>
                  </div>
                  <stat.icon className={`w-8 h-8 ${stat.color}`} />
                </div>
              </div>
            ))}
          </div>

          <div className="card-truck">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Activity size={20} />
              Actividad Reciente
            </h3>
            {recientes.length === 0 ? (
              <div className="text-slate-400 text-center py-8">No hay viajes registrados</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-400 border-b border-slate-700">
                      <th className="py-2 px-3">ODT</th>
                      <th className="py-2 px-3">Ruta</th>
                      <th className="py-2 px-3">Fecha Salida</th>
                      <th className="py-2 px-3">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recientes.map((viaje) => (
                      <tr key={viaje.id} className="border-b border-slate-800 last:border-0">
                        <td className="py-3 px-3 font-mono text-primary-400">{viaje.numero_odt}</td>
                        <td className="py-3 px-3 text-white">
                          {viaje.origen} → {viaje.destino}
                        </td>
                        <td className="py-3 px-3 text-slate-400">{viaje.fecha_salida}</td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-1 rounded-full text-xs ${estadoStyles[viaje.estado] || 'bg-slate-500/20 text-slate-400'}`}>
                            {viaje.estado}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default Dashboard