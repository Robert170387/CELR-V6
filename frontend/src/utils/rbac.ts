export const ROLES = ['admin', 'operador', 'contador', 'supervisor', 'cliente', 'conductor'] as const

export type Rol = (typeof ROLES)[number]

const ACCESO_POR_MODULO: Record<string, readonly string[]> = {
  '/scan': ['admin', 'operador', 'supervisor'],
  '/liquidaciones': ['admin', 'operador', 'contador', 'supervisor'],
  '/maestras': ['admin'],
}

export const puedeAccederModulo = (path: string, rol?: string | null): boolean => {
  const permitidos = ACCESO_POR_MODULO[path]
  if (!permitidos) return true
  return !!rol && permitidos.includes(rol)
}

export const menuPermitido = <T extends { path: string }>(items: T[], rol?: string | null): T[] =>
  items.filter((item) => puedeAccederModulo(item.path, rol))