import React, { useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Lock, Loader2, CheckCircle2 } from 'lucide-react'
import { authAPI } from '@/api'
import { extraerMensajeError } from '@/utils/format'
import PublicShell, { LinkVolver } from '@/components/PublicShell'

// A5.4 — A3.1, canje del token de enlace. OJO con el nombre: esta ruta es
// PUBLICA y autenticada por el token. `/cambiar-contrasena` es lo otro: exige
// sesion activa. No confundirlas; viven en lados opuestos de ProtectedRoute.
const ResetPassword: React.FC = () => {
  const [params] = useSearchParams()
  const token = params.get('token') || ''

  const [nueva, setNueva] = useState('')
  const [repetir, setRepetir] = useState('')
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [loading, setLoading] = useState(false)

  // Sin token no se dispara la peticion: el backend responderia 401 y, sin el
  // fix del interceptor, eso terminaba en una redireccion a /login. Ademas
  // un enlace sin token es un error del usuario, no del servidor.
  if (!token && !exito) {
    return (
      <PublicShell
        titulo="Enlace incompleto"
        subtitulo="Este enlace no trae un token de recuperación."
        pie={<LinkVolver>Volver a iniciar sesión</LinkVolver>}
      >
        <p className="text-sm text-slate-400">
          Es probable que se haya cortado el enlace. Pedí uno nuevo desde{' '}
          <Link to="/recuperar" className="text-primary-400 hover:text-primary-300">
            recuperar acceso
          </Link>
          .
        </p>
      </PublicShell>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (nueva !== repetir) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setLoading(true)
    try {
      // El backend valida la politica y devuelve 422 con el motivo exacto SIN
      // consumir el token, asi que un error de tipeo se puede reintentar con
      // el mismo enlace. Por eso la politica no se reimplementa aca: la
      // explica el servidor.
      setExito(await authAPI.resetPassword(token, nueva))
    } catch (err) {
      setError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <PublicShell
      titulo="Crear contraseña nueva"
      subtitulo="Definí la contraseña con la que vas a entrar desde ahora."
      error={error}
      pie={<LinkVolver>Volver a iniciar sesión</LinkVolver>}
    >
      {exito ? (
        <div className="space-y-4">
          <div className="flex items-start gap-2 bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg">
            <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
            <span>{exito}</span>
          </div>
          <p className="text-sm text-slate-400">
            Las demás sesiones abiertas quedaron cerradas por seguridad.
          </p>
          <Link to="/login" className="btn-celr w-full flex items-center justify-center gap-2">
            <Lock size={20} />
            Ir a iniciar sesión
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="nueva" className="block text-sm font-medium text-slate-300 mb-1">
              Contraseña nueva
            </label>
            <div className="relative">
              <Lock
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                size={18}
              />
              <input
                id="nueva"
                type="password"
                autoComplete="new-password"
                value={nueva}
                onChange={(e) => setNueva(e.target.value)}
                className="input-truck pl-10"
                required
              />
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Mínimo 8 caracteres. No puede ser igual a tu cédula ni a tu correo.
            </p>
          </div>

          <div>
            <label
              htmlFor="repetir"
              className="block text-sm font-medium text-slate-300 mb-1"
            >
              Repetir contraseña
            </label>
            <div className="relative">
              <Lock
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                size={18}
              />
              <input
                id="repetir"
                type="password"
                autoComplete="new-password"
                value={repetir}
                onChange={(e) => setRepetir(e.target.value)}
                className="input-truck pl-10"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-celr w-full flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="animate-spin" size={20} />}
            Guardar contraseña
          </button>
        </form>
      )}
    </PublicShell>
  )
}

export default ResetPassword
