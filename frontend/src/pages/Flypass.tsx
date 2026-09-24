import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  FileSpreadsheet,
  Filter,
  Loader2,
  RotateCcw,
  Search,
  Upload,
  X,
} from 'lucide-react'
import {
  flypassAPI,
  FlypassImportReporte,
  FlypassListItem,
  FlypassListParams,
} from '@/api'
import Pagination from '@/components/Pagination'
import { extraerMensajeError, formatearMoneda } from '@/utils/format'

interface Filtros {
  fecha_desde: string
  fecha_hasta: string
  placa: string
  sin_odt: boolean
  sin_gasto: boolean
}

const PAGE_SIZE = 50
const filtrosIniciales: Filtros = {
  fecha_desde: '',
  fecha_hasta: '',
  placa: '',
  sin_odt: false,
  sin_gasto: false,
}

const construirParams = (page: number, filtros: Filtros): FlypassListParams => {
  const params: FlypassListParams = {
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
  }
  if (filtros.fecha_desde) params.fecha_desde = filtros.fecha_desde
  if (filtros.fecha_hasta) params.fecha_hasta = filtros.fecha_hasta
  if (filtros.placa.trim()) params.placa = filtros.placa.trim()
  if (filtros.sin_odt) params.sin_odt = true
  if (filtros.sin_gasto) params.sin_gasto = true
  return params
}

const formatearFecha = (valor: string): string => {
  const fecha = new Date(valor)
  return Number.isNaN(fecha.getTime()) ? valor : fecha.toLocaleDateString('es-CO')
}

const formatearErrorImportacion = (item: Record<string, unknown>): string => {
  const fila = item.fila ? `Fila ${String(item.fila)}: ` : ''
  if (typeof item.error === 'string') return `${fila}${item.error}`
  if (item.tipo === 'sin_placa') return `${fila}Placa no encontrada: ${String(item.placa || '')}`
  if (item.tipo === 'gastos_ambiguos') {
    const candidatos = Array.isArray(item.candidatos) ? item.candidatos.length : 0
    return `${fila}Más de un gasto candidato (${candidatos})`
  }
  return `${fila}Revisar detalle de la importación`
}

