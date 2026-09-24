export const ROLES = ['admin', 'operador', 'contador', 'supervisor', 'cliente', 'conductor'] as const

export type Rol = (typeof ROLES)[number]

const ROLES_FINANZAS = ['admin', 'operador', 'contador', 'supervisor'] as const
const ROLES_RECURSOS = ['admin', 'operador', 'supervisor'] as const

const ACCESO_POR_MODULO: Record<string, readonly string[]> = {
  '/scan': ['admin', 'operador', 'supervisor'],
  '/liquidaciones': ROLES_FINANZAS,
  '/flypass': ROLES_FINANZAS,
  '/ingresos': ROLES_FINANZAS,
  '/maestras': ROLES_RECURSOS,
}

export const puedeAccederModulo = (path: string, rol?: string | null): boolean => {
  const permitidos = ACCESO_POR_MODULO[path]
  if (!permitidos) return true
  return !!rol && permitidos.includes(rol)
}

export const esRolFinanzas = (rol?: string | null): boolean => !!rol && ROLES_FINANZAS.includes(rol as any)
export const esRolRecursos = (rol?: string | null): boolean => !!rol && ROLES_RECURSOS.includes(rol as any)

export const menuPermitido = <T extends { path: string }>(items: T[], rol?: string | null): T[] =>
  items.filter((item) => puedeAccederModulo(item.path, rol))