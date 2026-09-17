# syntax=docker/dockerfile:1

FROM python:3.11-slim

# Salida sin buffer y sin bytecode para contenedores
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # OCR: binario de Tesseract + idioma español, y libgl1 requerido por Pillow
    TESSERACT_CMD=/usr/bin/tesseract \
    OCR_ENGINE=tesseract \
    OCR_LANGS=spa+eng

# Dependencias del sistema operativo requeridas por el OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
        libgl1 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache de capas: primero dependencias, luego el código
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Usuario sin privilegios
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render inyecta $PORT (por defecto 10000); localmente se usa 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