const Flypass: React.FC = () => {
  const [items, setItems] = useState<FlypassListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filtrosAplicados, setFiltrosAplicados] = useState<Filtros>(filtrosIniciales)
  const [filtros, setFiltros] = useState<Filtros>(filtrosIniciales)
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [importando, setImportando] = useState(false)
  const [importError, setImportError] = useState('')
  const [reporte, setReporte] = useState<FlypassImportReporte | null>(null)
  const [mostrarReporte, setMostrarReporte] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const cargar = useCallback(async () => {
    setLoading(true)
    setListError('')
    try {
      const respuesta = await flypassAPI.listar(construirParams(page, filtrosAplicados))
      setItems(respuesta.data)
      setTotal(respuesta.total)
    } catch (err) {
      setListError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }, [filtrosAplicados, page])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const aplicarFiltros = (event: React.FormEvent) => {
    event.preventDefault()
    setPage(1)
    setFiltrosAplicados({ ...filtros })
  }

  const limpiarFiltros = () => {
    setFiltros(filtrosIniciales)
    setFiltrosAplicados(filtrosIniciales)
    setPage(1)
  }

  const actualizarFiltro = (campo: keyof Filtros, valor: string | boolean) => {
    setFiltros((actual) => ({ ...actual, [campo]: valor }))
  }

  const importarArchivo = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget
    const archivo = input.files?.[0]
    if (!archivo) return
    if (!archivo.name.toLowerCase().endsWith('.xlsx')) {
      setImportError('Solo se admiten archivos .xlsx')
      input.value = ''
      return
    }

    setImportando(true)
    setImportError('')
    setReporte(null)
    try {
      const resultado = await flypassAPI.importar(archivo)
      setReporte(resultado)
      setMostrarReporte(true)
      await cargar()
    } catch (err) {
      setImportError(extraerMensajeError(err))
    } finally {
      setImportando(false)
      input.value = ''
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <FileSpreadsheet className="text-primary-400" size={28} />
            Flypass
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Consulta consumos y legaliza automáticamente los peajes importados.
          </p>
        </div>
        <div>
          <input
            ref={fileInput}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={importarArchivo}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={importando}
            className="btn-celr flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {importando ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
            {importando ? 'Importando...' : 'Importar Excel'}
          </button>
        </div>
      </div>

      {importError && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-500/30 bg-danger-500/10 p-3 text-sm text-danger-400">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <span>{importError}</span>
        </div>
      )}

      <form onSubmit={aplicarFiltros} className="card-truck space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <Filter size={17} className="text-primary-400" />
          Filtros
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <label className="text-sm text-slate-300">
            Fecha desde
            <input
              type="date"
              value={filtros.fecha_desde}
              onChange={(e) => actualizarFiltro('fecha_desde', e.target.value)}
              className="input-truck mt-1"
            />
          </label>
          <label className="text-sm text-slate-300">
            Fecha hasta
            <input
              type="date"
              value={filtros.fecha_hasta}
              onChange={(e) => actualizarFiltro('fecha_hasta', e.target.value)}
              className="input-truck mt-1"
            />
          </label>
          <label className="text-sm text-slate-300">
            Placa
            <input
              type="text"
              value={filtros.placa}
              onChange={(e) => actualizarFiltro('placa', e.target.value)}
              placeholder="Ej. ABC123"
              className="input-truck mt-1"
            />
          </label>
          <div className="flex items-end gap-4 pb-2 text-sm text-slate-300">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filtros.sin_odt}
                onChange={(e) => actualizarFiltro('sin_odt', e.target.checked)}
              />
              Sin ODT
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filtros.sin_gasto}
                onChange={(e) => actualizarFiltro('sin_gasto', e.target.checked)}
              />
              Sin gasto
            </label>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="btn-celr flex items-center gap-2">
            <Search size={16} />
            Aplicar filtros
          </button>
          <button
            type="button"
            onClick={limpiarFiltros}
            className="btn-secondary flex items-center gap-2"
          >
            <RotateCcw size={16} />
            Limpiar
          </button>
        </div>
      </form>

      {listError && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-500/30 bg-danger-500/10 p-3 text-sm text-danger-400">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <span>{listError}</span>
        </div>
      )}

      <div className="card-truck">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white">Transacciones</h3>
            <p className="text-xs text-slate-400 mt-1">{total} registros encontrados</p>
          </div>
          {loading && <Loader2 size={20} className="animate-spin text-primary-400" />}
        </div>

        {!loading && items.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            <FileSpreadsheet size={36} className="mx-auto mb-3 opacity-50" />
            <p>No hay transacciones Flypass para mostrar.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wider text-slate-500 border-b border-slate-700">
                <tr>
                  <th className="px-3 py-3">Fecha</th>
                  <th className="px-3 py-3">Placa</th>
                  <th className="px-3 py-3">Peaje</th>
                  <th className="px-3 py-3 text-right">Valor</th>
                  <th className="px-3 py-3">Transacción</th>
                  <th className="px-3 py-3">ODT</th>
                  <th className="px-3 py-3">Gasto</th>
                  <th className="px-3 py-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/50">
                    <td className="px-3 py-3 whitespace-nowrap text-slate-300">
                      {formatearFecha(item.fecha_transaccion)}
                    </td>
                    <td className="px-3 py-3 font-medium text-white">{item.placa || '—'}</td>
                    <td className="px-3 py-3 text-slate-300">{item.nombre_peaje || '—'}</td>
                    <td className="px-3 py-3 text-right text-white whitespace-nowrap">
                      {formatearMoneda(item.valor)}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-400 whitespace-nowrap">
                      {item.num_transaccion_flypass}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {item.viaje_id ? (
                        <a
                          href={`/viajes?odt=${item.viaje_id}`}
                          className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                        >
                          ODT #{item.viaje_id} <ExternalLink size={13} />
                        </a>
                      ) : (
                        <span className="text-slate-600">Sin ODT</span>
                      )}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {item.gasto_id ? (
                        <a
                          href={`/gastos?gasto=${item.gasto_id}`}
                          className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                        >
                          Gasto #{item.gasto_id} <ExternalLink size={13} />
                        </a>
                      ) : (
                        <span className="text-amber-400">Sin gasto</span>
                      )}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {item.legalizado_en_gastos ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-2 py-1 text-xs text-green-400">
                          <CheckCircle2 size={13} /> Legalizado
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-1 text-xs text-amber-400">
                          <AlertCircle size={13} /> Pendiente
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination total={total} page={page} pageSize={PAGE_SIZE} onPage={setPage} />
      </div>

      {mostrarReporte && reporte && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">Reporte de importación</h3>
                <p className="text-sm text-slate-400 mt-1">Resultado del archivo Excel procesado.</p>
              </div>
              <button
                type="button"
                onClick={() => setMostrarReporte(false)}
                className="p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
                title="Cerrar"
              >
                <X size={19} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ['Insertados', reporte.insertados],
                ['Duplicados', reporte.duplicados],
                ['Sin placa', reporte.sin_placa],
                ['Ambiguos', reporte.ambiguos],
                ['Gastos creados', reporte.creados_gastos],
                ['Gastos matcheados', reporte.matcheados_gastos],
                ['Sin ODT', reporte.sin_odt],
                ['Errores', reporte.errores.length],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-lg border border-slate-700 bg-slate-800/60 p-3">
                  <p className="text-xs text-slate-400">{label}</p>
                  <p className="text-xl font-semibold text-white mt-1">{value}</p>
                </div>
              ))}
            </div>
            {reporte.errores.length > 0 && (
              <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                <p className="text-sm font-semibold text-amber-300 mb-2">Detalles de filas</p>
                <ul className="space-y-1 text-sm text-amber-200">
                  {reporte.errores.map((item, index) => (
                    <li key={`${formatearErrorImportacion(item)}-${index}`}>
                      {formatearErrorImportacion(item)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-5 flex justify-end">
              <button type="button" onClick={() => setMostrarReporte(false)} className="btn-celr">
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Flypass
