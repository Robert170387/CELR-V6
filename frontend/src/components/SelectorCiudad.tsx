import React, { useEffect, useMemo, useState } from 'react'
import { useMunicipios } from '@/context/MunicipiosContext'

interface SelectorCiudadProps {
  value: string
  onChange: (municipioId: string, texto: string) => void
  labelDepartamento?: string
  labelMunicipio?: string
}

const SelectorCiudad: React.FC<SelectorCiudadProps> = ({
  value,
  onChange,
  labelDepartamento = 'Departamento',
  labelMunicipio = 'Municipio',
}) => {
  const { municipios } = useMunicipios()
  const [departamentoSel, setDepartamentoSel] = useState('')

  const departamentos = useMemo(() => {
    const unicos = new Set<string>()
    for (const m of municipios) unicos.add(m.departamento)
    return Array.from(unicos).sort((a, b) => a.localeCompare(b, 'es'))
  }, [municipios])

  const municipiosDelDepartamento = useMemo(() => {
    return municipios
      .filter((m) => m.departamento === departamentoSel)
      .sort((a, b) => a.municipio.localeCompare(b.municipio, 'es'))
  }, [municipios, departamentoSel])

  useEffect(() => {
    if (!value) {
      setDepartamentoSel('')
      return
    }
    const mun = municipios.find((m) => String(m.id) === String(value))
    if (mun) setDepartamentoSel(mun.departamento)
  }, [value, municipios])

  const seleccionarMunicipio = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    const mun = municipios.find((m) => String(m.id) === id)
    onChange(id, mun ? `${mun.municipio} (${mun.departamento})` : '')
  }

  return (
    <div className="flex flex-col sm:flex-row gap-2">
      <div className="flex-1 min-w-0">
        <label className="block text-xs text-slate-400 mb-1">{labelDepartamento}</label>
        <select
          className="input-truck"
          value={departamentoSel}
          onChange={(e) => {
            setDepartamentoSel(e.target.value)
            onChange('', '')
          }}
        >
          <option value="">Selecciona un departamento</option>
          {departamentos.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
      <div className="flex-1 min-w-0">
        <label className="block text-xs text-slate-400 mb-1">{labelMunicipio}</label>
        <select className="input-truck" value={value} onChange={seleccionarMunicipio}>
          <option value="">Selecciona un municipio</option>
          {municipiosDelDepartamento.map((m) => (
            <option key={m.id} value={m.id}>
              {m.municipio}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

export default SelectorCiudad