---
name: Security Auth
description: Procedimiento para revisar o cambiar autenticación, permisos, recuperación de credenciales, rate limiting o datos personales. Usar SIEMPRE que un cambio toque sesiones, roles, tokens o credenciales.
---

# Revisar y cambiar auth sin romper garantías

## Paso 0 — el interceptor de 401

Antes de tocar auth, verificar `frontend/src/api/client.ts`.

Dos endpoints devuelven **401 legítimamente** —token/código inválido, no sesión expirada—:
`/auth/reset-password` y `/auth/reset-codigo`. **Deben** estar en la lista de exclusión del
interceptor. Si no lo están: el 401 dispara un refresh que no puede tener éxito (pantalla
pública, sin sesión), cae en `clearSession()` y expulsa a `/login` **sin mostrar el error**.

## Las tres capas, y por qué se tocan por separado

| Capa | Dónde | Qué garantiza |
|---|---|---|
| Autenticación | `deps.py:get_current_user` | JWT válido, `activo`, `password_version` coincide |
| Primer login | `deps.py:exigir_contrasena_actualizada` vía `PROTEGIDOS` en `api.py:15-27` | 403 + `X-Celr-Requiere-Cambio` |
| Autorización | `deps.py:RoleChecker([...])` | El rol puede operar esto |

**`auth` y `municipios` están exentos de la capa 2, a propósito.** El flujo de cambio forzado
necesita `/auth/me` y `/auth/cambio-contrasena`. No los agregues sin entender por qué.

## Checklist de revisión

- [ ] ¿Se puede **enumerar** la existencia de una cuenta? Status, mensaje o timing.
- [ ] ¿El rate limit está keyeado por algo **canónico**? (`usuario:{id}`, no el texto del cliente)
- [ ] ¿Cambiar la credencial invalida las sesiones abiertas? (`password_version` sube)
- [ ] ¿La auto-acción está bloqueada donde corresponde?
- [ ] ¿Un rol nuevo quedó con permisos que no le corresponden?
- [ ] ¿El log nuevo escribe una credencial, un token o un código?
- [ ] ¿La UI puede **revertir** una garantía del backend por una decisión de presentación?

## Garantías que no se revierten sin ADR

| Garantía | Consecuencia si se rompe |
|---|---|
| Login con mensaje genérico | Enumeración de usuarios. |
| `forgot-password` **siempre 200 con el mismo texto** | Oráculo de enumeración (ADR-0003). |
| `reset-password`/`reset-codigo`: **401 genérico único** | Distinguir "no existe" de "expiró" también filtra. |
| Token de reset **nunca** en claro en la BD | Toma de cuentas. |
| Rate limit por `usuario:{id}` canónico | Rotar identificador limpia la cubeta (ADR-0001). |
| `password_version` en el JWT | Cambiar la clave no invalida sesiones. |
| Auto-acción bloqueada (4 endpoints) | El sistema puede quedar sin admins (ADR-0005). |
| Credenciales nunca en logs ni en `auditoria_evento.detalle` | El rastro se vuelve vector de robo. |

**Cubetas separadas** para `forgot:` y `reset-codigo:`: un usuario bloqueado por fallar el login
es justamente quien más necesita pedir un reset.

## La superficie de ataque es el frontend

El backend puede responder perfecto y la UI **descartar** la respuesta. Pasó 5 veces. Por cada
`catch` nuevo: **¿dónde ve esto el usuario?**

Y el camino inverso: un 401 de token es un **401 legítimo**, no una sesión expirada. Confundir
los dos es un logout forzado.

## Procedimiento de cambio

1. Releer `docs/04-decisions/ADR-0001`, `-0002`, `-0003`, `-0005`.
2. Verificar el enum de roles y su CHECK: `core/roles.py`. **Derivar de `RolUsuario`, nunca
   literales sueltos** — un rol huérfano en un `RoleChecker` pasa el typecheck y no existe.
3. Si agregás un endpoint protegido por rol, agregá el caso a `test_rbac.py`.
4. Si tocás el interceptor, probá **el camino de error**, no solo el feliz.
5. Suites: `test_auth.py` (TA-ID-*), `test_rbac.py`, `test_primer_login.py` (TA-FL-*),
   `test_password_reset.py` (TR-*), `test_reset_asistido.py` (TRA-*), `test_reset_codigo.py` (TRC-*),
   `test_auditoria.py` (TAUD-*), `test_ultimo_admin.py` (TUA-*), `test_usuarios_crud.py` (TUC-*).

Detalle: `docs/00-context/BUSINESS.md`, `docs/02-domain/GLOSSARY.md`.
