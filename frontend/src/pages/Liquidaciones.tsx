import React, { useState, useEffect, useCallback } from 'react'
import { Calculator, Loader2, AlertCircle, CheckCircle2, XCircle, Lock, TrendingUp, CalendarRange, RotateCcw, Ban, FolderOpen, FileText } from 'lucide-react'
import { viajesAPI, liquidacionesAPI, conductoresAPI, CompensadoMensual, CierreMensual } from '@/api'
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

  // B2 — cierre mensual COMPENSADO_RC persistido
  const [cierresMensuales, setCierresMensuales] = useState<CierreMensual[]>([])
  const [cargandoCierres, setCargandoCierres] = useState(false)
  const [cerrandoMes, setCerrandoMes] = useState(false)
  const [cierreError, setCierreError] = useState('')
  const [detalleCierre, setDetalleCierre] = useState<CierreMensual | null>(null)
  const [accionCierreId, setAccionCierreId] = useState<number | null>(null)

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

  const cargarCierresMensuales = useCallback(async (condId: number) => {
    setCargandoCierres(true)
    setCierreError('')
    try {
      const cierres = await liquidacionesAPI.cierresMensuales(condId)
      setCierresMensuales(cierres)
    } catch (err) {
      setCierresMensuales([])
      setCierreError(extraerMensajeError(err))
    } finally {
      setCargandoCierres(false)
    }
  }, [])

  // B2 — al seleccionar conductor se cargan los meses cerrados persistentes
  useEffect(() => {
    if (conductorId) {
      cargarCierresMensuales(Number(conductorId))
    } else {
      setCierresMensuales([])
    }
    setConsolidado(null)
    setDetalleCierre(null)
  }, [conductorId, cargarCierresMensuales])

  const cerrarMes = async () => {
    if (!conductorId) return
    setCerrandoMes(true)
    setCierreError('')
    setSuccess('')
    try {
      const cierre = await liquidacionesAPI.cierreMensualCrear({
        conductor_id: Number(conductorId),
        periodo_ym: mes,
        salario_basico: n(inputsMensuales.salario_basico),
        auxilio_transporte: n(inputsMensuales.auxilio_transporte),
        papeleria: n(inputsMensuales.papeleria),
        descuento_salud_pension: n(inputsMensuales.descuento_salud_pension),
        bonificaciones: n(inputsMensuales.bonificaciones),
        viaticos_reconocidos: n(inputsMensuales.viaticos_reconocidos),
        otros_haberes: n(inputsMensuales.otros_haberes),
        anticipos_entregados: n(inputsMensuales.anticipos_entregados),
        gastos_a_cargo_conductor: n(inputsMensuales.gastos_a_cargo_conductor),
        prestamos: n(inputsMensuales.prestamos),
        otros_descuentos: n(inputsMensuales.otros_descuentos),
        observaciones: `Cierre del mes ${mes} generado desde la UI`,
      })
      setSuccess(`Cierre mensual ${mes} creado (borrador). Saldo neto: ${formatearMoneda(cierre.saldo_neto)}`)
      setDetalleCierre(cierre)
      await cargarCierresMensuales(Number(conductorId))
      if (consolidado) {
        const { inicio, fin } = limitesMes(mes)
        const res = await liquidacionesAPI.compensado(Number(conductorId), inicio, fin)
        setConsolidado(res)
      }
    } catch (err) {
      setCierreError(extraerMensajeError(err))
    } finally {
      setCerrandoMes(false)
    }
  }

  const reabrirCierre = async (id: number) => {
    setAccionCierreId(id)
    setCierreError('')
    setSuccess('')
    try {
      const res = await liquidacionesAPI.reabrir(id)
      setSuccess(res.data.mensaje)
      if (conductorId) await cargarCierresMensuales(Number(conductorId))
    } catch (err) {
      setCierreError(extraerMensajeError(err))
    } finally {
      setAccionCierreId(null)
    }
  }

  const cancelarCierre = async (id: number) => {
    setAccionCierreId(id)
    setCierreError('')
    setSuccess('')
    try {
      const res = await liquidacionesAPI.cancelar(id)
      setSuccess(res.data.mensaje)
      if (conductorId) await cargarCierresMensuales(Number(conductorId))
    } catch (err) {
      setCierreError(extraerMensajeError(err))
    } finally {
      setAccionCierreId(null)
    }
  }

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
    setCierreError('')
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

  const camposHaberes: { name: string; label: string }[] = [
    { name: 'salario_basico', label: 'Salario básico' },
    { name: 'auxilio_transporte', label: 'Auxilio de transporte' },
    { name: 'papeleria', label: 'Papelería' },
    { name: 'bonificaciones', label: 'Bonificaciones' },
    { name: 'viaticos_reconocidos', label: 'Viáticos reconocidos' },
    { name: 'otros_haberes', label: 'Otros haberes' },
  ]

  const camposDescuentos: { name: string; label: string }[] = [
    { name: 'anticipos_entregados', label: 'Anticipos entregados' },
    { name: 'gastos_a_cargo_conductor', label: 'Gastos a cargo del conductor' },
    { name: 'prestamos', label: 'Préstamos' },
    { name: 'otros_descuentos', label: 'Otros descuentos' },
    { name: 'descuento_salud_pension', label: 'Salud y pensión' },
  ]

  const netoMensual = haberesMensuales - descuentosMensuales

  // FASE Liquidaciones — desglose completo del COMPENSADO_RC mensual
  const filasHaberes = consolidado
    ? [
        { label: 'Comisiones conductor (consolidado del mes)', valor: consolidado.comisiones_total, tono: 'text-green-400' },
        { label: 'Salario básico', valor: inputsMensuales.salario_basico, tono: 'text-white' },
        { label: 'Auxilio de transporte', valor: inputsMensuales.auxilio_transporte, tono: 'text-white' },
        { label: 'Papelería', valor: inputsMensuales.papeleria, tono: 'text-white' },
        { label: 'Bonificaciones', valor: inputsMensuales.bonificaciones, tono: 'text-white' },
        { label: 'Viáticos reconocidos', valor: inputsMensuales.viaticos_reconocidos, tono: 'text-white' },
        { label: 'Otros haberes', valor: inputsMensuales.otros_haberes, tono: 'text-white' },
      ]
    : []

  const filasDescuentos = consolidado
    ? [
        { label: 'Retiros tarjeta / anticipos (consolidado del mes)', valor: consolidado.retiros_tarjeta_anticipos, tono: 'text-orange-400' },
        { label: 'Descuento salud y pensión', valor: inputsMensuales.descuento_salud_pension, tono: 'text-orange-400' },
        { label: 'Anticipos entregados', valor: inputsMensuales.anticipos_entregados, tono: 'text-orange-400' },
        { label: 'Gastos a cargo del conductor', valor: inputsMensuales.gastos_a_cargo_conductor, tono: 'text-orange-400' },
        { label: 'Préstamos', valor: inputsMensuales.prestamos, tono: 'text-orange-400' },
        { label: 'Otros descuentos', valor: inputsMensuales.otros_descuentos, tono: 'text-orange-400' },
      ]
    : []

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
          Consolidados automáticos del mes (comisiones, conteo de viajes y retiros de tarjeta). El cierre formal del
          mes se persiste con «Cerrar mes»; los viajes del periodo quedan liquidados y bloqueados para cierre individual.
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
            {/* Conteo de viajes del periodo */}
            <div className="grid grid-cols-3 gap-3 mt-4">
              <div className="rounded-lg bg-slate-800/60 p-3 text-center">
                <p className="text-xs text-slate-400">Viajes nacionales</p>
                <p className="text-xl font-bold text-white">{consolidado.viajes_nacionales}</p>
              </div>
              <div className="rounded-lg bg-slate-800/60 p-3 text-center">
                <p className="text-xs text-slate-400">Viajes urbanos</p>
                <p className="text-xl font-bold text-white">{consolidado.viajes_urbanos}</p>
              </div>
              <div className="rounded-lg bg-slate-800/60 p-3 text-center">
                <p className="text-xs text-slate-400">Total viajes</p>
                <p className="text-xl font-bold text-white">{consolidado.total_viajes}</p>
              </div>
            </div>

            {/* Haberes / devengado */}
            <div className="mt-4">
              <p className="text-sm font-semibold text-white uppercase tracking-wide mb-2">Haberes (devengado del mes)</p>
              <div className="rounded-lg bg-slate-800/40 p-3 divide-y divide-slate-700/50">
                {filasHaberes.map((f) => (
                  <div key={f.label} className="flex items-center justify-between py-1.5 text-sm">
                    <span className="text-slate-400">{f.label}</span>
                    <span className={f.tono}>{formatearMoneda(f.valor)}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between py-2 pt-2 border-t border-slate-600">
                  <span className="text-sm font-semibold text-white">DEVENGADO TOTAL</span>
                  <span className="text-lg font-bold text-blue-400">{formatearMoneda(haberesMensuales)}</span>
                </div>
              </div>
            </div>

            {/* Deducciones */}
            <div className="mt-4">
              <p className="text-sm font-semibold text-white uppercase tracking-wide mb-2">Deducciones del mes</p>
              <div className="rounded-lg bg-slate-800/40 p-3 divide-y divide-slate-700/50">
                {filasDescuentos.map((f) => (
                  <div key={f.label} className="flex items-center justify-between py-1.5 text-sm">
                    <span className="text-slate-400">{f.label}</span>
                    <span className={f.tono}>{formatearMoneda(f.valor)}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between py-2 pt-2 border-t border-slate-600">
                  <span className="text-sm font-semibold text-white">DEDUCCIONES TOTALES</span>
                  <span className="text-lg font-bold text-orange-400">{formatearMoneda(descuentosMensuales)}</span>
                </div>
              </div>
            </div>

            {/* Inputs manuales agrupados por sección */}
            <div className="mt-4">
              <p className="text-sm font-semibold text-white uppercase tracking-wide mb-2">Ingresos manuales — haberes</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {camposHaberes.map((campo) => (
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
              <p className="text-sm font-semibold text-white uppercase tracking-wide mb-2 mt-4">Descuentos manuales</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {camposDescuentos.map((campo) => (
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
            </div>

            {/* Neto a pagar */}
            <div className="flex items-center justify-between mt-5 pt-4 border-t border-slate-600">
              <span className="text-base font-semibold text-white">NETO A PAGAR</span>
              <span className={`text-2xl font-bold ${netoMensual >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatearMoneda(netoMensual)}
              </span>
            </div>

            {/* B2 — cerrar el mes formalmente (persiste la liquidación mensual) */}
            {cierresMensuales.some((c) => c.periodo_ym === mes) ? (
              <div className="mt-4 flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/30 text-yellow-500 px-4 py-3 rounded-lg">
                <AlertCircle size={18} className="mt-0.5 shrink-0" />
                <span>
                  El mes {mes} ya tiene un cierre{' '}
                  {cierresMensuales.find((c) => c.periodo_ym === mes)?.estado}. Revisá «Meses cerrados» para
                  detalle, reabrir o cancelar.
                </span>
              </div>
            ) : (
              <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
                <button
                  onClick={cerrarMes}
                  disabled={cerrandoMes}
                  className="btn-celr flex items-center gap-2 disabled:opacity-50"
                >
                  {cerrandoMes ? <Loader2 className="animate-spin" size={20} /> : <Lock size={20} />}
                  {cerrandoMes ? 'Cerrando mes...' : 'Cerrar mes'}
                </button>
              </div>
            )}
            {cierreError && (
              <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mt-4">
                <AlertCircle size={18} />
                <span>{cierreError}</span>
              </div>
            )}
            <p className="text-xs text-slate-500 mt-2">
              Vista previa calculada con la misma fórmula del servidor (devengado − deducciones). «Cerrar mes»
              persiste la liquidación en borrador y los valores definitivos los deriva el backend del consolidado real.
            </p>
          </>
        )}
      </div>

      {/* B2 — Meses cerrados (liquidaciones mensuales persistidas del conductor) */}
      <div className="card-truck">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <FolderOpen size={20} />
          Meses cerrados
        </h3>
        <p className="text-sm text-slate-400 mb-4">
          Cierres mensuales persistidos del conductor seleccionado. El borrador bloquea el cierre individual de sus
          viajes; lo aprobado indica liquidación mensual firme.
        </p>

        {!conductorId ? (
          <p className="text-sm text-slate-500">Selecciona un conductor para ver sus meses cerrados.</p>
        ) : cargandoCierres ? (
          <div className="flex items-center justify-center py-6 text-slate-400">
            <Loader2 className="animate-spin mr-2" size={20} />
            Cargando meses cerrados...
          </div>
        ) : cierresMensuales.length === 0 ? (
          <p className="text-sm text-slate-500">Este conductor no tiene cierres mensuales persistidos todavía.</p>
        ) : (
          <div className="space-y-3">
            {cierresMensuales.map((c) => (
              <div key={c.id} className="rounded-lg bg-slate-800/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-bold text-white">{c.periodo_ym}</span>
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        c.estado === 'aprobado'
                          ? 'bg-green-500/15 text-green-400'
                          : 'bg-yellow-500/15 text-yellow-400'
                      }`}
                    >
                      {c.estado === 'aprobado' ? 'Aprobado' : 'Borrador'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setDetalleCierre(c)}
                      disabled={accionCierreId !== null}
                      className="flex items-center gap-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50 px-3 py-1.5 rounded-lg border border-slate-700 hover:border-slate-500"
                    >
                      <FileText size={15} />
                      Detalle
                    </button>
                    {c.estado === 'aprobado' && (
                      <button
                        onClick={() => reabrirCierre(c.id)}
                        disabled={accionCierreId !== null}
                        className="flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 disabled:opacity-50 px-3 py-1.5 rounded-lg border border-blue-500/30 hover:border-blue-500/60"
                      >
                        {accionCierreId === c.id ? (
                          <Loader2 className="animate-spin" size={15} />
                        ) : (
                          <RotateCcw size={15} />
                        )}
                        Reabrir
                      </button>
                    )}
                    {c.estado === 'borrador' && (
                      <button
                        onClick={() => cancelarCierre(c.id)}
                        disabled={accionCierreId !== null}
                        className="flex items-center gap-1.5 text-sm text-danger-500 hover:text-danger-400 disabled:opacity-50 px-3 py-1.5 rounded-lg border border-danger-500/30 hover:border-danger-500/60"
                      >
                        {accionCierreId === c.id ? (
                          <Loader2 className="animate-spin" size={15} />
                        ) : (
                          <Ban size={15} />
                        )}
                        Cancelar
                      </button>
                    )}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-slate-400">Viajes</p>
                    <p className="text-white font-semibold">{c.total_viajes}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Comisiones mes</p>
                    <p className="text-blue-400 font-semibold">{formatearMoneda(c.comisiones_total)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Total haberes</p>
                    <p className="text-white font-semibold">{formatearMoneda(c.total_haberes)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">Saldo neto</p>
                    <p className={`font-semibold ${Number(c.saldo_neto) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatearMoneda(c.saldo_neto)}
                    </p>
                  </div>
                </div>
                {c.observaciones && <p className="mt-2 text-xs text-slate-500 whitespace-pre-line">{c.observaciones}</p>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* B2 — Detalle del cierre mensual seleccionado */}
      {detalleCierre && (
        <div className="card-truck">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <FileText size={20} />
            Detalle del cierre {detalleCierre.periodo_ym}
          </h3>
          <div className="divide-y divide-slate-800 text-sm">
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Periodo</span>
              <span className="text-white">
                {detalleCierre.periodo_inicio} → {detalleCierre.periodo_fin}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Estado</span>
              <span className={detalleCierre.estado === 'aprobado' ? 'text-green-400' : 'text-yellow-400'}>
                {detalleCierre.estado === 'aprobado' ? 'Aprobado' : 'Borrador'}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Viajes del mes</span>
              <span className="text-white">
                {detalleCierre.viajes_nacionales} nacionales · {detalleCierre.viajes_urbanos} urbanos ·{' '}
                {detalleCierre.total_viajes} total
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Comisiones (consolidado)</span>
              <span className="text-blue-400">{formatearMoneda(detalleCierre.comisiones_total)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Salario básico</span>
              <span className="text-white">{formatearMoneda(detalleCierre.salario_basico)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Auxilio de transporte</span>
              <span className="text-white">{formatearMoneda(detalleCierre.auxilio_transporte)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Papelería</span>
              <span className="text-white">{formatearMoneda(detalleCierre.papeleria)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Bonificaciones, viáticos y otros haberes</span>
              <span className="text-white">
                {formatearMoneda(
                  Number(detalleCierre.bonificaciones) +
                    Number(detalleCierre.viaticos_reconocidos) +
                    Number(detalleCierre.otros_haberes)
                )}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Total haberes (devengado)</span>
              <span className="font-semibold text-white">{formatearMoneda(detalleCierre.total_haberes)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Retiros tarjeta / anticipos del mes</span>
              <span className="text-orange-400">{formatearMoneda(detalleCierre.retiros_tarjeta_anticipos)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Salud y pensión</span>
              <span className="text-orange-400">{formatearMoneda(detalleCierre.descuento_salud_pension)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Anticipos entregados</span>
              <span className="text-orange-400">{formatearMoneda(detalleCierre.anticipos_entregados)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Gastos a cargo del conductor</span>
              <span className="text-orange-400">{formatearMoneda(detalleCierre.gastos_a_cargo_conductor)}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Préstamos y otros descuentos</span>
              <span className="text-orange-400">
                {formatearMoneda(Number(detalleCierre.prestamos) + Number(detalleCierre.otros_descuentos))}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-slate-400">Total descuentos</span>
              <span className="font-semibold text-orange-400">{formatearMoneda(detalleCierre.total_descuentos)}</span>
            </div>
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-600">
            <span className="text-base font-semibold text-white">Saldo neto del mes</span>
            <span
              className={`text-2xl font-bold ${Number(detalleCierre.saldo_neto) >= 0 ? 'text-green-400' : 'text-red-400'}`}
            >
              {formatearMoneda(detalleCierre.saldo_neto)}
            </span>
          </div>
          {detalleCierre.observaciones && (
            <p className="mt-3 text-xs text-slate-500 whitespace-pre-line">{detalleCierre.observaciones}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default Liquidaciones