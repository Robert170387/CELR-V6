import apiClient from './client'

export const authAPI = {
  login: (correo: string, contrasena: string) => apiClient.post('/auth/login', { correo, contrasena }),
  getMe: () => apiClient.get('/auth/me'),
}

export const viajesAPI = {
  listar: (activo = true) => apiClient.get('/viajes', { params: { activo } }),
  crear: (data: any) => apiClient.post('/viajes', data),
  obtener: (id: number) => apiClient.get(`/viajes/${id}`),
  porConductor: (conductorId: number) => apiClient.get(`/viajes/conductor/${conductorId}`),
  actualizar: (id: number, data: any) => apiClient.put(`/viajes/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/viajes/${id}`),
}

export const vehiculosAPI = {
  listar: () => apiClient.get('/vehiculos'),
  crear: (data: any) => apiClient.post('/vehiculos', data),
  obtener: (id: number) => apiClient.get(`/vehiculos/${id}`),
}

export const conductoresAPI = {
  listar: () => apiClient.get('/conductores'),
  crear: (data: any) => apiClient.post('/conductores', data),
  obtener: (id: number) => apiClient.get(`/conductores/${id}`),
}

export const proveedoresAPI = {
  listar: () => apiClient.get('/proveedores'),
  crear: (data: any) => apiClient.post('/proveedores', data),
  obtener: (id: number) => apiClient.get(`/proveedores/${id}`),
}

export const gastosAPI = {
  listar: () => apiClient.get('/gastos'),
  porViaje: (viajeId: number) => apiClient.get(`/gastos/viaje/${viajeId}`),
  obtener: (id: number) => apiClient.get(`/gastos/${id}`),
  registrar: (data: any) => apiClient.post('/gastos', data),
  actualizar: (id: number, data: any) => apiClient.put(`/gastos/${id}`, data),
  eliminar: (id: number) => apiClient.delete(`/gastos/${id}`),
  scanReceipt: (file: File, viajeId: number, vehiculoId: number) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('viaje_id', String(viajeId))
    formData.append('vehiculo_id', String(vehiculoId))
    return apiClient.post('/gastos/scan-receipt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const liquidacionesAPI = {
  calcular: (viajeId: number) => apiClient.get(`/liquidaciones/calcular/${viajeId}`),
  cerrar: (viajeId: number, data: any) => apiClient.post(`/liquidaciones/cerrar/${viajeId}`, data),
}
