from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # Porcentaje de comisión por defecto para liquidaciones de conductores
    COMISION_CONDUCTOR_DEFAULT_PORCENTAJE: float = 10.0

    # Orígenes permitidos por CORS (lista separada por comas)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Origen del frontend, para armar enlaces de recuperacion de contrasena.
    # Es configuracion de despliegue (variable de entorno en Render), no de
    # negocio: por eso vive en Settings y no en configuracion_sistema.
    FRONTEND_URL: str = "http://localhost:5174"

    # OCR / lectura de comprobantes
    OCR_ENGINE: str = "tesseract"
    OCR_LANGS: str = "spa+eng"
    OCR_MIN_CONFIDENCE: float = 40.0
    OCR_MAX_FILE_MB: int = 8
    TESSERACT_CMD: Optional[str] = None
    GOOGLE_VISION_CREDENTIALS: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Aiven entrega el esquema como "postgres://"; SQLAlchemy 2.x exige "postgresql://"
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql://", 1)
        return value

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
