"""Helpers compartidos para scripts de test (no es una suite)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.flota import RefreshToken, Usuario


def capturar_token_ids(db: Session, correo: str) -> set[int]:
    """Captura los IDs de refresh_tokens de un usuario antes de la corrida."""
    usuario = db.query(Usuario).filter(Usuario.correo == correo).first()
    if usuario is None:
        return set()
    return {
        token.id
        for token in db.query(RefreshToken)
        .filter(RefreshToken.usuario_id == usuario.id)
        .all()
    }


def limpiar_tokens_nuevos(db: Session, correo: str, antes: set[int]) -> int:
    """Borra refresh_tokens creados después del snapshot y devuelve la cantidad.

    ESTE HELPER NO COMMITEA, por diseño (commit ``ac2e9ba``, que creó el helper):
    el caller decide cuándo. Si commiteás ANTES de llamar, el DELETE pendiente se
    descarta en el ``close()`` y el cleanup no ocurrió — aunque la suite anuncie que
    sí. Patrón de referencia: ``test_liquidaciones.py``, que commitea después.
    """
    usuario = db.query(Usuario).filter(Usuario.correo == correo).first()
    if usuario is None:
        return 0
    query = db.query(RefreshToken).filter(
        RefreshToken.usuario_id == usuario.id,
        RefreshToken.id.notin_(antes),
    )
    cantidad = query.count()
    if cantidad:
        query.delete(synchronize_session=False)
    return cantidad
