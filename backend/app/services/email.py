"""A3.1 — Abstraccion de envio de email.

D2: en local se usa un backend que LOGuea el mensaje (incluido el enlace con
el token) para poder completar el flujo sin SMTP. En produccion ese backend
se NIEGA a enviar: un reset de contrasena que se pierde en silencio es peor que
un fallo visible, asi que hasta que exista un proveedor real el forget-password
falla de forma explicita en vez de fingir que se envio el correo.

Cuando exista el proveedor real se implementa la misma interfaz y se cambia una
sola linea en get_email_backend; el resto de la app no cambia.
"""
import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailBackend(Protocol):
    """Contrato minimo de entrega. Si no hay destinatario real, no hay envio."""

    def enviar(self, destinatario: str, asunto: str, cuerpo: str) -> None: ...


class LogEmailBackend:
    """Backend de desarrollo: loguea el mensaje completo.

    Incluye el token en claro a proposito: en local es la unica forma de
    completar el flujo sin correo. Por eso se niega a correr en produccion.
    """

    def enviar(self, destinatario: str, asunto: str, cuerpo: str) -> None:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(
                "Email provider no configurado para produccion. "
                "Configure un backend real antes de usar reset por email."
            )
        logger.info(
            "[EMAIL-MOCK] to=%s subject=%s body=%s", destinatario, asunto, cuerpo
        )


def get_email_backend() -> EmailBackend:
    return LogEmailBackend()
