"""Usuarios — gestion de cuentas (A3.2, andamio para A5).

A3.2 implementa solo el reset asistido por admin. Los endpoints de CRUD
(listar, crear, editar, desactivar) llegan en A5.
"""
import logging
import secrets
from typing import Dict, FrozenSet

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import RoleChecker, get_current_user
from app.core.roles import RolUsuario
from app.core.security import hash_password
from app.db.session import get_db
from app.models.flota import Conductor as ConductorModel
from app.models.flota import PasswordResetToken
from app.models.flota import RefreshToken as RefreshTokenModel
from app.models.flota import Usuario as UsuarioModel
from app.schemas.usuario import (
    AdminResetCodigoResponse,
    AdminResetPasswordResponse,
    DegradarUsuarioRequest,
    DesactivarUsuarioRequest,
    UsuarioCreateA5,
    UsuarioCreateResponse,
    UsuarioListItem,
    UsuarioUpdateA5,
    UsuarioAccionResponse,
)
from app.services.auditoria import obtener_ip, obtener_user_agent
from app.services.auditoria import registrar as registrar_auditoria
from app.services.password_reset import generar_token_reset, ttl_por_tipo
from app.services.usuarios import (
    es_ultimo_admin_activo,
    validar_confirmacion_identificador,
)

logger = logging.getLogger(__name__)

# A3.2 — Reset asistido: el admin (o un rol de escritura) genera una contrasena
# temporal para un usuario que no puede entrar. Es distinto del reset por enlace
# de A3.1: aqui no hay token ni email, hay una credencial que el administrador
# comunica por un canal presencial. Por eso NO usa `password_reset_token`, que
# queda reservado para el codigo offline de A3.3.
ROLES_RESET_PERMITIDOS: FrozenSet[str] = frozenset(
    {
        RolUsuario.ADMIN.value,
        RolUsuario.OPERADOR.value,
        RolUsuario.CONTADOR.value,
        RolUsuario.SUPERVISOR.value,
    }
)

# A5.2: desactivar o degradar es territorio exclusivo de admin. Es la unica
# accion que puede dejar el sistema sin gestion de cuentas, asi que no se
# reparte con los roles de escritura. Derivado del enum, no un literal.
ROLES_ADMIN: FrozenSet[str] = frozenset({RolUsuario.ADMIN.value})

# Matriz anti-escalada: que rol de OBJETIVO puede resetear cada rol de EJECUTOR.
# Sin esto, un operador podria resetearle la contrasena a un admin y tomar su
# cuenta: la escalada no es "quien deberia", es "quien no debe poder tomar".
# Se construye desde el enum para que un rol nuevo no quede sin cobertura
# silenciosa (el error de A3.1 fue exactamente un rol huerfano).
ROLES_OBJETIVO_POR_EJECUTOR: Dict[str, FrozenSet[str]] = {
    RolUsuario.ADMIN.value: frozenset(rol.value for rol in RolUsuario),
    RolUsuario.OPERADOR.value: frozenset(
        {RolUsuario.CONDUCTOR.value, RolUsuario.CLIENTE.value}
    ),
    RolUsuario.CONTADOR.value: frozenset(
        {RolUsuario.CONDUCTOR.value, RolUsuario.CLIENTE.value}
    ),
    RolUsuario.SUPERVISOR.value: frozenset(
        {RolUsuario.CONDUCTOR.value, RolUsuario.CLIENTE.value}
    ),
}

router = APIRouter(dependencies=[Depends(RoleChecker(ROLES_RESET_PERMITIDOS))])


# ---------------------------------------------------------------------------
# A5.1 — CRUD de usuarios.
#
# `ROLES_OBJETIVO_POR_EJECUTOR` (definido mas abajo, de A3.2) es la UNICA
# fuente de verdad sobre que puede ver y crear cada rol. A5.1 le agrega su
# cuarto consumidor: listar. Con reset (A3.2), crear (A5.1) y degradar
# (A5.2), las cuatro operaciones leen la misma matriz.
#
# El listado sigue la convencion del repo: skip/limit con el total en el
# header X-Total-Count, que es lo que lee `conTotal()` en el frontend
# (api/index.ts). Devolver {data, total} en el body haria que la UI
# mostrara 0 elementos con el array lleno.


