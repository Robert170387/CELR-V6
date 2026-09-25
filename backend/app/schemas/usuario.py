import re

from pydantic import BaseModel, Field, field_validator, model_validator, validator
from typing import Optional
from datetime import date, datetime

from app.core.roles import ROLES_VALIDOS

# A5.1: NO se usa pydantic.EmailStr. Requiere el paquete `email-validator`,
# que no esta instalado: importar la clase funciona, pero DEFINIR un schema
# con ese tipo revienta con ImportError y deja sin importar app.main (API,
# suites, Docker y E2E caerián juntos). Se valida la forma basica con regex,
# que es lo que alcanza para este dominio y lo que hace el resto del repo.
_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def correo_valido(valor: str) -> bool:
    return bool(_PATRON_CORREO.match(valor or ""))


class UsuarioCreate(BaseModel):
    """NO lo usa ningun endpoint desde A5.1 (el alta real es
    UsuarioCreateA5, que no recibe contrasena porque el backend genera una
    temporal).

    Se conserva porque `test_rbac.py` lo importa como vehiculo para probar el
    validador de roles contra el enum: construye uno por rol valido y
    verifica que uno invalido se rechaza. No esta muerto, pero su unico
    consumidor es ese test, y por eso no se toca su forma."""

    correo: str = Field(..., max_length=100)
    contrasena: str = Field(..., min_length=6)
    rol: str = Field(default="conductor", max_length=20)
    conductor_id: Optional[int] = None

    @validator("rol")
    def validate_rol(cls, v):
        if v not in ROLES_VALIDOS:
            raise ValueError(f"debe ser uno de {sorted(ROLES_VALIDOS)}")
        return v


class UsuarioLogin(BaseModel):
    """A2 (D1 coexistencia): el login acepta `identificador` (cedula o correo).

    `correo` se conserva como alias legacy para no romper los clientes ya
    desplegados; si llegan ambos campos, `identificador` manda (ver endpoint
    /auth/login). A1 dejo `correo` nullable, asi que la cedula es hoy la
    identidad primaria, pero el alias sigue siendo la via de entrada mas usada.
    """

    identificador: Optional[str] = Field(default=None, max_length=100)
    correo: Optional[str] = Field(default=None, max_length=100)
    contrasena: str = Field(..., max_length=200)

    @model_validator(mode="after")
    def _requiere_identificador(self) -> "UsuarioLogin":
        if not (self.identificador or self.correo):
            raise ValueError(
                "Debe enviar 'identificador' (cedula o correo) o 'correo'"
            )
        return self


class AdminResetPasswordResponse(BaseModel):
    """A3.2 — Respuesta del reset asistido.

    `contrasena_temporal` se devuelve UNA sola vez. El frontend debe pedirla
    explícitamente (botón "generar") y no cachearla.
    """

    usuario_id: int
    correo: Optional[str] = None
    contrasena_temporal: str
    mensaje: str
    debe_cambiar_contrasena: bool = True


class AdminResetCodigoResponse(BaseModel):
    """A3.3 — Respuesta de la generacion de un codigo offline.

    El codigo se devuelve UNA sola vez y NO se envia por email: el admin lo
    dicta al usuario por canal presencial. `expira_en` va en la respuesta para
    que el admin sepa cuando deja de servir.
    """

    usuario_id: int
    correo: Optional[str] = None
    codigo: str
    expira_en: datetime
    mensaje: str


class UsuarioCreateA5(BaseModel):
    """A5.1 — Alta de usuario. NO recibe contrasena.

    El backend genera una temporal y la devuelve una sola vez; A4 obliga a
    cambiarla en el primer login. Es D4: el admin nunca conoce la contrasena
    final de la persona.

    `cedula` es obligatoria (identidad canonica de A1) y `correo` opcional:
    hay usuarios (conductores de campo) que no usan correo y recuperan
    acceso por codigo offline (A3.3) o por el admin (A3.2).

    `extra="forbid"`: un cliente que mande `contrasena` (hábito del schema
    viejo) recibe un 422 que lo dice, en vez de que el campo se descarte y
    el cliente crea que fijo la contraseña que quiso.
    """

    model_config = {"extra": "forbid"}

    cedula: str = Field(..., min_length=4, max_length=20)
    correo: Optional[str] = Field(default=None, max_length=100)
    rol: str = Field(..., max_length=20)
    conductor_id: Optional[int] = None

    @field_validator("correo")
    @classmethod
    def _validar_correo(cls, v):
        if v is not None and not correo_valido(v):
            raise ValueError("correo no tiene un formato valido")
        return v.lower() if v else v

    @field_validator("rol")
    @classmethod
    def _validar_rol(cls, v):
        if v not in ROLES_VALIDOS:
            raise ValueError(f"debe ser uno de {sorted(ROLES_VALIDOS)}")
        return v


