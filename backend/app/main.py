import logging

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_db
from app.api.v1.api import api_router

# Sin esto, el root logger queda en WARNING (default de Python) y NINGUN
# logger.info del proyecto se emite. LogEmailBackend imprime el enlace de
# recuperacion a proposito para que el flujo se pueda probar en local, y ese
# log era invisible: /recuperar no producia nada que leer. Es el mismo
# patron de fallo silencioso de A5.3, con el logger presente pero nunca
# configurado.
#
# En produccion baja a WARNING a proposito. Hoy ningun logger.info filtra un
# secreto (los de usuarios.py solo traen usuario_id y rol, y la traza de
# auditoria va a la tabla, no al log), asi que INFO seria inofensivo. El
# guard existe para que un logger.info futuro con una credencial dentro no
# empiece a filtrar a produccion sin que nadie lo note.
# ENVIRONMENT lo pone render.yaml (production) y el default de config.py es
# development, asi que el bare metal y el docker local quedan en INFO.
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT != "production" else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

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
