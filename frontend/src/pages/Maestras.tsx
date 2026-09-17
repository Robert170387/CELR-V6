import React, { useEffect, useState } from 'react'
import { Truck, Users, Building2, Plus, Loader2, AlertCircle, CheckCircle2, XCircle, type LucideIcon } from 'lucide-react'
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
  columnas: Columna[]
  campos: Campo[]
  inicial: Record<string, string>
}

function EntityPanel({ titulo, icono: Icono, listar, crear, columnas, campos, inicial }: EntityPanelProps) {
  const [items, setItems] = useState<any[]>([])
  const [form, setForm] = useState<Record<string, string>>(inicial)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [success, setSuccess] = useState('')

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')

    const payload: Record<string, any> = {}
    for (const campo of campos) {
      const raw = form[campo.name]
      if (raw === undefined || raw === '') {
        if (campo.required) {
          setFormError(`El campo "${campo.label}" es obligatorio`)
          return
        }
        continue
      }
      payload[campo.name] = campo.numeric ? Number(raw) : raw
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
  const [tab, setTab] = useState<Tab>('vehiculos')

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
              onClick={() => setTab(t.id)}
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
