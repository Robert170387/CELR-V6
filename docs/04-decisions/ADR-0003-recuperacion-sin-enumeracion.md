# ADR-0003 — Recuperación de contraseña que no revela existencia de cuentas

**Estado:** ACEPTADA
**Fecha:** 2026-09-25
**Decide:** usuario
**Ámbito:** seguridad

## Contexto

El login ya devuelve `"Credenciales incorrectas"` tanto para usuario inexistente como para
contraseña incorrecta. `POST /auth/forgot-password` es un endpoint **público** que recibe un
identificador y dice qué hacer con él.

**Evidencia:** `app/api/v1/endpoints/auth.py:200-259`. La constante del mensaje está en
`auth.py:48`.

## Problema

Un endpoint público que responde distinto según el usuario exista es un **oráculo de
enumeración**. Con él, cualquiera puede barrer el sistema y obtener el padrón de cuentas, sus
correos y quién tiene cuenta.

El riesgo no es teórico: el corpus de cédulas colombianas es enumerable y los correos
corporativos se adivinan por patrón.

## Opciones

1. **Respuesta genérica idéntica** siempre (elegida).
2. 404 "usuario no encontrado".
3. 200 genérico, pero **más lento** si no existe (timing side-channel).
4. 200 genérico en backend, y la UI_avisa "revisá tu correo" solo si se envió.

## Decisión

**Siempre 200, siempre el mismo texto**, exista o no la cuenta:

```python
MSG_RESET_GENERICO = "Si el identificador existe, se enviara un enlace de recuperacion."
```

Se descarten también las opciones 3 y 4:
- **3**: el timing es filtrable y no agregaba nada real.
- **4**: la UI es el mismo sistema. Si la UI confirma, la garantía se pierde igual. **La
  enumeración no se arregla en un lado y se rompe en el otro.**

### Consecuencia aceptada, y es la importante

> **Una cuenta sin correo registrado no tiene recuperación por sí sola, y no se le puede
> avisar.** Pedir un enlace y no recibir nada es indistinguible de pedir uno por una cuenta
> inexistente. Es el precio de no filtrar el padrón de cuentas.

Su salida es el **código offline** (lo genera un admin) o el **reset asistido** del admin.
La pantalla de recuperación ofrece el enlace al código offline de forma estática — sin
condicional, sin revelar nada.

## Consecuencias

**Positivas**

- El endpoint no sirve para enumerar cuentas, correos ni roles.
- Nada que "arreglar" después: la UI ya no puede romperlo.

**Negativas / costo aceptado**

- UX peor para el caso legítimo sin correo: el usuario queda sin salida y sin explicación.
- La auditoría tampoco escribe fila cuando el identificador no resuelve
  (`password_reset_solicitado` solo se registra si el usuario existe), para que la **tabla de
  auditoría no sea un segundo canal de enumeración**. Costo: no hay registro de los intentos
  fallidos de recuperación.

**Fuera de alcance**

- Rate limiter distribuido (B4).
- Rate limit por IP confiable: hoy `client.host` es la IP del proxy detrás de Render.

## Alternativas descartadas

| Opción | Por qué no |
|---|---|
| 404 "no encontrado" | Oráculo de enumeración directo. |
| Confirmar en la UI | La UI es parte del mismo sistema: romper la garantía es inmediato. |
| Delay artificial | Filtrable, y no agrega nada frente al resto de medidas. |
| Registrar todo intento en auditoría | La tabla pasa a ser un segundo canal de enumeración. |

## Restricciones de implementación

- El **texto del mensaje sale del backend** (`MSG_RESET_GENERICO`) y la UI lo muestra tal cual.
  **Nunca hardcodearlo en el frontend ni "mejorarlo"**: un texto más específico reintroduce el
  oráculo.
- La respuesta de `forgot-password` es idéntica en cuerpo y status. No agregar campos.
- `POST /auth/reset-password` y `/auth/reset-codigo` devuelven **401 genérico único** para
  token/código inválido, expirado, revocado o ya usado. No distinguirlos: un 404 para "no
  existe" y un 401 para "expiró" también filtran.
- **Estas rutas devuelven 401 legítimamente.** El interceptor global de 401 de
  `frontend/src/api/client.ts` debe excluirlas o intentará refrescar la sesión, y en una
  pantalla pública no hay token ⇒ expulsa a `/login` y el usuario nunca ve el error. Ya está
  excluido; **no quitarlo**.

## Pruebas requeridas

- `test_password_reset.py` (TR-1..TR-13) — respuesta genérica sin enumerar cuentas, expiración,
  uso único, revocación del anterior, buckets de rate limit separados, guard 503 en producción.
- `test_reset_codigo.py` (TRC-1..TRC-16) — 401 genérico, agotamiento de intentos, el código nunca
  en logs ni en claro en la BD.
