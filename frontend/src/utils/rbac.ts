export const ROLES = ['admin', 'operador', 'contador', 'supervisor', 'cliente', 'conductor'] as const

export type Rol = (typeof ROLES)[number]

const ROLES_FINANZAS = ['admin', 'operador', 'contador', 'supervisor'] as const
const ROLES_RECURSOS = ['admin', 'operador', 'supervisor'] as const

// A5.3 — Refleja ROLES_RESET_PERMITIDOS del backend (endpoints/usuarios.py).
// NO reutilizar esRolRecursos: esa es [admin, operador, supervisor] y
// excluye al contador, que en el backend SI puede entrar. Usar la constante
// equivocada aca daria una pantalla visible para un rol que el backend
// rechaza, o al reves.
export const ROLES_GESTION_USUARIOS = ['admin', 'operador', 'contador', 'supervisor'] as const

const ACCESO_POR_MODULO: Record<string, readonly string[]> = {
  '/scan': ['admin', 'operador', 'supervisor'],
  '/liquidaciones': ROLES_FINANZAS,
  '/flypass': ROLES_FINANZAS,
  '/ingresos': ROLES_FINANZAS,
  '/maestras': ROLES_RECURSOS,
  '/gestion-usuarios': ROLES_GESTION_USUARIOS,
}

export const puedeAccederModulo = (path: string, rol?: string | null): boolean => {
  const permitidos = ACCESO_POR_MODULO[path]
  if (!permitidos) return true
  return !!rol && permitidos.includes(rol)
}

export const esRolFinanzas = (rol?: string | null): boolean => !!rol && ROLES_FINANZAS.includes(rol as any)
export const esRolRecursos = (rol?: string | null): boolean => !!rol && ROLES_RECURSOS.includes(rol as any)
export const esRolGestionUsuarios = (rol?: string | null): boolean =>
  !!rol && ROLES_GESTION_USUARIOS.includes(rol as any)

export const menuPermitido = <T extends { path: string }>(items: T[], rol?: string | null): T[] =>
  items.filter((item) => puedeAccederModulo(item.path, rol))