@router.get("/usuarios", response_model=list[UsuarioListItem])
def listar_usuarios(
    response: Response,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    activo: bool | None = None,
    rol: str | None = None,
):
    """A5.1 — Lista usuarios que el ejecutor puede ver segun su matriz.

    El ejecutor SI se ve a si mismo, aunque su propio rol no este en su
    matriz: un operador listing conductors no deberia desaparecer de "su
    propia" pantalla de gestion, se leeria como un bug. El resto de la
    lista sigue gobernada por la matriz.
    """
    permitidos = ROLES_OBJETIVO_POR_EJECUTOR.get(current_user.rol, frozenset())
    if rol is not None and rol not in permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes listar usuarios con ese rol",
        )
    q = db.query(UsuarioModel).filter(
        (UsuarioModel.rol.in_(permitidos)) | (UsuarioModel.id == current_user.id)
    )
    if activo is not None:
        q = q.filter(UsuarioModel.activo.is_(activo))
    if rol is not None:
        q = q.filter(UsuarioModel.rol == rol)

    total = q.count()
    response.headers["X-Total-Count"] = str(total)
    return q.order_by(UsuarioModel.id).offset(skip).limit(limit).all()


def _resolver_objetivo(db: Session, usuario_id: int, current_user: UsuarioModel) -> UsuarioModel:
    """Valida el objetivo de un reset. Compartido por A3.2 y A3.3.

    Aplica las tres reglas que no dependen de como se entrega la credencial:
    existe, no sos vos mismo, y tu rol puede resetear ese rol. Que las dos
    vias compartan esta funcion es lo que garantiza que un endpoint nuevo no
    se CUERDE con una matriz mas laxa.
    """
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Admin no se resetea a si mismo por esta via. La credencial se muestra una
    # sola vez: si se pierde, se queda fuera del sistema de gestion de cuentas
    # y no hay forma de volver. Para su propia cuenta esta el flujo
    # /auth/forgot-password (que exige correo) o /auth/cambio-contrasena.
    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes restablecer tu propia contraseña por esta vía",
        )

    permitidos = ROLES_OBJETIVO_POR_EJECUTOR.get(current_user.rol, frozenset())
    if usuario.rol not in permitidos:
        # Mensaje generico a proposito: incluir el rol del objetivo confirmaria
        # a un ejecutor sin permisos que tipo de cuenta es la que probed.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para restablecer la contraseña de este usuario",
        )
    return usuario


