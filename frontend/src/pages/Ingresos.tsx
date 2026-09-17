import React, { useState, useEffect } from 'react'
import { Wallet, Plus, Loader2, AlertCircle, CheckCircle2, XCircle, Pencil, Trash2, X } from 'lucide-react'
import { ingresosAPI, viajesAPI } from '@/api'
import { extraerMensajeError, formatearMoneda } from '@/utils/format'

interface Viaje {
  id: number
  numero_odt: string
  vehiculo_id: number
}

interface Ingreso {
  id: number
  viaje_id: number
  vehiculo_id: number
  tipo_ingreso: string
  descripcion: string | null
  fecha_ingreso: string
  valor: string
  forma_pago: string | null
  num_referencia: string | null
  estado_pago: string
  observaciones: string | null
}

const tiposIngreso = [
  'flete',
  'anticipo',
  'cumplido',
  'compensacion',
  'bono',
  'traslado_fondos',
  'aporte_capital',
  'otro',
]

const formasPago = ['transferencia', 'cheque', 'efectivo', 'otro']
const estadosPago = ['pendiente', 'recibido', 'en_disputa']

const inicial = () => ({
  viaje_id: '',
  fecha_ingreso: new Date().toISOString().slice(0, 10),
  tipo_ingreso: 'anticipo',
  valor: '',
  forma_pago: 'transferencia',
  num_referencia: '',
  descripcion: '',
  observaciones: '',
  estado_pago: 'pendiente',
})

