import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import axios from 'axios'
import apiClient from '@/api/client'

interface User {
  id: number
  correo: string
  rol: string
  conductor_id?: number | null
  activo: boolean
}

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (correo: string, contrasena: string) => Promise<void>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('celr_token'))
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const restoreSession = async () => {
      if (!token) return
      try {
        const response = await apiClient.get('/auth/me')
        setUser(response.data)
      } catch (error) {
        localStorage.removeItem('celr_token')
        setToken(null)
        setUser(null)
      }
    }
    restoreSession()
  }, [token])

  const login = useCallback(async (correo: string, contrasena: string) => {
    setLoading(true)
    try {
      const response = await axios.post('/api/v1/auth/login', { correo, contrasena })
      const { access_token } = response.data
      localStorage.setItem('celr_token', access_token)
      setToken(access_token)
      const me = await apiClient.get('/auth/me')
      setUser(me.data)
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('celr_token')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated: !!token, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return context
}
