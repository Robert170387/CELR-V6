# ADR-0001 — Rate limit de login keyeado por `usuario:{id}`

**Estado:** ACEPTADA
**Fecha:** 2026-09-25
**Decide:** usuario
**Ámbito:** seguridad

## Contexto

El rate limiter (`backend/app/core/rate_limiter.py`) es un `deque` en memoria: clave → cola de
timestamps de fallo, 5 intentos / 15 min.

Con la identidad canónica ya definida (ADR-0002), el login recibe `identificador` (cédula **o**
correo). La clave del cubeta **no** puede ser el identificador que escribe el usuario.

**Evidencia:** `app/api/v1/endpoints/auth.py:72` computa `clave_efectiva` a partir del
`usuario.id` resuelto, no del texto enviado.

## Problema

Si la clave del cubeta fuera el identificador crudo:

- El atacante rota entre `1234567890`, `1 234 567 890`, `1234567890@x.com` y **`correo@x.com`**
  para obtener cubetas distintas de 5 intentos cada una.
- El bloqueo deja de ser un límite: pasa a ser un obstáculo de tipeo.
- Además, un bucket por identificador permite **enumeración**: Probar N identificadores y ver
  cuáles devuelven 429 revela cuáles existen.

## Opciones

1. **Clave = `usuario:{id}` canónico** (elegida).
2. Clave = identificador normalizado tal como lo envía el cliente.
3. Clave = IP del request.
4. Clave = `usuario:{id}` **y** límite global por IP.

## Decisión

La clave es **`usuario:{id}`**, canónica, después de resolver el usuario.

El conteo se hace **por usuario resuelto**. Un login con identificador inexistente se keyea por
un hash del identificador, para que no colisione con ningún `usuario:{id}` real.

Se **descarta explícitamente** usar solo IP: detrás de un proxy compartido eso bloquearía a
todos los usuarios legítimos a la vez. Y se descarta el par (usuario, IP): multiplica las
cubetas por debajo del umbral y el límite deja de proteger.

## Consecuencias

**Positivas**

- Rotar identificadores no limpia el cubeta.
- **Cierra la enumeración vía 429**: todos los intentos de un atacante caen en pocas cubetas.
- Un usuario bloqueado no puede "desbloquearse" cambiando cómo escribe su cédula.

**Negativas / costo aceptado**

- Un atacante distribuido (muchas IP, un mismo usuario) **sí** puede intentar más de 5 veces.
  Se acepta: mitigado por el límite global pendiente (B4).
- Requiere resolver el usuario **antes** de contar, lo que implica una query por intento.
  Aceptado: es una búsqueda por índice.

**Fuera de alcance**

- Rate limiter distribuido (B4).
- Límite global por IP como segunda capa.

## Alternativas descartadas

| Opción | Por qué no |
|---|---|
| Identificador crudo | Rotable. Anula el límite y abre enumeración. |
| Solo IP | Detrás de Render/proxy compartido bloquea a todos. Además `client.host` es la IP del proxy mientras no se agreguen `--proxy-headers`. |
| Par (usuario, IP) | Multiplica las cubetas y el umbral deja de proteger. |

## Restricciones de implementación

- La clave se computa en `auth.py` **después** de `resolver_usuario_por_identificador`.
- **No** cambiar la clave a algo derivado del texto del request. Es exactamente lo que este
  ADR previene.
- `forgot-password` y `reset-codigo` usan **cubetas separadas** (`forgot:`, `reset-codigo:`).
  Motivo: un usuario bloqueado por fallar el login es justamente quien más necesita pedir un
  reset; compartir cubeta lo dejaría sin salida.

## Pruebas requeridas

- `test_auth.py` — TA-ID-9: rate limit por identificador inexistente (5+1) → 429.
- `test_password_reset.py` — buckets separados entre login y `forgot-password`.

**Brecha declarada:** no hay suite que pruebe explícitamente que **rotar el identificador no
limpia la cubeta**. Es la razón de ser de este ADR y debería tener test propio. Ver
`docs/05-tasks/BACKLOG.md`.
