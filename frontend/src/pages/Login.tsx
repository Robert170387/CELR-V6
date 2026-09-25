import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Truck, Fingerprint, Lock, AlertCircle, Loader2 } from 'lucide-react'

const Login: React.FC = () => {
  const [identificador, setIdentificador] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(identificador, contrasena)
      navigate('/', { replace: true })
    } catch (err) {
      setError('Credenciales incorrectas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md animate-fade-in">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-xl mb-4 glow-blue">
            <Truck className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">CELR v6</h1>
          <p className="text-slate-400 mt-2">Gestión de Flota de Carga Pesada</p>
        </div>

        <div className="glass rounded-xl p-8">
          <h2 className="text-xl font-semibold text-white mb-6">Iniciar Sesión</h2>

          {error && (
            <div className="flex items-center gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="identificador" className="block text-sm font-medium text-slate-300 mb-1">
                Cédula o correo
              </label>
              <div className="relative">
                <Fingerprint className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                <input
                  id="identificador"
                  name="identificador"
                  // A2: type="text", no "email": el navegador rechazaba una
                  // cedula antes de enviar el formulario.
                  type="text"
                  inputMode="text"
                  autoComplete="username"
                  value={identificador}
                  onChange={(e) => setIdentificador(e.target.value)}
                  className="input-truck pl-10"
                  placeholder="Ej: 1234567890 o usuario@celr.com"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Contraseña</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                <input
                  id="contrasena"
                  name="contrasena"
                  type="password"
                  autoComplete="current-password"
                  value={contrasena}
                  onChange={(e) => setContrasena(e.target.value)}
                  className="input-truck pl-10"
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-celr w-full flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <Lock size={20} />}
              {loading ? 'Iniciando...' : 'Iniciar Sesión'}
            </button>
          </form>

          {/* A5.4 — Sin este link las pantallas de recuperacion quedan
              inalcanzables: nada en el login las lleva ahi. */}
          <div className="mt-4 text-center">
            <Link
              to="/recuperar"
              className="text-sm text-primary-400 hover:text-primary-300 transition-colors"
            >
              ¿Olvidaste tu contraseña?
            </Link>
          </div>

          {/* A2: las credenciales de demo no deben exponerse en produccion
              (Render sirve el build estatico); solo en desarrollo. */}
          {import.meta.env.DEV && (
            <p className="text-xs text-slate-500 mt-4 text-center">
              Demo: test@celr.com / admin123
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default Login
