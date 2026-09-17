export const esErrorDeRed = (err: any): boolean => !err?.response

export const extraerMensajeError = (err: any): string => {
  const status = err?.response?.status
  const detail = err?.response?.data?.detail

  if (!err?.response) {
    return 'No se pudo conectar con el servidor. Verifica tu conexión.'
  }
  if (Array.isArray(detail)) {
    return detail.map((d: any) => d?.msg || String(d)).join(', ')
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  switch (status) {
    case 400:
      return 'Solicitud inválida (400)'
    case 401:
      return 'Sesión expirada. Vuelve a iniciar sesión.'
    case 404:
      return 'El recurso especificado no existe (404)'
    case 403:
      return 'No tienes permisos para realizar esta acción (403)'
    case 409:
      return 'Conflicto: el registro ya existe (409)'
    case 422:
      return 'Datos inválidos en el formulario (422)'
    case 500:
      return 'Error interno del servidor (500)'
    default:
      return 'Ocurrió un error inesperado'
  }
}

export const formatearMoneda = (valor: number | string | null | undefined): string =>
  `$${Number(valor || 0).toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`