@router.post(
    "/usuarios/{usuario_id}/reset-password",
    response_model=AdminResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
def reset_password_asistido(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """Genera una contrasena temporal para el usuario objetivo.

    La contrasena en claro se devuelve SOLO en esta respuesta HTTP: nunca se
    loguea, nunca se persiste y no vuelve a mostrarse. Por eso va en el cuerpo
    de un POST y no en la URL, que acabaria en los access logs del servidor.
    """
    usuario = _resolver_objetivo(db, usuario_id, current_user)

    contrasena_temporal = secrets.token_urlsafe(12)

    usuario.contrasena_hash = hash_password(contrasena_temporal)
    # A4 ya hace que este flag bloquee de verdad: el usuario no entra a
    # endpoints de negocio hasta cambiarla.
    usuario.debe_cambiar_contrasena = True
    usuario.password_version = (usuario.password_version or 0) + 1
    usuario.ultimo_acceso = None

    # La credencial cambio: el resto de sesiones abiertas deben caer.
    db.query(RefreshTokenModel).filter(
        RefreshTokenModel.usuario_id == usuario.id,
        RefreshTokenModel.revocado.is_(False),
    ).update({"revocado": True}, synchronize_session=False)

    # A3.4: la contrasena temporal NO va en `detalle` ni en el log (invariante
    # TAUD-10). El rastro dice QUIEN reseteo a QUIEN, no QUE credencial.
    registrar_auditoria(
        db,
        "password_reset_admin",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
    )

    db.commit()
    # Traza minima: QUIEN reseteo y a QUIEN, nunca la contrasena. La auditoria
    # completa llega en A3.4.
    logger.info(
        "Reset asistido: usuario_id=%s por usuario_id=%s (rol=%s)",
        usuario.id,
        current_user.id,
        current_user.rol,
    )

    return AdminResetPasswordResponse(
        usuario_id=usuario.id,
        correo=usuario.correo,
        contrasena_temporal=contrasena_temporal,
        mensaje=(
            "Comuníquela al usuario por un canal seguro. No se mostrará de nuevo. "
            "El usuario deberá cambiarla al iniciar sesión."
        ),
        debe_cambiar_contrasena=True,
    )


@router.post(
    "/usuarios/{usuario_id}/reset-codigo",
    response_model=AdminResetCodigoResponse,
    status_code=status.HTTP_200_OK,
)
def reset_codigo_asistido(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """A3.3 — Genera un codigo de 6 digitos para un usuario sin acceso a email.

    A diferencia de A3.2, esto NO cambia la contrasena: solo emite un codigo que
    el usuario canjeara en /auth/reset-codigo. La contrasena se cambia cuando
    el usuario la elija, no cuando el admin lo decida.

    No se envia por email a proposito: el caso de uso es justamente quien no
    tiene buzon. El admin lo dicta por telefono/WhatsApp/presencial. Por eso
    este endpoint NO toca LogEmailBackend — si lo hiciera, el codigo caeria en
    los logs de la aplicacion.
    """
    usuario = _resolver_objetivo(db, usuario_id, current_user)

    codigo = generar_token_reset(db, usuario.id, tipo="codigo")
    # A3.4: el codigo de 6 digitos NO va en `detalle` (invariante TAUD-10).
    registrar_auditoria(
        db,
        "password_reset_codigo_generado",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
    )
    db.commit()
    fila = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.usuario_id == usuario.id,
            PasswordResetToken.tipo == "codigo",
        )
        .order_by(PasswordResetToken.id.desc())
        .first()
    )
    minutos = int(ttl_por_tipo(db, "codigo").total_seconds() // 60)

    # Traza minima: QUIEN genero el codigo y para QUIEN. Nunca el codigo.
    logger.info(
        "Codigo de reset generado: usuario_id=%s por usuario_id=%s (rol=%s)",
        usuario.id,
        current_user.id,
        current_user.rol,
    )

    return AdminResetCodigoResponse(
        usuario_id=usuario.id,
        correo=usuario.correo,
        codigo=codigo,
        expira_en=fila.expira_en if fila else None,
        mensaje=(
            f"Díctele el código al usuario por un canal seguro. No se mostrará de "
            f"nuevo. Caduca en {minutos} minutos."
        ),
    )


# ---------------------------------------------------------------------------
# A5.2 — Desactivar y degradar. Territorio exclusivo de admin.
#
# Por que NO hay bloqueo duro del ultimo admin: el caso que importa no es el
# error de tipeo, es la cuenta de admin comprometida. Si no hay forma de
# desactivarla, el atacante conserva el control y la unica salida es acceso
# directo a la base de datos. El control es exigir confirmacion humana
# (identificador tecleado, no un `confirmar=true` que manda un script) y
# dejar rastro. Decision cerrada antes de implementar.


def _resolver_para_accion(db: Session, usuario_id: int, current_user: UsuarioModel):
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes desactivar ni degradar tu propia cuenta",
        )
    return usuario


@router.post(
    "/usuarios/{usuario_id}/desactivar",
    response_model=UsuarioAccionResponse,
    dependencies=[Depends(RoleChecker(ROLES_ADMIN))],
)
def desactivar_usuario(
    usuario_id: int,
    payload: DesactivarUsuarioRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """A5.2 — Desactiva una cuenta. Exige confirmacion por identificador.

    Se permite desactivar al ultimo admin a proposito (caso de cuenta
    comprometida); lo que no se permite es hacerlo sin confirmacion y sin
    rastro. `era_ultimo_admin` viaja en la respuesta y en la auditoria para
    que quede visible.
    """
    usuario = _resolver_para_accion(db, usuario_id, current_user)

    try:
        validar_confirmacion_identificador(usuario, payload.confirmacion)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya está desactivado",
        )

    era_ultimo = es_ultimo_admin_activo(db, usuario.id)
    usuario.activo = False
    # La confirmacion va al rastro: el log dice que hubo confirmacion humana,
    # no solo que alguien llamo al endpoint.
    registrar_auditoria(
        db,
        "usuario_desactivado",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
        detalle={"motivo": payload.motivo, "era_ultimo_admin": era_ultimo},
    )
    db.commit()

    return UsuarioAccionResponse(
        usuario_id=usuario.id,
        activo=False,
        rol=usuario.rol,
        era_ultimo_admin=era_ultimo,
        mensaje=(
            "Cuenta desactivada. Leíste el identificador del objetivo para confirmar; "
            "el cambio quedó auditado."
        ),
    )


@router.post(
    "/usuarios/{usuario_id}/degradar",
    response_model=UsuarioAccionResponse,
    dependencies=[Depends(RoleChecker(ROLES_ADMIN))],
)
def degradar_usuario(
    usuario_id: int,
    payload: DegradarUsuarioRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """A5.2 — Cambia el rol de un usuario.

    `nuevo_rol` NO es libre: se valida contra la MISMA matriz que gobierna a
    quien puede resetear y a quien puede crear (A3.2). Asi degradar no
    introduce un editor de roles nuevo, reutiliza el permiso de concesion que
    ya existe. Un admin puede asignar cualquiera de los 6 roles.
    """
    usuario = _resolver_para_accion(db, usuario_id, current_user)

    # El rol se valida contra el enum ANTES que la matriz: "rol desconocido" es
    # un error de tipeo del ejecutor (422), no un problema de permisos (403).
    if payload.nuevo_rol not in {r.value for r in RolUsuario}:
        raise HTTPException(
            status_code=422,
            detail=f"Rol desconocido: {payload.nuevo_rol}. Validos: {sorted(r.value for r in RolUsuario)}",
        )
    # Misma matriz que gobierna resetear y crear: degradar no es un editor de
    # roles nuevo, es el permiso de concesion que ya existe. Hoy solo admin
    # entra a este endpoint y admin puede conceder los 6, asi que el 403 es
    # defensivo: si mañana se abre el endpoint a otro rol, la matriz ya limita.
    permitidos = ROLES_OBJETIVO_POR_EJECUTOR.get(current_user.rol, frozenset())
    if payload.nuevo_rol not in permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"No tienes permisos para asignar el rol '{payload.nuevo_rol}'. "
                "Los roles que puedes conceder son los mismos que puedes resetear."
            ),
        )
    if payload.nuevo_rol == usuario.rol:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya tiene ese rol",
        )

    try:
        validar_confirmacion_identificador(usuario, payload.confirmacion)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    era_ultimo = es_ultimo_admin_activo(db, usuario.id)
    rol_anterior = usuario.rol
    usuario.rol = payload.nuevo_rol

    registrar_auditoria(
        db,
        "usuario_degradado",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
        detalle={
            "motivo": payload.motivo,
            "rol_anterior": rol_anterior,
            "rol_nuevo": payload.nuevo_rol,
            "era_ultimo_admin": era_ultimo,
        },
    )
    db.commit()

    return UsuarioAccionResponse(
        usuario_id=usuario.id,
        activo=usuario.activo,
        rol=usuario.rol,
        era_ultimo_admin=era_ultimo,
        mensaje=f"Rol cambiado de '{rol_anterior}' a '{usuario.rol}'. Quedó auditado.",
    )


