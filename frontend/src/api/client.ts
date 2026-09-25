import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { setTransactionEstado } from '@/utils/offlineStore'

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
    // A5.4: `/auth/reset-password` y `/auth/reset-codigo` devuelven 401
    // cuando el token o el codigo es invalido, NO cuando la sesion expira.
    // Sin esta excepcion el 401 dispara un refresh que en una pantalla publica
    // no puede tener exito (no hay refresh token), cae en el refresh fallido y
    // el usuario que llega con un enlace vencido es expulsado a /login sin
    // ver jamas "Token invalido o expirado". Reintentar un 401 de token no
    // puede funcionar nunca, asi que excluirlo es lo correcto y no una
    // comodidad. `/auth/forgot-password` no se excluye: solo devuelve 200 o 429.
    const esLlamadaAuth =
      url.includes('/auth/login') ||
      url.includes('/auth/refresh') ||
      url.includes('/auth/logout') ||
      url.includes('/auth/reset-password') ||
      url.includes('/auth/reset-codigo')

    // A4 — Enforcement del primer login. El backend responde 403 con este
    // header mientras el usuario debe cambiar su contrasena. Actua como
    // backstop del guard de ruta: durante la hidratacion (user=null hasta
    // que /auth/me resuelve) el guard todavia no bloquea, pero el backend
    // ya responde 403 y estas llamadas son las que disparan la redireccion.
    // El header evita depender del texto del mensaje.
    if (status === 403 && error.response?.headers?.['x-celr-requiere-cambio'] === 'true') {
      // startsWith y no includes: una query string que contenga el path no
      // debe disparar la redireccion. Si ya estamos en la pantalla de cambio,
      // no recargar (seria un loop: 403 -> redirect -> recarga -> 403).
      if (!window.location.pathname.startsWith('/cambiar-contrasena')) {
        window.location.href = '/cambiar-contrasena'
      }
      return Promise.reject(error)
    }

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