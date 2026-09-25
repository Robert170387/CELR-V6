"""A3.1 — Generacion y validacion de tokens de reset de contrasena.

Reglas que sostienen el modulo:

* El secreto en claro NUNCA se persiste: se guarda el SHA-256 (igual que
  refresh_tokens). El token plano solo existe en la respuesta del servicio que
  lo genera, para que el endpoint lo envie por email.
* Un token es de un solo uso: `usado_en` lo inutiliza.
* Pedir un token nuevo invalida los tokens activos previos de la misma cuenta y
  tipo, para que un enlace viejo no siga sirviendo.
* `validar_token_reset` NO consume. La validacion de la politica de contrasenas
  ocurre despues y puede fallar con 422; si el consumo ocurriera antes, un
  simple error de tecleo al elegir la contrasena dejaria al usuario con un token
  muerto y tendria que pedir otro. Por eso validar y consumir estan separados.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ConfiguracionSistema
from app.models.flota import PasswordResetToken, Usuario

# Configuracion de negocio, en configuracion_sistema (clave/valor existente).
# Se insertan con ON CONFLICT DO NOTHING la primera vez que se usan, para que un
# entorno nuevo no necesite tocar seeds.
CONFIG_TTL_ENLACE_HORAS = "password_reset_enlace_ttl_horas"
CONFIG_TTL_CODIGO_MINUTOS = "password_reset_codigo_ttl_minutos"
CONFIG_INTENTOS_ENLACE = "password_reset_enlace_intentos_max"
CONFIG_INTENTOS_CODIGO = "password_reset_codigo_intentos_max"

DEFAULT_TTL_ENLACE_HORAS = 2
DEFAULT_TTL_CODIGO_MINUTOS = 15
DEFAULT_INTENTOS_ENLACE = 5
DEFAULT_INTENTOS_CODIGO = 5

# Intentos de generacion ante colision de hash (A3.3). Con 10^6 codigos la
# probabilidad es baja, pero una colision sin manejar seria un 500.
MAX_INTENTOS_GENERACION = 5

_TTL_POR_TIPO = {"enlace": CONFIG_TTL_ENLACE_HORAS, "codigo": CONFIG_TTL_CODIGO_MINUTOS}
_INTENTOS_POR_TIPO = {
    "enlace": CONFIG_INTENTOS_ENLACE,
    "codigo": CONFIG_INTENTOS_CODIGO,
}
_DEFAULTS = {
    CONFIG_TTL_ENLACE_HORAS: DEFAULT_TTL_ENLACE_HORAS,
    CONFIG_TTL_CODIGO_MINUTOS: DEFAULT_TTL_CODIGO_MINUTOS,
    CONFIG_INTENTOS_ENLACE: DEFAULT_INTENTOS_ENLACE,
    CONFIG_INTENTOS_CODIGO: DEFAULT_INTENTOS_CODIGO,
}


def _config_int(db: Session, clave: str, default: int) -> int:
    """Lee un entero de configuracion_sistema; inserta el default si falta.

    ON CONFLICT DO NOTHING: si dos peticiones simultaneas intento insertar la
    misma clave, una gana y la otra no rompe nada.
    """
    fila = db.execute(
        select(ConfiguracionSistema).where(ConfiguracionSistema.clave == clave)
    ).scalar_one_or_none()
    if fila is not None:
        try:
            return int(fila.valor)
        except (TypeError, ValueError):
            # Configuracion corrupta: se cae al default en vez de romper el flujo.
            return default
    db.execute(
        pg_insert(ConfiguracionSistema)
        .values(clave=clave, valor=str(default), descripcion="Configuracion de reset de contrasena (A3.1)")
        .on_conflict_do_nothing(index_elements=[ConfiguracionSistema.clave])
    )
    db.flush()
    return default


def ttl_por_tipo(db: Session, tipo: str) -> timedelta:
    if tipo == "codigo":
        return timedelta(minutes=_config_int(db, CONFIG_TTL_CODIGO_MINUTOS, DEFAULT_TTL_CODIGO_MINUTOS))
    return timedelta(hours=_config_int(db, CONFIG_TTL_ENLACE_HORAS, DEFAULT_TTL_ENLACE_HORAS))


def intentos_max_por_tipo(db: Session, tipo: str) -> int:
    clave = _INTENTOS_POR_TIPO.get(tipo, CONFIG_INTENTOS_ENLACE)
    default = DEFAULT_INTENTOS_CODIGO if tipo == "codigo" else DEFAULT_INTENTOS_ENLACE
    return _config_int(db, clave, default)


def _hash_token(token_plano: str) -> str:
    return hashlib.sha256((token_plano or "").encode("utf-8")).hexdigest()


def _revocar_activos(db: Session, usuario_id: int, tipo: str) -> None:
    """Invalida los tokens vivos del mismo usuario y tipo (solicitud nueva)."""
    filas = db.query(PasswordResetToken).filter(
        PasswordResetToken.usuario_id == usuario_id,
        PasswordResetToken.tipo == tipo,
        PasswordResetToken.usado_en.is_(None),
        PasswordResetToken.revocado.is_(False),
    )
    for fila in filas:
        fila.revocado = True
    db.flush()


def generar_token_reset(db: Session, usuario_id: int, tipo: str = "enlace") -> str:
    """Crea un token y devuelve el secreto EN CLARO (el hash es lo que se guarda).

    Para 'enlace' el secreto son 64 bytes aleatorios (no bruteforceable).
    Para 'codigo' son 6 digitos, que sí lo son: por eso ese flujo necesita TTL
    corto y limite de intentos.

    Colisiones: `token_hash` es UNIQUE global. Para 'enlace' es practicamente
    imposible; para 'codigo' hay 10^6 valores y las filas viejas NO se borran
    (solo se revocan), asi que el mismo codigo puede volver a salir y chocar
    contra su propio hash previo. Se reintenta con SAVEPOINT: un `db.rollback()`
    normal descartaria tambien la revocacion de los tokens activos que se hizo
    justo antes.
    """
    if tipo not in ("enlace", "codigo"):
        raise ValueError(f"tipo invalido: {tipo}")

    _revocar_activos(db, usuario_id, tipo)
    ttl = ttl_por_tipo(db, tipo)
    intentos_max = intentos_max_por_tipo(db, tipo)

    for _ in range(MAX_INTENTOS_GENERACION):
        token_plano = (
            f"{secrets.randbelow(10 ** 6):06d}"
            if tipo == "codigo"
            else secrets.token_urlsafe(64)
        )
        savepoint = db.begin_nested()
        try:
            db.add(
                PasswordResetToken(
                    usuario_id=usuario_id,
                    tipo=tipo,
                    token_hash=_hash_token(token_plano),
                    expira_en=datetime.now(timezone.utc) + ttl,
                    intentos_max=intentos_max,
                )
            )
            db.flush()
        except IntegrityError:
            savepoint.rollback()
            continue
        return token_plano

    raise RuntimeError(
        f"No se pudo generar un token unico tras {MAX_INTENTOS_GENERACION} intentos"
    )


def validar_token_reset(
    db: Session, token_plano: str, tipo: str = "enlace"
) -> Optional[PasswordResetToken]:
    """Devuelve el token si es utilizable, o None. NO consume ni incrementa.

    A3.3 reutiliza esta funcion para validar el codigo offline.
    """
    if not token_plano:
        return None
    fila = db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(token_plano),
            PasswordResetToken.tipo == tipo,
        )
    ).scalar_one_or_none()
    if fila is None:
        return None
    if fila.revocado or fila.usado_en is not None:
        return None
    if fila.expira_en < datetime.now(timezone.utc):
        return None
    if fila.intentos >= fila.intentos_max:
        return None
    return fila


def consumir_token_reset(db: Session, token_plano: str, tipo: str = "enlace") -> Optional[PasswordResetToken]:
    """Valida y consume en un solo paso (uso simple, p. ej. admin assisted en A3.2).

    El endpoint de reset por enlace NO usa esta funcion: usa validar() y luego
    marcar_token_consumido() sobre la fila ya validada, para no repetir la
    consulta y para poder validar la politica en medio sin quemar el token.
    """
    fila = validar_token_reset(db, token_plano, tipo)
    if fila is None:
        return None
    return marcar_token_consumido(db, fila)


def marcar_token_consumido(db: Session, fila: PasswordResetToken) -> PasswordResetToken:
    """Marca como usado un token YA validado (de un solo uso)."""
    fila.intentos += 1
    fila.usado_en = datetime.now(timezone.utc)
    fila.revocado = True
    db.flush()
    return fila


def registrar_intento_fallido(db: Session, fila: PasswordResetToken) -> None:
    """Suma un intento y revoca al agotar el maximo. Sostiene el modo 'codigo'."""
    fila.intentos += 1
    if fila.intentos >= fila.intentos_max:
        fila.revocado = True
    db.flush()


def usuario_por_id(db: Session, usuario_id: int) -> Optional[Usuario]:
    return db.execute(
        select(Usuario).where(Usuario.id == usuario_id)
    ).scalar_one_or_none()
