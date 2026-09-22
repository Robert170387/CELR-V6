"""Consecutivos atomicos por clave (ej. numero_odt) sobre secuencias_documento."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def siguiente_consecutivo(db: Session, clave: str) -> int:
    """Incrementa la secuencia y devuelve el nuevo valor, de forma atomica.

    El UPSERT corre en la misma transaccion que el commit del endpoint, de modo
    que dos peticiones concurrentes nunca obtienen el mismo consecutivo.
    """
    resultado = db.execute(
        text(
            "INSERT INTO secuencias_documento (clave, valor) VALUES (:clave, 1) "
            "ON CONFLICT (clave) DO UPDATE SET valor = secuencias_documento.valor + 1 "
            "RETURNING valor"
        ),
        {"clave": clave},
    )
    return int(resultado.scalar())