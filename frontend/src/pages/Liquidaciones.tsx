import React, { useState, useEffect } from 'react'
import { Calculator, Loader2, AlertCircle, CheckCircle2, XCircle, Lock, TrendingUp, CalendarRange } from 'lucide-react'
import { viajesAPI, liquidacionesAPI, conductoresAPI, CompensadoMensual } from '@/api'
import { extraerMensajeError, formatearMoneda } from '@/utils/format'

interface Viaje {
  id: number
  numero_odt: string
  estado: string
  conductor_id: number
  vehiculo_id: number
  fecha_salida: string
}

interface Conductor {
  id: number
  nombre_completo: string
  cedula: string
}

interface Desglose {
  viaje_id: number
  vehiculo_id: number
  conductor_id: number
  valor_flete_manifiesto: string | null
  retefuente_valor: string | null
  reteica_valor: string | null
  flete_neto: string | null
  total_gastos_empresa: string
  total_gastos_conductor: string
  total_anticipos: string
  total_ingresos: string
  comision_flete: string
  porcentaje_comision: number
  saldo_neto: string
}

const hoy = () => new Date().toISOString().slice(0, 10)
const mesActual = () => new Date().toISOString().slice(0, 7)

const limitesMes = (mes: string): { inicio: string; fin: string } => {
  const [anio, m] = mes.split('-').map(Number)
  const fin = new Date(Date.UTC(anio, m, 0)) // día 0 del mes siguiente => último día del mes
  return { inicio: `${mes}-01`, fin: fin.toISOString().slice(0, 10) }
}

// FASE A2 — inputs manuales del COMPENSADO_RC (los consolidados los calcula el servidor)
const inicialInputsMensuales = () => ({
  salario_basico: '',
  auxilio_transporte: '',
  papeleria: '',
  descuento_salud_pension: '',
  bonificaciones: '',
  viaticos_reconocidos: '',
  otros_haberes: '',
  anticipos_entregados: '',
  gastos_a_cargo_conductor: '',
  prestamos: '',
  otros_descuentos: '',
})

