from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from datetime import timedelta, datetime, timezone

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.flota import Usuario as UsuarioModel
from app.models.flota import RefreshToken as RefreshTokenModel
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    hash_refresh_token,
    validar_politica_contrasena,
)
from app.core.config import settings
from app.core.rate_limiter import excede_limite, registrar_fallo, limpiar_fallos
from app.services.auth import resolver_usuario_por_identificador
from app.services.email import get_email_backend
from app.services.password_reset import (
    generar_token_reset,
    marcar_token_consumido,
    registrar_intento_fallido,
    ttl_por_tipo,
    usuario_por_id,
    validar_token_reset,
)
from app.schemas.usuario import UsuarioLogin, UsuarioResponse
from app.schemas.token import (
    Token,
    RefreshRequest,
    LogoutRequest,
    CambioContrasenaRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ResetCodigoRequest,
)

router = APIRouter()

# A3.1 — Mensaje unico de forgot-password. Es la MISMA respuesta exista o no la
# cuenta: cualquier diferencia permitiria enumerar quienes tienen usuario.
MSG_RESET_GENERICO = "Si el identificador existe, se enviara un enlace de recuperacion."


@router.post("/auth/login", response_model=Token)
def login(login_data: UsuarioLogin, db: Session = Depends(get_db)):
    """A2 (D1): login por `identificador` (cedula o correo).

    `correo` se acepta como alias legacy. Si llegan ambos, `identificador` manda.
    """
    identificador = login_data.identificador or login_data.correo or ""
    clave = identificador.strip().lower()

    db_usuario = resolver_usuario_por_identificador(db, identificador)
    # A2: canonizar el rate limit por cuenta, no por puerta de entrada. Sin esto,
    # entrar por cedula o por correo abriria dos cubetas independientes para la
    # MISMA cuenta (10 intentos en vez de 5). Se resuelve primero y se consulta
    # UNA sola cubeta: la del usuario si existe, o la del identificador si no.
    # Asi el limite es 5 por cuenta y no se abre un oraculo de enumeracion (las
    # dos ramas responden 429 al sexto intento, indistinguibles para el atacante).
    clave_usuario = f"usuario:{db_usuario.id}" if db_usuario is not None else None
    clave_efectiva = clave_usuario or clave

    if excede_limite(clave_efectiva):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión. Inténtalo nuevamente en 15 minutos.",
        )
    if db_usuario is None or not verify_password(login_data.contrasena, db_usuario.contrasena_hash):
        # Marca las dos cubetas: la del identificador (por si dejara de resolver,
        # p. ej. tras un reset de contrasena en A3) y la de la cuenta.
        registrar_fallo(clave)
        if clave_usuario:
            registrar_fallo(clave_usuario)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not db_usuario.activo:
        registrar_fallo(clave)
        registrar_fallo(clave_usuario)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    # Exito: limpiar las dos cubetas para no arrastrar historial de otra puerta.
    limpiar_fallos(clave)
    limpiar_fallos(clave_usuario)
    token_data = {
        "usuario_id": db_usuario.id,
        "correo": db_usuario.correo,
        "password_version": db_usuario.password_version,
    }
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(db, db_usuario)
    db_usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/refresh", response_model=Token)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_refresh_token(request.refresh_token)
    registro = db.execute(
        select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
    ).scalar_one_or_none()
    if (
        registro is None
        or registro.revocado
        or registro.expira_en <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db_usuario = db.execute(
        select(UsuarioModel).where(UsuarioModel.id == registro.usuario_id)
    ).scalar_one_or_none()
    if db_usuario is None or not db_usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rotación: revoca el token usado y emite un par nuevo
    registro.revocado = True
    registro.usado_en = datetime.now(timezone.utc)

    new_refresh = create_refresh_token(db, db_usuario)
    token_data = {
        "usuario_id": db_usuario.id,
        "correo": db_usuario.correo,
        "password_version": db_usuario.password_version,
    }
    new_access = create_access_token(token_data, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    db.commit()
    return Token(access_token=new_access, refresh_token=new_refresh)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: LogoutRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(db, hash_refresh_token(request.refresh_token))
    db.commit()
    return None


@router.get("/auth/me", response_model=UsuarioResponse)
def get_current_user_endpoint(current_user: UsuarioModel = Depends(get_current_user)):
    return current_user


@router.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """A3.1 — Pide un enlace de recuperacion. Publico por diseno.

    Siempre responde 200 con el mismo mensaje, exista o no la cuenta: si el
    usuario no existe, ese es el mismo status y ese es el mismo texto. Un 404
    "usuario no encontrado" seria un oraculo de enumeracion de cuentas.

    Rate limit con prefijo propio ('forgot:') y no la clave de login: un usuario
    bloqueado por fallar el login cinco veces es justamente quien mas necesita
    poder pedir un reset. Compartir cubeta lo dejaria sin salida.
    """
    clave = f"forgot:{data.identificador.strip().lower()}"
    if excede_limite(clave):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes de recuperacion. Inténtalo nuevamente en 15 minutos.",
        )
    # Se cuenta CADA peticion, exista o no la cuenta: el limite aqui es anti-abuso
    # (no de credenciales), y la respuesta es 200 en ambos casos. No se limpia en
    # el exito a proposito: si se limpiara, un atacante podria reiniciar el
    # contador alternando un acierto con varios intentos.
    registrar_fallo(clave)

    usuario = resolver_usuario_por_identificador(db, data.identificador)
    if usuario is not None:
        token = generar_token_reset(db, usuario.id, tipo="enlace")
        # Sin correo no hay a quien enviarlo. El token se genera igual (A3.2
        # cubrira estos casos con reset asistido) pero no se finge un envio.
        if usuario.correo:
            enlace = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
            # El TTL del mensaje se lee del mismo lugar que el del token: si se
            # hardcodeara aqui, podria prometer 2 horas con un token de 1.
            horas = int(ttl_por_tipo(db, "enlace").total_seconds() // 3600)
            try:
                get_email_backend().enviar(
                    usuario.correo,
                    "CELR v6 - Recuperacion de contrasena",
                    f"Para restablecer tu contrasena usa este enlace: {enlace}\n"
                    f"El enlace expira en {horas} hora(s).",
                )
            except HTTPException:
                # El backend ya devuelve 503. Solo hay que deshacer el token que
                # se alcanzo a generar: sin rollback, el 503 dejaria un token
                # vivo que nadie recibio y que la sesion de reintento invalidaria.
                db.rollback()
                raise
        db.commit()

    # Sea como sea, la respuesta es identica.
    return {"detail": MSG_RESET_GENERICO}


@router.post("/auth/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """A3.1 — Consume el token y fija la nueva contrasena. Publico por diseno:
    el token es la prueba de que el solicitante tiene el buzon."""
    fila = validar_token_reset(db, data.token, tipo="enlace")
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )

    usuario = usuario_por_id(db, fila.usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )

    # La politica se valida ANTES de consumir: si la contrasena no cumple, el
    # usuario recibe 422 con el motivo y puede reintentar con el mismo token.
    # Consumir primero dejaria el enlace muerto por un simple error de tecleo.
    try:
        validar_politica_contrasena(
            data.nueva_contrasena,
            cedula=usuario.cedula,
            correo=usuario.correo,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    marcar_token_consumido(db, fila)

    usuario.contrasena_hash = hash_password(data.nueva_contrasena)
    # Quien recupera el acceso por buzon ya demostro quien es: no queda pendiente
    # el cambio forzado de la primera vez.
    usuario.debe_cambiar_contrasena = False
    usuario.password_version = (usuario.password_version or 0) + 1
    usuario.ultimo_acceso = datetime.now(timezone.utc)
    # El resto de sesiones abiertas deben caer: la credencial cambio.
    db.execute(
        update(RefreshTokenModel)
        .where(
            RefreshTokenModel.usuario_id == usuario.id,
            RefreshTokenModel.revocado == False,  # noqa: E712
        )
        .values(revocado=True)
    )
    db.commit()
    return {"detail": "Contraseña actualizada"}


@router.post("/auth/reset-codigo")
def reset_con_codigo(
    data: ResetCodigoRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """A3.3 — Canje de un codigo offline de 6 digitos. Publico por diseno.

    El codigo es la prueba. Este endpoint no recibe identificador de usuario, asi
    que la unica defense posible contra adivinar el codigo es el limite por IP.
    OJO: el Dockerfile corre uvicorn SIN `--proxy-headers`, asi que detras de un
    proxy (Render) `client.host` es la IP del proxy y la cubeta se vuelve global.
    Por eso el umbral es alto y configurable en vez de estricto: conviene
    atar el limite que se quiera acuitar, pero no bloquear a todos los usuarios
    por un proxy compartido. Ver deuda 'rate-limit-IP'.
    """
    ip = request.client.host if request.client else "desconocida"
    clave = f"reset-codigo:{ip}"
    if excede_limite(clave):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Inténtalo nuevamente en 15 minutos.",
        )
    registrar_fallo(clave)

    fila = validar_token_reset(db, data.codigo, tipo="codigo")
    if fila is None:
        # Unico 401 para codigo inexistente, expirado, revocado o ya usado: no
        # se distingue, o el endpoint seria un oraculo de que codigos existen.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código inválido o expirado",
        )

    usuario = usuario_por_id(db, fila.usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código inválido o expirado",
        )

    # La politica se valida ANTES de consumir (mismo criterio que A3.1: un error
    # de tecleo no debe matar el codigo). Pero aqui SI se cuenta el intento:
    # el codigo ya es valido y valido, lo que queda por adivinar es la
    # contrasena. `intentos` cuenta eso; marcar_usado() sigue reservandose
    # para el canje exitoso. Al agotar `intentos_max` el codigo se revoca.
    try:
        validar_politica_contrasena(
            data.nueva_contrasena,
            cedula=usuario.cedula,
            correo=usuario.correo,
        )
    except ValueError as e:
        registrar_intento_fallido(db, fila)
        db.commit()
        raise HTTPException(status_code=422, detail=str(e))

    marcar_token_consumido(db, fila)

    usuario.contrasena_hash = hash_password(data.nueva_contrasena)
    usuario.debe_cambiar_contrasena = False
    usuario.password_version = (usuario.password_version or 0) + 1
    usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.execute(
        update(RefreshTokenModel)
        .where(
            RefreshTokenModel.usuario_id == usuario.id,
            RefreshTokenModel.revocado == False,  # noqa: E712
        )
        .values(revocado=True)
    )
    db.commit()
    return {"detail": "Contraseña actualizada. Inicia sesión."}


@router.post("/auth/cambio-contrasena", response_model=Token)
def cambiar_contrasena(
    data: CambioContrasenaRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user),
):
    if not verify_password(data.contrasena_actual, current_user.contrasena_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta",
        )
    # A1: politica de contrasenas (min 8, no igual a cedula/correo, no comun,
    # no un solo caracter repetido). Se valida antes de hashear para no tocar
    # la BD si la contrasena sera rechazada.
    try:
        validar_politica_contrasena(
            data.nueva_contrasena,
            cedula=current_user.cedula,
            correo=current_user.correo,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    current_user.contrasena_hash = hash_password(data.nueva_contrasena)
    current_user.debe_cambiar_contrasena = False
    current_user.ultimo_acceso = datetime.now(timezone.utc)
    # Incrementa password_version: invalida de inmediato (server-side) todos los access
    # tokens emitidos antes del cambio, sin esperar a que expiren (ver deps.get_current_user).
    current_user.password_version = (current_user.password_version or 0) + 1
    # Revoca todos los refresh tokens activos: el resto de sesiones debe volver a iniciar sesión.
    db.execute(
        update(RefreshTokenModel)
        .where(
            RefreshTokenModel.usuario_id == current_user.id,
            RefreshTokenModel.revocado == False,  # noqa: E712
        )
        .values(revocado=True)
    )
    db.flush()  # asegura que password_version esté actualizado antes de leerlo
    # Emite un par de tokens nuevos con la versión ya incrementada: la sesión que acaba
    # de cambiar la contraseña no tiene que volver a iniciar sesión.
    new_refresh = create_refresh_token(db, current_user)
    token_data = {
        "usuario_id": current_user.id,
        "correo": current_user.correo,
        "password_version": current_user.password_version,
    }
    new_access = create_access_token(token_data, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    db.commit()
    return Token(access_token=new_access, refresh_token=new_refresh)