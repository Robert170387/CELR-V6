import React, { useState, useEffect } from 'react'
import { Fuel, Plus, Loader2, AlertCircle, CheckCircle2, XCircle, Pencil, Trash2, X } from 'lucide-react'
import { gastosAPI, viajesAPI, vehiculosAPI } from '@/api'
import Pagination from '@/components/Pagination'
import SelectorCiudad from '@/components/SelectorCiudad'
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
  viaje_id: number | null
  vehiculo_id: number
  categoria: string
  descripcion: string | null
  num_factura: string | null
  fecha_gasto: string
  valor_total: string
  asumido_por: string
  estado_validacion: string
  cantidad_galones: string | null
  precio_por_galon: string | null
  km_registro: string | null
  ciudad_abastecimiento: string | null
  ciudad_abastecimiento_municipio_id?: number | null
}

const categorias = ['combustible', 'peaje', 'viaticos', 'mantenimiento', 'lavado', 'parqueadero', 'otros']
const asumidoPor = ['empresa', 'owner', 'conductor']
const responsablePago = ['conductor', 'empresa', 'tarjeta_empresa']

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
  cantidad_galones: '',
  precio_por_galon: '',
  km_registro: '',
  ciudad_abastecimiento: '',
  ciudad_abastecimiento_municipio_id: '',
})

const camposBaseEdicion: { name: string; label: string }[] = [
  { name: 'viaje_id', label: 'Viaje / ODT' },
  { name: 'vehiculo_id', label: 'Vehículo' },
  { name: 'categoria', label: 'Categoría' },
  { name: 'fecha_gasto', label: 'Fecha' },
  { name: 'valor_total', label: 'Valor Total' },
  { name: 'num_factura', label: 'N° Factura' },
  { name: 'asumido_por', label: 'Asumido por' },
  { name: 'responsable_pago', label: 'Responsable de pago' },
  { name: 'descripcion', label: 'Descripción' },
]

const camposCombustibleEdicion: { name: string; label: string }[] = [
  { name: 'cantidad_galones', label: 'Cantidad de galones' },
  { name: 'precio_por_galon', label: 'Precio por galón' },
  { name: 'km_registro', label: 'Kilometraje del vehículo' },
  { name: 'ciudad_abastecimiento', label: 'Ciudad de abastecimiento' },
]

const camposEdicionPara = (categoria: string) => {
  const base = [...camposBaseEdicion]
  if (categoria !== 'combustible') return base
  const indiceValor = base.findIndex((c) => c.name === 'valor_total')
  base.splice(indiceValor + 1, 0, ...camposCombustibleEdicion)
  return base
}

