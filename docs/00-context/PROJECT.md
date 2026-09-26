# PROJECT.md — qué es CELR v6

## En una frase

**FACT.** Aplicación web para gestionar una flota de trucks de carga en Colombia:
ODTs, gastos, ingresos, liquidaciones a conductores, mantenimiento, peajes y control de
nóminas — con control de acceso por rol y soporte de trabajo sin conexión.

## Para quién

| Actor | Qué necesita |
|---|---|
| **Administrador** | Cuentas de usuario, roles, auditoría. Es el único que puede crear cuentas. |
| **Operador** | Registrar viajes, gastos, ingresos. No ve liquidaciones ni puede administrar cuentas de rol alto. |
| **Contador** | Liquidaciones, ingresos,Flypass. |
| **Supervisor** | Maestras (flota, personal, terceros) y operación. |
| **Conductor** | Solo sus viajes y gastos. Es quien más depende del modo sin conexión. |
| **Cliente** | Acceso acotado, sin escritura de operación. |

**FACT** — Los 6 roles son un enum canónico en `backend/app/core/roles.py` (`RolUsuario`)
con CHECK constraint en la BD. No se agregan roles por configuración: se cambian el enum,
el CHECK y la política.

## Stack

**FACT** — Verificado en `backend/requirements.txt`, `frontend/package.json`, `render.yaml`.

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL |
| Frontend | React 18, Vite, TypeScript estricto, Tailwind, PWA (service worker + IndexedDB) |
| Deploy | Render (backend container + sitio estático). GitHub como origen. |
| Tests | Suites Python propias contra la BD real. **No hay pytest.** |

**FACT** — El proyecto está en **español**: identificadores, comentarios, mensajes de error,
nombres de migración y documentación. Es una convención dura, no una preferencia.

## Puertos (no estándar, a propósito)

**FACT** — Elegidos para convivir con otro proyecto en la misma máquina.

| Servicio | Docker | Desarrollo local |
|---|---|---|
| PostgreSQL | `localhost:5433` | igual |
| Backend | `localhost:8001` | `localhost:8000` |
| Frontend | `localhost:5174` (nginx) | Vite en `:3000` |

```
postgresql://postgres:admin@localhost:5433/celr_v6_db
```

## Estructura

```
backend/
  app/
    api/v1/endpoints/   # routers; usuarios.py y auth.py grew en el módulo de identidad
    core/               # config, seguridad, roles, rate limiter
    db/                 # sesión y base declarativa
    models/             # 21 tablas en 6 módulos temáticos
    schemas/            # Pydantic
    services/           # lógica de dominio (no va en los endpoints)
  alembic/versions/     # historial de migraciones
  scripts/              # 21 suites + smoke + verify_* + CLI break-glass
  seed*.py              # base (siempre) y demo (opt-in local)
frontend/src/
  api/                  # cliente axios + métodos por módulo
  components/           # Layout, Pagination, PublicShell, ui/
  context/              # AuthContext, MunicipiosContext
  pages/                # una por pantalla
  utils/                # rbac, format, offlineStore
docs/                   # esta carpeta — memoria persistente
.opencode/              # agentes y skills
scripts/                # E2E (servidor vivo)
```

## Lo que este proyecto **no** tiene

- **No hay pytest.** Las suites son scripts que corren contra la BD real y limpian lo suyo.
- **No hay linter ni formateador** en el frontend. El gate de TS estricto es `tsc -b`.
- **No hay CI.** Los gates los corre el agente o la persona, localmente.
- **No hay `email-validator` instalado.** No usar `pydantic.EmailStr`; rompe la importación
  de `app.main` y tumba el arranque. El validador de correo propio vive en
  `backend/app/schemas/usuario.py`.
- **No hay Alembic `downgrade` de la baseline.** La baseline es `create_all`; revertirla
  no está soportado.

## Reglas del proyecto que no se negocian

Estas están en [`../../AGENTS.md`](../../AGENTS.md) y [`../../INSTRUCCIONES_OPENCODE.md`](../../INSTRUCCIONES_OPENCODE.md).
Se resumen aquí; el detalle y la razón viven allí.

1. **Alembic es el mecanismo de esquema.** `init_db.py` y `scripts/migrate_*.py` son históricos.
2. **Todo campo y función nueva tiene consumidor**, o una marca de "reservado para fase X".
3. **Fallo silencioso prohibido:** todo `catch` registra e informa.
4. **Ningún test afirma conteos globales de la app DB.**
5. **Nunca inventar una regla de negocio.** Si no se puede confirmar: `UNKNOWN`.
6. **Un commit por sub-fase**, mensaje en español.
7. **Antes de afirmar que algo no existe, buscar en el código.** La documentación histórica
   de este repo miente sobre ausencias.

> El punto 7 tiene historia: `AUDITORIA_CELR_v6.md` afirma que no existe recuperación de
> contraseña. Sí existe, y lleva 97 commits de antigüedad el documento.
