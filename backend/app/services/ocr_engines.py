"""Motores OCR intercambiables para CELR v6.

Motor por defecto: Tesseract (local, sin red, sin claves).
Adaptador de nube: Google Cloud Vision (opt-in con OCR_ENGINE=google + credenciales).

Todos los motores fallan de forma controlada: si falta el binario, el paquete o
las credenciales, `extract()` devuelve un `OcrResult` con `error` en lugar de
lanzar una excepción. Así el endpoint nunca responde 500.
"""

import io
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Type

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    text: str = ""
    confidence: float = 0.0
    engine: str = "none"
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class BaseOcrEngine:
    name = "base"

    def is_available(self) -> bool:
        return False

    def extract(self, image_bytes: bytes) -> OcrResult:
        raise NotImplementedError


class TesseractEngine(BaseOcrEngine):
    """OCR local con Tesseract. Requiere el binario del sistema y el idioma 'spa'."""

    name = "tesseract"

    def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except Exception:
            return False
        return True

    def _configure(self) -> None:
        import pytesseract

        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    def _preprocess(self, image_bytes: bytes):
        from PIL import Image, ImageOps

        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")

        gray = ImageOps.grayscale(image)

        width, height = gray.size
        if max(width, height) < 1000:
            factor = min(3, max(2, 1200 // max(width, height) + 1))
            gray = gray.resize((width * factor, height * factor))

        return ImageOps.autocontrast(gray)

    def _reconstruct_text(self, data: Dict) -> str:
        lines: Dict[tuple, list] = {}
        for i, word in enumerate(data.get("text", [])):
            word = (word or "").strip()
            if not word:
                continue
            key = (
                data.get("block_num", [0] * (i + 1))[i],
                data.get("par_num", [0] * (i + 1))[i],
                data.get("line_num", [0] * (i + 1))[i],
            )
            lines.setdefault(key, []).append(word)
        return "\n".join(" ".join(words) for words in lines.values())

    def extract(self, image_bytes: bytes) -> OcrResult:
        if not self.is_available():
            return OcrResult(
                engine=self.name,
                error="pytesseract/Pillow no instalados (pip install pytesseract Pillow)",
            )

        try:
            import pytesseract
            from pytesseract import Output

            self._configure()
            image = self._preprocess(image_bytes)
            data = pytesseract.image_to_data(
                image,
                lang=settings.OCR_LANGS,
                config="--oem 3 --psm 6",
                output_type=Output.DICT,
            )

            confidences = []
            for conf in data.get("conf", []):
                try:
                    value = float(conf)
                except (TypeError, ValueError):
                    continue
                if value >= 0:
                    confidences.append(value)

            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            return OcrResult(
                text=self._reconstruct_text(data),
                confidence=confidence,
                engine=self.name,
            )
        except Exception as exc:  # TesseractNotFoundError, idioma ausente, imagen inválida...
            logger.warning("OCR Tesseract no disponible: %s", exc)
            return OcrResult(engine=self.name, error=str(exc))


class GoogleVisionEngine(BaseOcrEngine):
    """Adaptador opcional a Google Cloud Vision.

    Se activa con OCR_ENGINE=google y GOOGLE_VISION_CREDENTIALS apuntando al JSON
    de la cuenta de servicio (o GOOGLE_APPLICATION_CREDENTIALS en el entorno).
    """

    name = "google"

    def is_available(self) -> bool:
        try:
            from google.cloud import vision  # noqa: F401
        except Exception:
            return False
        return bool(settings.GOOGLE_VISION_CREDENTIALS or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))

    def extract(self, image_bytes: bytes) -> OcrResult:
        if not self.is_available():
            return OcrResult(
                engine=self.name,
                error="google-cloud-vision no instalado o sin credenciales configuradas",
            )

        try:
            if settings.GOOGLE_VISION_CREDENTIALS and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_VISION_CREDENTIALS

            from google.cloud import vision

            client = vision.ImageAnnotatorClient()
            image = vision.Image(content=image_bytes)
            response = client.document_text_detection(image=image)

            if response.error.message:
                return OcrResult(engine=self.name, error=response.error.message)

            text = response.full_text_annotation.text if response.full_text_annotation else ""
            return OcrResult(text=text, confidence=self._mean_confidence(response), engine=self.name)
        except Exception as exc:
            logger.warning("OCR Google Vision falló: %s", exc)
            return OcrResult(engine=self.name, error=str(exc))

    @staticmethod
    def _mean_confidence(response) -> float:
        confidences = []
        try:
            annotation = response.full_text_annotation
            for page in annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            confidences.append(float(word.confidence) * 100)
        except Exception:
            pass
        return sum(confidences) / len(confidences) if confidences else 0.0


_ENGINES: Dict[str, Type[BaseOcrEngine]] = {
    TesseractEngine.name: TesseractEngine,
    GoogleVisionEngine.name: GoogleVisionEngine,
}

_ENGINE_CACHE: Dict[str, BaseOcrEngine] = {}


def get_ocr_engine(name: Optional[str] = None) -> BaseOcrEngine:
    """Devuelve el motor OCR configurado (cacheado por nombre).

    Si el motor pedido no existe, cae de vuelta a Tesseract.
    """
    configured = (name or settings.OCR_ENGINE or TesseractEngine.name).strip().lower()
    if configured not in _ENGINES:
        logger.warning("Motor OCR '%s' desconocido; usando tesseract", configured)
        configured = TesseractEngine.name

    if configured not in _ENGINE_CACHE:
        _ENGINE_CACHE[configured] = _ENGINES[configured]()
    return _ENGINE_CACHE[configured]