const Liquidaciones: React.FC = () => {
  const [viajes, setViajes] = useState<Viaje[]>([])
  const [viajeId, setViajeId] = useState('')
  const [desglose, setDesglose] = useState<Desglose | null>(null)
  const [loading, setLoading] = useState(true)
  const [calculando, setCalculando] = useState(false)
  const [cerrando, setCerrando] = useState(false)
  const [listError, setListError] = useState('')
  const [calcError, setCalcError] = useState('')
  const [closeError, setCloseError] = useState('')
  const [success, setSuccess] = useState('')

  // COMPENSADO_RC mensual
  const [conductores, setConductores] = useState<Conductor[]>([])
  const [conductorId, setConductorId] = useState('')
  const [mes, setMes] = useState(mesActual())
  const [consolidado, setConsolidado] = useState<CompensadoMensual | null>(null)
  const [consolidando, setConsolidando] = useState(false)
  const [consolError, setConsolError] = useState('')
  const [inputsMensuales, setInputsMensuales] = useState(inicialInputsMensuales)

  const cargarViajes = async () => {
    setLoading(true)
    setListError('')
    try {
      const [viajesRes, conductoresRes] = await Promise.all([viajesAPI.listar(false), conductoresAPI.listar()])
      setViajes(viajesRes.data)
      setConductores(conductoresRes.data)
    } catch (err) {
      setListError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarViajes()
  }, [])

  const viajeSeleccionado = viajes.find((v) => String(v.id) === viajeId)

  const calcular = async () => {
    if (!viajeId) return
    setCalculando(true)
    setCalcError('')
    setCloseError('')
    setSuccess('')
    setDesglose(null)
    try {
      const res = await liquidacionesAPI.calcular(Number(viajeId))
      setDesglose(res.data)
    } catch (err) {
      setCalcError(extraerMensajeError(err))
    } finally {
      setCalculando(false)
    }
  }

  const cerrar = async () => {
    if (!desglose || !viajeSeleccionado) return
    setCerrando(true)
    setCloseError('')
    setSuccess('')
    try {
      const res = await liquidacionesAPI.cerrar(desglose.viaje_id, {
        conductor_id: desglose.conductor_id,
        vehiculo_id: desglose.vehiculo_id,
        periodo_inicio: viajeSeleccionado.fecha_salida,
        periodo_fin: hoy(),
        comision_flete: Number(desglose.comision_flete),
        porcentaje_comision: Number(desglose.porcentaje_comision ?? 10),
        bonificaciones: 0,
        viaticos_reconocidos: 0,
        otros_haberes: 0,
        anticipos_entregados: Number(desglose.total_anticipos),
        gastos_a_cargo_conductor: Number(desglose.total_gastos_conductor),
        prestamos: 0,
        otros_descuentos: 0,
        viajes_ids: [desglose.viaje_id],
        estado: 'aprobado',
      })
      setSuccess(
        `${res.data.mensaje}. Liquidación #${res.data.liquidacion_id} — estado del viaje: ${res.data.estado_viaje}`
      )
      setDesglose(null)
      setViajeId('')
      const viajesRes = await viajesAPI.listar(false)
      setViajes(viajesRes.data)
    } catch (err) {
      setCloseError(extraerMensajeError(err))
    } finally {
      setCerrando(false)
    }
  }

  const consolidarMes = async () => {
    if (!conductorId) return
    setConsolidando(true)
    setConsolError('')
    setSuccess('')
    try {
      const { inicio, fin } = limitesMes(mes)
      const res = await liquidacionesAPI.compensado(Number(conductorId), inicio, fin)
      setConsolidado(res)
      setInputsMensuales(inicialInputsMensuales())
    } catch (err) {
      setConsolError(extraerMensajeError(err))
    } finally {
      setConsolidando(false)
    }
  }

  const handleInputMensual = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputsMensuales({ ...inputsMensuales, [e.target.name]: e.target.value })
  }

  const n = (v: string) => Number(v) || 0

  const haberesMensuales = consolidado
    ? Number(consolidado.comisiones_total) +
      n(inputsMensuales.bonificaciones) +
      n(inputsMensuales.viaticos_reconocidos) +
      n(inputsMensuales.otros_haberes) +
      n(inputsMensuales.salario_basico) +
      n(inputsMensuales.auxilio_transporte) +
      n(inputsMensuales.papeleria)
    : 0

  const descuentosMensuales = consolidado
    ? n(inputsMensuales.anticipos_entregados) +
      n(inputsMensuales.gastos_a_cargo_conductor) +
      n(inputsMensuales.prestamos) +
      n(inputsMensuales.otros_descuentos) +
      n(inputsMensuales.descuento_salud_pension) +
      Number(consolidado.retiros_tarjeta_anticipos)
    : 0

  const filas = desglose
    ? [
        { label: 'Valor flete manifiesto', valor: desglose.valor_flete_manifiesto, tono: 'text-white', negativo: false },
        { label: 'Retefuente', valor: desglose.retefuente_valor, tono: 'text-orange-400', negativo: true },
        { label: 'Reteica', valor: desglose.reteica_valor, tono: 'text-orange-400', negativo: true },
        { label: 'Flete neto', valor: desglose.flete_neto, tono: 'text-blue-400', negativo: false },
        { label: 'Gastos asumidos por empresa', valor: desglose.total_gastos_empresa, tono: 'text-orange-400', negativo: true },
        { label: 'Gastos a cargo del conductor', valor: desglose.total_gastos_conductor, tono: 'text-slate-300', negativo: false },
        { label: 'Anticipos entregados', valor: desglose.total_anticipos, tono: 'text-orange-400', negativo: true },
        { label: 'Ingresos totales', valor: desglose.total_ingresos, tono: 'text-green-400', negativo: false },
        { label: `Comisión flete (${desglose.porcentaje_comision ?? 10}%)`, valor: desglose.comision_flete, tono: 'text-orange-400', negativo: true },
      ]
    : []

  const camposMensuales: { name: string; label: string }[] = [
    { name: 'bonificaciones', label: 'Bonificaciones' },
    { name: 'viaticos_reconocidos', label: 'Viáticos reconocidos' },
    { name: 'otros_haberes', label: 'Otros haberes' },
    { name: 'salario_basico', label: 'Salario básico' },
    { name: 'auxilio_transporte', label: 'Auxilio de transporte' },
    { name: 'papeleria', label: 'Papelería' },
    { name: 'anticipos_entregados', label: 'Anticipos entregados' },
    { name: 'gastos_a_cargo_conductor', label: 'Gastos a cargo del conductor' },
    { name: 'prestamos', label: 'Préstamos' },
    { name: 'otros_descuentos', label: 'Otros descuentos' },
    { name: 'descuento_salud_pension', label: 'Salud y pensión' },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Liquidaciones</h2>
        <p className="text-slate-400">Módulo de compensados y liquidaciones de conductores</p>
      </div>

      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Calculator size={20} />
          Calcular Liquidación
        </h3>

        {listError && (
          <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
            <XCircle size={18} />
            <span>{listError}</span>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8 text-slate-400">
            <Loader2 className="animate-spin mr-2" size={20} />
            Cargando viajes...
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-300 mb-1">Viaje / ODT</label>
              <select value={viajeId} onChange={(e) => setViajeId(e.target.value)} className="input-truck">
                <option value="">Selecciona un viaje</option>
                {viajes.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.numero_odt} — {v.estado}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={calcular}
              disabled={!viajeId || calculando || viajeSeleccionado?.estado === 'liquidado'}
              className="btn-celr flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {calculando ? <Loader2 className="animate-spin" size={20} /> : <TrendingUp size={20} />}
              {calculando ? 'Calculando...' : 'Calcular'}
            </button>
          </div>
        )}

        {viajeSeleccionado?.estado === 'liquidado' && (
          <p className="text-sm text-yellow-400 mt-2">Este viaje ya está liquidado.</p>
        )}

        {calcError && (
          <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mt-4">
            <AlertCircle size={18} />
            <span>{calcError}</span>
          </div>
        )}
        {closeError && (
          <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mt-4">
            <AlertCircle size={18} />
            <span>{closeError}</span>
          </div>
        )}
        {success && (
          <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 text-green-500 px-4 py-3 rounded-lg mt-4">
            <CheckCircle2 size={18} />
            <span>{success}</span>
          </div>
        )}
      </div>

      {desglose && (
        <div className="card-truck">
          <h3 className="text-lg font-semibold text-white mb-4">Desglose Financiero</h3>
          <div className="divide-y divide-slate-800">
            {filas.map((fila) => (
              <div key={fila.label} className="flex items-center justify-between py-2 text-sm">
                <span className="text-slate-400">{fila.label}</span>
                <span className={fila.tono}>
                  {fila.negativo ? '- ' : ''}
                  {formatearMoneda(fila.valor)}
                </span>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-600">
            <span className="text-base font-semibold text-white">Saldo neto a liquidar</span>
            <span className="text-2xl font-bold text-green-400">{formatearMoneda(desglose.saldo_neto)}</span>
          </div>

          <div className="flex justify-end mt-6">
            <button onClick={cerrar} disabled={cerrando} className="btn-celr flex items-center gap-2 disabled:opacity-50">
              {cerrando ? <Loader2 className="animate-spin" size={20} /> : <Lock size={20} />}
              {cerrando ? 'Cerrando...' : 'Cerrar Liquidación'}
            </button>
          </div>
        </div>
      )}

      {/* FASE A2 — COMPENSADO_RC mensual del conductor */}
      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <CalendarRange size={20} />
          COMPENSADO_RC Mensual
        </h3>
        <p className="text-sm text-slate-400 mb-4">
          Consolidados automáticos del mes (comisiones, conteo de viajes y retiros de tarjeta). El cierre formal se hace
          por ODT en la sección superior; al cerrar se guardan los consolidados del periodo.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-300 mb-1">Conductor</label>
            <select value={conductorId} onChange={(e) => setConductorId(e.target.value)} className="input-truck">
              <option value="">Selecciona un conductor</option>
              {conductores.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre_completo} — {c.cedula}
                </option>
              ))}
            </select>
          </div>
          <div className="w-full sm:w-48">
            <label className="block text-sm font-medium text-slate-300 mb-1">Mes</label>
            <input type="month" value={mes} onChange={(e) => setMes(e.target.value)} className="input-truck" />
          </div>
          <button
            onClick={consolidarMes}
            disabled={!conductorId || consolidando}
            className="btn-celr flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {consolidando ? <Loader2 className="animate-spin" size={20} /> : <TrendingUp size={20} />}
            {consolidando ? 'Consolidando...' : 'Consolidar mes'}
          </button>
        </div>

        {consolError && (
          <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mt-4">
            <AlertCircle size={18} />
            <span>{consolError}</span>
          </div>
        )}

        {consolidado && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
              <div className="rounded-lg bg-slate-800/60 p-3">
                <p className="text-xs text-slate-400">Viajes en el mes</p>
                <p className="text-xl font-bold text-white">{consolidado.total_viajes}</p>
                <p className="text-xs text-slate-500">
                  {consolidado.viajes_nacionales} nac. · {consolidado.viajes_urbanos} urb.
                </p>
              </div>
              <div className="rounded-lg bg-slate-800/60 p-3">
                <p className="text-xs text-slate-400">Comisiones totales</p>
                <p className="text-xl font-bold text-green-400">{formatearMoneda(consolidado.comisiones_total)}</p>
              </div>
              <div className="rounded-lg bg-slate-800/60 p-3">
                <p className="text-xs text-slate-400">Retiros tarjeta (anticipos)</p>
                <p className="text-xl font-bold text-orange-400">{formatearMoneda(consolidado.retiros_tarjeta_anticipos)}</p>
              </div>
              <div className="rounded-lg bg-slate-800/60 p-3">
                <p className="text-xs text-slate-400">Haberes</p>
                <p className="text-xl font-bold text-blue-400">{formatearMoneda(haberesMensuales)}</p>
              </div>
              <div className="rounded-lg bg-slate-800/60 p-3">
                <p className="text-xs text-slate-400">Descuentos</p>
                <p className="text-xl font-bold text-orange-400">{formatearMoneda(descuentosMensuales)}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              {camposMensuales.map((campo) => (
                <div key={campo.name}>
                  <label className="block text-sm font-medium text-slate-300 mb-1">{campo.label}</label>
                  <input
                    type="number"
                    name={campo.name}
                    value={(inputsMensuales as Record<string, string>)[campo.name] ?? ''}
                    onChange={handleInputMensual}
                    className="input-truck"
                    min="0"
                    step="0.01"
                  />
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-600">
              <span className="text-base font-semibold text-white">Saldo estimado del mes (vista previa)</span>
              <span className={`text-2xl font-bold ${haberesMensuales - descuentosMensuales >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatearMoneda(haberesMensuales - descuentosMensuales)}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Vista previa calculada con la fórmula del servidor (haberes − descuentos). Los valores definitivos los
              deriva el backend al cerrar la liquidación de cada ODT del periodo.
            </p>
          </>
        )}
      </div>
    </div>
  )
}

export default Liquidaciones