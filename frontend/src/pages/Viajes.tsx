import React, { useState, useEffect } from 'react'
import { Package, Truck, Plus, Loader2, AlertCircle, CheckCircle2, XCircle } from 'lucide-react'
import { viajesAPI, vehiculosAPI, conductoresAPI } from '@/api'
import { extraerMensajeError, esErrorDeRed } from '@/utils/format'
import { encolarOffline } from '@/utils/offlineStore'
import { useAuth } from '@/context/AuthContext'

interface Vehiculo {
  id: number
  placa: string
  marca: string
}

interface Conductor {
  id: number
  nombre_completo: string
  cedula: string
}

interface Viaje {
  id: number
  numero_odt: string
  vehiculo_id: number
  conductor_id: number
  origen: string
  destino: string
  fecha_salida: string
  estado: string
  flete_neto: string | null
}

const estadoStyles: Record<string, string> = {
  en_curso: 'bg-blue-500/20 text-blue-400',
  programado: 'bg-yellow-500/20 text-yellow-400',
  completado: 'bg-green-500/20 text-green-400',
  liquidado: 'bg-purple-500/20 text-purple-400',
  cancelado: 'bg-red-500/20 text-red-400',
}

const estadoItems = [
  { value: 'en_curso', label: 'En curso' },
  { value: 'programado', label: 'Programado' },
  { value: 'completado', label: 'Completado' },
  { value: 'cancelado', label: 'Cancelado' },
]

const initialForm = {
  numero_odt: '',
  vehiculo_id: '',
  conductor_id: '',
  origen: '',
  destino: '',
  fecha_salida: '',
  valor_flete_manifiesto: '',
  retefuente_valor: '',
  reteica_valor: '',
  estado: 'en_curso',
}

