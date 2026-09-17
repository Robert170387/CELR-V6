from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, viajes, gastos, liquidaciones,
    vehiculos, conductores, proveedores, ingresos,
)

api_router = APIRouter()
api_router.include_router(vehiculos.router, prefix="/api/v1")
api_router.include_router(conductores.router, prefix="/api/v1")
api_router.include_router(proveedores.router, prefix="/api/v1")
api_router.include_router(viajes.router, prefix="/api/v1")
api_router.include_router(gastos.router, prefix="/api/v1")
api_router.include_router(liquidaciones.router, prefix="/api/v1")
api_router.include_router(ingresos.router, prefix="/api/v1")
api_router.include_router(auth.router, prefix="/api/v1")
