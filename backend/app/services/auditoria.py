"""A3.4 — Escritura de la auditoria de eventos sensibles.

Solo hacia adelante: esta migracion no reconstruye historia previa, asi que
los eventos anteriores a f6a7b8c9d0e1 no existen y no se inventan.

Invariante (verificada por test_auditoria.py, TAUD-10): `detalle` NUNCA lleva
secretos — ni tokens de enlace, ni codigos offline, ni contrasenas (temporales
o nuevas). Solo IDs, IPs, user-agent y motivos. Un log de auditoria que se
puede leer para recuperar una credencial es un vector de robo, no un control.

`registrar()` hace flush pero NO commit: el evento comparte transaccion con la
accion auditada. Si la accion falla y se hace rollback, el evento tampoco
persiste, que es lo coherente: no queremos eventos de cosas que no ocurrieron.
"""
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.auditoria import AuditoriaEvento


def obtener_ip(request: Request) -> Optional[str]:
    """Devuelve la IP del cliente segun la ve uvicorn.

    OJO: el Dockerfile corre uvicorn SIN `--proxy-headers`, asi que detras de un
    proxy (Render) esto devuelve la IP DEL PROXY, no la del cliente real. Ver
    la deuda IP-real-detras-de-proxy antes de usar este dato para investigar.
    """
    if request is None or request.client is None:
        return None
    return request.client.host


def obtener_user_agent(request: Request) -> Optional[str]:
    if request is None:
        return None
    return request.headers.get("user-agent")


def registrar(
    db: Session,
    evento: str,
    *,
    actor_id: Optional[int] = None,
    objetivo_id: Optional[int] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    detalle: Optional[Dict[str, Any]] = None,
) -> AuditoriaEvento:
    """Registra un evento. Flush, sin commit: la transaccion es la del caller."""
    fila = AuditoriaEvento(
        evento=evento,
        usuario_actor_id=actor_id,
        usuario_objetivo_id=objetivo_id,
        ip=ip,
        user_agent=user_agent,
        detalle=detalle,
    )
    db.add(fila)
    db.flush()
    return fila
