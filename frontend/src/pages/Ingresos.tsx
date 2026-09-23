import React, { useState, useEffect } from 'react'
import { Wallet, Plus, Loader2, AlertCircle, CheckCircle2, XCircle, Pencil, Trash2, X } from 'lucide-react'
import { ingresosAPI, viajesAPI, vehiculosAPI, proveedoresAPI } from '@/api'
import Pagination from '@/components/Pagination'
import { extraerMensajeError, formatearMoneda } from '@/utils/format'

interface Viaje {
  id: number
  numero_odt: string
  vehiculo_id: number
}

interface Vehiculo {
  id: number
  placa: string
  marca: string
}

interface Proveedor {
  id: number
  nit: string | null
  razon_social: string
  nombre_comercial: string | null
}

interface Ingreso {
  id: number
  viaje_id: number | null
  vehiculo_id: number
  tipo_ingreso: string
  descripcion: string | null
  fecha_ingreso: string
  valor: string
  forma_pago: string | null
  num_referencia: string | null
  estado_pago: string
  observaciones: string | null
  cliente_origen_id?: number | null
  receptor_destino?: string | null
}

// FASE A2 — enums del modelo contable/operativo
const tiposIngreso = [
  { value: 'anticipo_manifiesto', label: 'Anticipo de manifiesto' },
  { value: 'saldo_flete', label: 'Saldo de flete' },
  { value: 'ajuste_flete', label: 'Ajuste de flete' },
  { value: 'aporte_capital', label: 'Aporte de capital' },
  { value: 'otro', label: 'Otro' },
]

const formasPago = [
  { value: 'transferencia', label: 'Transferencia' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'otro', label: 'Otro' },
]

const estadosPago = [
  { value: 'por_cobrar', label: 'Por cobrar' },
  { value: 'recibido', label: 'Recibido' },
  { value: 'conciliado', label: 'Conciliado' },
]

const labelTipo = (v: string) => tiposIngreso.find((t) => t.value === v)?.label || v
const labelEstado = (v: string) => estadosPago.find((e) => e.value === v)?.label || v

const inicial = () => ({
  viaje_id: '',
  vehiculo_id: '',
  fecha_ingreso: new Date().toISOString().slice(0, 10),
  tipo_ingreso: 'anticipo_manifiesto',
  valor: '',
  forma_pago: 'transferencia',
  num_referencia: '',
  descripcion: '',
  observaciones: '',
  estado_pago: 'por_cobrar',
  cliente_origen_id: '',
  receptor_destino: '',
})

