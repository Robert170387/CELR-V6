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
  // A2 (D1): `identificador` acepta cedula o correo. El backend mantiene
  // `correo` como alias legacy, pero el frontend envia siempre el campo nuevo.
  login: (identificador: string, contrasena: string) =>
    apiClient.post('/auth/login', { identificador, contrasena }),
  getMe: () => apiClient.get('/auth/me'),
  cambioContrasena: (contrasenaActual: string, nuevaContrasena: string) =>
    apiClient.post('/auth/cambio-contrasena', {
      contrasena_actual: contrasenaActual,
      nueva_contrasena: nuevaContrasena,
    }),
}

export interface ViajeCandidato {
  id: number
  numero_odt: string
  vehiculo_id: number
  fecha_salida: string
  fecha_llegada: string | null
}

export const viajesAPI = {
  listar: (activo = true, params?: Paginado) =>
    apiClient.get('/viajes', { params: { activo, ...params } }).then((r) => conTotal<any>(r)),
  crear: (data: any) => apiClient.post('/viajes', data),
  obtener: (id: number) => apiClient.get(`/viajes/${id}`),
  porConductor: (conductorId: number) =>
    apiClient.get(`/viajes/conductor/${conductorId}`).then((r) => conTotal<any>(r)),
  porVehiculo: (vehiculoId: number) =>
    apiClient.get(`/viajes/vehiculo/${vehiculoId}`).then((r) => r.data as ViajeCandidato[]),
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
  // FASE B2 — cierre mensual COMPENSADO_RC persistido
  cierreMensualCrear: (data: any) =>
    apiClient.post('/liquidaciones/cierre-mensual', data).then((r) => r.data as CierreMensual),
  cierreMensualObtener: (conductorId: number, periodoYm: string) =>
    apiClient
      .get('/liquidaciones/cierre-mensual', {
        params: { conductor_id: conductorId, periodo_ym: periodoYm },
      })
      .then((r) => r.data as CierreMensual),
  cierresMensuales: (conductorId: number) =>
    apiClient
      .get('/liquidaciones/cierres-mensuales', { params: { conductor_id: conductorId } })
      .then((r) => r.data as CierreMensual[]),
  reabrir: (id: number) => apiClient.post(`/liquidaciones/${id}/reabrir`),
  cancelar: (id: number) => apiClient.post(`/liquidaciones/${id}/cancelar`),
}

export interface BloqueosCierre {
  viaje_id: number
  numero_odt: string
  cercable: boolean
  bloqueos: string[]
}

export interface FlypassListItem {
  id: number
  fecha_transaccion: string
  valor: string
  num_transaccion_flypass: string
  nombre_peaje: string | null
  vehiculo_id: number
  placa: string | null
  viaje_id: number | null
  gasto_id: number | null
  legalizado_en_gastos: boolean
  estado: string
}

export interface FlypassUpdateBody {
  viaje_id?: number | null
  estado?: string
}

export interface FlypassListResponse {
  data: FlypassListItem[]
  total: number
}

export interface FlypassListParams {
  fecha_desde?: string
  fecha_hasta?: string
  placa?: string
  sin_odt?: boolean
  sin_gasto?: boolean
  skip?: number
  limit?: number
}

export interface FlypassImportReporte {
  insertados: number
  duplicados: number
  sin_placa: number
  ambiguos: number
  creados_gastos: number
  matcheados_gastos: number
  sin_odt: number
  errores: Array<Record<string, unknown>>
}

export const flypassAPI = {
  listar: (params: FlypassListParams = {}) =>
    apiClient.get('/flypass', { params }).then((r) => r.data as FlypassListResponse),
  importar: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient
      .post('/flypass/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data as FlypassImportReporte)
  },
  editarFlypass: (id: number, body: FlypassUpdateBody) =>
    apiClient.patch(`/flypass/${id}`, body).then((r) => r.data as FlypassListItem),
}