# ---------------------------------------------------------------------------
# A5.1 — Alta, edicion y reactivacion.


def _permitidos_del_ejecutor(current_user: UsuarioModel) -> FrozenSet[str]:
    return ROLES_OBJETIVO_POR_EJECUTOR.get(current_user.rol, frozenset())


@router.post("/usuarios", response_model=UsuarioCreateResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    payload: UsuarioCreateA5,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """A5.1 — Crea una cuenta. NO recibe contrasena: el backend genera una
    temporal y la devuelve una sola vez, y A4 obliga a cambiarla al primer
    login. Es D4: el admin nunca conoce la contrasena final de la persona.
    """
    permitidos = _permitidos_del_ejecutor(current_user)
    if payload.rol not in permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"No tienes permisos para crear usuarios con rol "
                f"'{payload.rol}'. Puedes crear: {sorted(permitidos)}"
            ),
        )

    cedula = payload.cedula.strip()
    if db.query(UsuarioModel).filter(UsuarioModel.cedula == cedula).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con esa cédula",
        )
    if payload.correo and db.query(UsuarioModel).filter(
        func.lower(UsuarioModel.correo) == payload.correo.lower()
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo",
        )

    if payload.conductor_id is not None:
        conductor = db.query(ConductorModel).filter(
            ConductorModel.id == payload.conductor_id
        ).first()
        if conductor is None:
            raise HTTPException(status_code=404, detail="Conductor no encontrado")
        # Coherencia persona=cuenta: si el conductor existe, la cedula de la
        # cuenta DEBE ser la del conductor. Sin esto se podrian crear dos
        # identidades para la misma persona.
        if conductor.cedula != cedula:
            raise HTTPException(
                status_code=422,
                detail=(
                    "La cédula no coincide con la del conductor vinculado "
                    f"({conductor.cedula})"
                ),
            )
        if db.query(UsuarioModel).filter(
            UsuarioModel.conductor_id == payload.conductor_id
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El conductor ya está vinculado a otro usuario",
            )

    contrasena_temporal = secrets.token_urlsafe(12)
    usuario = UsuarioModel(
        cedula=cedula,
        correo=payload.correo,
        rol=payload.rol,
        conductor_id=payload.conductor_id,
        contrasena_hash=hash_password(contrasena_temporal),
        # A4 lo bloquea hasta que la cambie.
        debe_cambiar_contrasena=True,
        activo=True,
    )
    db.add(usuario)
    db.flush()

    # La contrasena temporal NO va en `detalle` ni en el log (invariante TAUD-10).
    registrar_auditoria(
        db,
        "usuario_creado",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
        detalle={"rol": payload.rol, "conductor_id": payload.conductor_id},
    )
    db.commit()

    return UsuarioCreateResponse(
        usuario_id=usuario.id,
        cedula=usuario.cedula,
        correo=usuario.correo,
        rol=usuario.rol,
        contrasena_temporal=contrasena_temporal,
        mensaje=(
            "Comuníquela al usuario por un canal seguro. No se mostrará de "
            "nuevo. Deberá cambiarla al iniciar sesión."
        ),
    )


