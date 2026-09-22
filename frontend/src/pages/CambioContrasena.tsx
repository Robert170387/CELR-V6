import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { KeyRound, AlertCircle, CheckCircle2, Loader2, Lock } from 'lucide-react'
import { extraerMensajeError } from '@/utils/format'

const CambioContrasena: React.FC = () => {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const { cambiarContrasena, logout } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (nueva.length < 6) {
      setError('La nueva contraseña debe tener al menos 6 caracteres')
      return
    }
    if (nueva !== confirmacion) {
      setError('La confirmación no coincide con la nueva contraseña')
      return
    }
    setLoading(true)
    try {
      await cambiarContrasena(actual, nueva)
      setSuccess('Contraseña actualizada correctamente')
      setTimeout(() => navigate('/', { replace: true }), 900)
    } catch (err) {
      setError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md animate-fade-in">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-xl mb-4 glow-blue">
            <KeyRound className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Cambiar Contraseña</h1>
          <p className="text-slate-400 mt-2 text-sm">
            Por seguridad debes cambiar tu contraseña antes de continuar
          </p>
        </div>

        <div className="glass rounded-xl p-8">
          {error && (
            <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 text-green-500 px-4 py-3 rounded-lg mb-4">
              <CheckCircle2 size={18} />
              <span>{success}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Contraseña actual</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                <input
                  type="password"
                  value={actual}
                  onChange={(e) => setActual(e.target.value)}
                  className="input-truck pl-10"
                  placeholder="     ••••••••"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Nueva contraseña</label>
              <input
                type="password"
                value={nueva}
                onChange={(e) => setNueva(e.target.value)}
                className="input-truck"
                placeholder="Mínimo 6 caracteres"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Confirmar nueva contraseña</label>
              <input
                type="password"
                value={confirmacion}
                onChange={(e) => setConfirmacion(e.target.value)}
                className="input-truck"
                placeholder="Repite la nueva contraseña"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-celr w-full flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <KeyRound size={20} />}
              {loading ? 'Guardando...' : 'Cambiar Contraseña'}
            </button>
          </form>

          <button
            type="button"
            onClick={logout}
            className="w-full text-center text-xs text-slate-500 mt-4 hover:text-slate-300 transition-colors"
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    </div>
  )
}

export default CambioContrasena