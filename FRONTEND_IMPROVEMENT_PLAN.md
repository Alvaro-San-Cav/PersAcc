# PersAcc v4.1 — Plan de mejora del frontend React

Objetivo: recuperar la funcionalidad y el "feel" de la UI Streamlit original (legacy/) sobre el
stack nuevo (React 19 + TS + Tailwind 4 + shadcn + TanStack Query), y superarla donde el stack
lo permite (deep-links, edición fluida, sin reruns).

Estado de partida: frontend nuevo ≈ 2.300 líneas y cubre ~40 % de la UI legacy (≈ 7.000 líneas).
Casi todo es de solo lectura; el uso diario (editar, corregir, defaults) se perdió.

Convenciones del plan:
- **[F]** solo frontend · **[B]** requiere backend · **[F+B]** ambos.
- P0 = uso diario roto/pobre · P1 = paridad funcional · P2 = pulido.
- Rutas frontend relativas a `frontend/src/`.

---

## 0. Bugs y deudas concretas del código actual (arreglar primero, ~½ día)

| # | Dónde | Problema | Fix |
|---|-------|----------|-----|
| 1 | `pages/Proyecciones.tsx:28` | `useState(12)` sin setter: el horizonte de proyección no se puede cambiar | Selector 6/12/24/36 meses en el header |
| 2 | `pages/Cierre.tsx:81` | `window.location.assign('/')` recarga la SPA entera | `useNavigate()` de react-router |
| 3 | `components/dashboard/QuickAddForm.tsx:29` | Fecha default hardcoded a día 15 (`${mesFiscal}-15`) | Hoy si `mesFiscal` = mes actual; día 1 del mes si es otro (paridad con `legacy/ui/sidebar.py:38-48`) |
| 4 | `QuickAddForm` | No expone `flag_liquidez` para INGRESO (el backend `LedgerEntryCreate` lo acepta y afecta a `fecha_contable`) | Checkbox "⚡ Liquidez inmediata" visible solo con tipo INGRESO |
| 5 | `components/dashboard/LedgerTable.tsx:96` | Borrado sin confirmación | `ConfirmDialog` reutilizable (AlertDialog shadcn) |
| 6 | `pages/Historico.tsx:56` | Si no hay años con datos → skeleton infinito (`isLoading \|\| !data` con query disabled) | Empty state "Sin datos históricos" |
| 7 | `pages/Utilidades.tsx` | El selector de idioma guarda config pero la UI no cambia (no hay i18n) | Se resuelve en Fase F; mientras, ocultar o marcar "(requiere i18n)" |
| 8 | `backend/server.py:243` | `_assert_entry_editable` escanea todo el ledger para encontrar 1 id | `db.get_ledger_entry(id)` directo (añadir helper en `src/database.py`) |

---

## Fase A — Uso diario y feel (P0, ~2-3 días)

Lo que hace que la app "se sienta" bien a diario. Todo el backend necesario **ya existe** salvo A5.

### A1. Edición de movimientos [F]
- `EntryEditDialog.tsx` (nuevo, `components/dashboard/`): dialog con el mismo layout que QuickAddForm
  (tipo, categoría filtrada por tipo, fecha, concepto, importe, relevancia, flag_liquidez).
- Lápiz por fila en `LedgerTable` (junto al Trash2), oculto si `locked`.
- Usa `useUpdateEntry` (**ya existe** en `api/queries.ts:86`, hoy sin consumidor) → `PUT /api/ledger/{id}`.
- Nota: el PUT actual no permite cambiar `fecha_real` ni `tipo_movimiento`. Ampliar
  `LedgerEntryUpdate` + `db.update_ledger_entry` para soportarlos (recalculando `mes_fiscal`/`fecha_contable`) **[B pequeño]**.
- Criterio: editar categoría/importe/relevancia de un gasto y ver el dashboard refrescado sin recargar.

### A2. Filtros, orden y totales en la tabla de movimientos [F]
- `LedgerFilters.tsx`: filtro por tipo (chips), por categoría (select), búsqueda de texto en concepto.
- Orden clicable por columna (fecha, importe, categoría). Client-side: el mes ya viene completo.
- Footer con nº de movimientos y suma de lo filtrado.
- Criterio: "ver solo GASTO de Comida ordenado por importe" en 2 clics.

### A3. QuickAdd con inteligencia del legacy [F+B]
- **Defaults por categoría**: al elegir categoría, precargar concepto/importe/relevancia desde
  `config.conceptos_default / importes_default / relevancias_default` (clave = nombre en minúsculas
  con `_`). Config ya viaja en `GET /api/config`. No pisar si el usuario ya escribió (misma lógica
  que `sidebar.py:150-183`: solo resetear si el valor actual es un default conocido o vacío).
