import React, { useState, useEffect, useMemo } from 'react'
import { Package, Truck, Plus, Loader2, AlertCircle, CheckCircle2, XCircle, Pencil, Trash2, X, Calculator, ShieldAlert } from 'lucide-react'
import { viajesAPI, vehiculosAPI, conductoresAPI, gastosAPI, proveedoresAPI } from '@/api'
import Pagination from '@/components/Pagination'
import SelectorCiudad from '@/components/SelectorCiudad'
import { extraerMensajeError, esErrorDeRed, formatearMoneda } from '@/utils/format'
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

interface Proveedor {
  id: number
  nit: string | null
  razon_social: string
  nombre_comercial: string | null
}

interface GastoResumen {
  viaje_id: number | null
  valor_total: string
}

interface Viaje {
  id: number
  numero_odt: string
  vehiculo_id: number
  conductor_id: number
  origen: string
  destino: string
  origen_municipio_id?: number | null
  destino_municipio_id?: number | null
  fecha_salida: string
  estado: string
  // FASE A2 — inputs manuales de la ODT
  tipo_viaje: string
  empresa_manifiesto_id?: number | null
  fecha_manifiesto?: string | null
  valor_flete_manifiesto: string | null
  retefuente_porcentaje?: string | null
  reteica_porcentaje?: string | null
  otras_deducciones?: string | null
  anticipo_manifiesto?: string | null
  porcentaje_comision?: string | null
  // FASE A2 — calculados por el servidor (solo lectura)
  flete_neto: string | null
  retefuente_valor?: string | null
  reteica_valor?: string | null
  comision_conductor?: string | null
  saldo_flete_esperado?: string | null
  gastos_totales_viaje?: string | null
  utilidad_neta_odt?: string | null
  // FASE ODT — inputs del form (existen en modelo/schema; UI añadida)
  num_manifiesto?: string | null
  tipo_carga?: string | null
  peso_declarado_ton?: string | null
  peso_bascula_origen?: string | null
  peso_bascula_destino?: string | null
  km_inicial?: string | null
  km_final?: string | null
  km_recorridos?: string | null
  fecha_llegada?: string | null
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

const tipoViajeItems = [
  { value: 'urbano', label: 'Urbano' },
  { value: 'nacional', label: 'Nacional' },
  { value: 'internacional', label: 'Internacional' },
  { value: 'vacio', label: 'Vacío' },
]

const initialForm = {
  vehiculo_id: '',
  conductor_id: '',
  origen: '',
  origen_municipio_id: '',
  destino: '',
  destino_municipio_id: '',
  fecha_salida: '',
  valor_flete_manifiesto: '',
  retefuente_porcentaje: '',
  reteica_porcentaje: '',
  tipo_viaje: 'nacional',
  empresa_manifiesto_id: '',
  fecha_manifiesto: '',
  otras_deducciones: '',
  anticipo_manifiesto: '',
  porcentaje_comision: '',
  num_manifiesto: '',
  tipo_carga: '',
  peso_declarado_ton: '',
  peso_bascula_origen: '',
  peso_bascula_destino: '',
  km_inicial: '',
  km_final: '',
  fecha_llegada: '',
  estado: 'en_curso',
}

const camposViaje = [
  'numero_odt',
  'vehiculo_id',
  'conductor_id',
  'origen',
  'destino',
  'fecha_salida',
  'tipo_viaje',
  'empresa_manifiesto_id',
  'fecha_manifiesto',
  'valor_flete_manifiesto',
  'retefuente_porcentaje',
  'reteica_porcentaje',
  'otras_deducciones',
  'anticipo_manifiesto',
  'porcentaje_comision',
  'num_manifiesto',
  'tipo_carga',
  'peso_declarado_ton',
  'peso_bascula_origen',
  'peso_bascula_destino',
  'km_inicial',
  'km_final',
  'fecha_llegada',
  'estado',
] as const

const Viajes: React.FC = () => {
  const PAGE_SIZE = 100
  const { user } = useAuth()
  const esConductor = user?.rol === 'conductor'
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([])
  const [conductores, setConductores] = useState<Conductor[]>([])
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [viajes, setViajes] = useState<Viaje[]>([])
  const [totalViajes, setTotalViajes] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [gastos, setGastos] = useState<GastoResumen[]>([])
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [formError, setFormError] = useState('')

  const [editando, setEditando] = useState<Viaje | null>(null)
  const [editForm, setEditForm] = useState<Record<string, string>>({})
  const [editError, setEditError] = useState('')
  const [editandoSubmit, setEditandoSubmit] = useState(false)

  const [eliminarTarget, setEliminarTarget] = useState<Viaje | null>(null)
  const [eliminarError, setEliminarError] = useState('')
  const [eliminando, setEliminando] = useState(false)

  const [bloqueosInfo, setBloqueosInfo] = useState<{ numero_odt: string; cercable: boolean; bloqueos: string[] } | null>(null)
  const [cargandoBloqueos, setCargandoBloqueos] = useState<number | null>(null)

  const cargarDatos = async () => {
    setLoading(true)
    setError('')
    try {
      const viajesPromise =
        esConductor && user?.conductor_id
          ? viajesAPI.porConductor(user.conductor_id)
          : viajesAPI.listar(false, { skip: (pagina - 1) * PAGE_SIZE, limit: PAGE_SIZE })
      const [viajesRes, vehiculosRes, conductoresRes, gastosRes, proveedoresRes] = await Promise.all([
        viajesPromise,
        vehiculosAPI.listar(),
        conductoresAPI.listar(),
        gastosAPI.listar(),
        proveedoresAPI.listar(),
      ])
      setViajes(viajesRes.data)
      setTotalViajes(viajesRes.total)
      setGastos(gastosRes.data)
      setVehiculos(vehiculosRes.data)
      setConductores(conductoresRes.data)
      setProveedores(proveedoresRes.data)
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
  }, [user?.id, pagina])

  const recargarViajes = async () => {
    const viajesRes = esConductor && user?.conductor_id
      ? await viajesAPI.porConductor(user.conductor_id)
      : await viajesAPI.listar(false, { skip: (pagina - 1) * PAGE_SIZE, limit: PAGE_SIZE })
    setViajes(viajesRes.data)
    setTotalViajes(viajesRes.total)
    const gastosRes = await gastosAPI.listar()
    setGastos(gastosRes.data)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const setCiudad = (textoKey: 'origen' | 'destino', muniKey: 'origen_municipio_id' | 'destino_municipio_id') => (
    municipioId: string,
    texto: string
  ) => {
    setForm((f) => ({ ...f, [muniKey]: municipioId, [textoKey]: texto }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    setSuccess('')
    if (!form.vehiculo_id || !form.conductor_id) {
      setFormError('Selecciona un vehículo y un conductor')
      return
    }
    if (!form.origen_municipio_id || !form.destino_municipio_id) {
      setFormError('Selecciona municipio de origen y destino')
      return
    }
    setSubmitting(true)
    const payload: Record<string, any> = {
      vehiculo_id: Number(form.vehiculo_id),
      conductor_id: Number(form.conductor_id),
      origen: form.origen.trim(),
      origen_municipio_id: Number(form.origen_municipio_id),
      destino: form.destino.trim(),
      destino_municipio_id: Number(form.destino_municipio_id),
      fecha_salida: form.fecha_salida,
      estado: form.estado,
    }
    if (form.valor_flete_manifiesto) payload.valor_flete_manifiesto = form.valor_flete_manifiesto
    // FASE A2: el cliente envia SOLO inputs manuales; los calculados los deriva el servidor
    if (form.retefuente_porcentaje) payload.retefuente_porcentaje = Number(form.retefuente_porcentaje)
    if (form.reteica_porcentaje) payload.reteica_porcentaje = Number(form.reteica_porcentaje)
    if (form.tipo_viaje) payload.tipo_viaje = form.tipo_viaje
    if (form.empresa_manifiesto_id) payload.empresa_manifiesto_id = Number(form.empresa_manifiesto_id)
    if (form.fecha_manifiesto) payload.fecha_manifiesto = form.fecha_manifiesto
    if (form.otras_deducciones) payload.otras_deducciones = Number(form.otras_deducciones)
    if (form.anticipo_manifiesto) payload.anticipo_manifiesto = Number(form.anticipo_manifiesto)
    if (form.porcentaje_comision) payload.porcentaje_comision = Number(form.porcentaje_comision)
    // FASE ODT — nuevos inputs del form (ya soportados por el schema/backend)
    if (form.num_manifiesto) payload.num_manifiesto = form.num_manifiesto
    if (form.tipo_carga) payload.tipo_carga = form.tipo_carga
    if (form.peso_declarado_ton) payload.peso_declarado_ton = Number(form.peso_declarado_ton)
    if (form.peso_bascula_origen) payload.peso_bascula_origen = Number(form.peso_bascula_origen)
    if (form.peso_bascula_destino) payload.peso_bascula_destino = Number(form.peso_bascula_destino)
    if (form.km_inicial) payload.km_inicial = Number(form.km_inicial)
    if (form.km_final) payload.km_final = Number(form.km_final)
    if (form.fecha_llegada) payload.fecha_llegada = form.fecha_llegada
    try {
      const creado = await viajesAPI.crear(payload)
      setSuccess(`ODT ${creado.data.numero_odt} creada correctamente`)
      setForm((f) => ({ ...initialForm, vehiculo_id: String(f.vehiculo_id), conductor_id: String(f.conductor_id) }))
      const viajesRes = await viajesAPI.listar(false, { skip: (pagina - 1) * PAGE_SIZE, limit: PAGE_SIZE })
      setViajes(viajesRes.data)
      setTotalViajes(viajesRes.total)
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

  const abrirEdicion = (viaje: Viaje) => {
    const values: Record<string, string> = {}
    for (const campo of camposViaje) {
      const v = (viaje as any)[campo]
      values[campo] = v === null || v === undefined ? '' : String(v)
    }
    values.origen_municipio_id = viaje.origen_municipio_id ? String(viaje.origen_municipio_id) : ''
    values.destino_municipio_id = viaje.destino_municipio_id ? String(viaje.destino_municipio_id) : ''
    setEditando(viaje)
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
    if (!editForm.vehiculo_id || !editForm.conductor_id) {
      setEditError('Selecciona un vehículo y un conductor')
      return
    }

    const payload: Record<string, any> = {
      numero_odt: editForm.numero_odt.trim(),
      vehiculo_id: Number(editForm.vehiculo_id),
      conductor_id: Number(editForm.conductor_id),
      origen: editForm.origen.trim(),
      destino: editForm.destino.trim(),
      fecha_salida: editForm.fecha_salida,
      estado: editForm.estado,
    }
    if (editForm.valor_flete_manifiesto) payload.valor_flete_manifiesto = Number(editForm.valor_flete_manifiesto)
    // FASE A2: solo inputs manuales; retenciones/comision/saldo/utilidad => servidor
    if (editForm.retefuente_porcentaje) payload.retefuente_porcentaje = Number(editForm.retefuente_porcentaje)
    if (editForm.reteica_porcentaje) payload.reteica_porcentaje = Number(editForm.reteica_porcentaje)
    if (editForm.tipo_viaje) payload.tipo_viaje = editForm.tipo_viaje
    payload.empresa_manifiesto_id = editForm.empresa_manifiesto_id ? Number(editForm.empresa_manifiesto_id) : null
    if (editForm.fecha_manifiesto) payload.fecha_manifiesto = editForm.fecha_manifiesto
    if (editForm.otras_deducciones) payload.otras_deducciones = Number(editForm.otras_deducciones)
    if (editForm.anticipo_manifiesto) payload.anticipo_manifiesto = Number(editForm.anticipo_manifiesto)
    if (editForm.porcentaje_comision) payload.porcentaje_comision = Number(editForm.porcentaje_comision)
    // FASE ODT — nuevos inputs del form (ya soportados por el schema/backend)
    if (editForm.num_manifiesto) payload.num_manifiesto = editForm.num_manifiesto
    if (editForm.tipo_carga) payload.tipo_carga = editForm.tipo_carga
    if (editForm.peso_declarado_ton) payload.peso_declarado_ton = Number(editForm.peso_declarado_ton)
    if (editForm.peso_bascula_origen) payload.peso_bascula_origen = Number(editForm.peso_bascula_origen)
    if (editForm.peso_bascula_destino) payload.peso_bascula_destino = Number(editForm.peso_bascula_destino)
    if (editForm.km_inicial) payload.km_inicial = Number(editForm.km_inicial)
    if (editForm.km_final) payload.km_final = Number(editForm.km_final)
    if (editForm.fecha_llegada) payload.fecha_llegada = editForm.fecha_llegada
    payload.origen_municipio_id = editForm.origen_municipio_id ? Number(editForm.origen_municipio_id) : null
    payload.destino_municipio_id = editForm.destino_municipio_id ? Number(editForm.destino_municipio_id) : null

    setEditandoSubmit(true)
    try {
      await viajesAPI.actualizar(editando.id, payload)
      setSuccess(`ODT ${editando.numero_odt} actualizada correctamente`)
      setEditando(null)
      await recargarViajes()
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
      await viajesAPI.eliminar(eliminarTarget.id)
      setSuccess(`ODT ${eliminarTarget.numero_odt} eliminada correctamente`)
      setEliminarTarget(null)
      await recargarViajes()
    } catch (err) {
      setEliminarError(extraerMensajeError(err))
    } finally {
      setEliminando(false)
    }
  }

  const verBloqueosCierre = async (viaje: Viaje) => {
    setCargandoBloqueos(viaje.id)
    setError('')
    try {
      const res = await viajesAPI.bloqueosCierre(viaje.id)
      setBloqueosInfo({ numero_odt: res.numero_odt, cercable: res.cercable, bloqueos: res.bloqueos })
    } catch (err) {
      setError(extraerMensajeError(err))
    } finally {
      setCargandoBloqueos(null)
    }
  }

  const renderCampoEdicion = (campo: (typeof camposViaje)[number]) => {
    if (campo === 'vehiculo_id') {
      return (
        <select name={campo} value={editForm[campo] || ''} onChange={handleEditChange} className="input-truck" required>
          <option value="">Selecciona un vehículo</option>
          {vehiculos.map((v) => (
            <option key={v.id} value={v.id}>
              {v.placa} - {v.marca}
            </option>
          ))}
        </select>
      )
    }
    if (campo === 'conductor_id') {
      return (
        <select name={campo} value={editForm[campo] || ''} onChange={handleEditChange} className="input-truck" required>
          <option value="">Selecciona un conductor</option>
          {conductores.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre_completo}
            </option>
          ))}
        </select>
      )
    }
    if (campo === 'estado') {
      return (
        <select name={campo} value={editForm[campo] || ''} onChange={handleEditChange} className="input-truck">
          {estadoItems.map((e) => (
            <option key={e.value} value={e.value}>
              {e.label}
            </option>
          ))}
        </select>
      )
    }
    if (campo === 'tipo_viaje') {
      return (
        <select name={campo} value={editForm[campo] || 'nacional'} onChange={handleEditChange} className="input-truck">
          {tipoViajeItems.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      )
    }
    if (campo === 'empresa_manifiesto_id') {
      return (
        <select name={campo} value={editForm[campo] || ''} onChange={handleEditChange} className="input-truck">
          <option value="">Sin empresa / cliente</option>
          {proveedores.map((p) => (
            <option key={p.id} value={p.id}>
              {p.nombre_comercial || p.razon_social}
            </option>
          ))}
        </select>
      )
    }
    if (campo === 'origen') {
      return (
        <SelectorCiudad
          value={editForm.origen_municipio_id || ''}
          onChange={(id, texto) => setEditForm((f) => ({ ...f, origen_municipio_id: id, origen: texto }))}
        />
      )
    }
    if (campo === 'destino') {
      return (
        <SelectorCiudad
          value={editForm.destino_municipio_id || ''}
          onChange={(id, texto) => setEditForm((f) => ({ ...f, destino_municipio_id: id, destino: texto }))}
        />
      )
    }
    const esNumero = ['valor_flete_manifiesto', 'retefuente_porcentaje', 'reteica_porcentaje', 'otras_deducciones', 'anticipo_manifiesto', 'porcentaje_comision', 'peso_declarado_ton', 'peso_bascula_origen', 'peso_bascula_destino', 'km_inicial', 'km_final'].includes(campo)
    return (
      <input
        type={campo === 'fecha_salida' || campo === 'fecha_manifiesto' || campo === 'fecha_llegada' ? 'date' : esNumero ? 'number' : 'text'}
        name={campo}
        value={editForm[campo] || ''}
        onChange={handleEditChange}
        className="input-truck"
        min={esNumero ? '0' : undefined}
        step={esNumero ? '0.01' : undefined}
      />
    )
  }

const traduccionCampo: Record<string, string> = {
  numero_odt: 'Número ODT',
  vehiculo_id: 'Vehículo',
  conductor_id: 'Conductor',
  origen: 'Origen',
  destino: 'Destino',
  fecha_salida: 'Fecha salida',
  tipo_viaje: 'Tipo de viaje',
  empresa_manifiesto_id: 'Empresa / Cliente',
  fecha_manifiesto: 'Fecha manifiesto',
  valor_flete_manifiesto: 'Valor flete manifiesto',
  retefuente_porcentaje: 'Retefuente %',
  reteica_porcentaje: 'Reteica %',
  otras_deducciones: 'Otras deducciones',
  anticipo_manifiesto: 'Anticipo de manifiesto',
  porcentaje_comision: '% Comisión',
  num_manifiesto: 'N° Manifiesto',
  tipo_carga: 'Material / carga',
  peso_declarado_ton: 'Peso declarado (ton)',
  peso_bascula_origen: 'Peso báscula origen (ton)',
  peso_bascula_destino: 'Peso báscula destino (ton)',
  km_inicial: 'KMS inicial tacómetro',
  km_final: 'KMS final tacómetro',
  fecha_llegada: 'Fecha llegada',
  estado: 'Estado',
}

const gastosPorViaje = useMemo(() => {
  const mapa: Record<number, number> = {}
  for (const g of gastos) {
    if (g.viaje_id == null) continue
    mapa[g.viaje_id] = (mapa[g.viaje_id] || 0) + Number(g.valor_total || 0)
  }
  return mapa
}, [gastos])

const margenDe = (viaje: Viaje): number | null => {
  const neto = Number(viaje.flete_neto) || Number(viaje.valor_flete_manifiesto) || 0
  if (!viaje.flete_neto && !viaje.valor_flete_manifiesto) return null
  return neto - (gastosPorViaje[viaje.id] || 0)
}

const FilaCalculada: React.FC<{ label: string; valor: number; tono?: string }> = ({ label, valor, tono = 'text-white' }) => (
  <div className="flex items-center justify-between gap-2">
    <span className="text-slate-400">{label}</span>
    <span className={tono}>{formatearMoneda(Math.round(valor * 100) / 100)}</span>
  </div>
)

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
            <SelectorCiudad
              value={form.origen_municipio_id}
              onChange={setCiudad('origen', 'origen_municipio_id')}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Destino</label>
            <SelectorCiudad
              value={form.destino_municipio_id}
              onChange={setCiudad('destino', 'destino_municipio_id')}
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
            <label className="block text-sm font-medium text-slate-300 mb-1">Retefuente %</label>
            <input
              type="number"
              name="retefuente_porcentaje"
              value={form.retefuente_porcentaje}
              onChange={handleChange}
              className="input-truck"
              placeholder="1"
              min="0"
              max="100"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Reteica %</label>
            <input
              type="number"
              name="reteica_porcentaje"
              value={form.reteica_porcentaje}
              onChange={handleChange}
              className="input-truck"
              placeholder="0.5"
              min="0"
              max="100"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Tipo de viaje</label>
            <select name="tipo_viaje" value={form.tipo_viaje} onChange={handleChange} className="input-truck">
              {tipoViajeItems.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Empresa / Cliente que despacha</label>
            <select name="empresa_manifiesto_id" value={form.empresa_manifiesto_id} onChange={handleChange} className="input-truck">
              <option value="">Sin empresa / cliente</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre_comercial || p.razon_social}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Fecha manifiesto</label>
            <input
              type="date"
              name="fecha_manifiesto"
              value={form.fecha_manifiesto}
              onChange={handleChange}
              className="input-truck"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Otras deducciones</label>
            <input
              type="number"
              name="otras_deducciones"
              value={form.otras_deducciones}
              onChange={handleChange}
              className="input-truck"
              placeholder="0"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Anticipo de manifiesto</label>
            <input
              type="number"
              name="anticipo_manifiesto"
              value={form.anticipo_manifiesto}
              onChange={handleChange}
              className="input-truck"
              placeholder="0"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">% Comisión conductor</label>
            <input
              type="number"
              name="porcentaje_comision"
              value={form.porcentaje_comision}
              onChange={handleChange}
              className="input-truck"
              placeholder="10 (default del conductor)"
              min="0"
              max="100"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">N° Manifiesto</label>
            <input
              type="text"
              name="num_manifiesto"
              value={form.num_manifiesto}
              onChange={handleChange}
              className="input-truck"
              placeholder="Ej: 0001234"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Material / carga</label>
            <input
              type="text"
              name="tipo_carga"
              value={form.tipo_carga}
              onChange={handleChange}
              className="input-truck"
              placeholder="Ej: Cemento, fertilizante..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Peso declarado (ton)</label>
            <input
              type="number"
              name="peso_declarado_ton"
              value={form.peso_declarado_ton}
              onChange={handleChange}
              className="input-truck"
              placeholder="0"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Peso báscula origen (ton)</label>
            <input
              type="number"
              name="peso_bascula_origen"
              value={form.peso_bascula_origen}
              onChange={handleChange}
              className="input-truck"
              placeholder="0"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Peso báscula destino (ton)</label>
            <input
              type="number"
              name="peso_bascula_destino"
              value={form.peso_bascula_destino}
              onChange={handleChange}
              className="input-truck"
              placeholder="0"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">KMS inicial tacómetro</label>
            <input
              type="number"
              name="km_inicial"
              value={form.km_inicial}
              onChange={handleChange}
              className="input-truck"
              placeholder="0"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">KMS final tacómetro</label>
            <input
              type="number"
              name="km_final"
              value={form.km_final}
              onChange={handleChange}
              className="input-truck"
              placeholder="0"
              min="0"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Fecha llegada</label>
            <input
              type="date"
              name="fecha_llegada"
              value={form.fecha_llegada}
              onChange={handleChange}
              className="input-truck"
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

          {(() => {
            const flete = Number(form.valor_flete_manifiesto) || 0
            const rfuenteValor = Math.round(flete * ((Number(form.retefuente_porcentaje) || 0) / 100) * 100) / 100
            const ricaValor = Math.round(flete * ((Number(form.reteica_porcentaje) || 0) / 100) * 100) / 100
            const otras = Number(form.otras_deducciones) || 0
            const anticipo = Number(form.anticipo_manifiesto) || 0
            // 0 explicito se respeta; default 10 solo si vacio/null/undefined
            const rawComision = form.porcentaje_comision
            const comisionPct = rawComision === '' || rawComision === null || rawComision === undefined
              ? 10
              : Number(rawComision)
            const fleteNeto = Math.round((flete - rfuenteValor - ricaValor - otras) * 100) / 100
            const comision = Math.round((fleteNeto * comisionPct) / 100 * 100) / 100
            const kmInicial = Number(form.km_inicial) || 0
            const kmFinal = Number(form.km_final) || 0
            const kmRecorridos = kmFinal - kmInicial
            return flete > 0 || kmRecorridos > 0 ? (
              <div className="md:col-span-2 lg:col-span-3">
                <div className="rounded-lg border border-primary-500/30 bg-primary-500/5 p-4">
                  <p className="text-sm font-semibold text-primary-300 mb-2 flex items-center gap-2">
                    <Calculator size={16} />
                    Vista previa estimada (el servidor recalcula al guardar)
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-1 text-sm">
                    <FilaCalculada label="Retefuente valor" valor={rfuenteValor} />
                    <FilaCalculada label="Reteica valor" valor={ricaValor} />
                    <FilaCalculada label="Flete neto" valor={fleteNeto} tono="text-blue-400" />
                    <FilaCalculada label={`Comisión (${comisionPct}%)`} valor={comision} tono="text-orange-400" />
                    <FilaCalculada label="Saldo flete esperado" valor={Math.round((fleteNeto - anticipo) * 100) / 100} tono="text-green-400" />
                    <FilaCalculada label="Utilidad est. (sin gastos)" valor={Math.round((fleteNeto - comision) * 100) / 100} tono="text-green-400" />
                    {kmRecorridos > 0 && (
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-slate-400">KMS recorridos</span>
                        <span className="text-white">{kmRecorridos.toLocaleString('es-CO')} km</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : null
          })()}

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
                  <th className="py-2 px-3">KMS</th>
                  <th className="py-2 px-3">Flete Neto</th>
                  <th className="py-2 px-3">Utilidad</th>
                  <th className="py-2 px-3">Margen Est.</th>
                  <th className="py-2 px-3">Estado</th>
                  {!esConductor && <th className="py-2 px-3 text-right">Acciones</th>}
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
                      <td className="py-3 px-3 text-slate-400">{viaje.km_recorridos != null ? `${Number(viaje.km_recorridos).toLocaleString('es-CO')}` : '-'}</td>
                      <td className="py-3 px-3 text-white">{viaje.flete_neto ? `$${Number(viaje.flete_neto).toLocaleString('es-CO')}` : '-'}</td>
                      <td className="py-3 px-3">
                        {viaje.utilidad_neta_odt != null ? (
                          <span className={`font-semibold ${Number(viaje.utilidad_neta_odt) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {formatearMoneda(Number(viaje.utilidad_neta_odt))}
                          </span>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {(() => {
                          const margen = margenDe(viaje)
                          if (margen === null) return <span className="text-slate-500">-</span>
                          return (
                            <span className={`font-semibold ${margen >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {formatearMoneda(margen)}
                            </span>
                          )
                        })()}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-1 rounded-full text-xs ${estadoStyles[viaje.estado] || 'bg-slate-500/20 text-slate-400'}`}>
                          {viaje.estado}
                        </span>
                      </td>
                      {!esConductor && (
                        <td className="py-3 px-3">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => verBloqueosCierre(viaje)}
                              className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-amber-400 transition-colors"
                              title="Bloqueos de cierre"
                            >
                              {cargandoBloqueos === viaje.id ? <Loader2 size={16} className="animate-spin" /> : <ShieldAlert size={16} />}
                            </button>
                            <button
                              type="button"
                              onClick={() => abrirEdicion(viaje)}
                              className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-primary-400 transition-colors"
                              title="Editar"
                            >
                              <Pencil size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEliminarError('')
                                setEliminarTarget(viaje)
                              }}
                              className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-danger-500 transition-colors"
                              title="Eliminar"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!esConductor && <Pagination total={totalViajes} page={pagina} pageSize={PAGE_SIZE} onPage={setPagina} />}
          </div>
        )}
      </div>

      {editando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Pencil size={18} className="text-primary-400" />
                Editar ODT {editando.numero_odt}
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
              {camposViaje.map((campo) => (
                <div key={campo}>
                  <label className="block text-sm font-medium text-slate-300 mb-1">{traduccionCampo[campo]}</label>
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
                  ¿Seguro que deseas eliminar la ODT{' '}
                  <span className="text-white font-semibold">{eliminarTarget.numero_odt}</span>? Esta acción no se puede
                  deshacer.
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

      {bloqueosInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-md">
            <div className="flex items-start gap-3 mb-4">
              <div className={`p-2 rounded-full ${bloqueosInfo.cercable ? 'bg-green-500/20 text-green-500' : 'bg-amber-500/20 text-amber-500'}`}>
                <ShieldAlert size={22} />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white">Bloqueos de cierre</h3>
                <p className="text-sm text-slate-400 mt-1">
                  ODT <span className="text-white font-semibold">{bloqueosInfo.numero_odt}</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setBloqueosInfo(null)}
                className="p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {bloqueosInfo.cercable ? (
              <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 text-green-500 px-4 py-3 rounded-lg">
                <CheckCircle2 size={18} />
                <span>La ODT no presenta bloqueos y puede finalizarse.</span>
              </div>
            ) : (
              <ul className="space-y-2">
                {bloqueosInfo.bloqueos.map((b, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 text-amber-500 px-4 py-3 rounded-lg text-sm"
                  >
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex items-center justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={() => setBloqueosInfo(null)}
                className="py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Viajes