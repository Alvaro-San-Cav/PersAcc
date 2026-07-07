# PersAcc — Plan de Migración a Stack Moderno

> Objetivo: sustituir la app Streamlit actual por una arquitectura **FastAPI + React** idéntica en espíritu a la de `Global-Position`, migrando todos los datos y funcionalidades existentes.

## 1. Situación actual vs. destino

| | Actual (PersAcc v3.2) | Destino |
|---|---|---|
| UI | Streamlit (monolito `app.py` + `src/ui/*.py`) | React 19 + TypeScript + Vite |
| Estilos | CSS inyectado (`styles.py`) | Tailwind CSS 4 + shadcn/ui (Radix) |
| Backend | Lógica mezclada con UI | FastAPI (`server.py`) con modelos Pydantic |
| Estado/datos UI | `st.session_state` + disk_cache pickle | TanStack Query (cache + invalidación) |
| Gráficos | Plotly | Recharts |
| DB | SQLite (`data/persacc.db`) | **Sin cambios** — misma DB y esquema |
| IA | Ollama local | Sin cambios (se expone vía API) |
| ML | scikit-learn / SARIMAX | Sin cambios (se expone vía API) |
| i18n | `locales/*.json` + `i18n.py` | Mismos JSON, consumidos por frontend (i18next o solución ligera propia) |
| Tests | pytest | pytest (backend) + Vitest (frontend) |
| Lint/format | — | ruff (backend), oxlint + prettier (frontend) |

**Ventaja clave**: la separación `src/` (business_logic, database, models, ai/) ya existe y está razonablemente desacoplada de Streamlit. La DB no se toca. El grueso del trabajo es (a) envolver la lógica en una API REST y (b) reescribir la UI.

## 2. Arquitectura destino

```
PersAcc/
├── backend/
│   ├── server.py              # FastAPI app + rutas
│   ├── main.py                # (opcional) CLI para operaciones batch
│   ├── requirements.txt
│   └── src/
│       ├── api_models.py      # Modelos Pydantic request/response
│       ├── database.py        # ← migrado de src/database.py (quitar caché pickle)
│       ├── business_logic.py  # ← migrado tal cual (cierre, retenciones, KPIs)
│       ├── config.py          # ← migrado (config.json)
│       ├── constants.py       # ← migrado
│       └── ai/                # ← migrado completo (llm_service, ml_engine, nn_projector, file_parser, prompts)
│       └── integrations/      # ← migrado (notion, notion_parser)
├── frontend/
│   ├── package.json           # Mismas deps que Global-Position
│   ├── vite.config.ts         # Proxy /api → localhost:8001
│   └── src/
│       ├── api/               # client.ts, queries.ts, schema.d.ts (openapi-typescript)
│       ├── components/
│       │   ├── ui/            # shadcn: button, card, dialog, table, tabs, select...
│       │   ├── layout/        # AppShell (sidebar con navegación + quick-entry)
│       │   ├── ledger/        # Tabla editable, quick entry, relevancia badges
│       │   ├── closing/       # Wizard de cierre (4 pasos)
│       │   ├── charts/        # QualityDonut, YearEvolution, CategoryBars...
│       │   └── import/        # Dropzone, preview dedup, revisión IA
│       ├── pages/             # Dashboard, Closing, History, Projections, Import, Chat, Settings, Manual
│       ├── lib/               # format.ts (moneda, fechas), i18n.ts
│       └── locales/           # es.json, en.json (migrados)
├── data/                      # SIN CAMBIOS: persacc.db, config.json, models/
├── scripts/                   # setup_db.py, migration.py se conservan
└── .claude/launch.json        # frontend dev server (patrón Global-Position)
```

Puertos: backend `8001`, frontend dev `5174` (para no chocar con Global-Position 8000/5173 si corren a la vez).

## 3. Diseño de la API

Contrato OpenAPI → tipos TS autogenerados con `openapi-typescript` (script `gen:api`, igual que Global-Position).

### Endpoints

**Ledger / mes activo**
- `GET  /api/dashboard?month=` — KPIs mes, entradas, estado cierre, gráfico calidad (datos crudos, el chart lo pinta React)
- `GET  /api/ledger?month=|year=` — entradas con filtros
- `POST /api/ledger` — crear entrada
- `PUT  /api/ledger/{id}` / `DELETE /api/ledger/{id}` — editar/borrar (bloqueado si mes CERRADO)

**Categorías y configuración**
- `GET/POST/PUT /api/categories` (+ archivar; orden por uso histórico lo calcula el backend)
- `GET /api/relevance-codes`
- `GET/PUT /api/config` — todo lo de Utilities > Configuration (idioma, moneda, dark mode, toggles, retenciones, defaults por categoría, modelos IA, Notion, bank URL, dedup)

