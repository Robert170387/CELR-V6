import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, Lock, Loader2, CheckCircle2, ShieldAlert } from 'lucide-react'
import { authAPI } from '@/api'
import { extraerMensajeError } from '@/utils/format'
import PublicShell, { LinkVolver } from '@/components/PublicShell'

// A5.4 — A3.3, canje del codigo offline de 6 digitos. No recibe
// identificador: el codigo ES la prueba, y la unica defensa contra adivinarlo
// es el limite por IP del backend.
const ResetCodigo: React.FC = () => {
  const [codigo, setCodigo] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetir, setRepetir] = useState('')
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (nueva !== repetir) {
      setError('Las contraseñas no coinciden.')
      return
    }
    if (!/^\d{6}$/.test(codigo)) {
      setError('El código son 6 dígitos.')
      return
    }
    setLoading(true)
    try {
      setExito(await authAPI.resetCodigo(codigo, nueva))
    } catch (err) {
      setError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <PublicShell
      titulo="Usar código de recuperación"
      subtitulo="Escribí el código de 6 dígitos que te dio un administrador y definí tu contraseña nueva."
      error={error}
      pie={<LinkVolver>Volver a iniciar sesión</LinkVolver>}
    >
      {exito ? (
        <div className="space-y-4">
          <div className="flex items-start gap-2 bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg">
            <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
            <span>{exito}</span>
          </div>
          <Link to="/login" className="btn-celr w-full flex items-center justify-center gap-2">
            <Lock size={20} />
            Ir a iniciar sesión
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="codigo" className="block text-sm font-medium text-slate-300 mb-1">
              Código de 6 dígitos
            </label>
            <div className="relative">
              <KeyRound
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                size={18}
              />
              <input
                id="codigo"
                // inputMode numeric y type text: un type="number" perderia los
                // ceros iniciales ("012345" -> 12345) y el backend genera
                // codigos que los llevan. El patron del schema es ^\d{6}$.
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={codigo}
                onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className="input-truck pl-10 font-mono tracking-widest text-lg"
                placeholder="000000"
                required
              />
            </div>
          </div>

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
            <p className="text-xs text-slate-500 mt-1">Mínimo 8 caracteres.</p>
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

          {/* A3.3: un 422 por politica CUENTA como intento fallido, a
              diferencia del enlace. Decirlo evita que alguien queme sus
              intentos sin saber por que. */}
          <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 text-amber-400 px-4 py-3 rounded-lg">
            <ShieldAlert size={18} className="shrink-0 mt-0.5" />
            <span className="text-sm">
              El código tiene un número limitado de intentos. Si la contraseña no cumple la
              política, el intento cuenta igual.
            </span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-celr w-full flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : <KeyRound size={20} />}
            {loading ? 'Validando...' : 'Usar código'}
          </button>
        </form>
      )}
    </PublicShell>
  )
}

export default ResetCodigo