class UsuarioUpdateA5(BaseModel):
    """A5.1 — Edicion de usuario. SIN campo `rol` a proposito.

    El rol no se edita por PUT: corregir un rol mal asignado se hace
    desactivando y recreando.

    `extra="forbid"` es lo que hace que mandar `rol` (o cualquier campo
    desconocido) sea un 422 explicito en vez de un 200 en el que el campo se
    descarto en silencio. Sin esto, pydantic borra el extra antes de que el
    endpoint lo vea: el cliente creeria que el cambio se aplico y se descubre
    meses despues. Tambien convierte un typo simple ("correoo") en un error
    visible en vez de un no-op silencioso.
    """

    model_config = {"extra": "forbid"}

    correo: Optional[str] = Field(default=None, max_length=100)
    cedula: Optional[str] = Field(default=None, min_length=4, max_length=20)
    conductor_id: Optional[int] = None

    @field_validator("correo")
    @classmethod
    def _validar_correo(cls, v):
        if v is not None and not correo_valido(v):
            raise ValueError("correo no tiene un formato valido")
        return v.lower() if v else v

    @field_validator("cedula")
    @classmethod
    def _limpiar_cedula(cls, v):
        return v.strip() if v else v


class UsuarioListItem(BaseModel):
    """A5.1 — Fila del listado de usuarios."""

    id: int
    cedula: Optional[str] = None
    correo: Optional[str] = None
    rol: str
    conductor_id: Optional[int] = None
    activo: bool
    debe_cambiar_contrasena: bool = False
    ultimo_acceso: Optional[datetime] = None
    creado_en: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class UsuarioCreateResponse(BaseModel):
    """A5.1 — La contrasena temporal se devuelve UNA sola vez, en el cuerpo."""

    usuario_id: int
    cedula: Optional[str] = None
    correo: Optional[str] = None
    rol: str
    contrasena_temporal: str
    mensaje: str
    debe_cambiar_contrasena: bool = True


class UsuarioAccionResponse(BaseModel):
    """A5.2 — Respuesta de desactivar/degradar un usuario.

    `era_ultimo_admin` viaja en la respuesta (y en la auditoria) para que el
    operador sepa en el momento que acaba de dejar el sistema con un unico
    admin. No bloquea: la decision fue auditar, no impedir.
    """

    usuario_id: int
    activo: bool
    rol: str
    era_ultimo_admin: bool
    mensaje: str


class DesactivarUsuarioRequest(BaseModel):
    """A5.2 — Desactivar es irreversible a efectos practicos: la cuenta queda
    inactiva y no puede iniciar sesion."""

    confirmacion: str = Field(..., min_length=1, max_length=150)
    motivo: Optional[str] = Field(default=None, max_length=500)


class DegradarUsuarioRequest(BaseModel):
    """A5.2 — Degradar cambia el rol. `nuevo_rol` se valida contra la matriz
    de roles que el ejecutor puede conceder, asi que no es un editor de roles
    libre: es el mismo permiso que crear."""

    confirmacion: str = Field(..., min_length=1, max_length=150)
    nuevo_rol: str = Field(..., min_length=1, max_length=20)
    motivo: Optional[str] = Field(default=None, max_length=500)


class UsuarioResponse(BaseModel):
    id: int
    # A1: la cedula es la identidad primaria y el correo queda opcional.
    cedula: Optional[str] = None
    correo: Optional[str] = None
    rol: str
    conductor_id: Optional[int]
    activo: bool
    debe_cambiar_contrasena: bool = False
    ultimo_acceso: Optional[datetime]
    creado_en: datetime
    actualizado_en: datetime

    class ConfigDict:
        from_attributes = True
