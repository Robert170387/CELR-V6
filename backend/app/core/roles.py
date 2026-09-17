from enum import Enum


class RolUsuario(str, Enum):
    """ENUM canonico de roles validos en la base de datos."""

    ADMIN = "admin"
    OPERADOR = "operador"
    CONTADOR = "contador"
    SUPERVISOR = "supervisor"
    CLIENTE = "cliente"
    CONDUCTOR = "conductor"


ROLES_VALIDOS = tuple(rol.value for rol in RolUsuario)

# Politicas de acceso por modulo (aplicadas en el backend via RoleChecker)
ROLES_ESCRITURA_MAESTROS = tuple(
    rol.value for rol in RolUsuario if rol is not RolUsuario.CONDUCTOR
)
ROLES_LIQUIDACIONES = (
    RolUsuario.ADMIN.value,
    RolUsuario.OPERADOR.value,
    RolUsuario.CONTADOR.value,
    RolUsuario.SUPERVISOR.value,
)
ROLES_INGRESOS = ROLES_LIQUIDACIONES

# Fragmento SQL para el CHECK constraint del modelo Usuario
SQL_CHECK_ROL = "rol IN (" + ", ".join(f"'{rol}'" for rol in ROLES_VALIDOS) + ")"
