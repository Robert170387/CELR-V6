import hashlib
import secrets
import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Usuario, RefreshToken


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# --- Politica de contrasenas (A1) -------------------------------------------------
# Alcance deliberado: se aplica al CAMBIO de contrasena (/auth/cambio-contrasena).
# El login sigue aceptando las contrasenas historicas y la creacion de cuentas
# todavia no la exige (eso llega en A2/A5 con la identidad por cedula).
LONGITUD_MINIMA_CONTRASENA = 8

CONTRASENAS_BLOQUEADAS = {
    "admin123",
    "12345678",
    "password",
    "contrasena",
    "celr123",
}


def validar_politica_contrasena(
    contrasena: str,
    *,
    cedula: Optional[str] = None,
    correo: Optional[str] = None,
) -> None:
    """Lanza ValueError con mensaje en espanol si la contrasena no cumple la politica.

    Reglas, en orden: no vacia, minimo 8 caracteres, distinta de la cedula,
    distinta del correo, no esta en la lista de contrasenas comunes y no repite
    un unico caracter. `cedula` y `correo` son opcionales porque todavia no
    todas las cuentas tienen esos datos (A1 no hace backfill).
    """
    valor = (contrasena or "").strip()
    if not valor:
        raise ValueError("La contrasena no puede estar vacia")
    if len(valor) < LONGITUD_MINIMA_CONTRASENA:
        raise ValueError(
            f"La contrasena debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres"
        )
    if cedula and valor.casefold() == cedula.strip().casefold():
        raise ValueError("La contrasena no puede ser igual a tu cedula")
    if correo and valor.casefold() == correo.strip().casefold():
        raise ValueError("La contrasena no puede ser igual a tu correo")
    if valor.casefold() in CONTRASENAS_BLOQUEADAS:
        raise ValueError("Esa contrasena es demasiado comun, elige otra")
    if len(set(valor)) == 1:
        raise ValueError("La contrasena no puede repetir un solo caracter")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access", "jti": uuid.uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, usuario: Usuario) -> str:
    raw = generate_refresh_token()
    expira = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(usuario_id=usuario.id, token_hash=hash_refresh_token(raw), expira_en=expira))
    db.flush()
    return raw


def revoke_refresh_token(db: Session, token_hash: str) -> bool:
    registro = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not registro:
        return False
    registro.revocado = True
    registro.usado_en = datetime.now(timezone.utc)
    db.flush()
    return True


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    usuario_id: Optional[int] = None
    correo: Optional[str] = None