export interface UsuarioListItem {
  id: number
  cedula: string | null
  correo: string | null
  rol: string
  conductor_id: number | null
  activo: boolean
  debe_cambiar_contrasena: boolean
  ultimo_acceso?: string | null
  creado_en: string
}

export interface UsuarioTemporalResponse {
  usuario_id: number
  cedula?: string | null
  correo?: string | null
  rol?: string
  contrasena_temporal: string
  mensaje: string
  debe_cambiar_contrasena: boolean
}

export interface ResetCodigoResponse {
  usuario_id: number
  correo: string | null
  codigo: string
  expira_en: string
  mensaje: string
}

export interface UsuarioAccionResponse {
  usuario_id: number
  activo: boolean
  rol: string
  era_ultimo_admin: boolean
  mensaje: string
}

// A5.3 — Consume el CRUD de A5.1/A5.2. El listado usa conTotal(), que lee el
// total del header X-Total-Count; hay que pasararle el tipo explicito porque su
// parametro es `any` y TypeScript no puede inferirlo desde ahi.
export const usuariosAPI = {
  listar: (params?: { skip?: number; limit?: number; activo?: boolean; rol?: string }) =>
    apiClient
      .get<UsuarioListItem[]>('/usuarios', { params })
      .then((r) => conTotal<UsuarioListItem>(r)),
  crear: (data: {
    cedula: string
    correo?: string | null
    rol: string
    conductor_id?: number | null
  }) => apiClient.post<UsuarioTemporalResponse>('/usuarios', data).then((r) => r.data),
  actualizar: (
    id: number,
    data: { correo?: string | null; cedula?: string | null; conductor_id?: number | null }
  ) => apiClient.put<UsuarioListItem>(`/usuarios/${id}`, data).then((r) => r.data),
  activar: (id: number) =>
    apiClient.post<UsuarioAccionResponse>(`/usuarios/${id}/activar`).then((r) => r.data),
  desactivar: (id: number, confirmacion: string, motivo?: string) =>
    apiClient
      .post<UsuarioAccionResponse>(`/usuarios/${id}/desactivar`, { confirmacion, motivo })
      .then((r) => r.data),
  degradar: (id: number, nuevo_rol: string, confirmacion: string, motivo?: string) =>
    apiClient
      .post<UsuarioAccionResponse>(`/usuarios/${id}/degradar`, {
        confirmacion,
        nuevo_rol: nuevo_rol,
        motivo,
      })
      .then((r) => r.data),
  resetPassword: (id: number) =>
    apiClient
      .post<UsuarioTemporalResponse>(`/usuarios/${id}/reset-password`)
      .then((r) => r.data),
  resetCodigo: (id: number) =>
    apiClient
      .post<ResetCodigoResponse>(`/usuarios/${id}/reset-codigo`)
      .then((r) => r.data),
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

// FASE B2 — cierre mensual COMPENSADO_RC persistido en liquidaciones_conductores
export interface CierreMensual {
  id: number
  conductor_id: number
  vehiculo_id: number | null
  periodo_inicio: string
  periodo_fin: string
  periodo_ym: string
  es_cierre_mensual: boolean
  estado: string
  comision_flete: string
  comisiones_total: string
  salario_basico: string
  auxilio_transporte: string
  papeleria: string
  descuento_salud_pension: string
  retiros_tarjeta_anticipos: string
  viajes_nacionales: number
  viajes_urbanos: number
  total_viajes: number
  bonificaciones: string
  viaticos_reconocidos: string
  otros_haberes: string
  anticipos_entregados: string
  gastos_a_cargo_conductor: string
  prestamos: string
  otros_descuentos: string
  total_haberes: string
  total_descuentos: string
  saldo_neto: string
  viajes_ids: number[] | null
  observaciones: string | null
  creado_por: number | null
  aprobado_por: number | null
}

export const municipiosAPI = {
  listar: () => apiClient.get('/municipios').then((r) => r.data as Municipio[]),
}
