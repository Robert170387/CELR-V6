# GATES.md — calidad

Fuente operativa completa: [`../../INSTRUCCIONES_OPENCODE.md`](../../INSTRUCCIONES_OPENCODE.md)
§3–§4. Este documento es el **resumen accionable** y las seis normas, que son lo que más
se olvida. Las cuatro primeras viven también en `INSTRUCCIONES §4`; las dos de
verificación (5 y 6) son **solo de este archivo** — si allá no están, es lo esperado.

## Los cuatro gates

| Gate | Comando | Verde cuando |
|---|---|---|
| **Suite** | 21 × `venv\Scripts\python.exe scripts\test_<suite>.py` desde `backend/` | 21/21 |
| **Humo** | `venv\Scripts\python.exe scripts\smoke.py` | `[SMOKE OK]` |
| **E2E** | `venv\Scripts\python.exe ..\scripts\e2e_flow_test.py` (servidor vivo) | 5/5 |
| **Frontend** | `npm.cmd run build` en `frontend/` | exit 0, sin warnings |

```powershell
# Windows — el pipe rompe los caracteres ✓/✗ con cp1252
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql://postgres:admin@localhost:5433/celr_v6_db"
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

**El conteo se verifica contra el disco**, no contra la documentación:
`(Get-ChildItem backend\scripts\test_*.py).Count` → **21**. La etiqueta "suite N" es
histórica y no cubre todos los archivos; ya dio 18 cuando había 19.

### Regla de los lotes

Correr en **lotes de 5** con `timeout: 900000`. Nunca aceptar "15 + 1" por corte de timeout:
eso es un timeout, no un resultado.

## Gate de migración (obligatorio antes de commitear)

```powershell
venv\Scripts\python.exe scripts\test_fresh_db.py
```

Crea y destruye **únicamente** `celr_v6_fresh_test`. Valida `upgrade head` → `downgrade base`
→ `upgrade head` (TM1–TM9). **Nunca toca `celr_v6_db`.**

**Actualizar `test_fresh_db.HEAD_REVISION`** al agregar una revisión, o la precondición aborta
antes de empezar. Síntoma: `Precondición fallida: alembic_version=...`.

`test_a1_guard_downgrade.py` es la excepción equivalente para el guard de A1: crea y destruye
`celr_v6_a1_guard_test` y verifica que el `downgrade()` **aborte** si hay `correo=NULL`.

---

# Las cuatro normas

Cada una costó un incidente. No son consejos.

## 1. Fallo silencioso prohibido

Todo `catch` debe **registrar el error e informar al usuario**. Nunca cerrar un camino de error
sin dejar rastro visible.

**La subclase peligrosa: el 403 descartado en la UI.** El endpoint se comportó bien, la capa de
presentación lo tira, y **ningún test de endpoint lo detecta**. Ocurrió 5 veces:

| Dónde | Qué pasaba |
|---|---|
| A4 | `debe_cambiar_contrasena` se escribía pero no bloqueaba nada. |
| A3.3 | `registrar_intento_fallido` existía y nadie la llamaba: `intentos_max` no se aplicaba. |
| A5.3 | `setErrorModal` pintado fuera de todo modal ⇒ **403 invisible**. |
| A5.3 | `catch` mudo en `writeText` ⇒ clic sin señal. |
| **A5.4** | El interceptor de 401 veía "token inválido" como "sesión expirada", intentaba refrescar, fallaba y **expulsaba a `/login` sin mostrar el error**. |

**Cómo se previene:** preguntarse, por cada `catch`, *¿dónde ve esto el usuario?* Si la respuesta
es "en ningún lado", el código está mal.

## 2. Campo o función sin consumidor, prohibido

Todo campo nuevo necesita un lector real, toda función nueva un caller, todo estado (`setX`) una
UI que lo lea. Si es "reservado para fase X", se marca explícitamente en el código.

Ocurrió con `debe_cambiar_contrasena`, `registrar_intento_fallido`, `temporal.mensaje` /
`codigo.mensaje` (el backend los mandaba y el JSX los tenía hardcodeados), y el check de
"Copiado" que era **código muerto** porque leía un campo que solo se escribía en `false`.

Es la misma raíz que la norma 1: un valor que se escribe y nadie lee es **seguridad decorativa**.

## 3. Baseline absoluto en app DB, prohibido

Ningún test puede afirmar conteos globales (`usuarios=7`, `gastos=37`, `ConductorModel.id == 2`).

La BD de desarrollo acumula datos reales y otras suites borran lo que crean. Un assert así **pasa
en una BD limpia y falla con el uso diario**: el gate se pone rojo sin que nadie haya tocado el
código.

Los tests miden **delta** (snapshot antes/después), filtran por sus propias filas, o construyen un
**escenario controlado** y lo restauran.

Afectó a: `test_fresh_db`, `smoke.py`, `test_flypass_list`, `test_reset_asistido` (TRA-13),
`test_ultimo_admin` (TUA-2), `test_usuarios_crud` (TUC-9).

**Patrón de referencia** — `test_ultimo_admin` neutraliza los admins ajenos y los restaura:

```python
ajenos = [...]                      # snapshot
if ajenos: ...activo=False...       # neutralizar
try:
    assert contar_admins_activos(db) == 1
    assert es_ultimo_admin_activo(db, meta.id) is True
finally:
    ...activo=True...               # restaurar SIEMPRE
