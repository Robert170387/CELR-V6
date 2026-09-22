"""Rate limiting en memoria para intentos de inicio de sesión.

Simple y suficiente para el deploy local/single-worker. Si se escala a
multi-proceso o multi-instancia, reemplazar por una implementación respaldada
en Redis/Postgres con la misma API (excede_limite / registrar_fallo / limpiar_fallos).
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 15 * 60

_fallidos: Dict[str, Deque[float]] = defaultdict(deque)


def excede_limite(clave: str) -> bool:
    """True si la clave tiene >= MAX_INTENTOS fallos dentro de la ventana."""
    cola = _fallidos[clave]
    ahora = time.monotonic()
    while cola and ahora - cola[0] > VENTANA_SEGUNDOS:
        cola.popleft()
    return len(cola) >= MAX_INTENTOS


def registrar_fallo(clave: str) -> None:
    """Registra un intento fallido y descarta los fuera de la ventana."""
    ahora = time.monotonic()
    cola = _fallidos[clave]
    while cola and ahora - cola[0] > VENTANA_SEGUNDOS:
        cola.popleft()
    cola.append(ahora)


def limpiar_fallos(clave: str) -> None:
    """Limpia el historial tras un inicio de sesión exitoso."""
    _fallidos.pop(clave, None)