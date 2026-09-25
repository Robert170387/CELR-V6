import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Fingerprint, Mail, Loader2, CheckCircle2 } from 'lucide-react'
import { authAPI } from '@/api'
import { extraerMensajeError } from '@/utils/format'
import PublicShell, { LinkVolver } from '@/components/PublicShell'

// A5.4 — A3.1, pantalla publica. Pedir un enlace NO revela si la cuenta existe:
// el backend responde 200 con el mismo texto exista o no, y esta pantalla
// muestra ese texto tal cual. Agregar un "revisá tu correo" condicional
// seria un oraculo de enumeracion de cuentas, asi que no se agrega. La
// diferencia entre un 200 y otro tampoco se puede insinuar.
const Recuperar: React.FC = () => {
  const [identificador, setIdentificador] = useState('')
  const [enviado, setEnviado] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      setEnviado(await authAPI.forgotPassword(identificador.trim()))
    } catch (err) {
      // El unico 4xx posible aca es 429 por rate limit, cuyo detail dice
      // cuanto esperar. Sin ese mensaje el usuario creeria que se envio.
      setError(extraerMensajeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <PublicShell
      titulo="Recuperar acceso"
      subtitulo="Ingresá tu cédula o correo y te enviamos un enlace para crear una contraseña nueva."
      error={error}
      pie={<LinkVolver>Volver a iniciar sesión</LinkVolver>}
    >
      {enviado ? (
        <div className="space-y-4">
          <div className="flex items-start gap-2 bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg">
            <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
            <span>{enviado}</span>
          </div>
          {/* Ruta para quien no tiene correo registrado: el enlace no le va a
              llegar nunca y esta pantalla no puede decírselo. El codigo
              offline de A3.3 es la salida, y se lo puede pasar un admin. */}
          <p className="text-sm text-slate-400">
            ¿No tenés correo registrado? Pedíle a un administrador que te genere un{' '}
            <Link to="/reset-codigo" className="text-primary-400 hover:text-primary-300">
              código de recuperación
            </Link>{' '}
            y usalo acá.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="identificador"
              className="block text-sm font-medium text-slate-300 mb-1"
            >
              Cédula o correo
            </label>
            <div className="relative">
              <Fingerprint
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                size={18}
              />
              <input
                id="identificador"
                name="identificador"
                // type="text" y no "email": el mismo motivo que en Login (A2).
                type="text"
                autoComplete="username"
                value={identificador}
                onChange={(e) => setIdentificador(e.target.value)}
                className="input-truck pl-10"
                placeholder="Ej: 1234567890 o usuario@celr.com"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-celr w-full flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : <Mail size={20} />}
            {loading ? 'Enviando...' : 'Enviar enlace'}
          </button>
        </form>
      )}
    </PublicShell>
  )
}

export default Recuperar