```

## 4. La trampa del service worker

Al verificar cambios de UI, el SW puede servir el **bundle viejo** y producir un falso
"el fix no funciona".

**Siempre `Ctrl+Shift+R`**, o desregistrar el SW en DevTools → Application → Service Workers,
antes de concluir que un cambio de frontend no surtió efecto. Ya mordió dos veces.

---

# Las dos normas de verificación

Las cuatro anteriores son **normas de defecto**: describen una clase de fallo que ya
ocurrió. Estas dos son **normas de verificación**: un check que hay que hacer *antes* de
escribir, para no descubrir tarde que lo que se iba a usar no existe.

## 5. Verificar los nombres antes de escribir un gate

Un gate que dice "correr `docker compose build <servicio>`" se escribe contra un nombre
**verificado**, nunca de memoria:

```powershell
docker compose config --services    # los nombres reales, de una
```

**Bug detectado (R1-pre-2, 2026-09-26).** El gate decía `docker compose build web`. El
servicio se llama **`frontend`**. El comando falló con `no such service: web`, pero el
filtro de captura de salida (`Select-String "Built|ERROR"`) **se comió el error**, y el
HTTP 200 siguiente era del contenedor viejo sirviendo el bundle viejo. **El gate
reportó verde sin haber corrido nada.**

Es la tercera vez con la misma forma — un check con la especificidad justa para pasar y
la ceguera justa para no detectar. Las otras dos: un `grep ^## D\d` que por diseño no
veía D8, y un `git commit -F` con redirección de PowerShell que corrompió acentos en
silencio.

**El generalizador:** un filtro de salida también es un check. Si el filtro solo deja
pasar la palabra esperada, no verifica nada — **oculta justamente el fallo que le
corresponde ver**: un error cuyo mensaje no contiene ninguna de las palabras buscadas.
Nunca dar por bueno un comando porque su filtro salió limpio: **el filtro decide qué
errores son invisibles.**

## 6. Verificar que la API exista, no solo su forma

Antes de usar un símbolo importado — `EmailStr`, un icono, una función de librería —
**verificarlo contra el paquete instalado**. La forma del nombre no dice nada.

```powershell
# ejemplo: el icono existe, pero con otro nombre
Select-String -Path "node_modules\lucide-react\dist\lucide-react.d.ts" -Pattern "declare const AlertTriangle\b" -Quiet
```

**Bug detectado (R1-pre-2, 2026-09-26).** El spec pedía `AlertTriangle`; en
`lucide-react@0.414.0` ese nombre **no existe** — el real es `TriangleAlert`. El build
fallaba. Precedente de la misma clase: `EmailStr` importado sin que `email-validator`
estuviera instalado, que tumbaba `app.main`.

**Y el hermano silencioso: `httpx2` en `requirements.txt`.** No es un símbolo, es un
nombre de paquete. `httpx2` **existe en PyPI** — por eso `pip install` nunca falló y
nadie lo notó — pero arrastra `httpcore2` y no sirve para `fastapi.testclient.TestClient`,
que es lo que el comentario de esa misma línea decía. Un nombre mal escrito que **resuelve
a algo real** es peor que uno que no resuelve: el primero instala el error sin queja.

**Regla:** el mismo check aplica a paquetes, iconos, clases de pydantic y helpers de
librería. Si el nombre no está en el artefacto instalado, no existe.

> **Duplicación deliberada.** Las normas 1–4 están en `INSTRUCCIONES_OPENCODE.md` §4 con
> su evidencia. La 5 y la 6 **no** se copian allá todavía: `INSTRUCCIONES` ya tiene
> pendientes sin commitear de esta sesión, y anexar ahí mezclaría dos cambios. Cuando
> Commit B cierre, la 5 y la 6 deben pasar también a `INSTRUCCIONES §4` para que un agente
> que solo lea ese archivo no se las pierda.

---

## Limpieza de datos de test

**El orden importa, y olvidarlo falla en silencio.**

1. `refresh_tokens.usuario_id` es FK a `usuarios.id` **sin CASCADE**. Un `DELETE FROM usuarios`
   se **rechaza**, y los contadores de los demás statements del cleanup se leen como éxito.
2. **Borrar en orden inverso de FK** y **dentro de una transacción**.
3. **Verificar después**, no asumir.
4. Rastrear temporales por **`id`**, nunca por `correo`: con `correo` nullable, un temporal sin
   correo tiene `correo IS NULL` y no se encuentra nunca, dejando su `cedula` (UNIQUE parcial)
   plantada y rompiendo la corrida siguiente.
5. **Nunca** borrar filas de `auditoria_evento` para cuadrar un gate. Es append-only.

```sql
BEGIN;
DELETE FROM password_reset_token WHERE usuario_id = :id;
DELETE FROM refresh_tokens        WHERE usuario_id = :id;
DELETE FROM usuarios              WHERE id = :id;
COMMIT;
-- y después VERIFICAR
```

## Lo que nunca es un gate

- `verify_seed.py` — no es `test_*.py`. **Solo válido en BD recién sembrada**; con la BD de
  desarrollo falla a propósito. No convertirlo a delta: su valor es detectar un seed a medias.
- `verify_models.py` — chequeo de mapeo ORM. Útil como diagnóstico, no como gate de entrega.

## Antes de commitear

- [ ] Los 4 gates verdes **con los datos reales presentes**.
- [ ] `git diff --check` sin errores.
- [ ] El diff **revisado**, no solo el exit code. Un gate que pasa con un assert que no prueba
      lo que dice es peor que uno rojo.
- [ ] La documentación afectada actualizada en el **mismo** commit.
- [ ] Si tocaste migraciones: `test_fresh_db.py` y `HEAD_REVISION` al día.
- [ ] Si tocaste UI: verificado **por render**, y el camino de error primero.
- [ ] Los nombres usados en un comando de gate, **verificados** (norma 5): un filtro de
      salida que se comió el error no cuenta como verificación.
- [ ] Todo símbolo importado nuevo, **existente** en el paquete instalado (norma 6).
