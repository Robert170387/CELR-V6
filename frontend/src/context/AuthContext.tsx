import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import axios from 'axios'
import apiClient, {
  getAccessToken,
  getRefreshToken,
  clearSession,
  TOKEN_KEY,
  REFRESH_KEY,
} from '@/api/client'
import { authAPI } from '@/api'

interface User {
  id: number
  correo: string
  rol: string
  conductor_id?: number | null
  activo: boolean
  debe_cambiar_contrasena?: boolean
  ultimo_acceso?: string | null
}

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (correo: string, contrasena: string) => Promise<void>
  logout: () => void
  cambiarContrasena: (contrasenaActual: string, nuevaContrasena: string) => Promise<void>
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => getAccessToken())
  const [loading, setLoading] = useState(false)

  const limpiarSesion = useCallback(() => {
    clearSession()
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    const handleSessionExpired = () => {
      setToken(null)
      setUser(null)
    }
    window.addEventListener('celr:session-expired', handleSessionExpired)
    return () => window.removeEventListener('celr:session-expired', handleSessionExpired)
  }, [])

  useEffect(() => {
    const restoreSession = async () => {
      if (!token) return
      try {
        const response = await apiClient.get('/auth/me')
        setUser(response.data)
      } catch {
        // El interceptor resuelve los 401 con /auth/refresh; si no pudo,
        // ya estás deslogueado en la UI.
        limpiarSesion()
      }
    }
    restoreSession()
  }, [token, limpiarSesion])

  const login = useCallback(async (correo: string, contrasena: string) => {
    setLoading(true)
    try {
      const response = await axios.post('/api/v1/auth/login', { correo, contrasena })
      const { access_token, refresh_token } = response.data
      localStorage.setItem(TOKEN_KEY, access_token)
      if (refresh_token) {
        localStorage.setItem(REFRESH_KEY, refresh_token)
      }
      setToken(access_token)
      const me = await apiClient.get('/auth/me')
      setUser(me.data)
    } finally {
      setLoading(false)
    }
  }, [])

  const cambiarContrasena = useCallback(async (contrasenaActual: string, nuevaContrasena: string) => {
    const response = await authAPI.cambioContrasena(contrasenaActual, nuevaContrasena)
    const { access_token, refresh_token } = response.data
    localStorage.setItem(TOKEN_KEY, access_token)
    if (refresh_token) {
      localStorage.setItem(REFRESH_KEY, refresh_token)
    }
    setToken(access_token)
    const me = await apiClient.get('/auth/me')
    setUser(me.data)
  }, [])

  const logout = useCallback(() => {
    const refresh = getRefreshToken()
    if (refresh) {
      void apiClient
        .post('/auth/logout', { refresh_token: refresh })
        .catch(() => undefined)
        .finally(limpiarSesion)
    } else {
      limpiarSesion()
    }
  }, [limpiarSesion])

  return (
    <AuthContext.Provider
      value={{ user, token, isAuthenticated: !!token, login, logout, cambiarContrasena, loading }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return context
}