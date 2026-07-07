# PersAcc Backend (FastAPI)

API REST que reutiliza la capa de dominio de `src/` (database, business_logic,
config, models). No duplica lógica. Usa `data/finanzas.db` tal cual.

## Arranque (desde la raíz del proyecto)

```bash
# 1. Backend  (http://localhost:8001, docs en /docs)
.venv/Scripts/python.exe -m uvicorn server:app --app-dir backend --port 8001 --reload

# 2. Frontend (http://localhost:5174, proxy /api -> 8001)
pnpm --dir frontend dev --port 5174
```

Instalar deps la primera vez:

```bash
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
pnpm --dir frontend install
```

## Tests

```bash
.venv/Scripts/python.exe -m pytest backend/tests -q
```

Los tests de paridad (`test_api_parity.py`) verifican que la API devuelve
exactamente lo que calcula `business_logic` sobre la DB real y que los meses
cerrados son inmutables.

## Producción (un proceso)

```bash
# Compila el frontend y sírvelo desde el backend:
pnpm --dir ../frontend build
uvicorn server:app --app-dir . --port 8001   # sirve API + frontend/dist
```

O directamente `../run.ps1` desde la raíz.

## Estado

Migración completa (Fase 1-6): config, categorías, ledger CRUD, dashboard, cierre
(preview/execute), histórico anual, notas, export CSV, IA Ollama (comentario, análisis,
chat NL), proyecciones SARIMAX, importación bancaria (N43/SEPA/Excel) + Notion.

La app Streamlit original está en `../legacy/`. Ver `../MIGRATION_PLAN.md`.
