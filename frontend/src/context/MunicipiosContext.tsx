import React, { createContext, useContext, useEffect, useState } from 'react'
import { municipiosAPI } from '@/api'
import type { Municipio } from '@/api'
import { useAuth } from '@/context/AuthContext'

interface MunicipiosContextValue {
  municipios: Municipio[]
  cargando: boolean
}

const MunicipiosContext = createContext<MunicipiosContextValue>({
  municipios: [],
  cargando: true,
})

export const MunicipiosProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [municipios, setMunicipios] = useState<Municipio[]>([])
  const [cargando, setCargando] = useState(true)
  const { token } = useAuth()

  useEffect(() => {
    let activo = true
    if (!token) {
      setMunicipios([])
      setCargando(false)
      return () => {
        activo = false
      }
    }

    setCargando(true)
    municipiosAPI
      .listar()
      .then((data) => {
        if (activo) setMunicipios(data)
      })
      .catch(() => {
        // Catálogo no disponible: el selector funciona con lista vacía
        if (activo) setMunicipios([])
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [token])

  return (
    <MunicipiosContext.Provider value={{ municipios, cargando }}>{children}</MunicipiosContext.Provider>
  )
}

export const useMunicipios = () => useContext(MunicipiosContext)