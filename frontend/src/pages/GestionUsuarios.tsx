import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Users,
  UserPlus,
  Pencil,
  KeyRound,
  ShieldCheck,
  Ban,
  Power,
  Copy,
  Check,
  X,
  AlertCircle,
  Loader2,
  Search,
  UserX,
  UserCog,
} from 'lucide-react'
import { usuariosAPI, UsuarioListItem, ResetCodigoResponse } from '@/api'
import { conductoresAPI } from '@/api'
import { useAuth } from '@/context/AuthContext'
import { extraerMensajeError } from '@/utils/format'
import Pagination from '@/components/Pagination'

// Igual que en Viajes.tsx: `Conductor` no vive en api/index.ts, cada pagina
// declara la forma que usa.
interface Conductor {
  id: number
  nombre_completo: string
  cedula: string
  telefono?: string | null
  correo?: string | null
  estado?: string
}

const PAGE_SIZE = 50

const ROLES = ['admin', 'operador', 'contador', 'supervisor', 'cliente', 'conductor'] as const

// A5.3 — Refleja ROLES_OBJETIVO_POR_EJECUTOR (A3.2). El backend es la
// fuente de verdad y devuelve 403 si el rol pedido no esta aca: esta lista
// es la que evita ofrecer una opcion que el servidor va a rechazar.
const ROLES_POR_EJECUTOR: Record<string, readonly string[]> = {
  admin: ROLES,
  operador: ['conductor', 'cliente'],
  contador: ['conductor', 'cliente'],
  supervisor: ['conductor', 'cliente'],
}

const badgeRol = (rol: string) => {
  const mapa: Record<string, string> = {
    admin: 'bg-purple-500/20 text-purple-400',
    operador: 'bg-blue-500/20 text-blue-400',
    contador: 'bg-cyan-500/20 text-cyan-400',
    supervisor: 'bg-amber-500/20 text-amber-400',
    cliente: 'bg-green-500/20 text-green-400',
    conductor: 'bg-slate-500/20 text-slate-300',
  }
  return mapa[rol] || 'bg-slate-500/20 text-slate-300'
}

const formatFecha = (valor?: string | null) => {
  if (!valor) return 'Nunca'
  const d = new Date(valor)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })
}

type ModalTipo = 'crear' | 'editar' | 'temporal' | 'codigo' | 'desactivar' | 'degradar' | null