const Viajes: React.FC = () => {
  const { user } = useAuth()
  const esConductor = user?.rol === 'conductor'
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([])
  const [conductores, setConductores] = useState<Conductor[]>([])
  const [viajes, setViajes] = useState<Viaje[]>([])
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [formError, setFormError] = useState('')

  const cargarDatos = async () => {
    setLoading(true)
    setError('')
    try {
      const viajesPromise =
        esConductor && user?.conductor_id
          ? viajesAPI.porConductor(user.conductor_id)
          : viajesAPI.listar(false)
      const [viajesRes, vehiculosRes, conductoresRes] = await Promise.all([
        viajesPromise,
        vehiculosAPI.listar(),
        conductoresAPI.listar(),
      ])
      setViajes(viajesRes.data)
      setVehiculos(vehiculosRes.data)
      setConductores(conductoresRes.data)
      if (!form.vehiculo_id && vehiculosRes.data.length > 0) {
        setForm((f) => ({ ...f, vehiculo_id: String(vehiculosRes.data[0].id) }))
      }
      if (!form.conductor_id && conductoresRes.data.length > 0) {
        setForm((f) => ({ ...f, conductor_id: String(conductoresRes.data[0].id) }))
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudieron cargar los datos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarDatos()
  }, [user?.id])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')
    if (!form.vehiculo_id || !form.conductor_id) {
      setFormError('Selecciona un vehículo y un conductor')
      return
    }
    setSubmitting(true)
    const payload: Record<string, any> = {
      numero_odt: form.numero_odt.trim(),
      vehiculo_id: Number(form.vehiculo_id),
      conductor_id: Number(form.conductor_id),
      origen: form.origen.trim(),
      destino: form.destino.trim(),
      fecha_salida: form.fecha_salida,
      estado: form.estado,
    }
    if (form.valor_flete_manifiesto) payload.valor_flete_manifiesto = form.valor_flete_manifiesto
    if (form.retefuente_valor) payload.retefuente_valor = form.retefuente_valor
    if (form.reteica_valor) payload.reteica_valor = form.reteica_valor
    try {
      await viajesAPI.crear(payload)
      setSuccess(`ODT ${form.numero_odt.trim()} creada correctamente`)
      setForm((f) => ({ ...initialForm, vehiculo_id: String(f.vehiculo_id), conductor_id: String(f.conductor_id) }))
      const viajesRes = await viajesAPI.listar(false)
      setViajes(viajesRes.data)
    } catch (err: any) {
      if (esErrorDeRed(err)) {
        try {
          const colaId = await encolarOffline('viaje', payload)
          setSuccess(
            `Sin conexión. ODT guardada en cola local (#${colaId}); se enviará automáticamente al recuperar la red.`
          )
          setForm((f) => ({ ...initialForm, vehiculo_id: String(f.vehiculo_id), conductor_id: String(f.conductor_id) }))
        } catch {
          setFormError('Sin conexión y no se pudo guardar la ODT localmente.')
        }
      } else {
        setFormError(extraerMensajeError(err))
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Viajes</h2>
          <p className="text-slate-400">Gestión de Órdenes de Trabajo</p>
        </div>
      </div>

      {!esConductor && (
        <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Plus size={20} />
          Nueva ODT
        </h3>

        {formError && (
          <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
            <AlertCircle size={18} />
            <span>{formError}</span>
          </div>
        )}
        {success && (
          <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 text-green-500 px-4 py-3 rounded-lg mb-4">
            <CheckCircle2 size={18} />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Número ODT</label>
            <input
              type="text"
              name="numero_odt"
              value={form.numero_odt}
              onChange={handleChange}
              className="input-truck"
              placeholder="ODT-2026-001"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Vehículo</label>
            <select
              name="vehiculo_id"
              value={form.vehiculo_id}
              onChange={handleChange}
              className="input-truck"
              required
            >
              <option value="">Selecciona un vehículo</option>
              {vehiculos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.placa} - {v.marca}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Conductor</label>
            <select
              name="conductor_id"
              value={form.conductor_id}
              onChange={handleChange}
              className="input-truck"
              required
            >
              <option value="">Selecciona un conductor</option>
              {conductores.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre_completo}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Origen</label>
            <input
              type="text"
              name="origen"
              value={form.origen}
              onChange={handleChange}
              className="input-truck"
              placeholder="Bogotá"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Destino</label>
            <input
              type="text"
              name="destino"
              value={form.destino}
              onChange={handleChange}
              className="input-truck"
              placeholder="Medellín"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Fecha Salida</label>
            <input
              type="date"
              name="fecha_salida"
              value={form.fecha_salida}
              onChange={handleChange}
              className="input-truck"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Valor Flete Manifiesto</label>
            <input
              type="number"
              name="valor_flete_manifiesto"
              value={form.valor_flete_manifiesto}
              onChange={handleChange}
              className="input-truck"
              placeholder="1.000.000"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Retefuente Valor</label>
            <input
              type="number"
              name="retefuente_valor"
              value={form.retefuente_valor}
              onChange={handleChange}
              className="input-truck"
              placeholder="100.000"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Reteica Valor</label>
            <input
              type="number"
              name="reteica_valor"
              value={form.reteica_valor}
              onChange={handleChange}
              className="input-truck"
              placeholder="50.000"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Estado</label>
            <select
              name="estado"
              value={form.estado}
              onChange={handleChange}
              className="input-truck"
            >
              {estadoItems.map((e) => (
                <option key={e.value} value={e.value}>
                  {e.label}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2 lg:col-span-3 flex items-end justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="btn-celr flex items-center gap-2"
            >
              {submitting ? <Loader2 className="animate-spin" size={20} /> : <Plus size={20} />}
              {submitting ? 'Creando...' : 'Crear ODT'}
            </button>
          </div>
        </form>
        </div>
      )}

      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Package size={20} />
          ODTs Registradas
        </h3>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="animate-spin mr-2" size={20} />
            Cargando...
          </div>
        ) : error ? (
          <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg">
            <XCircle size={18} />
            <span>{error}</span>
          </div>
        ) : viajes.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <div className="text-center">
              <Truck className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg">{esConductor ? 'No tienes ODTs asignadas' : 'No hay viajes registrados'}</p>
              <p className="text-sm mt-1">
                {esConductor
                  ? 'Aquí verás los viajes que te sean asignados'
                  : 'Usa el formulario para crear la primera ODT'}
              </p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="py-2 px-3">ODT</th>
                  <th className="py-2 px-3">Vehiculo</th>
                  <th className="py-2 px-3">Conductor</th>
                  <th className="py-2 px-3">Ruta</th>
                  <th className="py-2 px-3">Fecha Salida</th>
                  <th className="py-2 px-3">Flete Neto</th>
                  <th className="py-2 px-3">Estado</th>
                </tr>
              </thead>
              <tbody>
                {viajes.map((viaje) => {
                  const vehiculo = vehiculos.find((v) => v.id === viaje.vehiculo_id)
                  const conductor = conductores.find((c) => c.id === viaje.conductor_id)
                  return (
                    <tr key={viaje.id} className="border-b border-slate-800 last:border-0">
                      <td className="py-3 px-3 font-mono text-primary-400">{viaje.numero_odt}</td>
                      <td className="py-3 px-3 text-white">{vehiculo ? `${vehiculo.placa} - ${vehiculo.marca}` : viaje.vehiculo_id}</td>
                      <td className="py-3 px-3 text-white">{conductor ? conductor.nombre_completo : viaje.conductor_id}</td>
                      <td className="py-3 px-3 text-white">
                        {viaje.origen} → {viaje.destino}
                      </td>
                      <td className="py-3 px-3 text-slate-400">{viaje.fecha_salida}</td>
                      <td className="py-3 px-3 text-white">{viaje.flete_neto ? `$${Number(viaje.flete_neto).toLocaleString('es-CO')}` : '-'}</td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-1 rounded-full text-xs ${estadoStyles[viaje.estado] || 'bg-slate-500/20 text-slate-400'}`}>
                          {viaje.estado}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default Viajes