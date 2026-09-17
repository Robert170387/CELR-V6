from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_db
from app.api.v1.api import api_router

app = FastAPI(
    title="CELR v6 API",
    description="API de backend para gestión de flota de carga pesada CELR",
    version="1.0.0"
)

# Configurar CORS para permitir que el frontend se comunique con esta API.
# Los orígenes se definen por variable de entorno (CORS_ORIGINS) para soportar
# el despliegue en Render sin recompilar ni cambiar el código.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    """
    Endpoint de diagnóstico para verificar que la API está viva
    y conectada a la base de datos PostgreSQL.
    """
    try:
        # Intentar ejecutar una consulta simple para verificar la conexión
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # Si falla la conexión, devolver un error 500 con el detalle
        raise HTTPException(
            status_code=500, 
            detail=f"Database connection failed: {str(e)}"
        )
