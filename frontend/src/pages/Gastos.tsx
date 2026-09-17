import React, { useState, useEffect } from 'react'
import { Fuel, Plus, Loader2, AlertCircle, CheckCircle2, XCircle } from 'lucide-react'
import { gastosAPI, viajesAPI, vehiculosAPI } from '@/api'
import { extraerMensajeError, formatearMoneda, esErrorDeRed } from '@/utils/format'
import { encolarOffline } from '@/utils/offlineStore'

interface Viaje {
  id: number
  numero_odt: string
  estado: string
}

interface Vehiculo {
  id: number
  placa: string
  marca: string
}

interface Gasto {
  id: number
  viaje_id: number
  vehiculo_id: number
  categoria: string
  descripcion: string | null
  num_factura: string | null
  fecha_gasto: string
  valor_total: string
  asumido_por: string
  estado_validacion: string
}

const categorias = ['combustible', 'peaje', 'viaticos', 'mantenimiento', 'lavado', 'parqueadero', 'otros']
const asumidoPor = ['empresa', 'owner', 'conductor']
const responsablePago = ['conductor', 'empresa', 'tarjeta_empresa']

const generarHash = () =>
  Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('')

const hoy = () => new Date().toISOString().slice(0, 10)

const initialForm = () => ({
  viaje_id: '',
  vehiculo_id: '',
  categoria: 'combustible',
  descripcion: '',
  num_factura: '',
  fecha_gasto: hoy(),
  valor_total: '',
  asumido_por: 'empresa',
  responsable_pago: 'conductor',
  hash_comprobante: generarHash(),
})