const Gastos: React.FC = () => {
  const PAGE_SIZE = 100
  const [gastos, setGastos] = useState<Gasto[]>([])
  const [totalGastos, setTotalGastos] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [viajes, setViajes] = useState<Viaje[]>([])
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([])
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [listError, setListError] = useState('')
  const [formError, setFormError] = useState('')
  const [success, setSuccess] = useState('')

  const [editando, setEditando] = useState<Gasto | null>(null)
  const [editForm, setEditForm] = useState<Record<string, string>>({})
  const [editError, setEditError] = useState('')
  const [editandoSubmit, setEditandoSubmit] = useState(false)

  const [eliminarTarget, setEliminarTarget] = useState<Gasto | null>(null)
  const [eliminarError, setEliminarError] = useState('')
  const [eliminando, setEliminando] = useState(false)

  const cargarDatos = async () => {
    setLoading(true)
    setListError('')
    try {
      const [gastosRes, viajesRes, vehiculosRes] = await Promise.all([
        gastosAPI.listar({ skip: (pagina - 1) * PAGE_SIZE, limit: PAGE_SIZE }),
        viajesAPI.listar(false),
        vehiculosAPI.listar(),
      ])
      const activos = (viajesRes.data as Viaje[]).filter(
        (v) => v.estado !== 'liquidado' && v.estado !== 'cancelado'
      )
      setGastos(gastosRes.data)
      setTotalGastos(gastosRes.total)
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
  }, [pagina])

  const recargarGastos = async () => {
    const gastosRes = await gastosAPI.listar({ skip: (pagina - 1) * PAGE_SIZE, limit: PAGE_SIZE })
    setGastos(gastosRes.data)
    setTotalGastos(gastosRes.total)
  }

const SIN_VIAJE = 'gasto_fijo'

const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
  if (e.target.name === 'viaje_id' && e.target.value === SIN_VIAJE) {
    setForm({ ...form, viaje_id: e.target.value, categoria: 'mantenimiento' })
    return
  }
  const cambios: Record<string, string> = { [e.target.name]: e.target.value }
  if (
    form.categoria === 'combustible' &&
    (e.target.name === 'cantidad_galones' || e.target.name === 'precio_por_galon')
  ) {
    const gal = e.target.name === 'cantidad_galones' ? Number(e.target.value) : Number(form.cantidad_galones)
    const ppg = e.target.name === 'precio_por_galon' ? Number(e.target.value) : Number(form.precio_por_galon)
    if (gal > 0 && ppg > 0) {
      cambios.valor_total = (Math.round(gal * ppg * 100) / 100).toFixed(2)
    }
  }
  setForm({ ...form, ...cambios })
}

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')
    if (!form.vehiculo_id) {
      setFormError('Selecciona un vehículo')
      return
    }
    setSubmitting(true)
    const payload: Record<string, any> = {
      vehiculo_id: Number(form.vehiculo_id),
      categoria: form.categoria,
      descripcion: form.descripcion || undefined,
      num_factura: form.num_factura || undefined,
      fecha_gasto: form.fecha_gasto,
      valor_total: form.valor_total,
      asumido_por: form.asumido_por,
      responsable_pago: form.responsable_pago,
      tiene_num_factura: Boolean(form.num_factura),
    }
    if (form.viaje_id && form.viaje_id !== SIN_VIAJE) {
      payload.viaje_id = Number(form.viaje_id)
    }
    if (!payload.viaje_id) {
      payload.categoria = 'mantenimiento'
      payload.descripcion = form.descripcion || 'Gasto fijo / mantenimiento de vehículo'
    }
    if (payload.categoria === 'combustible') {
      payload.cantidad_galones = form.cantidad_galones ? Number(form.cantidad_galones) : undefined
      payload.precio_por_galon = form.precio_por_galon ? Number(form.precio_por_galon) : undefined
      payload.km_registro = form.km_registro ? Number(form.km_registro) : undefined
      payload.ciudad_abastecimiento = form.ciudad_abastecimiento || undefined
      if (form.ciudad_abastecimiento_municipio_id) {
        payload.ciudad_abastecimiento_municipio_id = Number(form.ciudad_abastecimiento_municipio_id)
      }
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

  const abrirEdicion = (gasto: Gasto) => {
    const values: Record<string, string> = {}
    for (const campo of camposEdicionPara(gasto.categoria)) {
      const v = (gasto as any)[campo.name]
      values[campo.name] = v === null || v === undefined ? '' : String(v)
    }
    values.ciudad_abastecimiento_municipio_id = gasto.ciudad_abastecimiento_municipio_id
      ? String(gasto.ciudad_abastecimiento_municipio_id)
      : ''
    setEditando(gasto)
    setEditForm(values)
    setEditError('')
  }

  const handleEditChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setEditForm({ ...editForm, [e.target.name]: e.target.value })
  }

  const guardarEdicion = async (e: React.FormEvent) => {
    e.preventDefault()
    setEditError('')
    if (!editando) return
    if (!editForm.vehiculo_id) {
      setEditError('Selecciona un vehículo')
      return
    }

    const payload: Record<string, any> = {
      vehiculo_id: Number(editForm.vehiculo_id),
      categoria: editForm.categoria,
      fecha_gasto: editForm.fecha_gasto,
      valor_total: Number(editForm.valor_total),
    }
    if (editForm.viaje_id) payload.viaje_id = Number(editForm.viaje_id)
    if (editForm.descripcion) payload.descripcion = editForm.descripcion
    if (editForm.num_factura) payload.num_factura = editForm.num_factura
    if (editForm.asumido_por) payload.asumido_por = editForm.asumido_por
    if (editForm.responsable_pago) payload.responsable_pago = editForm.responsable_pago
    if (editForm.categoria === 'combustible') {
      if (editForm.cantidad_galones) payload.cantidad_galones = Number(editForm.cantidad_galones)
      if (editForm.precio_por_galon) payload.precio_por_galon = Number(editForm.precio_por_galon)
      if (editForm.km_registro) payload.km_registro = Number(editForm.km_registro)
      if (editForm.ciudad_abastecimiento) payload.ciudad_abastecimiento = editForm.ciudad_abastecimiento
      payload.ciudad_abastecimiento_municipio_id = editForm.ciudad_abastecimiento_municipio_id
        ? Number(editForm.ciudad_abastecimiento_municipio_id)
        : null
    }

    setEditandoSubmit(true)
    try {
      const res = await gastosAPI.actualizar(editando.id, payload)
      setSuccess(`Gasto #${res.data.id} actualizado correctamente`)
      setEditando(null)
      await recargarGastos()
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
      await gastosAPI.eliminar(eliminarTarget.id)
      setSuccess(`Gasto #${eliminarTarget.id} eliminado correctamente`)
      setEliminarTarget(null)
      await recargarGastos()
    } catch (err) {
      setEliminarError(extraerMensajeError(err))
    } finally {
      setEliminando(false)
    }
  }

  const numeroOdt = (id: number) => viajes.find((v) => v.id === id)?.numero_odt || `ODT #${id}`
  const placaVehiculo = (id: number) => vehiculos.find((v) => v.id === id)?.placa || `Vehículo #${id}`

  const patronesNumericosEdicion: Record<string, { step: string; min: string }> = {
    valor_total: { step: '0.01', min: '0' },
    cantidad_galones: { step: '0.001', min: '0.001' },
    precio_por_galon: { step: '0.01', min: '0.01' },
    km_registro: { step: '1', min: '0' },
  }

  const renderCampoEdicion = (campo: { name: string; label: string }) => {
    if (campo.name === 'viaje_id') {
      return (
        <select name={campo.name} value={editForm[campo.name] || ''} onChange={handleEditChange} className="input-truck">
          <option value="">Gastos fijos / Mantenimiento (sin ODT)</option>
          {viajes.map((v) => (
            <option key={v.id} value={v.id}>
              {v.numero_odt} ({v.estado})
            </option>
          ))}
        </select>
      )
    }
    if (campo.name === 'vehiculo_id') {
      return (
        <select name={campo.name} value={editForm[campo.name] || ''} onChange={handleEditChange} className="input-truck" required>
          <option value="">Selecciona un vehículo</option>
          {vehiculos.map((v) => (
            <option key={v.id} value={v.id}>
              {v.placa} - {v.marca}
            </option>
          ))}
        </select>
      )
    }
    if (campo.name === 'categoria') {
      return (
        <select name={campo.name} value={editForm[campo.name] || ''} onChange={handleEditChange} className="input-truck">
          {categorias.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      )
    }
    if (campo.name === 'asumido_por') {
      return (
        <select name={campo.name} value={editForm[campo.name] || ''} onChange={handleEditChange} className="input-truck">
          {asumidoPor.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      )
    }
    if (campo.name === 'responsable_pago') {
      return (
        <select name={campo.name} value={editForm[campo.name] || ''} onChange={handleEditChange} className="input-truck">
          {responsablePago.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      )
    }
    if (campo.name === 'descripcion') {
      return (
        <input
          type="text"
          name={campo.name}
          value={editForm[campo.name] || ''}
          onChange={handleEditChange}
          className="input-truck"
          placeholder="Detalle del gasto"
        />
      )
    }
    if (campo.name === 'ciudad_abastecimiento') {
      return (
        <SelectorCiudad
          value={editForm.ciudad_abastecimiento_municipio_id || ''}
          onChange={(id, texto) =>
            setEditForm((f) => ({ ...f, ciudad_abastecimiento_municipio_id: id, ciudad_abastecimiento: texto }))
          }
        />
      )
    }
    const patron = patronesNumericosEdicion[campo.name]
    return (
      <input
        type={campo.name === 'fecha_gasto' ? 'date' : patron ? 'number' : 'text'}
        name={campo.name}
        value={editForm[campo.name] || ''}
        onChange={handleEditChange}
        className="input-truck"
        min={patron ? patron.min : undefined}
        step={patron ? patron.step : undefined}
        required={campo.name === 'fecha_gasto' || !!patron}
      />
    )
  }

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
            <select name="viaje_id" value={form.viaje_id} onChange={handleChange} className="input-truck">
              <option value="">Selecciona un viaje</option>
              <option value={SIN_VIAJE}>
                Gastos fijos / Mantenimiento (sin ODT)
              </option>
              {viajes.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.numero_odt} ({v.estado})
                </option>
              ))}
            </select>
            {form.viaje_id === SIN_VIAJE && (
              <p className="text-xs text-yellow-400 mt-1">
                Sin ODT: se clasificará como Gasto Fijo / Mantenimiento de Vehículo.
              </p>
            )}
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
            <select
              name="categoria"
              value={form.categoria}
              onChange={handleChange}
              className="input-truck"
              disabled={form.viaje_id === SIN_VIAJE}
            >
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

          {form.categoria === 'combustible' && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Cantidad de galones</label>
                <input
                  type="number"
                  name="cantidad_galones"
                  value={form.cantidad_galones}
                  onChange={handleChange}
                  className="input-truck"
                  placeholder="50.5"
                  min="0.001"
                  step="0.001"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Precio por galón</label>
                <input
                  type="number"
                  name="precio_por_galon"
                  value={form.precio_por_galon}
                  onChange={handleChange}
                  className="input-truck"
                  placeholder="12000"
                  min="0.01"
                  step="0.01"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Kilometraje del vehículo</label>
                <input
                  type="number"
                  name="km_registro"
                  value={form.km_registro}
                  onChange={handleChange}
                  className="input-truck"
                  placeholder="125000"
                  min="0"
                  step="1"
                  required
                />
                <p className="text-xs text-slate-500 mt-1">Actualizará el km actual del vehículo si es mayor.</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Ciudad de abastecimiento</label>
                <SelectorCiudad
                  value={form.ciudad_abastecimiento_municipio_id}
                  onChange={(id, texto) =>
                    setForm((f) => ({ ...f, ciudad_abastecimiento_municipio_id: id, ciudad_abastecimiento: texto }))
                  }
                />
              </div>
            </>
          )}

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
                  <th className="py-2 px-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {gastos.map((g) => (
                  <tr key={g.id} className="border-b border-slate-800 last:border-0">
                    <td className="py-3 px-3 text-slate-400">{g.fecha_gasto}</td>
                    <td className="py-3 px-3 font-mono text-primary-400">
                    {g.viaje_id ? (
                      numeroOdt(g.viaje_id)
                    ) : (
                      <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded-full text-xs uppercase tracking-wide">
                        Gasto fijo / Mant.
                      </span>
                    )}
                  </td>
                    <td className="py-3 px-3 text-white">{placaVehiculo(g.vehiculo_id)}</td>
                    <td className="py-3 px-3 text-white capitalize">{g.categoria}</td>
                    <td className="py-3 px-3 text-slate-400">{g.num_factura || '-'}</td>
                    <td className="py-3 px-3 text-slate-400 capitalize">{g.asumido_por}</td>
                    <td className="py-3 px-3 text-right text-white">{formatearMoneda(g.valor_total)}</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => abrirEdicion(g)}
                          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-primary-400 transition-colors"
                          title="Editar"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEliminarError('')
                            setEliminarTarget(g)
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
            <Pagination total={totalGastos} page={pagina} pageSize={PAGE_SIZE} onPage={setPagina} />
          </div>
        )}
      </div>

      {editando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Pencil size={18} className="text-primary-400" />
                Editar Gasto #{editando.id}
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
              {camposEdicionPara(editForm.categoria || '').map((campo) => (
                <div key={campo.name} className={campo.name === 'descripcion' ? 'md:col-span-2' : ''}>
                  <label className="block text-sm font-medium text-slate-300 mb-1">{campo.label}</label>
                  {renderCampoEdicion(campo)}
                </div>
              ))}
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
                  ¿Seguro que deseas eliminar el gasto{' '}
                  <span className="text-white font-semibold">#{eliminarTarget.id}</span> con valor{' '}
                  <span className="text-white font-semibold">{formatearMoneda(eliminarTarget.valor_total)}</span>? Esta
                  acción no se puede deshacer.
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

export default Gastos