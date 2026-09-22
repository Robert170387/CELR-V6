import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'

// En producción (Render static site) se apunta al backend con VITE_API_URL.
// En desarrollo cae a la ruta relativa, que Vite redirige vía proxy.
const baseURL = import.meta.env.VITE_API_URL || '/api/v1'

export const TOKEN_KEY = 'celr_token'
export const REFRESH_KEY = 'celr_refresh'

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  window.dispatchEvent(new CustomEvent('celr:session-expired'))
}

interface CelrRequestConfig extends AxiosRequestConfig {
  _retried?: boolean
  _celrOffline?: boolean
  _celrTxId?: number
}

const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshingPromise: Promise<string | null> | null = null

async function tryRefresh(): Promise<string | null> {
  const current = getRefreshToken()
  if (!current) return null
  if (!refreshingPromise) {
    refreshingPromise = axios
      .post(`${baseURL}/auth/refresh`, { refresh_token: current })
      .then((response) => {
        const { access_token, refresh_token } = response.data
        localStorage.setItem(TOKEN_KEY, access_token)
        if (refresh_token) {
          localStorage.setItem(REFRESH_KEY, refresh_token)
        } else {
          localStorage.removeItem(REFRESH_KEY)
        }
        return access_token as string
      })
      .catch(() => null)
      .finally(() => {
        refreshingPromise = null
      })
  }
  return refreshingPromise
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = (error.config || {}) as CelrRequestConfig
    const status = error.response?.status
    const url = original?.url || ''
    const esLlamadaAuth =
      url.includes('/auth/login') || url.includes('/auth/refresh') || url.includes('/auth/logout')

    if (status === 401 && original && !original._retried && !esLlamadaAuth) {
      original._retried = true
      const newToken = await tryRefresh()
      if (newToken) {
        // Reintenta la petición original con el token renovado (una sola vez).
        original.headers = {
          ...(original.headers as Record<string, string>),
          Authorization: `Bearer ${newToken}`,
        }
        return apiClient(original as InternalAxiosRequestConfig)
      }
      // El refresh falló de forma definitiva: la sesión ya no es recuperable.
      clearSession()
      if (original._celrOffline) {
        // La transacción de la cola offline queda esperando autenticación:
        // NO se descarta ni se redirige; la UI muestra el contador "requieren iniciar sesión".
        if (original._celrTxId) {
          const { setTransactionEstado } = await import('@/utils/offlineStore')
          await setTransactionEstado(original._celrTxId, 'pending_auth')
        }
        window.dispatchEvent(new Event('celr:queued'))
        return Promise.reject(error)
      }
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
    return Promise.reject(error)
  }
)

export default apiClient