@router.put("/usuarios/{usuario_id}", response_model=UsuarioListItem)
def actualizar_usuario(
    usuario_id: int,
    payload: UsuarioUpdateA5,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """A5.1 — Edita correo, cedula y conductor. NO edita el rol.

    Si el payload trae `rol` (o cualquier campo desconocido) el schema
    responde 422, no lo ignora: un 200 con el campo descartado hace creer al
    cliente que el cambio se aplico, y eso se descubre meses despues. El
    `extra="forbid"` del schema lo cubre. Corregir un rol es desactivar +
    recrear.
    """
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    permitidos = _permitidos_del_ejecutor(current_user)
    if usuario.rol not in permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para editar a este usuario",
        )

    campos = payload.model_dump(exclude_unset=True)

    if "cedula" in campos and campos["cedula"] is not None:
        nueva = campos["cedula"]
        if usuario.conductor_id is not None:
            conductor = db.query(ConductorModel).filter(
                ConductorModel.id == usuario.conductor_id
            ).first()
            if conductor and conductor.cedula != nueva:
                raise HTTPException(
                    status_code=422,
                    detail="La cédula debe coincidir con la del conductor vinculado",
                )
        if db.query(UsuarioModel).filter(
            UsuarioModel.cedula == nueva, UsuarioModel.id != usuario.id
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Ya existe otro usuario con esa cédula"
            )
        usuario.cedula = nueva

    if "correo" in campos:
        nuevo = campos["correo"]
        if nuevo and db.query(UsuarioModel).filter(
            func.lower(UsuarioModel.correo) == nuevo.lower(), UsuarioModel.id != usuario.id
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Ya existe otro usuario con ese correo"
            )
        usuario.correo = nuevo

    if "conductor_id" in campos:
        nuevo_conductor_id = campos["conductor_id"]
        if nuevo_conductor_id is not None:
            conductor = db.query(ConductorModel).filter(
                ConductorModel.id == nuevo_conductor_id
            ).first()
            if conductor is None:
                raise HTTPException(status_code=404, detail="Conductor no encontrado")
            if usuario.cedula and conductor.cedula != usuario.cedula:
                raise HTTPException(
                    status_code=422,
                    detail="La cédula del conductor no coincide con la de la cuenta",
                )
            if db.query(UsuarioModel).filter(
                UsuarioModel.conductor_id == nuevo_conductor_id,
                UsuarioModel.id != usuario.id,
            ).first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El conductor ya está vinculado a otro usuario",
                )
        usuario.conductor_id = nuevo_conductor_id

    # Solo los NOMBRES de los campos, nunca sus valores: un cambio de correo
    # pondria la direccion en el rastro, que no es un secreto pero no aporta.
    registrar_auditoria(
        db,
        "usuario_editado",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
        detalle={"campos": sorted(campos.keys())},
    )
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post(
    "/usuarios/{usuario_id}/activar",
    response_model=UsuarioAccionResponse,
    dependencies=[Depends(RoleChecker(ROLES_ADMIN))],
)
def activar_usuario(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    """A5.1 — Reactiva una cuenta desactivada. Solo admin.

    Sin este endpoint una cuenta desactivada era terminal desde la API: un
    conductor que se va y vuelve no tenia forma de recuperar el acceso sin
    tocar la base. Reactivar es mas privilegiado que crear (devuelve acceso
    a alguien que ya no lo tiene), asi que se reserva a admin igual que
    desactivar y degradar.
    """
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El usuario ya está activo"
        )

    usuario.activo = True
    registrar_auditoria(
        db,
        "usuario_activado",
        actor_id=current_user.id,
        objetivo_id=usuario.id,
        ip=obtener_ip(request),
        user_agent=obtener_user_agent(request),
    )
    db.commit()
    return UsuarioAccionResponse(
        usuario_id=usuario.id,
        activo=True,
        rol=usuario.rol,
        era_ultimo_admin=False,
        mensaje="Cuenta reactivada. Quedó auditado.",
    )