const GestionUsuarios: React.FC = () => {
  const { user } = useAuth()
  const esAdmin = user?.rol === 'admin'
  const rolesPermitidos = useMemo(
    () => ROLES_POR_EJECUTOR[user?.rol || ''] ?? [],
    [user?.rol]
  )

  const [usuarios, setUsuarios] = useState<UsuarioListItem[]>([])
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [cargando, setCargando] = useState(true)
  const [errorLista, setErrorLista] = useState('')

  const [filtroActivo, setFiltroActivo] = useState<string>('')
  const [filtroRol, setFiltroRol] = useState<string>('')
  const [filtroTexto, setFiltroTexto] = useState('')
  const [filtros, setFiltros] = useState<{ activo?: boolean; rol?: string }>({})

  const [conductores, setConductores] = useState<Conductor[]>([])
  const [modal, setModal] = useState<ModalTipo>(null)
  const [objetivo, setObjetivo] = useState<UsuarioListItem | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [errorModal, setErrorModal] = useState('')

  const [formCrear, setFormCrear] = useState({
    cedula: '',
    correo: '',
    rol: '',
    conductor_id: '',
  })
  const [formEditar, setFormEditar] = useState({ cedula: '', correo: '', conductor_id: '' })
  const [temporal, setTemporal] = useState<{ valor: string; mensaje: string; copiado: boolean } | null>(
    null
  )
  const [codigo, setCodigo] = useState<ResetCodigoResponse | null>(null)
  const [copiado, setCopiado] = useState(false)
  const [formConfirma, setFormConfirma] = useState({ confirmacion: '', motivo: '', nuevo_rol: '' })

  const cargar = useCallback(async () => {
    setCargando(true)
    setErrorLista('')
    try {
      const res = await usuariosAPI.listar({
        skip: (pagina - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
        ...filtros,
      })
      setUsuarios(res.data)
      setTotal(res.total)
    } catch (e) {
      setErrorLista(extraerMensajeError(e))
    } finally {
      setCargando(false)
    }
  }, [pagina, filtros])

  useEffect(() => {
    cargar()
  }, [cargar])

  useEffect(() => {
    // Sin conductores no se puede vincular: la lista queda vacia y el select
    // lo avisa. No es motivo para romper la pagina.
    conductoresAPI
      .listar({ limit: 200 })
      .then((res) => setConductores(res.data as unknown as Conductor[]))
      .catch(() => setConductores([]))
  }, [])

  const abrir = (tipo: ModalTipo, u?: UsuarioListItem) => {
    setErrorModal('')
    setModal(tipo)
    setObjetivo(u || null)
    setTemporal(null)
    setCodigo(null)
    setCopiado(false)
    setFormConfirma({ confirmacion: '', motivo: '', nuevo_rol: '' })
    if (tipo === 'crear') {
      setFormCrear({ cedula: '', correo: '', rol: rolesPermitidos[0] || '', conductor_id: '' })
    }
    if (tipo === 'editar' && u) {
      setFormEditar({
        cedula: u.cedula || '',
        correo: u.correo || '',
        conductor_id: u.conductor_id ? String(u.conductor_id) : '',
      })
    }
  }

  const cerrar = () => {
    setModal(null)
    setObjetivo(null)
    setTemporal(null)
    setCodigo(null)
    setErrorModal('')
  }

  const copiar = async (texto: string) => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
    } catch {
      setCopiado(false)
    }
  }

  const crear = async (e: React.FormEvent) => {
    e.preventDefault()
    setEnviando(true)
    setErrorModal('')
    try {
      const res = await usuariosAPI.crear({
        cedula: formCrear.cedula.trim(),
        correo: formCrear.correo.trim() || null,
        rol: formCrear.rol,
        conductor_id: formCrear.conductor_id ? Number(formCrear.conductor_id) : null,
      })
      setTemporal({
        valor: res.contrasena_temporal,
        mensaje: res.mensaje,
        copiado: false,
      })
      setModal('temporal')
      cargar()
    } catch (err) {
      setErrorModal(extraerMensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  const editar = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!objetivo) return
    setEnviando(true)
    setErrorModal('')
    try {
      await usuariosAPI.actualizar(objetivo.id, {
        cedula: formEditar.cedula.trim() || null,
        correo: formEditar.correo.trim() || null,
        conductor_id: formEditar.conductor_id ? Number(formEditar.conductor_id) : null,
      })
      cerrar()
      cargar()
    } catch (err) {
      setErrorModal(extraerMensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  const confirmarAccion = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!objetivo) return
    setEnviando(true)
    setErrorModal('')
    try {
      if (modal === 'desactivar') {
        await usuariosAPI.desactivar(
          objetivo.id,
          formConfirma.confirmacion.trim(),
          formConfirma.motivo.trim() || undefined
        )
      } else if (modal === 'degradar') {
        await usuariosAPI.degradar(
          objetivo.id,
          formConfirma.nuevo_rol,
          formConfirma.confirmacion.trim(),
          formConfirma.motivo.trim() || undefined
        )
      }
      cerrar()
      cargar()
    } catch (err) {
      setErrorModal(extraerMensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  const resetPassword = async (u: UsuarioListItem) => {
    setEnviando(true)
    try {
      const res = await usuariosAPI.resetPassword(u.id)
      setObjetivo(u)
      setTemporal({ valor: res.contrasena_temporal, mensaje: res.mensaje, copiado: false })
      setModal('temporal')
    } catch (err) {
      abrir('crear', u)
      setErrorModal(extraerMensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  const generarCodigo = async (u: UsuarioListItem) => {
    setEnviando(true)
    try {
      const res = await usuariosAPI.resetCodigo(u.id)
      setObjetivo(u)
      setCodigo(res)
      setCopiado(false)
      setModal('codigo')
    } catch (err) {
      setErrorModal(extraerMensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  const activar = async (u: UsuarioListItem) => {
    setEnviando(true)
    setErrorModal('')
    try {
      await usuariosAPI.activar(u.id)
      cargar()
    } catch (err) {
      setErrorModal(extraerMensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  // Filtro de texto en el cliente: la cedula, el correo y el rol. El backend
  // no expone busqueda y agregar un endpoint para esto seria alcance de A5.1
  // que ya cerro; con la lista paginada el filtro opera sobre la pagina
  // visible, y el texto lo aclara en la UI.
  const visibles = useMemo(() => {
    const t = filtroTexto.trim().toLowerCase()
    if (!t) return usuarios
    return usuarios.filter((u) =>
      [u.cedula, u.correo, u.rol].some((campo) => (campo || '').toLowerCase().includes(t))
    )
  }, [usuarios, filtroTexto])

  const aplicarFiltros = () => {
    setFiltros({
      ...(filtroActivo !== '' ? { activo: filtroActivo === 'true' } : {}),
      ...(filtroRol !== '' ? { rol: filtroRol } : {}),
    })
    setPagina(1)
  }

  const limpiarFiltros = () => {
    setFiltroActivo('')
    setFiltroRol('')
    setFiltroTexto('')
    setFiltros({})
    setPagina(1)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users size={24} className="text-primary-400" />
            Gestión de Usuarios
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {esAdmin
              ? 'Como admin ves todas las cuentas y podés crear cualquiera.'
              : `Como ${user?.rol} ves solo los roles que podés administrar.`}
          </p>
        </div>
        <button type="button" onClick={() => abrir('crear')} className="btn-celr flex items-center gap-2">
          <UserPlus size={20} />
          Crear usuario
        </button>
      </div>

      {errorLista && (
        <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg">
          <AlertCircle size={18} />
          <span>{errorLista}</span>
        </div>
      )}

      <div className="card-truck">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Estado</label>
            <select
              value={filtroActivo}
              onChange={(e) => setFiltroActivo(e.target.value)}
              className="input-truck"
            >
              <option value="">Todos</option>
              <option value="true">Activos</option>
              <option value="false">Inactivos</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Rol</label>
            <select value={filtroRol} onChange={(e) => setFiltroRol(e.target.value)} className="input-truck">
              <option value="">Todos</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Buscar</label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={filtroTexto}
                onChange={(e) => setFiltroTexto(e.target.value)}
                className="input-truck pl-9"
                placeholder="Cédula, correo o rol"
              />
            </div>
          </div>
          <div className="flex items-end gap-2">
            <button type="button" onClick={aplicarFiltros} className="btn-celr">
              Aplicar
            </button>
            <button
              type="button"
              onClick={limpiarFiltros}
              className="py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
            >
              Limpiar
            </button>
          </div>
        </div>
        {filtroTexto.trim() && (
          <p className="text-xs text-slate-500 mt-2">
            La búsqueda de texto filtra la página visible ({visibles.length} de {usuarios.length}).
          </p>
        )}
      </div>

      <div className="card-truck">
        {cargando ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="animate-spin" size={24} />
          </div>
        ) : visibles.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-500">
            <UserX size={32} className="mb-2" />
            <p>No hay usuarios para mostrar.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="py-2 px-3">Cédula</th>
                  <th className="py-2 px-3">Correo</th>
                  <th className="py-2 px-3">Rol</th>
                  <th className="py-2 px-3">Activo</th>
                  <th className="py-2 px-3">Último acceso</th>
                  <th className="py-2 px-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {visibles.map((u) => (
                  <tr key={u.id} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/40">
                    <td className="py-3 px-3 font-mono text-primary-400">{u.cedula || '—'}</td>
                    <td className="py-3 px-3 text-white">{u.correo || '—'}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${badgeRol(u.rol)}`}>
                        {u.rol}
                      </span>
                      {u.debe_cambiar_contrasena && (
                        <span className="ml-1 px-2 py-1 rounded text-xs bg-amber-500/20 text-amber-400">
                          debe cambiar clave
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          u.activo ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'
                        }`}
                      >
                        {u.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-400">{formatFecha(u.ultimo_acceso)}</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center justify-end gap-1 flex-wrap">
                        <button
                          type="button"
                          title="Editar"
                          onClick={() => abrir('editar', u)}
                          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          type="button"
                          title="Restablecer contraseña (temporal)"
                          onClick={() => resetPassword(u)}
                          disabled={enviando}
                          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors disabled:opacity-40"
                        >
                          <KeyRound size={16} />
                        </button>
                        <button
                          type="button"
                          title="Generar código offline"
                          onClick={() => generarCodigo(u)}
                          disabled={enviando}
                          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors disabled:opacity-40"
                        >
                          <ShieldCheck size={16} />
                        </button>
                        {u.activo ? (
                          <button
                            type="button"
                            title="Desactivar"
                            onClick={() => abrir('desactivar', u)}
                            className="p-2 rounded-lg text-amber-300 hover:bg-slate-800 transition-colors"
                          >
                            <Ban size={16} />
                          </button>
                        ) : (
                          <button
                            type="button"
                            title="Reactivar"
                            onClick={() => activar(u)}
                            disabled={enviando}
                            className="p-2 rounded-lg text-green-400 hover:bg-slate-800 transition-colors disabled:opacity-40"
                          >
                            <Power size={16} />
                          </button>
                        )}
                        {esAdmin && u.rol !== 'conductor' && u.rol !== 'cliente' && (
                          <button
                            type="button"
                            title="Cambiar rol"
                            onClick={() => abrir('degradar', u)}
                            className="p-2 rounded-lg text-purple-300 hover:bg-slate-800 transition-colors"
                          >
                            <UserCog size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination total={total} page={pagina} pageSize={PAGE_SIZE} onPage={setPagina} />
      </div>

      {/* ---- Modal Crear ---- */}
      {modal === 'crear' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <ModalHeader titulo="Crear usuario" onClose={cerrar} />
            {errorModal && <ErrorBox mensaje={errorModal} />}
            <form onSubmit={crear} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Cédula <span className="text-red-400">*</span>
                </label>
                <input
                  value={formCrear.cedula}
                  onChange={(e) => setFormCrear({ ...formCrear, cedula: e.target.value })}
                  className="input-truck"
                  required
                />
                <p className="text-xs text-slate-500 mt-1">
                  Identidad canónica de la cuenta. Es obligatoria.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Correo</label>
                <input
                  type="email"
                  value={formCrear.correo}
                  onChange={(e) => setFormCrear({ ...formCrear, correo: e.target.value })}
                  className="input-truck"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Opcional. Sin correo no hay enlace de recuperación por email.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Rol <span className="text-red-400">*</span>
                </label>
                <select
                  value={formCrear.rol}
                  onChange={(e) => setFormCrear({ ...formCrear, rol: e.target.value })}
                  className="input-truck"
                  required
                >
                  {rolesPermitidos.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500 mt-1">
                  Solo los roles que tu cuenta puede conceder.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Vincular a conductor</label>
                <select
                  value={formCrear.conductor_id}
                  onChange={(e) => setFormCrear({ ...formCrear, conductor_id: e.target.value })}
                  className="input-truck"
                >
                  <option value="">No vincular</option>
                  {conductores.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre_completo} (céd. {c.cedula})
                    </option>
                  ))}
                </select>
                {formCrear.conductor_id && (
                  <p className="text-xs text-amber-400 mt-1">
                    La cédula de arriba debe coincidir con la del conductor ({conductores.find(
                      (c) => String(c.id) === formCrear.conductor_id
                    )?.cedula || '—'}
                    ), si no el servidor lo rechaza.
                  </p>
                )}
              </div>
              <div className="md:col-span-2 flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={cerrar}
                  className="py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Cancelar
                </button>
                <button type="submit" disabled={enviando} className="btn-celr flex items-center gap-2">
                  {enviando ? <Loader2 className="animate-spin" size={20} /> : <UserPlus size={20} />}
                  Crear
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---- Modal Editar ---- */}
      {modal === 'editar' && objetivo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <ModalHeader titulo={`Editar usuario ${objetivo.cedula || objetivo.correo || objetivo.id}`} onClose={cerrar} />
            {errorModal && <ErrorBox mensaje={errorModal} />}
            <form onSubmit={editar} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Rol</label>
                <div className="input-truck bg-slate-800/60 text-slate-400">{objetivo.rol}</div>
                <p className="text-xs text-slate-500 mt-1">
                  El rol no se edita acá. Para cambiarlo, desactivá la cuenta y creá una nueva.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Cédula</label>
                <input
                  value={formEditar.cedula}
                  onChange={(e) => setFormEditar({ ...formEditar, cedula: e.target.value })}
                  className="input-truck"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Correo</label>
                <input
                  type="email"
                  value={formEditar.correo}
                  onChange={(e) => setFormEditar({ ...formEditar, correo: e.target.value })}
                  className="input-truck"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-slate-300 mb-1">Conductor vinculado</label>
                <select
                  value={formEditar.conductor_id}
                  onChange={(e) => setFormEditar({ ...formEditar, conductor_id: e.target.value })}
                  className="input-truck"
                >
                  <option value="">Desvincular</option>
                  {conductores.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre_completo} (céd. {c.cedula})
                    </option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2 flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={cerrar}
                  className="py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Cancelar
                </button>
                <button type="submit" disabled={enviando} className="btn-celr flex items-center gap-2">
                  {enviando ? <Loader2 className="animate-spin" size={20} /> : <Pencil size={20} />}
                  Guardar cambios
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---- Modal credencial temporal ---- */}
      {modal === 'temporal' && temporal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-lg">
            <ModalHeader titulo="Contraseña temporal" onClose={cerrar} />
            <p className="text-sm text-slate-300 mb-4">
              Comunicásela al usuario por un canal seguro. <strong>No se mostrará de nuevo.</strong>
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-4 py-3 rounded-lg bg-slate-800 border border-slate-700 text-white font-mono text-lg break-all">
                {temporal.valor}
              </code>
              <button
                type="button"
                onClick={() => copiar(temporal.valor)}
                title="Copiar"
                className="p-3 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
              >
                {temporal.copiado ? <Check size={20} className="text-green-400" /> : <Copy size={20} />}
              </button>
            </div>
            {objetivo && (
              <p className="text-xs text-slate-500 mt-3">
                Usuario: {objetivo.cedula || objetivo.correo || `#${objetivo.id}`}. Deberá cambiarla al
                iniciar sesión.
              </p>
            )}
            <div className="flex justify-end mt-5">
              <button type="button" onClick={cerrar} className="btn-celr">
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Modal codigo offline ---- */}
      {modal === 'codigo' && codigo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-lg">
            <ModalHeader titulo="Código de recuperación" onClose={cerrar} />
            <p className="text-sm text-slate-300 mb-4">
              <strong>No se envía por email.</strong> Dictáselo al usuario por teléfono o presencial.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-4 py-3 rounded-lg bg-slate-800 border border-slate-700 text-white font-mono text-3xl tracking-widest text-center">
                {codigo.codigo}
              </code>
              <button
                type="button"
                onClick={() => copiar(codigo.codigo)}
                title="Copiar"
                className="p-3 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
              >
                {copiado ? <Check size={20} className="text-green-400" /> : <Copy size={20} />}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-3">
              Vence: {formatFecha(codigo.expira_en)} · El usuario lo canjea junto con su nueva contraseña.
            </p>
            <div className="flex justify-end mt-5">
              <button type="button" onClick={cerrar} className="btn-celr">
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Modal desactivar / degradar ---- */}
      {(modal === 'desactivar' || modal === 'degradar') && objetivo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card-truck w-full max-w-lg">
            <ModalHeader
              titulo={modal === 'desactivar' ? 'Desactivar usuario' : 'Cambiar rol'}
              onClose={cerrar}
            />
            {errorModal && <ErrorBox mensaje={errorModal} />}
            <form onSubmit={confirmarAccion} className="space-y-4">
              {modal === 'degradar' && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Nuevo rol</label>
                  <select
                    value={formConfirma.nuevo_rol}
                    onChange={(e) => setFormConfirma({ ...formConfirma, nuevo_rol: e.target.value })}
                    className="input-truck"
                    required
                  >
                    <option value="">Elegí un rol</option>
                    {(ROLES as readonly string[])
                      .filter((r) => r !== objetivo.rol)
                      .map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Escribí la cédula o el correo de <span className="text-white">{objetivo.cedula || objetivo.correo || `#${objetivo.id}`}</span>{' '}
                  para confirmar
                </label>
                <input
                  value={formConfirma.confirmacion}
                  onChange={(e) => setFormConfirma({ ...formConfirma, confirmacion: e.target.value })}
                  className="input-truck"
                  placeholder="Cédula o correo del usuario"
                  required
                />
                <p className="text-xs text-slate-500 mt-1">
                  Confirmación deliberada: la operación queda auditada con lo que escribiste.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Motivo (opcional)</label>
                <input
                  value={formConfirma.motivo}
                  onChange={(e) => setFormConfirma({ ...formConfirma, motivo: e.target.value })}
                  className="input-truck"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={cerrar}
                  className="py-2 px-4 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Cancelar
                </button>
                <button type="submit" disabled={enviando} className="btn-celr flex items-center gap-2">
                  {enviando && <Loader2 className="animate-spin" size={20} />}
                  {modal === 'desactivar' ? 'Desactivar' : 'Cambiar rol'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

const ModalHeader: React.FC<{ titulo: string; onClose: () => void }> = ({ titulo, onClose }) => (
  <div className="flex items-center justify-between mb-4">
    <h3 className="text-lg font-semibold text-white">{titulo}</h3>
    <button
      type="button"
      onClick={onClose}
      className="p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
    >
      <X size={20} />
    </button>
  </div>
)

const ErrorBox: React.FC<{ mensaje: string }> = ({ mensaje }) => (
  <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
    <AlertCircle size={18} />
    <span>{mensaje}</span>
  </div>
)

export default GestionUsuarios
