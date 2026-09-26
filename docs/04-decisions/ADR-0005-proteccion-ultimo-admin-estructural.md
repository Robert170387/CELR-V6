# ADR-0005 — Protección del último admin como garantía estructural, no como bandera

**Estado:** ACEPTADA
**Fecha:** 2026-09-25
**Decide:** usuario
**Ámbito:** seguridad, dominio

## Contexto

`POST /usuarios/{id}/desactivar` y `/degradar` son endpoints admin. Una cuenta mal procesada
podría dejar el sistema **sin ninguna forma de administrar cuentas**, incluido el ability de
resetear contraseñas y de crear el usuario perdido.

La amenaza real no es un atacante: es un operador que desactiva al último admin por error.

**Evidencia:** `app/api/v1/endpoints/usuarios.py:310-319` (`_resolver_para_accion`).

## Problema

La solución obvia es una bandera: calcular si el objetivo es el último admin y **rechazar** el
borrado. Es lo que se implementó primero y tiene un defecto: **por diseño, nunca se dispara.**

## El hallazgo

`era_ultimo_admin=True` es **inalcanzable por la API**. Razón:

1. Para desactivar al último admin, el ejecutor tiene que ser un admin activo.
2. Si el ejecutor es admin **activo** y distinto del objetivo, entonces **hay al menos dos
   admins activos**, así que el objetivo no es el último.
3. Si el objetivo **es** el ejecutor, el auto-acción está bloqueado (403).
4. Los dos casos juntos ⇒ la condición nunca se cumple.

Es decir: la bandera de "último admin" no es una defensa, es decorativa. **Da sensación de
seguridad sin dar seguridad.** Es el mismo patrón que un campo escrito y nunca leído, que en
este proyecto ya costó dos veces.

## Opciones

1. **Bloqueo duro** cuando el objetivo es el último admin.
2. **Permitir con confirmación explícita + auditoría** (elegida).
3. Solo la bandera informativa, sin cambiar nada.

## Decisión

Se eligió la opción 2, y la garantía se separan en dos capas con responsabilidades distintas:

| Capa | Garantía | Cómo se verifica |
|---|---|---|
| **Estructural** | La API **no puede** llegar a 0 admins activos | Invariante: el ejecutor es siempre admin activo + auto-acción bloqueada |
| **Humana** | El operador que va a hacer algo irreversible lo confirma escribiendo el identificador del objetivo | `confirmacion` debe coincidir con cédula o correo; 422 si no |

Se **descarta la opción 1** (bloqueo duro) porque: el bloqueo duro convertiría un error operativo
en una situacion irrecuperable, y ante un admin bloqueado solo queda el CLI de servidor. Un bloqueo
duro que obliga a entrar por consola es peor que una confirmación.

Se **descarta la opción 3**: era el estado inicial y es justo la que da seguridad decorativa.

**Consecuencia aceptada:** el sistema **permite** quedarse sin admins activos **si un humano
confirma dos veces**. La red es la confirmación, no el código.

## Consecuencias

**Positivas**

- Nunca se pierde el acceso por error: siempre queda una vía (confirmación en UI o CLI).
- Toda acción irreversible queda **auditada** con quién, a quién, y con qué confirmación.
- La bandera `era_ultimo_admin` se mantiene en la respuesta: es informativa, y algún día otro
  rol puede_ENABLED el permiso y volverla alcanzable.

**Negativas / costo aceptado**

- Un admin determined puede quedarse fuera del sistema. Mitigación: `scripts/admin_reset.py`,
  CLI de servidor, **solo contraseñas**, dry-run por defecto, con `--execute` explícito.
- La "protección" es parcialmente humana. **Es un compromiso consciente**, no un descuido.

**Fuera de alcance**

- Rotación de credenciales del último admin.
- Alertas al quedarse con un solo admin.

## Alternativas descartadas

| Opción | Por qué no |
|---|---|
| Bloqueo duro (409) | Vuelve irrecuperable un error operativo; obliga a consola. |
| Solo la bandera | Seguridad decorativa. Era el diseño inicial y se descartó por eso. |
| Un segundo admin obligatorio en el seed | El seed crea **un** admin. Obligar a más complica el bootstrap sin agregar seguridad real. |

## Restricciones de implementación

- `_resolver_para_accion` (desactivar, degradar) y `_resolver_objetivo` (reset-password,
  reset-codigo) **deben** rechazar el auto-acción con 403. Es lo que hace estructuralmente
  imposible llegar a 0 admins.
- El helper `es_ultimo_admin_activo` se **prueba a nivel de servicio**, construyendo el estado a
  mano. La API no alcanza ese caso, y el test tiene que decirlo explícitamente para que nadie
  lea un test verde como "la API lo cubre".
- **`conteo-admins-cache`:** `es_ultimo_admin_activo` hace COUNT en cada llamada. Hoy es correcto
  y barato. Candidato a índice parcial `WHERE rol='admin' AND activo` si el volumen lo justifica.
  **No** cachear el resultado entre requests: el conteo se usa para decidir y una caché
  desactualizada habilitaría el borrado peligroso.

## Pruebas requeridas

- `test_ultimo_admin.py` (TUA-1..TUA-12) — invariante de la API, auto-acción bloqueada, TUA-2
  construye el estado a mano para probar el helper, break-glass CLI **por subprocess**.

> **Nota sobre TUA-2:** el test neutraliza temporalmente los admins ajenos (snapshot →
> desactivar → afirmar → restaurar) porque el helper cuenta admins de **toda** la base. Sin eso,
> una cuenta real creada a mano rompe el test. Es la norma "nada de baseline absoluto" aplicada
> — ver `docs/06-quality/GATES.md`.
