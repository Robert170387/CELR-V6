from fastapi import APIRouter, Depends

from app.api.v1.deps import exigir_contrasena_actualizada
from app.api.v1.endpoints import (
    auth, viajes, gastos, liquidaciones, flypass,
    vehiculos, conductores, proveedores, ingresos, municipios, usuarios,
)

api_router = APIRouter()

# A4 — Enforcement del primer login: mientras debe_cambiar_contrasena=True,
# el usuario no entra a ningun endpoint de negocio. La dependencia existia
# desde S1/hardening en deps.py pero nunca se aplico, asi que el flag era
# decorativo.
PROTEGIDOS = [Depends(exigir_contrasena_actualizada)]

api_router.include_router(vehiculos.router, prefix="/api/v1", dependencies=PROTEGIDOS)
api_router.include_router(conductores.router, prefix="/api/v1", dependencies=PROTEGIDOS)
api_router.include_router(proveedores.router, prefix="/api/v1", dependencies=PROTEGIDOS)
api_router.include_router(viajes.router, prefix="/api/v1", dependencies=PROTEGIDOS)
api_router.include_router(gastos.router, prefix="/api/v1", dependencies=PROTEGIDOS)
api_router.include_router(liquidaciones.router, prefix="/api/v1", dependencies=PROTEGIDOS)
api_router.include_router(flypass.router, prefix="/api/v1", dependencies=PROTEGIDOS)
api_router.include_router(ingresos.router, prefix="/api/v1", dependencies=PROTEGIDOS)
# A3.2: el reset asistido es endpoint de negocio, asi que entra en PROTEGIDOS.
# Un usuario con debe_cambiar_contrasena=True no puede resetear a otro.
api_router.include_router(usuarios.router, prefix="/api/v1", dependencies=PROTEGIDOS)

# Sin proteccion, y el motivo importa:
# - auth: el usuario bloqueado debe poder llamar a /auth/me, /auth/refresh,
#   /auth/logout y /auth/cambio-contrasena. Si no, no hay forma de desbloquearse.
# - municipios: MunicipiosProvider se monta por encima de las rutas (App.tsx),
#   o sea tambien en /cambiar-contrasena. Protegerlo daria 403 -> el
#   interceptor redirige -> recarga infinita en la unica pantalla que
#   permite desbloquear. El catalogo DIVIPOLA no es dato sensible.
api_router.include_router(municipios.router, prefix="/api/v1")
api_router.include_router(auth.router, prefix="/api/v1")