const Ingresos: React.FC = () => {
  const [ingresos, setIngresos] = useState<Ingreso[]>([])
  const [viajes, setViajes] = useState<Viaje[]>([])
  const [form, setForm] = useState(inicial)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [listError, setListError] = useState('')
  const [formError, setFormError] = useState('')
  const [success, setSuccess] = useState('')

  const [editando, setEditando] = useState<Ingreso | null>(null)
  const [editForm, setEditForm] = useState<Record<string, string>>({})
  const [editError, setEditError] = useState('')
  const [editandoSubmit, setEditandoSubmit] = useState(false)

  const [eliminarTarget, setEliminarTarget] = useState<Ingreso | null>(null)
  const [eliminarError, setEliminarError] = useState('')
  const [eliminando, setEliminando] = useState(false)

  const cargarDatos = async () => {
    setLoading(true)
    setListError('')
    try {
      const [ingresosRes, viajesRes] = await Promise.all([
        ingresosAPI.listar(),
        viajesAPI.listar(false),
      ])
      setIngresos(ingresosRes.data)
      setViajes(viajesRes.data)
      setForm((f) => ({
        ...f,
        viaje_id: f.viaje_id || (viajesRes.data[0] ? String(viajesRes.data[0].id) : ''),
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

  const recargarIngresos = async () => {
    const res = await ingresosAPI.listar()
    setIngresos(res.data)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const vehiculoDelViaje = (viajeId: string) => {
    const viaje = viajes.find((v) => String(v.id) === viajeId)
    return viaje ? String(viaje.vehiculo_id) : ''
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')
    if (!form.viaje_id) {
      setFormError('Selecciona un viaje para registrar el ingreso')
      return
    }
    const vehiculoId = vehiculoDelViaje(form.viaje_id)
    if (!vehiculoId) {
      setFormError('El viaje seleccionado no tiene vehículo asignado')
      return
    }
    setSubmitting(true)
    const payload: Record<string, any> = {
      viaje_id: Number(form.viaje_id),
      vehiculo_id: Number(vehiculoId),
      tipo_ingreso: form.tipo_ingreso,
      fecha_ingreso: form.fecha_ingreso,
      valor: form.valor,
      estado_pago: form.estado_pago,
    }
    if (form.forma_pago) payload.forma_pago = form.forma_pago
    if (form.num_referencia) payload.num_referencia = form.num_referencia
    if (form.descripcion) payload.descripcion = form.descripcion
    if (form.observaciones) payload.observaciones = form.observaciones
    try {
      const res = await ingresosAPI.crear(payload)
      setSuccess(`Ingreso #${res.data.id} registrado correctamente`)
      setForm({ ...inicial(), viaje_id: form.viaje_id })
      await recargarIngresos()
    } catch (err) {
      setFormError(extraerMensajeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const abrirEdicion = (ingreso: Ingreso) => {
    const valores: Record<string, string> = {
      fecha_ingreso: ingreso.fecha_ingreso,
      tipo_ingreso: ingreso.tipo_ingreso,
      valor: String(ingreso.valor),
      forma_pago: ingreso.forma_pago || '',
      num_referencia: ingreso.num_referencia || '',
      descripcion: ingreso.descripcion || '',
      observaciones: ingreso.observaciones || '',
      estado_pago: ingreso.estado_pago,
    }
    setEditando(ingreso)
    setEditForm(valores)
    setEditError('')
  }

  const handleEditChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setEditForm({ ...editForm, [e.target.name]: e.target.value })
  }

  const guardarEdicion = async (e: React.FormEvent) => {
    e.preventDefault()
    setEditError('')
    if (!editando) return
    const payload: Record<string, any> = {
      tipo_ingreso: editForm.tipo_ingreso,
      fecha_ingreso: editForm.fecha_ingreso,
      valor: editForm.valor,
      estado_pago: editForm.estado_pago,
    }
    if (editForm.forma_pago) payload.forma_pago = editForm.forma_pago
    if (editForm.num_referencia) payload.num_referencia = editForm.num_referencia
    if (editForm.descripcion) payload.descripcion = editForm.descripcion
    if (editForm.observaciones) payload.observaciones = editForm.observaciones
    setEditandoSubmit(true)
    try {
      await ingresosAPI.actualizar(editando.id, payload)
      setSuccess(`Ingreso #${editando.id} actualizado correctamente`)
      setEditando(null)
      await recargarIngresos()
    } catch (err) {
      setEditError(extraerMensajeError(err))
    } finally {
      setEditandoSubmit(false)
    }
  }

  const confirmarEliminar = async () => {
    if (!eliminarTarget) return
    setEliminarError('')
    setEliminando(true)
    try {
      await ingresosAPI.eliminar(eliminarTarget.id)
      setSuccess(`Ingreso #${eliminarTarget.id} eliminado correctamente`)
      setEliminarTarget(null)
      await recargarIngresos()
    } catch (err) {
      setEliminarError(extraerMensajeError(err))
    } finally {
      setEliminando(false)
    }
  }

  const numeroOdt = (id: number) => viajes.find((v) => v.id === id)?.numero_odt || `ODT #${id}`

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Ingresos</h2>
        <p className="text-slate-400">Anticipos, saldos de fletes e ingresos complementarios</p>
      </div>

      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Plus size={20} />
          Registrar Ingreso
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
                  {v.numero_odt}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Tipo de ingreso</label>
            <select name="tipo_ingreso" value={form.tipo_ingreso} onChange={handleChange} className="input-truck">
              {tiposIngreso.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Fecha</label>
            <input type="date" name="fecha_ingreso" value={form.fecha_ingreso} onChange={handleChange} className="input-truck" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Valor</label>
            <input type="number" name="valor" value={form.valor} onChange={handleChange} className="input-truck" min="0.01" step="0.01" placeholder="100000" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Forma de pago</label>
            <select name="forma_pago" value={form.forma_pago} onChange={handleChange} className="input-truck">
              {formasPago.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Estado de pago</label>
            <select name="estado_pago" value={form.estado_pago} onChange={handleChange} className="input-truck">
              {estadosPago.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">N° Referencia</label>
            <input type="text" name="num_referencia" value={form.num_referencia} onChange={handleChange} className="input-truck" placeholder="Comprobante / consignación" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Descripción</label>
            <input type="text" name="descripcion" value={form.descripcion} onChange={handleChange} className="input-truck" placeholder="Anticipo de flete" />
          </div>
          <div className="md:col-span-2 lg:col-span-3">
            <label className="block text-sm font-medium text-slate-300 mb-1">Observaciones</label>
            <input type="text" name="observaciones" value={form.observaciones} onChange={handleChange} className="input-truck" placeholder="Notas adicionales" />
          </div>
          <div className="md:col-span-2 lg:col-span-3 flex justify-end">
            <button type="submit" disabled={submitting} className="btn-celr flex items-center gap-2">
              {submitting ? <Loader2 className="animate-spin" size={20} /> : <Plus size={20} />}
              {submitting ? 'Guardando...' : 'Registrar Ingreso'}
            </button>
          </div>
        </form>
      </div>

      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Wallet size={20} />
          Ingresos Registrados ({ingresos.length})
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
        ) : ingresos.length === 0 ? (
          <div className="text-slate-400 text-center py-8">No hay ingresos registrados</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="py-2 px-3">Fecha</th>
                  <th className="py-2 px-3">ODT</th>
                  <th className="py-2 px-3">Tipo</th>
                  <th className="py-2 px-3">Forma</th>
                  <th className="py-2 px-3">Estado</th>
                  <th className="py-2 px-3 text-right">Valor</th>
                  <th className="py-2 px-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {ingresos.map((ing) => (
                  <tr key={ing.id} className="border-b border-slate-800 last:border-0">
                    <td className="py-3 px-3 text-slate-400">{ing.fecha_ingreso}</td>
                    <td className="py-3 px-3 font-mono text-primary-400">{numeroOdt(ing.viaje_id)}</td>
                    <td className="py-3 px-3 text-white capitalize">{ing.tipo_ingreso}</td>
                    <td className="py-3 px-3 text-slate-400">{ing.forma_pago || '-'}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-1 rounded-full text-xs capitalize ${
                        ing.estado_pago === 'recibido'
                          ? 'bg-green-500/20 text-green-400'
                          : ing.estado_pago === 'en_disputa'
                            ? 'bg-red-500/20 text-red-400'
                            : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {ing.estado_pago}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-white">{formatearMoneda(ing.valor)}</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => abrirEdicion(ing)}
                          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-primary-400 transition-colors"
                          title="Editar"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEliminarError('')
                            setEliminarTarget(ing)
                          }}
                          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-danger-500 transition-colors"
                          title="Eliminar"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Pencil size={18} className="text-primary-400" />
                Editar Ingreso #{editando.id} — {numeroOdt(editando.viaje_id)}
              </h3>
              <button
                type="button"
                onClick={() => setEditando(null)}
                className="p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {editError && (
              <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
                <AlertCircle size={18} />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={guardarEdicion} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Fecha</label>
                <input type="date" name="fecha_ingreso" value={editForm.fecha_ingreso} onChange={handleEditChange} className="input-truck" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Valor</label>
                <input type="number" name="valor" value={editForm.valor} onChange={handleEditChange} className="input-truck" min="0.01" step="0.01" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Tipo de ingreso</label>
                <select name="tipo_ingreso" value={editForm.tipo_ingreso} onChange={handleEditChange} className="input-truck">
                  {tiposIngreso.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Forma de pago</label>
                <select name="forma_pago" value={editForm.forma_pago} onChange={handleEditChange} className="input-truck">
                  <option value="">Sin especificar</option>
                  {formasPago.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Estado de pago</label>
                <select name="estado_pago" value={editForm.estado_pago} onChange={handleEditChange} className="input-truck">
                  {estadosPago.map((e) => (
                    <option key={e} value={e}>
                      {e}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">N° Referencia</label>
                <input type="text" name="num_referencia" value={editForm.num_referencia} onChange={handleEditChange} className="input-truck" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Descripción</label>
                <input type="text" name="descripcion" value={editForm.descripcion} onChange={handleEditChange} className="input-truck" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Observaciones</label>
                <input type="text" name="observaciones" value={editForm.observaciones} onChange={handleEditChange} className="input-truck" />
              </div>
              <div className="md:col-span-2 flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditando(null)}
                  className="py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Cancelar
                </button>
                <button type="submit" disabled={editandoSubmit} className="btn-celr flex items-center gap-2">
                  {editandoSubmit ? <Loader2 className="animate-spin" size={20} /> : <CheckCircle2 size={20} />}
                  {editandoSubmit ? 'Guardando...' : 'Guardar cambios'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {eliminarTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-md">
            <div className="flex items-start gap-3 mb-4">
              <div className="p-2 rounded-full bg-danger-500/20 text-danger-500">
                <Trash2 size={22} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Confirmar eliminación</h3>
                <p className="text-sm text-slate-400 mt-1">
                  ¿Seguro que deseas eliminar el ingreso{' '}
                  <span className="text-white font-semibold">#{eliminarTarget.id}</span> de{' '}
                  <span className="text-white font-semibold">{formatearMoneda(eliminarTarget.valor)}</span>? Esta acción
                  no se puede deshacer.
                </p>
              </div>
            </div>

            {eliminarError && (
              <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
                <AlertCircle size={18} />
                <span>{eliminarError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setEliminarTarget(null)}
                className="py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={confirmarEliminar}
                disabled={eliminando}
                className="btn-celr-danger flex items-center gap-2"
              >
                {eliminando ? <Loader2 className="animate-spin" size={20} /> : <Trash2 size={18} />}
                {eliminando ? 'Eliminando...' : 'Eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Ingresos