- **Orden inteligente de categorías**: nuevo endpoint **[B]** `GET /api/categories/usage-stats?tipo=&month=&year=`
  que expone `db.get_category_usage_stats` (frecuencia histórica + uso ese mes en años anteriores).
  Orden: historia desc, año actual desc, nombre. Hoy ordena por `count` global — pierde estacionalidad.
- **Autocomplete de conceptos**: datalist con conceptos recientes distintos de esa categoría.
  Client-side desde `GET /api/ledger?year=` o endpoint ligero `GET /api/ledger/concepts?categoria_id=`.
- **flag_liquidez** (bug #4).
- Criterio: elegir categoría "Gimnasio" y que concepto/importe/relevancia se rellenen solos.

### A4. Notas por periodo [F]
- Backend **ya existe**: `GET/PUT /api/notes/{period_type}/{period_id}`.
- `NotesCard.tsx`: textarea colapsable con guardado (botón + Ctrl-Enter), estado "guardado ✓".
- Colocar en Dashboard (mes activo, editable) y en Histórico (vista año y mes; readonly si cerrado, como legacy).
- Hooks nuevos: `useNotes(periodType, periodId)` + `useSaveNotes`.

### A5. Tema claro/oscuro [F]
- `index.css`: bloque `:root[data-theme='light']` con la paleta clara del legacy (`styles.py` la define; fondo blanco, texto #333, mismos acentos).
- Toggle sol/luna al pie del sidebar (`AppShell`). Persistir en `config.dark_mode` vía `PUT /api/config`; aplicar al arrancar desde `useConfig`.
- Los charts ya usan CSS vars → cambian solos. Revisar los `contentStyle` de Recharts (ya usan vars ✓).

### A6. Detalles de shell [F]
- Logo real: copiar `assets/logo.ico` (o exportar PNG) a `frontend/public/` y usarlo en sidebar + favicon.
- Cierre: `useNavigate` (bug #2) + si hay varios meses abiertos, selector de mes a cerrar
  (`/api/closing/status` hoy devuelve solo el primero → ampliar a `meses_abiertos: string[]` **[B pequeño]**).
- Enlace "banco" en sidebar si `config.bank_url` (legacy lo tenía).

---

## Fase B — Histórico rico (P1, ~2-3 días). El gap más grande.

### B1. Endpoint de detalle mensual [B]
`GET /api/history/{anio}/{mes}` → reutiliza dominio existente:
```json
{
  "mes_fiscal": "2026-03",
  "kpis": { ... },                          // bl.calcular_kpis
  "relevancia": { ... },                    // bl.calcular_kpis_relevancia
  "gastos_por_categoria": [{"categoria": "Comida", "importe": 312.5}],
  "retenciones": [ ...entradas INVERSION del cierre... ],
  "entries": [ ... ]
}
```
Y `GET /api/history/{anio}/analysis?tipo=GASTO|INGRESO|INVERSION` →
`word_counts` (bl.get_word_counts), `top_entries` (bl.get_top_entries), `curiosities`
(bl.calculate_curious_metrics: día top, importe día top, media días activos, nº días activos).

### B2. Drill-down mensual [F]
- Ruta nueva `/historico/:anio/:mes` (deep-linkable, mejora sobre legacy).
- Navegación: click en barra del BarChart anual (`onClick` de Recharts) + select de mes.
- Contenido (paridad con `render_month_view` de `historico.py:388`):
  - 4 KPIs del mes + botón volver al año.
  - Donut gastos por categoría + tabla desglose + "explorar movimientos por categoría" (select → tabla filtrada, dedupe visual).
  - Donut calidad del gasto (reusar `QualityDonut`).
  - Desglose de retenciones del cierre.
  - `NotesCard` readonly + comentario IA (reusar `AnalysisPanel` con `period_type="month"`).
  - Tabla completa de movimientos del mes (readonly si cerrado).

### B3. Vista anual ampliada [F]
- Añadir a las stats actuales: medias mensuales (ingresos/gastos/salario) — derivables de `data.meses`.
- Tabs como legacy: **Resumen** (lo actual + donut categorías del año), **Análisis** (word-frequency
  bar chart, top 10 movimientos, curiosidades; selector GASTO/INGRESO/INVERSION), **Datos** (tabla completa del año con filtros de A2).
- Componentes nuevos reutilizables: `CategoryDonut.tsx`, `WordFreqChart.tsx`, `TopEntriesTable.tsx`, `CuriositiesCards.tsx`.

---

## Fase C — Utilidades completas (P1, ~2 días)

### C1. CRUD de categorías [F]
- Backend **ya existe** (`POST/PUT/DELETE /api/categories`).
- `CategoriesEditor.tsx`: tabla editable — renombrar inline, crear (nombre + tipo), borrar con
  confirmación (bloquear/avisar si `count > 0`; el backend ya valida FK — mostrar su error).

### C2. Editor de consecuencias [F]
- Las reglas viven en `config.consequences_rules` → **sin backend nuevo**: leer de `useConfig`, guardar con `PUT /api/config`.
- Tabla editable con columnas del legacy (`utilidades.py:355`): activa (checkbox), nombre,
  filtro relevancia (NE/LI/SUP/TON), filtro categoría (select), filtro concepto (texto),
  tipo acción (percent/fixed), valor. `id` = uuid al crear. Filas dinámicas (añadir/borrar).
- Mostrar aviso si `enable_consequences` está off.

### C3. Defaults por categoría [F]
- También en config (`conceptos_default`, `importes_default`, `relevancias_default`).
- `DefaultsEditor.tsx`: una fila por categoría de gasto → concepto default, importe default, relevancia default. Guardar vía `PUT /api/config`.
- Es la otra mitad de A3: sin este editor los defaults solo se pueden tocar a mano en `config.json`.

### C4. Config completa [F, B pequeño]
Ampliar tab Configuración con lo que falta del legacy (`utilidades.py:466-713`):
- Toggle dark mode (enlazado con A5) y toggle IA (`llm.enabled`).
- % retenciones default (sliders remanente/salario → `config.retenciones`).
- Método de saldo del cierre (`antes_salario` / `despues_salario`).
- URL del banco.
- Parámetros de deduplicación de carga automática (`config.automatic_load`: tolerancia importe, ventana días, umbral texto, score mínimo, etc.) — en un acordeón "Avanzado".
- **Modelos LLM por tarea**: selects para `llm.model_analysis/chat/summary/import`.
  Necesita **[B]** `GET /api/ai/models` (lista de modelos Ollama instalados; `llm_service` ya sabe consultarlo).
- **Notion**: toggle enabled, token (input password), database_id, check_on_startup, botón
  "probar conexión" (`GET /api/notion/status` ya existe). Todo a `config.notion` vía `PUT /api/config`.

### C5. Restaurar backup y limpieza [B+F]
- **[B]** `POST /api/import/backup` (multipart CSV + `tipo=expenses|income|investments`):
  refactorizar `scripts/migration.py` a función importable (nada de `subprocess` como hacía legacy). Devolver `{inserted, errors[]}`.
- **[B]** `POST /api/admin/cleanup` con `{scope: 'ledger'|'full', confirm: string}`:
  borra LEDGER+CIERRES+SNAPSHOTS; `full` además CAT_MAESTROS y re-siembra categorías
  (refactorizar `scripts/setup_db.py` a función). Rechazar si `confirm` no coincide con la frase exacta.
- **[F]** Tab "Datos" ampliado: Exportar (existe) · Restaurar CSV (uploader + preview 5 líneas + formato esperado por tipo) · Zona de peligro (dos opciones con input de confirmación textual, estilo legacy).

---

## Fase D — Importar y Notion con revisión (P1, ~1-2 días)

### D1. Editor de preview de importación [F]
Paridad con `cargar_datos.py`. Sobre la tabla de preview actual:
- Celdas editables: categoría (select), tipo, relevancia, fecha, concepto, importe.
- Tabs por confianza como legacy: **Buenas** (≥ umbral), **A revisar** (< umbral o sin categoría), **Ignoradas** (duplicados/fuera de periodo) con motivo visible.
- Al duplicado, mostrar el best-match (fecha/concepto/importe del existente) en tooltip o fila expandible — la info ya viene del preview si se amplía `ImportEntry` con `duplicate_of` **[B pequeño]**.
- El commit envía las filas editadas (el endpoint ya acepta entries arbitrarias ✓).

### D2. Notion con revisión [F, B pequeño]
- **Banner al arrancar**: si `notion.enabled && check_on_startup`, `AppShell` consulta
  `POST /api/notion/preview` (o nuevo `GET /api/notion/pending-count` más barato **[B]**) y muestra
  banner "📥 N entradas pendientes en Notion — Revisar".
- **`NotionReviewDialog.tsx`**: lista de entradas con edición por fila (tipo, categoría, relevancia,
  fecha) y acción por fila: Importar / Omitir. Legacy además actualizaba/borraba en Notion
  (`notion_sync.py:95-183`) → **[B]** `POST /api/notion/entries/{id}/delete` y `/update` si se quiere paridad total (P2; el flujo mínimo es importar+omitir).
- Reemplaza el botón "sincronizar a ciegas" actual de Utilidades.

---

## Fase E — Chat y Proyecciones (P1/P2, ~1-2 días)

### E1. Chat con refinamiento [F, B opcional]
- Mostrar tras cada búsqueda los **parámetros extraídos** (tipo de búsqueda, categoría, año, mes)
  como formulario editable + "volver a ejecutar" (paridad con `search_assistant_new.py:316`).
  Requiere que `POST /api/chat` devuelva `params` usados **[B pequeño]** (chat_search ya los extrae).
- Historial de la sesión: lista de Q&A apiladas (no solo la última respuesta).
- Feedback de latencia: el modelo local tarda >60 s → mostrar cronómetro + fase ("extrayendo parámetros… ejecutando…"). Streaming SSE real: P2.
- Export CSV del resultado.

### E2. Proyecciones completas [F]
- Selector de horizonte funcional (bug #1).
- Tabla de desglose anual bajo cada chart (año → total proyectado, media mensual) — datos ya presentes en `projected`.
- Métricas resumen arriba: tasa de ahorro proyectada, total proyectado por serie (paridad con `proyecciones.py:174-188`).
- Toggle mostrar histórico + proyección en el mismo chart (hoy solo proyección; la banda sin contexto histórico confunde).

---

## Fase F — i18n, responsive y pulido (P2, ~1-2 días)

### F1. i18n [F]
- `react-i18next`. **No** reutilizar `locales/*.json` tal cual (claves acopladas a Streamlit):
  crear `frontend/src/i18n/{es,en}.json` nuevos, copiando textos desde `locales/` donde valgan.
- Idioma desde `config.language` (el select de Utilidades por fin funciona). `fmtMoney/fmtDate` ya localizables en `lib/format.ts`.

### F2. Responsive [F]
- Sidebar colapsable a iconos (desktop) y drawer con burger (<768 px).
- Grids ya usan `md:`/`lg:` ✓; revisar tablas (scroll horizontal en móvil).

### F3. Micro-feel [F]
- Atajos: `N` enfoca QuickAdd, `/` enfoca búsqueda de tabla, `g d/h/c` navegación.
- Empty states con CTA (p. ej. dashboard sin movimientos → "añade el primero" señalando QuickAdd).
- Transiciones suaves al cambiar de mes (fade en KpiGrid), `tabular-nums` ya ✓.
- Title de la pestaña por página (`PersAcc — Histórico 2026`).
- Toast con "deshacer" al borrar movimiento (guardar payload y re-crear).

---

## Resumen de trabajo backend nuevo

| Endpoint | Fase | Esfuerzo |
|----------|------|----------|
| Ampliar `PUT /api/ledger/{id}` (fecha, tipo) | A1 | XS |
| `GET /api/categories/usage-stats` | A3 | XS (función ya existe) |
| `closing/status` → `meses_abiertos[]` | A6 | XS |
| `GET /api/history/{anio}/{mes}` | B1 | S |
| `GET /api/history/{anio}/analysis` | B1 | S (funciones ya existen) |
| `GET /api/ai/models` | C4 | XS |
| `POST /api/import/backup` | C5 | M (refactor migration.py) |
| `POST /api/admin/cleanup` | C5 | S (refactor setup_db.py) |
| `ImportEntry.duplicate_of` | D1 | XS |
| `GET /api/notion/pending-count` | D2 | XS |
| `POST /api/chat` devuelve `params` | E1 | XS |
| Notion update/delete remoto | D2 (P2) | S |

Añadir tests de paridad en `backend/tests/` por cada endpoint nuevo (patrón de `test_api_parity.py`).

## Orden y estimación

| Fase | Contenido | Días | Hito |
|------|-----------|------|------|
| 0 | Bugs | 0,5 | — |
| A | Edición, filtros, QuickAdd, notas, tema, shell | 2-3 | **App agradable a diario** |
| B | Histórico drill-down + análisis | 2-3 | Paridad analítica |
| C | Utilidades completas | 2 | Paridad configuración |
| D | Importar/Notion con revisión | 1-2 | Paridad integraciones |
| E | Chat + Proyecciones | 1-2 | Paridad IA |
| F | i18n + responsive + micro-feel | 1-2 | Pulido |

Total: **10-14 días**. Cada fase es entregable independiente; A y B concentran el 80 % del valor percibido.

## Riesgos
- `PUT /api/config` guarda el objeto completo: los editores de C2/C3/C4 deben hacer merge
  sobre la config fresca (releer antes de guardar) para no pisarse entre tabs.
- Edición de fecha/tipo en A1 recalcula `mes_fiscal`: bloquear si el destino es un mes cerrado (409 del backend ya cubre; mostrar mensaje claro).
- Cleanup es destructivo: doble confirmación textual + recomendar export previo en la misma pantalla.
- Chat con gemma 26b >120 s: subir timeout del fetch en `api/client.ts` para `/api/chat` o quedará colgado antes de responder.