**Cierre mensual**
- `GET  /api/closing/status` — mes a cerrar, estado
- `POST /api/closing/preview` — cálculo de retenciones/desviación/consecuencias sin ejecutar (los 4 pasos del wizard consumen esto)
- `POST /api/closing/execute` — cierre inmutable + apertura mes siguiente
- `GET  /api/closing/snapshots` — histórico de cierres

**Histórico y análisis**
- `GET /api/history/years` · `GET /api/history/{year}` — KPIs anuales, evolución mensual, desglose categorías
- `GET/PUT /api/notes/{period_type}/{period_id}` — anotaciones

**IA (Ollama)**
- `GET  /api/ai/models` — modelos disponibles en Ollama
- `POST /api/ai/commentary` — comentario del ledger
- `POST /api/ai/analysis` — análisis de periodo (persiste en AI_ANALYSIS); `GET` para recuperar cacheado
- `POST /api/ai/chat` — búsqueda en lenguaje natural (extracción de parámetros + resultados)

**Proyecciones ML**
- `GET /api/projections?years=` — SARIMAX/NN por serie (ingreso, gasto, ahorro) con intervalos 80%

**Importación**
- `POST /api/import/upload` — subir fichero (N43, SEPA, Excel, CSV)
- `POST /api/import/preview` — parseo + clasificación IA + detección duplicados
- `POST /api/import/commit` — guardar seleccionados
- `POST /api/import/notion/sync` · `GET /api/import/notion/status`

**Export**
- `GET /api/export/csv?scope=` — backup/exportación

Nota: tareas largas (análisis IA, sync Notion, entrenamiento ML) pueden tardar >30 s con Ollama. Primera versión: request síncrona con timeout generoso + spinner. Si molesta: patrón job (`POST` devuelve `job_id`, `GET /api/jobs/{id}` para polling).

## 4. Fases de trabajo

### Fase 0 — Preparación (½ día)
- [ ] Backup de `data/persacc.db` y `data/config.json`
- [ ] Crear rama/carpetas `backend/` y `frontend/`; congelar la app Streamlit (se mantiene funcional hasta Fase 6)
- [ ] `.claude/launch.json` con config frontend (patrón Global-Position)

### Fase 1 — Backend API (2-3 días)
- [ ] Mover `src/` a `backend/src/` sin tocar lógica; eliminar imports de `streamlit` residuales en business_logic/database
- [ ] **Eliminar `disk_cache.py`** (pickles de figuras Plotly — obsoleto: los charts ya no se generan en Python). Purgar funciones `_fig_*` de business_logic o moverlas a endpoints que devuelvan datos tabulares
- [ ] `api_models.py` con Pydantic para todos los contratos de §3
- [ ] `server.py` con las rutas; CORS para dev
- [ ] Adaptar `i18n.py`: el backend solo necesita idioma para prompts IA; los textos UI pasan al frontend
- [ ] Tests pytest de los endpoints críticos: cierre (preview+execute), CRUD ledger con mes cerrado, dedup import
- [ ] Verificar contra la DB real: KPIs de un mes cerrado conocido deben cuadrar céntimo a céntimo con la app Streamlit (test de paridad, mismo enfoque que `docs/paridad.md` de Global-Position)

### Fase 2 — Esqueleto frontend (1-2 días)
- [ ] Scaffold Vite + React 19 + TS + Tailwind 4 + shadcn (copiar configuración de `Global-Position/frontend`: tsconfigs, oxlint, prettier, vitest, components.json)
- [ ] `AppShell` con sidebar: navegación (Dashboard, Cierre, Histórico, Proyecciones, Importar, Chat, Utilidades, Manual) + formulario quick-entry + link banco
- [ ] Cliente API + TanStack Query + `gen:api` funcionando
- [ ] i18n: cargar `locales/es|en.json`, selector de idioma; dark mode con Tailwind
- [ ] `lib/format.ts` — moneda configurable, fechas es/en

### Fase 3 — Páginas core (3-4 días) — *hito: app usable para el día a día*
- [ ] **Dashboard (mes activo)**: KPIs, tabla ledger editable inline (categoría, relevancia, importe), alta rápida, donut calidad gasto NE/LI/SUP/TON, comentario IA opcional
- [ ] **Cierre mensual**: wizard 4 pasos (saldo real → nómina → retenciones → confirmación) sobre `closing/preview`; ejecución y apertura de mes
- [ ] **Utilidades/Configuración**: formulario completo de config, gestión de categorías (CRUD + archivar + defaults), export/import CSV

