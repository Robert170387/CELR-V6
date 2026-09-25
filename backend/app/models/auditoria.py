"""A3.4 — Modelo de auditoria de eventos sensibles.

Segun D-Aud-4', el endpoint de lectura y la UI van en A5; aca esta solo el
modelo y las escrituras.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class AuditoriaEvento(Base):
    __tablename__ = "auditoria_evento"

    id = Column(Integer, primary_key=True)
    # Texto libre a proposito: la lista de eventos todavia no se ha estabilizado
    # y derivarla a enum implica una migracion cada vez que se agrega uno.
    evento = Column(String(50), nullable=False, index=True)
    # ON DELETE SET NULL: si se borra el usuario, el evento sobrevive aunque
    # pierda el vinculo. Perder el rastro es peor que perder la referencia.
    usuario_actor_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    usuario_objetivo_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # OJO: en produccion detras de proxy sin --proxy-headers guarda la IP DEL
    # PROXY, no la del cliente. Deuda IP-real-detras-de-proxy.
    # 45 chars: IPv6 con prefijo de alcance (fe80::1%eth0).
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    # Nunca secretos: tokens, contrasenas ni codigos. Ver invariante en
    # services/auditoria.py y el test TAUD-10.
    detalle = Column(JSONB, nullable=True)
    creado_en = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor = relationship("Usuario", foreign_keys=[usuario_actor_id])
    objetivo = relationship("Usuario", foreign_keys=[usuario_objetivo_id])
