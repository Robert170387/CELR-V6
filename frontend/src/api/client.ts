import axios from 'axios'

// En producción (Render static site) se apunta al backend con VITE_API_URL.
// En desarrollo cae a la ruta relativa, que Vite redirige vía proxy.
const baseURL = import.meta.env.VITE_API_URL || '/api/v1'

const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('celr_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('celr_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient
