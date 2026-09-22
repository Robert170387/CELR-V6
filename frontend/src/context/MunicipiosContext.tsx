import React, { createContext, useContext, useEffect, useState } from 'react'
import { municipiosAPI } from '@/api'
import type { Municipio } from '@/api'

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

  useEffect(() => {
    let activo = true
    municipiosAPI
      .listar()
      .then((data) => {
        if (activo) setMunicipios(data)
      })
      .catch(() => {
        // Catálogo no disponible: el selector funciona con lista vacía
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [])

  return (
    <MunicipiosContext.Provider value={{ municipios, cargando }}>{children}</MunicipiosContext.Provider>
  )
}

export const useMunicipios = () => useContext(MunicipiosContext)