### Fase 4 — Analítica e IA (2-3 días) — *parcialmente HECHO*
- [x] **Histórico**: KPIs anuales, evolución mensual (Recharts), desglose categorías, análisis IA de periodo (con caché en AI_ANALYSIS) — endpoints `/api/ai/analysis`, panel `AnalysisPanel`
- [x] **Proyecciones**: gráficos con bandas de confianza 80%, reentrenar modelos — endpoints `/api/projections` + `/train`
- [x] **Comentario IA del mes** en Dashboard — `/api/ai/commentary`
- [ ] **Chat/búsqueda**: input NL → parámetros extraídos → tabla resultados (pendiente)

### Fase 5 — Importación e integraciones (2 días) — *parcialmente HECHO*
- [x] **Importar**: subida → preview con clasificación IA y duplicados marcados → revisión manual (checkboxes) → commit — endpoints `/api/import/preview` + `/commit`
- [ ] **Notion sync**: config + sync manual + indicador auto-check al arrancar (pendiente)
- [ ] **Manual**: portar contenido de `manual.py`/`manual_en.py` a markdown renderizado (pendiente)

### Fase 6 — Paridad, empaquetado y retirada de Streamlit — *HECHO*
- [x] `run.ps1` (uvicorn sirve `frontend/dist` desde FastAPI en un solo proceso, verificado: API + SPA + rutas profundas)
- [x] README y Dockerfile actualizados (multi-stage: node build frontend + uvicorn)
- [x] Streamlit retirado a `legacy/` (`app.py`, `src/ui/`, `.streamlit/` conservados, no borrados); `disk_cache` de figuras eliminado; `persacc.db` vacía eliminada; `streamlit` fuera de `requirements.txt`
- [ ] Installer PyInstaller: pendiente decidir (opción simple: zip + `run.ps1`)
- [ ] Tag `v4.0.0`: pendiente (no hay repo git en este árbol)

## Estado final

Todas las funcionalidades del README v3.2 migradas y verificadas contra la DB real:
dashboard con KPIs/tabla/alta rápida/calidad de gasto, cierre mensual (wizard 4 pasos),
histórico anual, proyecciones SARIMAX con bandas 80 %, comentario y análisis IA (Ollama),
asistente de búsqueda NL, importación bancaria (N43/SEPA/Excel) con dedup, sync Notion,
export CSV, manual. Backend con 11 tests de paridad en verde. Streamlit conservado en
`legacy/` como red de seguridad.

## 5. Migración de datos

**No hay migración de esquema.** La DB real es **`data/finanzas.db`** (1454 entradas, 34 categorías, 7 cierres) — es la que apunta `DEFAULT_DB_PATH` en `src/database.py`. `data/persacc.db` está **vacía** (sin tablas): es un artefacto muerto, archivar/borrar. El backend usa `finanzas.db` tal cual (tablas CAT_MAESTROS, CAT_RELEVANCIA, LEDGER, SNAPSHOTS_MENSUALES, CIERRES_MENSUALES, AI_ANALYSIS, PERIOD_NOTES). Acciones puntuales:

- `data/config.json` — se conserva; añadir claves nuevas con defaults si hacen falta (puerto API, etc.)
- `data/models/*.joblib` — modelos NN se conservan y siguen usándose desde `ml_engine`/`nn_projector`
- `data/.disk_cache/` — **borrar** (pickles de figuras, irrecuperables e innecesarios)
- `data/finanzas.db` — verificar si es legacy; si nada la lee, archivar
- Aclarar `styles_original.py` / `search_assistant_new.py` / `setup_db_en.py` (duplicados aparentes) — no migran, solo la versión viva

## 6. Riesgos y decisiones

| Riesgo | Mitigación |
|---|---|
| Lógica de cierre acoplada a `st.session_state` en `cierre.py` | El estado del wizard vive en React; backend expone solo `preview`/`execute` puros e idempotentes |
| Latencia Ollama (>30 s) bloquea requests | Timeouts largos + UI con estados de carga; escalar a patrón job si duele |
| Tabla editable inline (hoy `st.data_editor`) | shadcn Table + edición por fila o dialog; no intentar réplica exacta de data_editor en v1 |
| Regresión en cálculos de cierre/retenciones | Test de paridad Fase 1 contra datos reales antes de escribir una línea de frontend |
| Installer PyInstaller se complica con frontend | Decidir en Fase 6; opción simple: zip + `run.ps1` como Global-Position |
| Dos apps FIN corriendo a la vez | Puertos separados (8001/5174) |

## 7. Estimación total

~11-16 días de trabajo efectivo. Hito intermedio importante: **fin de Fase 3** ya permite operar el día a día (ledger + cierre + config) sin Streamlit; Fases 4-5 completan analítica, IA e importación.
