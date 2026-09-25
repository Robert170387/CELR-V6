import React from 'react'
import { Link } from 'react-router-dom'
import { Truck, AlertCircle } from 'lucide-react'

// A5.4 — Las tres pantallas de recuperacion son publicas y comparten la misma
// envoltura: fondo centrado, bloque de marca y card. Se extrae para no
// duplicar el chrome en tres archivos (el repo si tiene componentes
// compartidos en components/, aunque los modales si se inlinean).
const PublicShell: React.FC<{
  titulo: string
  subtitulo: string
  children: React.ReactNode
  /** Aviso de error. Se pinta arriba del contenido, igual que en Login. */
  error?: string
  pie?: React.ReactNode
}> = ({ titulo, subtitulo, children, error, pie }) => (
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
        <h2 className="text-xl font-semibold text-white mb-2">{titulo}</h2>
        <p className="text-sm text-slate-400 mb-6">{subtitulo}</p>

        {error && (
          <div className="flex items-start gap-2 bg-danger-500/10 border border-danger-500/30 text-danger-500 px-4 py-3 rounded-lg mb-4">
            <AlertCircle size={18} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {children}

        {pie && <div className="mt-6 pt-4 border-t border-slate-700 text-center">{pie}</div>}
      </div>
    </div>
  </div>
)

export const LinkVolver: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Link to="/login" className="text-sm text-primary-400 hover:text-primary-300 transition-colors">
    {children}
  </Link>
)

export default PublicShell
