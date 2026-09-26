---
name: Release Git
description: Procedimiento para commitear, pushear y cerrar una sub-fase en CELR v6. Usar al cerrar trabajo, antes de un commit, o cuando haya que dejar el repositorio sincronizado.
---

# Commit y cierre de sub-fase

## La regla del mensaje

> **Prepará el mensaje con la herramienta de escritura. NUNCA `git commit -F` con redirección
> de PowerShell.**

```powershell
# MAL — corrompe acentos y mete BOM
git commit -F C:\ruta\mensaje.txt > $null
Get-Content msg.txt | git commit -F -

# BIEN
git commit --file "C:\ruta\mensaje.txt"
```

El proyecto es **en español con acentos**. Un mensaje con `é` o con BOM visible es un
defecto, no un detalle.

## Estructura de un commit

```
tipo(ámbito): descripción en imperativo, minúscula, sin punto

Cuerpo: qué cambió y POR QUÉ. Los "por qué" valen más que los "qué".

Refs: ADR, suite o incidente relacionado.
```

Tipos en uso: `feat`, `fix`, `docs`, `chore`.

## Antes de commitear

```powershell
$env:PYTHONPATH="."; $env:DATABASE_URL="postgresql://postgres:admin@localhost:5433/celr_v6_db"
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"

cd backend
venv\Scripts\python.exe scripts\test_fresh_db.py   # si tocaste migraciones
# 21 suites en LOTES DE 5, timeout amplio
venv\Scripts\python.exe scripts\smoke.py
$env:CELR_BASE_URL="http://localhost:8001"
venv\Scripts\python.exe ..\scripts\e2e_flow_test.py
cd ..\frontend; npm.cmd run build
cd ..

git diff --check
git status --short
git diff --stat
```

- [ ] Los 4 gates verdes **con los datos reales presentes**.
- [ ] `git diff --check` limpio.
- [ ] **El diff leído**, no solo el exit code. Un gate que pasa con un assert que no prueba lo
      que dice es peor que uno rojo.
- [ ] Documentación actualizada **en el mismo commit**.
- [ ] Baseline preservado. Releé los conteos; no los asumas.
- [ ] Sin `??` de archivos que no te pertenecen.

## Un commit por sub-fase

No mezclar. Si el diff toca backend **y** docs de otro tema, son dos commits.

## Push

```powershell
git push origin main:fase-a2-fase-2-local
git rev-list --left-right --count origin/fase-a2-fase-2-local...main   # esperado 0 0
```

**Nunca `git push` a `main` sin que lo pidan** (requiere PAT del usuario). El backup
`origin/fase-a2-fase-2-local` se mantiene al día con `main` local tras cada sesión.

## Baseline — leer, no asumir

```powershell
docker exec celr_v6_db psql -U postgres -d celr_v6_db -P pager=off -c "SELECT ..."
```

| Tabla | Qué mirar |
|---|---|
| `usuarios` | Total, inactivos, admins activos. **Puede haber cuentas reales del usuario.** |
| `viajes_odt` | Viajes (el E2E con `--purge` los limpia). |
| `password_reset_token` | **Puede tener filas legítimas** de un código pedido a mano. No las borres. |
| `refresh_tokens` | Solo el activo que corresponde. |
| `auditoria_evento` | **Nunca** la limpies. Es append-only. |

**Cuidado con los subqueries de una fila que devuelven varias:** abortan el comando y la
salida parcial se lee como éxito. Usá un `SELECT` separado.

**Cuidado con el orden de borrado:** `refresh_tokens.usuario_id` es FK a `usuarios.id` sin
CASCADE. Un `DELETE FROM usuarios` se rechaza **en silencio** para los demás statements.
Verificá después de limpiar.

## Cerrar la sesión

1. Actualizar `docs/00-context/CURRENT.md` si cambió el estado.
2. Actualizar `SESSION-HANDOFF.md` con la plantilla del repo.
3. Si hubo decisión: **ADR** en `docs/04-decisions/`.
4. Reportar: hash, `git diff --stat`, gates, **y qué NO se pudo hacer**. Un "OK las 3" cuando
   solo se hicieron 2 es el peor resultado posible.
