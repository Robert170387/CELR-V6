import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Truck, Users, Building2, Plus, Loader2, AlertCircle, CheckCircle2, XCircle, Pencil, Trash2, X, type LucideIcon } from 'lucide-react'
import { vehiculosAPI, conductoresAPI, proveedoresAPI } from '@/api'
import { extraerMensajeError } from '@/utils/format'

interface Campo {
  name: string
  label: string
  type?: 'text' | 'number' | 'select'
  required?: boolean
  numeric?: boolean
  placeholder?: string
  options?: { value: string; label: string }[]
}

interface Columna {
  key: string
  label: string
}

interface EntityPanelProps {
  titulo: string
  icono: LucideIcon
  listar: () => Promise<{ data: any[] }>
  crear: (data: any) => Promise<{ data: any }>
  actualizar: (id: number, data: any) => Promise<{ data: any }>
  eliminar: (id: number) => Promise<any>
  columnas: Columna[]
  campos: Campo[]
  inicial: Record<string, string>
  campoIdentificador: string
}

function EntityPanel({ titulo, icono: Icono, listar, crear, actualizar, eliminar, columnas, campos, inicial, campoIdentificador }: EntityPanelProps) {
  const [items, setItems] = useState<any[]>([])
  const [form, setForm] = useState<Record<string, string>>(inicial)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [success, setSuccess] = useState('')

  const [editando, setEditando] = useState<any | null>(null)
  const [editForm, setEditForm] = useState<Record<string, string>>({})
  const [editError, setEditError] = useState('')
  const [editandoSubmit, setEditandoSubmit] = useState(false)

  const [eliminarTarget, setEliminarTarget] = useState<any | null>(null)
  const [eliminarError, setEliminarError] = useState('')
  const [eliminando, setEliminando] = useState(false)

  const cargar = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await listar()
      setItems(res.data)
    } catch (err) {
      setError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargar()
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const construirPayload = (values: Record<string, string>) => {
    const payload: Record<string, any> = {}
    for (const campo of campos) {
      const raw = values[campo.name]
      if (raw === undefined || raw === '') {
        if (campo.required) return { error: `El campo "${campo.label}" es obligatorio` }
        continue
      }
      payload[campo.name] = campo.numeric ? Number(raw) : raw
    }
    return { payload }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')

    const { payload, error: errPayload } = construirPayload(form)
    if (errPayload) {
      setFormError(errPayload)
      return
    }

    setSubmitting(true)
    try {
      const res = await crear(payload)
      setSuccess(`${titulo} registrado correctamente (ID ${res.data.id})`)
      setForm(inicial)
      await cargar()
    } catch (err) {
      setFormError(extraerMensajeError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const abrirEdicion = (item: any) => {
    const values: Record<string, string> = {}
    for (const campo of campos) {
      const v = item[campo.name]
      values[campo.name] = v === null || v === undefined ? '' : String(v)
    }
    setEditando(item)
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

    const { payload, error: errPayload } = construirPayload(editForm)
    if (errPayload) {
      setEditError(errPayload)
      return
    }

    setEditandoSubmit(true)
    try {
      const res = await actualizar(editando.id, payload)
      setSuccess(`${titulo} #${res.data.id} actualizado correctamente`)
      setEditando(null)
      await cargar()
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
      await eliminar(eliminarTarget.id)
      setSuccess(`${titulo} #${eliminarTarget.id} eliminado correctamente`)
      setEliminarTarget(null)
      await cargar()
    } catch (err) {
      setEliminarError(extraerMensajeError(err))
    } finally {
      setEliminando(false)
    }
  }

  const identificador = (item: any) => String(item[campoIdentificador] ?? item.id)

  return (
    <div className="space-y-6">
      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Plus size={20} />
          Nuevo {titulo.toLowerCase()}
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
          {campos.map((campo) => (
            <div key={campo.name}>
              <label className="block text-sm font-medium text-slate-300 mb-1">
                {campo.label}
                {campo.required && <span className="text-danger-500"> *</span>}
              </label>
              {campo.type === 'select' ? (
                <select
                  name={campo.name}
                  value={form[campo.name] || ''}
                  onChange={handleChange}
                  className="input-truck"
                  required={campo.required}
                >
                  <option value="">Selecciona...</option>
                  {campo.options?.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={campo.type || 'text'}
                  name={campo.name}
                  value={form[campo.name] || ''}
                  onChange={handleChange}
                  className="input-truck"
                  placeholder={campo.placeholder}
                  required={campo.required}
                />
              )}
            </div>
          ))}

          <div className="md:col-span-2 lg:col-span-3 flex items-end justify-end">
            <button type="submit" disabled={submitting} className="btn-celr flex items-center gap-2">
              {submitting ? <Loader2 className="animate-spin" size={20} /> : <Plus size={20} />}
              {submitting ? 'Guardando...' : 'Agregar'}
            </button>
          </div>
        </form>
      </div>

      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Icono size={20} />
          {titulo} registrados ({items.length})
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
        ) : items.length === 0 ? (
          <div className="text-slate-400 text-center py-8">No hay registros aún</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  {columnas.map((c) => (
                    <th key={c.key} className="py-2 px-3">
                      {c.label}
                    </th>
                  ))}
                  <th className="py-2 px-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-800 last:border-0">
                    {columnas.map((c) => (
                      <td key={c.key} className="py-3 px-3 text-white">
                        {item[c.key] === null || item[c.key] === undefined || item[c.key] === ''
                          ? '-'
                          : String(item[c.key])}
                      </td>
                    ))}
                    <td className="py-3 px-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => abrirEdicion(item)}
                          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-primary-400 transition-colors"
                          title="Editar"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEliminarError('')
                            setEliminarTarget(item)
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
                Editar {titulo.toLowerCase()} {identificador(editando)}
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
              {campos.map((campo) => (
                <div key={campo.name}>
                  <label className="block text-sm font-medium text-slate-300 mb-1">{campo.label}</label>
                  {campo.type === 'select' ? (
                    <select
                      name={campo.name}
                      value={editForm[campo.name] || ''}
                      onChange={handleEditChange}
                      className="input-truck"
                    >
                      <option value="">Selecciona...</option>
                      {campo.options?.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={campo.type || 'text'}
                      name={campo.name}
                      value={editForm[campo.name] || ''}
                      onChange={handleEditChange}
                      className="input-truck"
                      placeholder={campo.placeholder}
                    />
                  )}
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
                  ¿Seguro que deseas eliminar {titulo.toLowerCase()}{' '}
                  <span className="text-white font-semibold">#{identificador(eliminarTarget)}</span>? Esta acción no se
                  puede deshacer.
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

const ESTADOS_VEHICULO = [
  { value: 'activo', label: 'Activo' },
  { value: 'en_taller', label: 'En taller' },
  { value: 'inactivo', label: 'Inactivo' },
]

const ESTADOS_CONDUCTOR = [
  { value: 'activo', label: 'Activo' },
  { value: 'inactivo', label: 'Inactivo' },
  { value: 'vacaciones', label: 'Vacaciones' },
  { value: 'incapacitado', label: 'Incapacitado' },
]

const TIPOS_PROVEEDOR = [
  'combustible',
  'peaje',
  'taller',
  'aseguradora',
  'repuestos',
  'viaticos',
  'administrativo',
  'otro',
].map((t) => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) }))

type Tab = 'vehiculos' | 'conductores' | 'proveedores'

const tabs: { id: Tab; label: string; icono: LucideIcon }[] = [
  { id: 'vehiculos', label: 'Vehículos', icono: Truck },
  { id: 'conductores', label: 'Conductores', icono: Users },
  { id: 'proveedores', label: 'Proveedores', icono: Building2 },
]

const Maestras: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const tab: Tab = (tabParam === 'conductores' || tabParam === 'proveedores') ? tabParam : 'vehiculos'

  const cambiarTab = (t: Tab) => setSearchParams({ tab: t }, { replace: true })

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Entidades Maestras</h2>
        <p className="text-slate-400">Administración de vehículos, conductores y proveedores</p>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-700 pb-2">
        {tabs.map((t) => {
          const activo = tab === t.id
          return (
            <button
              key={t.id}
              onClick={() => cambiarTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
                activo
                  ? 'bg-primary-600 text-white'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <t.icono size={18} />
              {t.label}
            </button>
          )
        })}
      </div>

      {tab === 'vehiculos' && (
        <EntityPanel
          titulo="Vehículo"
          icono={Truck}
          listar={vehiculosAPI.listar}
          crear={vehiculosAPI.crear}
          actualizar={vehiculosAPI.actualizar}
          eliminar={vehiculosAPI.eliminar}
          campoIdentificador="placa"
          columnas={[
            { key: 'placa', label: 'Placa' },
            { key: 'marca', label: 'Marca' },
            { key: 'modelo', label: 'Modelo' },
            { key: 'anio', label: 'Año' },
            { key: 'km_actual', label: 'Km actual' },
            { key: 'estado', label: 'Estado' },
          ]}
          campos={[
            { name: 'placa', label: 'Placa', required: true, placeholder: 'ABC123' },
            { name: 'marca', label: 'Marca', required: true, placeholder: 'Kenworth' },
            { name: 'modelo', label: 'Modelo', placeholder: 'T680' },
            { name: 'anio', label: 'Año', type: 'number', numeric: true },
            { name: 'km_actual', label: 'Km actual', type: 'number', numeric: true },
            { name: 'estado', label: 'Estado', type: 'select', options: ESTADOS_VEHICULO },
          ]}
          inicial={{ placa: '', marca: '', modelo: '', anio: '', km_actual: '', estado: 'activo' }}
        />
      )}

      {tab === 'conductores' && (
        <EntityPanel
          titulo="Conductor"
          icono={Users}
          listar={conductoresAPI.listar}
          crear={conductoresAPI.crear}
          actualizar={conductoresAPI.actualizar}
          eliminar={conductoresAPI.eliminar}
          campoIdentificador="nombre_completo"
          columnas={[
            { key: 'nombre_completo', label: 'Nombre' },
            { key: 'cedula', label: 'Cédula' },
            { key: 'telefono', label: 'Teléfono' },
            { key: 'num_licencia', label: 'Licencia' },
            { key: 'estado', label: 'Estado' },
          ]}
          campos={[
            { name: 'nombre_completo', label: 'Nombre completo', required: true },
            { name: 'cedula', label: 'Cédula', required: true },
            { name: 'telefono', label: 'Teléfono' },
            { name: 'num_licencia', label: 'Número de licencia' },
            { name: 'estado', label: 'Estado', type: 'select', options: ESTADOS_CONDUCTOR },
          ]}
          inicial={{ nombre_completo: '', cedula: '', telefono: '', num_licencia: '', estado: 'activo' }}
        />
      )}

      {tab === 'proveedores' && (
        <EntityPanel
          titulo="Proveedor"
          icono={Building2}
          listar={proveedoresAPI.listar}
          crear={proveedoresAPI.crear}
          actualizar={proveedoresAPI.actualizar}
          eliminar={proveedoresAPI.eliminar}
          campoIdentificador="razon_social"
          columnas={[
            { key: 'razon_social', label: 'Razón social' },
            { key: 'nit', label: 'NIT' },
            { key: 'tipo', label: 'Tipo' },
            { key: 'telefono', label: 'Teléfono' },
            { key: 'ciudad', label: 'Ciudad' },
          ]}
          campos={[
            { name: 'razon_social', label: 'Razón social', required: true },
            { name: 'nit', label: 'NIT' },
            { name: 'tipo', label: 'Tipo', type: 'select', options: TIPOS_PROVEEDOR, required: true },
            { name: 'telefono', label: 'Teléfono' },
            { name: 'ciudad', label: 'Ciudad' },
          ]}
          inicial={{ razon_social: '', nit: '', tipo: '', telefono: '', ciudad: '' }}
        />
      )}
    </div>
  )
}

export default Maestras