import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, Scan, Loader2, AlertCircle, CheckCircle2, XCircle, Receipt, Save } from 'lucide-react'
import { gastosAPI, viajesAPI, vehiculosAPI } from '@/api'
import { extraerMensajeError, formatearMoneda } from '@/utils/format'

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

interface ScanResult {
  gasto_id: number
  hash_comprobante: string
  num_factura: string | null
  valor_total: number
  fecha_gasto: string
  proveedor: string
  cantidad_galones: number | null
  km_registro: number | null
}

interface CapturaForm {
  num_factura: string
  valor_total: string
  fecha_gasto: string
  categoria: string
  descripcion: string
  cantidad_galones: string
  km_registro: string
}

const categorias = ['combustible', 'peaje', 'viaticos', 'mantenimiento', 'lavado', 'parqueadero', 'otros']

const ScanReceipt: React.FC = () => {
  const navigate = useNavigate()

  const [viajes, setViajes] = useState<Viaje[]>([])
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([])
  const [viajeId, setViajeId] = useState('')
  const [vehiculoId, setVehiculoId] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [saving, setSaving] = useState(false)
  const [scanError, setScanError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [success, setSuccess] = useState('')

  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [form, setForm] = useState<CapturaForm>({
    num_factura: '',
    valor_total: '',
    fecha_gasto: '',
    categoria: 'combustible',
    descripcion: '',
    cantidad_galones: '',
    km_registro: '',
  })

  useEffect(() => {
    const cargar = async () => {
      setLoading(true)
      setScanError('')
      try {
        const [viajesRes, vehiculosRes] = await Promise.all([viajesAPI.listar(false), vehiculosAPI.listar()])
        const activos = (viajesRes.data as Viaje[]).filter(
          (v) => v.estado !== 'liquidado' && v.estado !== 'cancelado'
        )
        setViajes(activos)
        setVehiculos(vehiculosRes.data)
        if (activos[0]) setViajeId(String(activos[0].id))
        if (vehiculosRes.data[0]) setVehiculoId(String(vehiculosRes.data[0].id))
      } catch (err) {
        setScanError(extraerMensajeError(err))
      } finally {
        setLoading(false)
      }
    }
    cargar()
  }, [])

  const handleScan = async () => {
    if (!file || !viajeId || !vehiculoId) return
    setScanning(true)
    setScanError('')
    setSaveError('')
    setSuccess('')
    setScanResult(null)
    try {
      const res = await gastosAPI.scanReceipt(file, Number(viajeId), Number(vehiculoId))
      const data: ScanResult = res.data
      setScanResult(data)
      setForm({
        num_factura: data.num_factura || '',
        valor_total: String(data.valor_total ?? ''),
        fecha_gasto: data.fecha_gasto || '',
        categoria: 'combustible',
        descripcion: data.proveedor ? `Compra a ${data.proveedor}` : '',
        cantidad_galones: data.cantidad_galones != null ? String(data.cantidad_galones) : '',
        km_registro: data.km_registro != null ? String(data.km_registro) : '',
      })
      setSuccess('Recibo procesado. Revisa y confirma los datos extraídos.')
    } catch (err) {
      setScanError(extraerMensajeError(err))
    } finally {
      setScanning(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!scanResult) return
    setSaving(true)
    setSaveError('')
    setSuccess('')
    try {
      await gastosAPI.actualizar(scanResult.gasto_id, {
        viaje_id: Number(viajeId),
        vehiculo_id: Number(vehiculoId),
        categoria: form.categoria,
        descripcion: form.descripcion || undefined,
        num_factura: form.num_factura || undefined,
        fecha_gasto: form.fecha_gasto,
        valor_total: form.valor_total,
        cantidad_galones: form.cantidad_galones || undefined,
        km_registro: form.km_registro || undefined,
        asumido_por: 'empresa',
        responsable_pago: 'conductor',
        tiene_num_factura: Boolean(form.num_factura),
        hash_comprobante: scanResult.hash_comprobante,
      })
      setSuccess(`Gasto #${scanResult.gasto_id} confirmado correctamente`)
      navigate('/gastos')
    } catch (err) {
      setSaveError(extraerMensajeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Scan Receipt</h2>
        <p className="text-slate-400">Escanea recibos para registro automático de gastos</p>
      </div>

      <div className="card-truck">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="animate-spin mr-2" size={20} />
            Cargando datos...
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Viaje / ODT</label>
                <select value={viajeId} onChange={(e) => setViajeId(e.target.value)} className="input-truck">
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
                <select value={vehiculoId} onChange={(e) => setVehiculoId(e.target.value)} className="input-truck">
                  <option value="">Selecciona un vehículo</option>
                  {vehiculos.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.placa} - {v.marca}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="border-2 border-dashed border-slate-600 rounded-xl p-8 text-center">
              <Upload className="w-12 h-12 mx-auto text-slate-400 mb-4" />
              <p className="text-slate-300 mb-2">Arrastra una imagen o haz clic para seleccionar</p>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="hidden"
                id="file-input"
              />
              <label htmlFor="file-input" className="btn-celr-orange inline-block cursor-pointer">
                Seleccionar Archivo
              </label>
            </div>

            {file && (
              <div className="mt-4 flex items-center gap-4">
                <div className="glass rounded-lg p-3">
                  <p className="text-sm text-slate-400">Archivo:</p>
                  <p className="text-white font-medium">{file.name}</p>
                </div>
                <button
                  onClick={handleScan}
                  disabled={scanning || !viajeId || !vehiculoId}
                  className="btn-celr disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    {scanning ? <Loader2 className="animate-spin" size={20} /> : <Scan size={20} />}
                    {scanning ? 'Escaneando...' : 'Escanear'}
                  </span>
                </button>
              </div>
            )}

            {scanError && (
              <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mt-4">
                <AlertCircle size={18} />
                <span>{scanError}</span>
              </div>
            )}
            {saveError && (
              <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mt-4">
                <XCircle size={18} />
                <span>{saveError}</span>
              </div>
            )}
            {success && (
              <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 text-green-500 px-4 py-3 rounded-lg mt-4">
                <CheckCircle2 size={18} />
                <span>{success}</span>
              </div>
            )}
          </>
        )}
      </div>

      {scanResult && (
        <div className="card-truck">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Receipt size={20} />
            Formulario de Captura
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 text-sm">
            <div className="glass rounded-lg p-3">
              <p className="text-slate-400">Proveedor (OCR)</p>
              <p className="text-white font-medium">{scanResult.proveedor}</p>
            </div>
            <div className="glass rounded-lg p-3">
              <p className="text-slate-400">Hash comprobante</p>
              <p className="text-slate-300 font-mono text-xs break-all">{scanResult.hash_comprobante}</p>
            </div>
            <div className="glass rounded-lg p-3">
              <p className="text-slate-400">Gasto generado</p>
              <p className="text-white font-medium">#{scanResult.gasto_id}</p>
            </div>
          </div>

          <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Monto</label>
              <input
                type="number"
                value={form.valor_total}
                onChange={(e) => setForm({ ...form, valor_total: e.target.value })}
                className="input-truck"
                min="0.01"
                step="0.01"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Fecha</label>
              <input
                type="date"
                value={form.fecha_gasto}
                onChange={(e) => setForm({ ...form, fecha_gasto: e.target.value })}
                className="input-truck"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">N° Factura</label>
              <input
                type="text"
                value={form.num_factura}
                onChange={(e) => setForm({ ...form, num_factura: e.target.value })}
                className="input-truck"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Categoría</label>
              <select
                value={form.categoria}
                onChange={(e) => setForm({ ...form, categoria: e.target.value })}
                className="input-truck"
              >
                {categorias.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Galones</label>
              <input
                type="number"
                value={form.cantidad_galones}
                onChange={(e) => setForm({ ...form, cantidad_galones: e.target.value })}
                className="input-truck"
                step="0.01"
                min="0"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">KM Registro</label>
              <input
                type="number"
                value={form.km_registro}
                onChange={(e) => setForm({ ...form, km_registro: e.target.value })}
                className="input-truck"
                step="0.01"
                min="0"
              />
            </div>
            <div className="md:col-span-2 lg:col-span-3">
              <label className="block text-sm font-medium text-slate-300 mb-1">Descripción</label>
              <input
                type="text"
                value={form.descripcion}
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
                className="input-truck"
              />
            </div>
            <div className="md:col-span-2 lg:col-span-3 flex items-center justify-between">
              <span className="text-sm text-slate-400">Total detectado: {formatearMoneda(scanResult.valor_total)}</span>
              <button type="submit" disabled={saving} className="btn-celr flex items-center gap-2">
                {saving ? <Loader2 className="animate-spin" size={20} /> : <Save size={20} />}
                {saving ? 'Guardando...' : 'Confirmar Gasto'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

export default ScanReceipt