const Gastos: React.FC = () => {
  const [gastos, setGastos] = useState<Gasto[]>([])
  const [viajes, setViajes] = useState<Viaje[]>([])
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([])
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [listError, setListError] = useState('')
  const [formError, setFormError] = useState('')
  const [success, setSuccess] = useState('')

  const cargarDatos = async () => {
    setLoading(true)
    setListError('')
    try {
      const [gastosRes, viajesRes, vehiculosRes] = await Promise.all([
        gastosAPI.listar(),
        viajesAPI.listar(false),
        vehiculosAPI.listar(),
      ])
      const activos = (viajesRes.data as Viaje[]).filter(
        (v) => v.estado !== 'liquidado' && v.estado !== 'cancelado'
      )
      setGastos(gastosRes.data)
      setViajes(activos)
      setVehiculos(vehiculosRes.data)
      setForm((f) => ({
        ...f,
        viaje_id: f.viaje_id || (activos[0] ? String(activos[0].id) : ''),
        vehiculo_id: f.vehiculo_id || (vehiculosRes.data[0] ? String(vehiculosRes.data[0].id) : ''),
      }))
    } catch (err) {
      setListError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarDatos()
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')
    if (!form.viaje_id || !form.vehiculo_id) {
      setFormError('Selecciona un viaje y un vehículo')
      return
    }
    setSubmitting(true)
    const payload = {
      viaje_id: Number(form.viaje_id),
      vehiculo_id: Number(form.vehiculo_id),
      categoria: form.categoria,
      descripcion: form.descripcion || undefined,
      num_factura: form.num_factura || undefined,
      fecha_gasto: form.fecha_gasto,
      valor_total: form.valor_total,
      asumido_por: form.asumido_por,
      responsable_pago: form.responsable_pago,
      tiene_num_factura: Boolean(form.num_factura),
      hash_comprobante: form.hash_comprobante,
    }
    try {
      const res = await gastosAPI.registrar(payload)
      setSuccess(`Gasto #${res.data.id} registrado correctamente`)
      setForm({ ...initialForm(), viaje_id: form.viaje_id, vehiculo_id: form.vehiculo_id })
      const gastosRes = await gastosAPI.listar()
      setGastos(gastosRes.data)
    } catch (err) {
      if (esErrorDeRed(err)) {
        try {
          const colaId = await encolarOffline('gasto', payload)
          setSuccess(
            `Sin conexión. Gasto guardado en cola local (#${colaId}); se enviará automáticamente al recuperar la red.`
          )
          setForm({ ...initialForm(), viaje_id: form.viaje_id, vehiculo_id: form.vehiculo_id })
        } catch {
          setFormError('Sin conexión y no se pudo guardar el gasto localmente.')
        }
      } else {
        setFormError(extraerMensajeError(err))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const numeroOdt = (id: number) => viajes.find((v) => v.id === id)?.numero_odt || `ODT #${id}`
  const placaVehiculo = (id: number) => vehiculos.find((v) => v.id === id)?.placa || `Vehículo #${id}`

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Gastos</h2>
        <p className="text-slate-400">Registro y control de gastos operativos</p>
      </div>

      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Plus size={20} />
          Registrar Gasto
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
            <label className="block text-sm font-medium text-slate-300 mb-1">Viaje / ODT</label>
            <select name="viaje_id" value={form.viaje_id} onChange={handleChange} className="input-truck" required>
              <option value="">Selecciona un viaje</option>
              {viajes.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.numero_odt} ({v.estado})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Vehículo</label>
            <select name="vehiculo_id" value={form.vehiculo_id} onChange={handleChange} className="input-truck" required>
              <option value="">Selecciona un vehículo</option>
              {vehiculos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.placa} - {v.marca}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Categoría</label>
            <select name="categoria" value={form.categoria} onChange={handleChange} className="input-truck">
              {categorias.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Fecha</label>
            <input type="date" name="fecha_gasto" value={form.fecha_gasto} onChange={handleChange} className="input-truck" required />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Valor Total</label>
            <input
              type="number"
              name="valor_total"
              value={form.valor_total}
              onChange={handleChange}
              className="input-truck"
              placeholder="300000"
              min="0.01"
              step="0.01"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">N° Factura</label>
            <input type="text" name="num_factura" value={form.num_factura} onChange={handleChange} className="input-truck" placeholder="FACT-000123" />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Asumido por</label>
            <select name="asumido_por" value={form.asumido_por} onChange={handleChange} className="input-truck">
              {asumidoPor.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Responsable de pago</label>
            <select name="responsable_pago" value={form.responsable_pago} onChange={handleChange} className="input-truck">
              {responsablePago.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Hash comprobante</label>
            <input type="text" name="hash_comprobante" value={form.hash_comprobante} onChange={handleChange} className="input-truck font-mono text-xs" required />
          </div>

          <div className="md:col-span-2 lg:col-span-3">
            <label className="block text-sm font-medium text-slate-300 mb-1">Descripción</label>
            <input type="text" name="descripcion" value={form.descripcion} onChange={handleChange} className="input-truck" placeholder="Detalle del gasto" />
          </div>

          <div className="md:col-span-2 lg:col-span-3 flex justify-end">
            <button type="submit" disabled={submitting} className="btn-celr flex items-center gap-2">
              {submitting ? <Loader2 className="animate-spin" size={20} /> : <Plus size={20} />}
              {submitting ? 'Guardando...' : 'Registrar Gasto'}
            </button>
          </div>
        </form>
      </div>

      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Fuel size={20} />
          Gastos Registrados
        </h3>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="animate-spin mr-2" size={20} />
            Cargando...
          </div>
        ) : listError ? (
          <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg">
            <XCircle size={18} />
            <span>{listError}</span>
          </div>
        ) : gastos.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <div className="text-center">
              <Fuel className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg">No hay gastos registrados</p>
              <p className="text-sm mt-1">Registra un gasto o escanea un receipt</p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="py-2 px-3">Fecha</th>
                  <th className="py-2 px-3">ODT</th>
                  <th className="py-2 px-3">Vehículo</th>
                  <th className="py-2 px-3">Categoría</th>
                  <th className="py-2 px-3">N° Factura</th>
                  <th className="py-2 px-3">Asumido</th>
                  <th className="py-2 px-3 text-right">Valor</th>
                </tr>
              </thead>
              <tbody>
                {gastos.map((g) => (
                  <tr key={g.id} className="border-b border-slate-800 last:border-0">
                    <td className="py-3 px-3 text-slate-400">{g.fecha_gasto}</td>
                    <td className="py-3 px-3 font-mono text-primary-400">{numeroOdt(g.viaje_id)}</td>
                    <td className="py-3 px-3 text-white">{placaVehiculo(g.vehiculo_id)}</td>
                    <td className="py-3 px-3 text-white capitalize">{g.categoria}</td>
                    <td className="py-3 px-3 text-slate-400">{g.num_factura || '-'}</td>
                    <td className="py-3 px-3 text-slate-400 capitalize">{g.asumido_por}</td>
                    <td className="py-3 px-3 text-right text-white">{formatearMoneda(g.valor_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default Gastos