const Ingresos: React.FC = () => {
  const PAGE_SIZE = 100
  const [ingresos, setIngresos] = useState<Ingreso[]>([])
  const [totalIngresos, setTotalIngresos] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [viajes, setViajes] = useState<Viaje[]>([])
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([])
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
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
      const [ingresosRes, viajesRes, vehiculosRes, proveedoresRes] = await Promise.all([
        ingresosAPI.listar(undefined, { skip: (pagina - 1) * PAGE_SIZE, limit: PAGE_SIZE }),
        viajesAPI.listar(false),
        vehiculosAPI.listar(),
        proveedoresAPI.listar(),
      ])
      setIngresos(ingresosRes.data)
      setTotalIngresos(ingresosRes.total)
      setViajes(viajesRes.data)
      setVehiculos(vehiculosRes.data)
      setProveedores(proveedoresRes.data)
    } catch (err) {
      setListError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarDatos()
  }, [pagina])

  const recargarIngresos = async () => {
    const res = await ingresosAPI.listar(undefined, { skip: (pagina - 1) * PAGE_SIZE, limit: PAGE_SIZE })
    setIngresos(res.data)
    setTotalIngresos(res.total)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  // Al elegir una ODT se toma su vehículo; sin ODT el usuario elige vehículo libremente
  const handleViajeChange = (viajeId: string) => {
    setForm((f) => {
      const viaje = viajes.find((v) => String(v.id) === viajeId)
      return {
        ...f,
        viaje_id: viajeId,
        vehiculo_id: viaje ? String(viaje.vehiculo_id) : '',
      }
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')
    if (!form.vehiculo_id) {
      setFormError('Selecciona un vehículo (o una ODT que lo lleve asignado)')
      return
    }
    setSubmitting(true)
    const payload: Record<string, any> = {
      vehiculo_id: Number(form.vehiculo_id),
      tipo_ingreso: form.tipo_ingreso,
      fecha_ingreso: form.fecha_ingreso,
      valor: form.valor,
      estado_pago: form.estado_pago,
    }
    // FASE A2: el ingreso puede existir sin ODT (viaje_id opcional)
    if (form.viaje_id) payload.viaje_id = Number(form.viaje_id)
    if (form.forma_pago) payload.forma_pago = form.forma_pago
    if (form.num_referencia) payload.num_referencia = form.num_referencia
    if (form.descripcion) payload.descripcion = form.descripcion
    if (form.observaciones) payload.observaciones = form.observaciones
    if (form.cliente_origen_id) payload.cliente_origen_id = Number(form.cliente_origen_id)
    if (form.receptor_destino) payload.receptor_destino = form.receptor_destino
    try {
      const res = await ingresosAPI.crear(payload)
      setSuccess(`Ingreso #${res.data.id} registrado correctamente`)
      setForm(inicial())
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
      cliente_origen_id: ingreso.cliente_origen_id ? String(ingreso.cliente_origen_id) : '',
      receptor_destino: ingreso.receptor_destino || '',
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
    payload.cliente_origen_id = editForm.cliente_origen_id ? Number(editForm.cliente_origen_id) : null
    if (editForm.receptor_destino) payload.receptor_destino = editForm.receptor_destino
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

  const numeroOdt = (id: number | null) => (id ? viajes.find((v) => v.id === id)?.numero_odt || `ODT #${id}` : 'General')

  const nombreProveedor = (id: number | null | undefined) => {
    if (!id) return null
    const p = proveedores.find((x) => x.id === id)
    return p ? p.nombre_comercial || p.razon_social : null
  }

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
            <select name="viaje_id" value={form.viaje_id} onChange={(e) => handleViajeChange(e.target.value)} className="input-truck">
              <option value="">Ingreso general (sin ODT)</option>
              {viajes.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.numero_odt}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Vehículo</label>
            <select
              name="vehiculo_id"
              value={form.vehiculo_id}
              onChange={handleChange}
              disabled={!!form.viaje_id}
              className="input-truck"
              required
            >
              <option value="">{form.viaje_id ? 'Tomado de la ODT' : 'Selecciona un vehículo'}</option>
              {vehiculos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.placa} - {v.marca}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Tipo de ingreso</label>
            <select name="tipo_ingreso" value={form.tipo_ingreso} onChange={handleChange} className="input-truck">
              {tiposIngreso.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
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
            <label className="block text-sm font-medium text-slate-300 mb-1">Cliente que despacha</label>
            <select name="cliente_origen_id" value={form.cliente_origen_id} onChange={handleChange} className="input-truck">
              <option value="">Sin especificar</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre_comercial || p.razon_social}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Receptor / destino</label>
            <input type="text" name="receptor_destino" value={form.receptor_destino} onChange={handleChange} className="input-truck" placeholder="¿Quién recibe? (opcional)" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Forma de pago</label>
            <select name="forma_pago" value={form.forma_pago} onChange={handleChange} className="input-truck">
              {formasPago.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Estado de pago</label>
            <select name="estado_pago" value={form.estado_pago} onChange={handleChange} className="input-truck">
              {estadosPago.map((e) => (
                <option key={e.value} value={e.value}>
                  {e.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">N° Referencia</label>
            <input type="text" name="num_referencia" value={form.num_referencia} onChange={handleChange} className="input-truck" placeholder="Comprobante / consignación" />
          </div>
          <div className="md:col-span-2 lg:col-span-3">
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
                {ingresos.map((ing) => {
                  const cliente = nombreProveedor(ing.cliente_origen_id)
                  return (
                    <tr key={ing.id} className="border-b border-slate-800 last:border-0">
                      <td className="py-3 px-3 text-slate-400">{ing.fecha_ingreso}</td>
                      <td className="py-3 px-3 font-mono text-primary-400">{numeroOdt(ing.viaje_id)}</td>
                      <td className="py-3 px-3 text-white">
                        {labelTipo(ing.tipo_ingreso)}
                        {cliente && <span className="block text-xs text-slate-500">{cliente}</span>}
                      </td>
                      <td className="py-3 px-3 text-slate-400">{ing.forma_pago || '-'}</td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-1 rounded-full text-xs capitalize ${
                          ing.estado_pago === 'recibido'
                            ? 'bg-green-500/20 text-green-400'
                            : ing.estado_pago === 'conciliado'
                              ? 'bg-blue-500/20 text-blue-400'
                              : 'bg-yellow-500/20 text-yellow-400'
                        }`}>
                          {labelEstado(ing.estado_pago)}
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
                  )
                })}
              </tbody>
            </table>
            <Pagination total={totalIngresos} page={pagina} pageSize={PAGE_SIZE} onPage={setPagina} />
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
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Cliente que despacha</label>
                <select name="cliente_origen_id" value={editForm.cliente_origen_id} onChange={handleEditChange} className="input-truck">
                  <option value="">Sin especificar</option>
                  {proveedores.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre_comercial || p.razon_social}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Receptor / destino</label>
                <input type="text" name="receptor_destino" value={editForm.receptor_destino} onChange={handleEditChange} className="input-truck" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Forma de pago</label>
                <select name="forma_pago" value={editForm.forma_pago} onChange={handleEditChange} className="input-truck">
                  <option value="">Sin especificar</option>
                  {formasPago.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Estado de pago</label>
                <select name="estado_pago" value={editForm.estado_pago} onChange={handleEditChange} className="input-truck">
                  {estadosPago.map((e) => (
                    <option key={e.value} value={e.value}>
                      {e.label}
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