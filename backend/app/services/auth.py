"""A2 — Resolucion de usuario por identificador unico (cedula o correo).

D1 (coexistencia): el login acepta un unico campo `identificador` que puede ser
la cedula o el correo. Este modulo centraliza la busqueda para que el endpoint
no tenga que conocer los dos campos ni sus reglas de normalizacion.
"""
from typing import List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.flota import Usuario

# Tope de filas a leer: 1 (match unico) o 2 (ambiguedad -> hay que fallar).
# Con mas de 2 no hay nada que distinguishes, asi que no se leen mas.
TOPE_CANDIDATOS = 2


def _candidatos(db: Session, objetivo: str) -> List[Usuario]:
    """Filas de usuarios cuya cedula o cuyo correo coinciden con `objetivo`.

    `objetivo` llega en minusculas y sin espacios. Se compara con lower() en
    ambos lados para que el login no dependa de como el usuario escribio su
    correo. Los NULL se descartan explicitamente (lower(NULL) nunca iguala).
    """
    return list(
        db.execute(
            select(Usuario)
            .where(
                or_(
                    and_(Usuario.cedula.is_not(None), func.lower(Usuario.cedula) == objetivo),
                    and_(Usuario.correo.is_not(None), func.lower(Usuario.correo) == objetivo),
                )
            )
            .limit(TOPE_CANDIDATOS)
        )
        .scalars()
        .all()
    )


def resolver_usuario_por_identificador(db: Session, identificador: str) -> Optional[Usuario]:
    """Devuelve el usuario que matchea cedula o correo (case-insensitive).

    Devuelve None — y el endpoint responde el 401 generico de siempre — cuando:
      * el identificador viene vacio,
      * no matchea ninguna cuenta,
      * matchea cuentas DISTINTAS por un lado y por el otro (p. ej. la cedula de
        un usuario es el correo de otro). Es ambiguedad real y no debe resolverse
        por prioridad: se trata como credencial invalida.

    Que ambos campos del MISMO usuario coincidan no es ambiguedad: la consulta
    devuelve una sola fila para esa cuenta y se resuelve con normalidad.
    """
    valor = (identificador or "").strip()
    if not valor:
        return None

    filas = _candidatos(db, valor.lower())
    if len(filas) == 1:
        return filas[0]
    if not filas:
        return None
    # Mas de una fila = cuentas distintas. Sin informacion de cual es la correcta.
    return None
