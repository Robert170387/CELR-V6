import apiClient from './client'

export interface Paginado {
  skip?: number
  limit?: number
}

export interface Municipio {
  id: number
  codigo_dane: string
  departamento: string
  municipio: string
}

export interface RespuestaLista<T> {
  data: T[]
  total: number
}

const leerTotal = (resp: any): number => {
  const header = resp?.headers?.['x-total-count']
  return header !== undefined && header !== null ? Number(header) : 0
}

const conTotal = <T,>(resp: any): RespuestaLista<T> => ({ data: resp.data as T[], total: leerTotal(resp) })

export const authAPI = {
  login: (correo: string, contrasena: string) => apiClient.post('/auth/login', { correo, contrasena }),
  getMe: () => apiClient.get('/auth/me'),
  cambioContrasena: (contrasenaActual: string, nuevaContrasena: string) =>
    apiClient.post('/auth/cambio-contrasena', {
      contrasena_actual: contrasenaActual,
      nueva_contrasena: nuevaContrasena,
    }),
}

export const viajesAPI = {
  listar: (activo = true, params?: Paginado) =>
    apiClient.get('/viajes', { params: { activo, ...params } }).then((r) => conTotal<any>(r)),
  crear: (data: any) => apiClient.post('/viajes', data),
  obtener: (id: number) => apiClient.get(`/viajes/${id}`),
  porConductor: (conductorId: number) =>
    apiClient.get(`/viajes/conductor/${conductorId}`).then((r) => conTotal<any>(r)),
  actualizar: (id: number, data: any) => apiClient.put(`/viajes/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/viajes/${id}`),
  // FASE A2 — Regla 4: bloqueos para finalizar la ODT
  bloqueosCierre: (id: number) => apiClient.get(`/viajes/${id}/bloqueos-cierre`).then((r) => r.data as BloqueosCierre),
}

export const vehiculosAPI = {
  listar: (params?: Paginado) => apiClient.get('/vehiculos', { params }).then((r) => conTotal<any>(r)),
  crear: (data: any) => apiClient.post('/vehiculos', data),
  obtener: (id: number) => apiClient.get(`/vehiculos/${id}`),
  actualizar: (id: number, data: any) => apiClient.put(`/vehiculos/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/vehiculos/${id}`),
}

export const conductoresAPI = {
  listar: (params?: Paginado) => apiClient.get('/conductores', { params }).then((r) => conTotal<any>(r)),
  crear: (data: any) => apiClient.post('/conductores', data),
  obtener: (id: number) => apiClient.get(`/conductores/${id}`),
  actualizar: (id: number, data: any) => apiClient.put(`/conductores/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/conductores/${id}`),
}

export const proveedoresAPI = {
  listar: (params?: Paginado) => apiClient.get('/proveedores', { params }).then((r) => conTotal<any>(r)),
  crear: (data: any) => apiClient.post('/proveedores', data),
  obtener: (id: number) => apiClient.get(`/proveedores/${id}`),
  actualizar: (id: number, data: any) => apiClient.put(`/proveedores/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/proveedores/${id}`),
}

export const ingresosAPI = {
  listar: (viajeId?: number, params?: Paginado) =>
    apiClient
      .get('/ingresos', {
        params: {
          ...(viajeId ? { viaje_id: viajeId } : {}),
          ...params,
        },
      })
      .then((r) => conTotal<any>(r)),
  crear: (data: any) => apiClient.post('/ingresos', data),
  obtener: (id: number) => apiClient.get(`/ingresos/${id}`),
  actualizar: (id: number, data: any) => apiClient.put(`/ingresos/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/ingresos/${id}`),
}

export const gastosAPI = {
  listar: (params?: Paginado) => apiClient.get('/gastos', { params }).then((r) => conTotal<any>(r)),
  porViaje: (viajeId: number) => apiClient.get(`/gastos/viaje/${viajeId}`),
  obtener: (id: number) => apiClient.get(`/gastos/${id}`),
  registrar: (data: any) => apiClient.post('/gastos', data),
  actualizar: (id: number, data: any) => apiClient.put(`/gastos/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/gastos/${id}`),
  scanReceipt: (file: File, viajeId: number | null, vehiculoId: number) => {
    const formData = new FormData()
    formData.append('file', file)
    if (viajeId) formData.append('viaje_id', String(viajeId))
    formData.append('vehiculo_id', String(vehiculoId))
    return apiClient.post('/gastos/scan-receipt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const liquidacionesAPI = {
  calcular: (viajeId: number) => apiClient.get(`/liquidaciones/calcular/${viajeId}`),
  cerrar: (viajeId: number, data: any) => apiClient.post(`/liquidaciones/cerrar/${viajeId}`, data),
  // FASE A2 — COMPENSADO_RC mensual del conductor
  compensado: (conductorId: number, periodoInicio: string, periodoFin: string) =>
    apiClient
      .get('/liquidaciones/compensado', {
        params: { conductor_id: conductorId, periodo_inicio: periodoInicio, periodo_fin: periodoFin },
      })
      .then((r) => r.data as CompensadoMensual),
}

export interface BloqueosCierre {
  viaje_id: number
  numero_odt: string
  cercable: boolean
  bloqueos: string[]
}

export interface CompensadoMensual {
  conductor_id: number
  periodo_inicio: string
  periodo_fin: string
  total_viajes: number
  viajes_nacionales: number
  viajes_urbanos: number
  comisiones_total: string
  retiros_tarjeta_anticipos: string
  odts_incluidas: number[]
}

export const municipiosAPI = {
  listar: () => apiClient.get('/municipios').then((r) => r.data as Municipio[]),
}
