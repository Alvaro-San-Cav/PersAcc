"""
Rutas de IA (Ollama), proyecciones ML (SARIMAX) e importación de ficheros.

Reutilizan src/ai/* e src/integrations/*. Los endpoints que dependen de Ollama
degradan con elegancia: si no está corriendo devuelven 503 con detalle claro.
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from src import database as db
from src import business_logic as bl
from src import config as cfg
from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry
from src.ai import llm_service as llm
from src.ai import nn_projector as proj
from src.ai import file_parser

from api_models import (
    AiStatus, TextResponse, AnalysisRequest,
    ProjectionsResponse,
    ImportEntry, ImportPreviewResponse, ImportCommitRequest, ImportCommitResponse,
    BackupImportResponse, CleanupRequest, CleanupResponse,
    ChatRequest, ChatRunRequest, ChatResponse, ChatResultEntry, NotionStatus,
    NotionArchiveRequest, NotionArchiveResponse, LifeDeckSyncResponse,
)

# Hacer importables los scripts de mantenimiento (migration, setup_db).
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

router = APIRouter(prefix="/api")

# Frase de confirmación exacta que exige el cleanup (evita borrados accidentales).
_CLEANUP_PHRASE = "BORRAR TODO"
_BACKUP_MODE = {"expenses": "GASTO", "income": "INGRESO", "investments": "INVERSION"}


# ── IA ──────────────────────────────────────────────────────────────────────
@router.get("/ai/status", response_model=AiStatus)
def ai_status() -> AiStatus:
    running = llm.check_ollama_running()
    return AiStatus(
        enabled=llm.is_llm_enabled(),
        ollama_running=running,
        models=llm.get_available_models() if running else [],
    )


@router.get("/ai/models", response_model=List[str])
def ai_models() -> List[str]:
    """Modelos Ollama instalados (para los selects de config). [] si Ollama no corre."""
    if not llm.check_ollama_running():
        return []
    return llm.get_available_models()


@router.get("/ai/commentary", response_model=TextResponse)
def ai_commentary(month: str) -> TextResponse:
    """Comentario ingenioso del mes activo (requiere Ollama)."""
    if not llm.is_llm_enabled():
        return TextResponse(text="")
    if not llm.check_ollama_running():
        raise HTTPException(503, "Ollama no está en ejecución.")

    kpis = bl.calcular_kpis(month)
    entries = db.get_ledger_by_month(month)
    cat_names = {c.id: c.nombre for c in db.get_all_categorias()}
    expense_items = [
        {"categoria": cat_names.get(e.categoria_id, ""), "concepto": e.concepto or "", "importe": e.importe}
        for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO
    ]
    lang = cfg.get_config_value("language", "es")
    text = llm.generate_quick_summary(
        income=kpis["total_ingresos"], expenses=kpis["total_gastos"],
        balance=kpis["balance_mes"], lang=lang, expense_items=expense_items,
    )
    return TextResponse(text=text)


@router.get("/ai/analysis/{period_type}/{period_id}", response_model=TextResponse)
def ai_analysis_cached(period_type: str, period_id: str) -> TextResponse:
    text = db.get_ai_analysis(period_type, period_id)
    return TextResponse(text=text or "", cached=text is not None)


@router.post("/ai/analysis", response_model=TextResponse)
def ai_analysis(req: AnalysisRequest) -> TextResponse:
    """Análisis profundo de un periodo. Cachea en AI_ANALYSIS."""
    if not req.regenerate:
        cached = db.get_ai_analysis(req.period_type, req.period_id)
        if cached:
            return TextResponse(text=cached, cached=True)

    if not llm.check_ollama_running():
        raise HTTPException(503, "Ollama no está en ejecución.")

    lang = cfg.get_config_value("language", "es")
    llm_cfg = llm.get_llm_config()
    model = llm_cfg.get("model_analysis", "phi3")
    max_tokens = int(llm_cfg.get("max_tokens", 800))
    cat_names = {c.id: c.nombre for c in db.get_all_categorias()}

    if req.period_type == "month":
        kpis = bl.calcular_kpis(req.period_id)
        entries = db.get_ledger_by_month(req.period_id)
        data = {
            "period": req.period_id, "income": kpis["total_ingresos"],
            "expenses": kpis["total_gastos"], "balance": kpis["balance_mes"],
            "investment": kpis["total_inversion"],
            "savings_percent": kpis["pct_salary_retention"] * 100,
        }
    else:
        anual = bl.calcular_kpis_anuales(int(req.period_id))
        entries = db.get_ledger_by_year(int(req.period_id))
        data = {
            "period": req.period_id, "income": anual["total_ingresos"],
            "expenses": anual["total_gastos"], "balance": anual["total_ahorrado"],
            "investment": anual.get("total_inversion", 0), "savings_percent": anual["pct_ahorro"],
        }

    movements = [
        {
            "fecha": e.fecha_real.isoformat(), "tipo": e.tipo_movimiento.value,
            "categoria": cat_names.get(e.categoria_id, ""), "concepto": e.concepto or "",
            "importe": e.importe,
        }
        for e in entries
    ]

    try:
        text = llm.analyze_financial_period(
            data=data, period_type=req.period_type, lang=lang,
            model_tier=model, max_tokens=max_tokens, movements=movements,
        )
    except (ConnectionError, ValueError) as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:  # respuesta vacía u otros errores del modelo
        raise HTTPException(502, str(exc))

    db.save_ai_analysis(req.period_type, req.period_id, text, model_used=model, lang=lang)
    return TextResponse(text=text)


# ── Proyecciones ────────────────────────────────────────────────────────────
@router.get("/projections", response_model=ProjectionsResponse)
def projections(months: int = 12) -> ProjectionsResponse:
    series = {}
    for tipo in ("gasto", "ingreso", "ahorro"):
        projector = proj.get_or_create_projector(tipo)
        series[tipo] = projector.predict(months_ahead=months)
    return ProjectionsResponse(
        months=months, series=series, status=proj.get_all_models_status(),
    )


@router.post("/projections/train", response_model=ProjectionsResponse)
def projections_train(months: int = 12) -> ProjectionsResponse:
    proj.retrain_all_models()
    series = {}
    for tipo in ("gasto", "ingreso", "ahorro"):
        series[tipo] = proj.get_or_create_projector(tipo).predict(months_ahead=months)
    return ProjectionsResponse(
        months=months, series=series, status=proj.get_all_models_status(),
    )


# ── Importación ─────────────────────────────────────────────────────────────
def _existing_keys(mes_fiscal: str) -> set:
    """Claves (importe redondeado, fecha) de las entradas ya existentes del mes."""
    return {
        (round(e.importe, 2), e.fecha_real.isoformat())
        for e in db.get_ledger_by_month(mes_fiscal)
    }


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(files: List[UploadFile] = File(...)) -> ImportPreviewResponse:
    """Parsea un fichero bancario, clasifica con IA y marca duplicados."""
    if not files:
        raise HTTPException(400, "No se recibió ningún fichero.")
    upload = files[0]
    content = await upload.read()

    ftype, text = file_parser.parse_file(upload.filename or "archivo", content)

    if not llm.check_ollama_running():
        raise HTTPException(503, "Ollama no está en ejecución; la clasificación IA lo requiere.")

    categorias = [c.nombre for c in db.get_all_categorias()]
    try:
        raw = llm.classify_bank_transactions(text, ftype.name, categorias)
    except (ConnectionError, ValueError) as exc:
        raise HTTPException(503, str(exc))

    # Marcar duplicados contra lo ya guardado en el mes correspondiente.
    entries: list[ImportEntry] = []
    keys_cache: dict[str, set] = {}
    for item in raw:
        fecha = item.get("fecha", "")
        mes = fecha[:7] if len(fecha) >= 7 else ""
        if mes and mes not in keys_cache:
            keys_cache[mes] = _existing_keys(mes)
        dup = bool(mes) and (round(float(item.get("importe", 0)), 2), fecha) in keys_cache.get(mes, set())
        entries.append(ImportEntry(**item, is_duplicate=dup))

    return ImportPreviewResponse(file_type=ftype.value, entries=entries)


@router.post("/import/commit", response_model=ImportCommitResponse)
def import_commit(req: ImportCommitRequest) -> ImportCommitResponse:
    all_cats = db.get_all_categorias()
    # Clave por (tipo, nombre): los nombres se repiten entre tipos (p.ej. "Otros"),
    # y quedarse con el último provocaba que ingresos/traspasos no encontrasen su
    # categoría y se descartasen en silencio.
    cat_by_tipo_name = {
        (c.tipo_movimiento.value, c.nombre.lower()): c for c in all_cats
    }
    to_insert: list[LedgerEntry] = []
    notion_ids: list[str] = []  # ids de la bandeja (Notion/LifeDeck) a marcar tras insertar
    dup_inbox_ids: list[str] = []  # ids de la bandeja que ya estaban en el ledger
    skipped = 0
    duplicates = 0
    keys_cache: dict[str, set] = {}  # mes_fiscal → claves ya en el ledger
    batch_keys: set = set()          # evita duplicados dentro del propio lote

    for item in req.entries:
        try:
            tipo = TipoMovimiento(item.tipo_movimiento)
        except ValueError:
            skipped += 1
            continue
        cat = cat_by_tipo_name.get((tipo.value, (item.categoria_sugerida or "").lower()))
        if not cat:
            skipped += 1
            continue
        try:
            fecha = date.fromisoformat(item.fecha)
        except ValueError:
            skipped += 1
            continue
        mes_fiscal = bl.calcular_mes_fiscal(fecha)
        if db.is_mes_cerrado(mes_fiscal):
            skipped += 1
            continue

        # Duplicado: mismo importe y misma fecha ya guardados (o repetidos en el lote).
        key = (round(abs(item.importe), 2), fecha.isoformat())
        if mes_fiscal not in keys_cache:
            keys_cache[mes_fiscal] = _existing_keys(mes_fiscal)
        if key in keys_cache[mes_fiscal] or key in batch_keys:
            duplicates += 1
            # LifeDeck: ya está en el ledger → se marca importado para que no vuelva a la bandeja.
            if item.notion_id:
                dup_inbox_ids.append(item.notion_id)
            continue
        batch_keys.add(key)

        rel = None
        if tipo == TipoMovimiento.GASTO and item.relevancia:
            try:
                rel = RelevanciaCode(item.relevancia)
            except ValueError:
                rel = None

        to_insert.append(LedgerEntry(
            id=None, fecha_real=fecha, fecha_contable=fecha,
            mes_fiscal=bl.calcular_mes_fiscal(fecha), tipo_movimiento=tipo,
            categoria_id=cat.id, concepto=item.concepto or item.concepto_original,
            importe=abs(item.importe), relevancia_code=rel, flag_liquidez=False,
        ))
        if item.notion_id:
            notion_ids.append(item.notion_id)

    inserted = db.batch_insert_ledger_entries(to_insert) if to_insert else 0

    # Marcar en la bandeja solo lo que se insertó con éxito (Notion: archivar; LifeDeck: 'imported').
    notion_archived = 0
    source = None
    if inserted and notion_ids:
        notion_archived = _archive_notion(notion_ids)
    if notion_ids or dup_inbox_ids:
        from src.integrations import inbox
        client = inbox.get_inbox_client()
        source = inbox.source_name(client)
        # Duplicados: solo LifeDeck (en Notion se mantiene el comportamiento de no archivarlos).
        if dup_inbox_ids and inbox.is_lifedeck(client):
            notion_archived += inbox.mark_imported(dup_inbox_ids)
    if inserted:
        _sync_lifedeck_background()

    return ImportCommitResponse(
        inserted=inserted, skipped=skipped, duplicates=duplicates,
        notion_archived=notion_archived, source=source,
    )


def _archive_notion(page_ids: list[str]) -> int:
    """Marca como importadas las entradas de la bandeja activa (LifeDeck o Notion). Nunca aborta el import."""
    from src.integrations import inbox
    return inbox.mark_imported(page_ids)


def _sync_lifedeck_background() -> None:
    """Sube categorías + resumen del mes a LifeDeck en segundo plano (si está activo)."""
    try:
        from src.integrations.lifedeck import sync_summary_background
        sync_summary_background()
    except Exception:
        pass


@router.post("/notion/archive", response_model=NotionArchiveResponse)
@router.post("/inbox/archive", response_model=NotionArchiveResponse)
def notion_archive(req: NotionArchiveRequest) -> NotionArchiveResponse:
    """Descarta entradas de la bandeja sin importarlas (Notion: archiva; LifeDeck: 'discarded')."""
    from src.integrations import inbox
    ids = [pid for pid in req.page_ids if pid]
    if not ids:
        raise HTTPException(400, "No hay entradas para borrar.")
    return NotionArchiveResponse(archived=inbox.mark_discarded(ids))


# ── Chat / búsqueda en lenguaje natural ─────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    import chat_search
    if not llm.is_llm_enabled():
        raise HTTPException(503, "IA desactivada. Actívala en Utilidades.")
    try:
        extracted = chat_search.extract_params(req.query)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"No se pudo interpretar la consulta: {exc}")

    result = chat_search.run_search(extracted["tool"], extracted["params"])
    return ChatResponse(
        tool=extracted["tool"], params=extracted["params"],
        summary=result["summary"], count=result["count"], total=result["total"],
        entries=[ChatResultEntry(**e) for e in result["entries"]],
    )


@router.post("/chat/run", response_model=ChatResponse)
def chat_run(req: ChatRunRequest) -> ChatResponse:
    """Re-ejecuta una búsqueda con parámetros ya extraídos (refinamiento manual),
    sin volver a llamar al LLM."""
    import chat_search
    try:
        result = chat_search.run_search(req.tool, req.params)
    except Exception as exc:
        raise HTTPException(502, f"Error ejecutando la búsqueda: {exc}")
    return ChatResponse(
        tool=req.tool, params=req.params,
        summary=result["summary"], count=result["count"], total=result["total"],
        entries=[ChatResultEntry(**e) for e in result["entries"]],
    )


# ── Notion ──────────────────────────────────────────────────────────────────


# Rutas /notion/* y /inbox/*: misma lógica sobre la bandeja activa (LifeDeck si está activado, si no Notion).
@router.get("/notion/status", response_model=NotionStatus)
@router.get("/inbox/status", response_model=NotionStatus)
def notion_status() -> NotionStatus:
    source = "Notion"
    try:
        from src.integrations import inbox
        client = inbox.get_inbox_client()
        source = inbox.source_name(client)
        if not client.is_configured():
            return NotionStatus(configured=False, ok=False, detail=f"{source} no configurado.", source=source)
        ok, detail = client.test_connection()
        return NotionStatus(configured=True, ok=ok, detail=detail, source=source)
    except Exception as exc:
        return NotionStatus(configured=False, ok=False, detail=str(exc), source=source)


@router.get("/notion/pending-count", response_model=dict)
@router.get("/inbox/pending-count", response_model=dict)
def notion_pending_count() -> dict:
    """Nº de entradas nuevas (no duplicadas) pendientes en la bandeja. 0 si no aplica.
    Ligero para el banner de arranque; degrada a 0 ante cualquier error."""
    source = "Notion"
    try:
        from src.integrations import inbox
        client = inbox.get_inbox_client()
        source = inbox.source_name(client)
        if not client.is_configured():
            return {"count": 0, "configured": False, "source": source}
        raw = client.get_all_entries()
        existing = _existing_keys_all()
        count = 0
        needs_ai = 0
        from src.config import load_config
        llm_on = bool(load_config().get("llm", {}).get("enabled", False))
        for it in raw:
            fecha = it.get("fecha")
            fecha_str = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha or "")
            importe = abs(float(it.get("importe", 0)))
            if (round(importe, 2), fecha_str) not in existing:
                count += 1
            # Sin categoría (o gasto sin relevancia) → la vista previa preguntará a la IA.
            tipo = str(it.get("tipo", "")).upper()
            if llm_on and (not it.get("categoria") or ("GASTO" in tipo and not it.get("relevancia"))):
                needs_ai += 1
        return {"count": count, "configured": True, "source": source, "total": len(raw), "needs_ai": needs_ai}
    except Exception:
        return {"count": 0, "configured": False, "source": source}


@router.post("/notion/preview", response_model=ImportPreviewResponse)
@router.post("/inbox/preview", response_model=ImportPreviewResponse)
def notion_preview() -> ImportPreviewResponse:
    from src.integrations import inbox
    from src.integrations import notion_parser as np
    client = inbox.get_inbox_client()
    source = inbox.source_name(client)
    if not client.is_configured():
        raise HTTPException(400, f"{source} no está configurado.")
    try:
        raw = client.get_all_entries()
    except Exception as exc:
        raise HTTPException(502, f"Error consultando {source}: {exc}")
    if inbox.is_lifedeck(client):
        _sync_lifedeck_background()

    existing = _existing_keys_all()
    # id → nombre para resolver la categoría sugerida a un nombre real de la app,
    # de modo que coincida con un <SelectItem> en el UI y con la búsqueda en commit.
    cat_name_by_id = {c.id: c.nombre for c in db.get_all_categorias()}
    # Mapeo de tipos flexible (emojis, "Traspaso Entrada", inglés, aliases de config).
    import time
    from concurrent.futures import ThreadPoolExecutor
    from src.config import load_config
    config = load_config()
    tipo_mapping = np._build_tipo_mapping(config)
    llm_on = bool(config.get("llm", {}).get("enabled", False))
    t0 = time.monotonic()

    def classify(it: dict) -> ImportEntry:
        fecha = it.get("fecha")
        fecha_str = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha or "")
        importe = abs(float(it.get("importe", 0)))
        dup = (round(importe, 2), fecha_str) in existing

        concepto = str(it.get("concepto", ""))
        cat_hint = it.get("categoria") or ""
        tipo_enum = np.map_tipo_movimiento(str(it.get("tipo", "")), tipo_mapping=tipo_mapping)
        tipo = tipo_enum.value

        # Resolver la categoría a una categoría real de la app (exacta/fuzzy; IA solo si no casa).
        cat_id = np.find_best_category(concepto, tipo_enum, cat_hint)
        cat_name = cat_name_by_id.get(cat_id) if cat_id else None
        confianza = 1.0 if cat_name else 0.0
        hint_ok = bool(cat_hint) and cat_name is not None and np.normalize_text(cat_name) == np.normalize_text(cat_hint)
        ai = llm_on and not hint_ok

        # Relevancia sólo para gastos: usar la que llega o sugerirla (IA si está activada).
        relevancia = None
        if tipo_enum == TipoMovimiento.GASTO:
            rel_in = it.get("relevancia") or ""
            if rel_in:
                relevancia = rel_in
            else:
                relevancia = np.suggest_relevancia(concepto, cat_name or cat_hint).value
                ai = ai or llm_on

        return ImportEntry(
            fecha=fecha_str, concepto=concepto,
            importe=importe, tipo_movimiento=tipo,
            categoria_sugerida=cat_name, relevancia=relevancia,
            confianza=confianza, is_duplicate=dup,
            notion_id=it.get("id"), ai_classified=ai,
        )

    # En paralelo: las consultas a Ollama de cada apunte no se esperan unas a otras.
    if len(raw) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(raw))) as pool:
            entries = list(pool.map(classify, raw))
    else:
        entries = [classify(it) for it in raw]
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return ImportPreviewResponse(
        file_type=source, entries=entries,
        ai_count=sum(1 for e in entries if e.ai_classified), elapsed_ms=elapsed_ms,
    )


# ── LifeDeck ────────────────────────────────────────────────────────────────
@router.get("/lifedeck/status", response_model=NotionStatus)
def lifedeck_status() -> NotionStatus:
    """Prueba la conexión con LifeDeck aunque no esté activado como bandeja."""
    from src.integrations.lifedeck import get_lifedeck_client
    client = get_lifedeck_client()
    if not client.is_configured():
        return NotionStatus(configured=False, ok=False, detail="Falta la URL o el token de LifeDeck.", source="LifeDeck")
    ok, detail = client.test_connection()
    return NotionStatus(configured=True, ok=ok, detail=detail, source="LifeDeck")


@router.post("/lifedeck/sync", response_model=LifeDeckSyncResponse)
def lifedeck_sync() -> LifeDeckSyncResponse:
    """Sube ahora el catálogo de categorías y el resumen del mes actual a LifeDeck."""
    from src.integrations.lifedeck import LifeDeckError, get_lifedeck_client, sync_summary
    if not get_lifedeck_client().is_configured():
        raise HTTPException(400, "Falta la URL o el token de LifeDeck.")
    try:
        res = sync_summary()
    except LifeDeckError as exc:
        raise HTTPException(502, str(exc))
    return LifeDeckSyncResponse(
        ok=True, categories=res["categories"], month=res["month"], hints=res.get("hints", 0),
        detail=(
            f"Resumen de {res['month']}, {res['categories']} categorías y "
            f"{res.get('hints', 0)} pistas de clasificación subidos a LifeDeck."
        ),
    )


def _existing_keys_all() -> set:
    return {
        (round(e.importe, 2), e.fecha_real.isoformat())
        for e in db.get_all_ledger_entries()
    }


# ── Admin: restaurar backup CSV / limpieza destructiva ──────────────────────
@router.post("/import/backup", response_model=BackupImportResponse)
async def import_backup(
    file: UploadFile = File(...),
    tipo: str = Form(...),
) -> BackupImportResponse:
    """Importa un CSV de backup (expenses|income|investments) reutilizando la
    migración legacy como función (sin subprocess)."""
    mode = _BACKUP_MODE.get(tipo)
    if not mode:
        raise HTTPException(400, f"tipo inválido: {tipo}. Usa expenses|income|investments.")

    import migration  # scripts/migration.py

    content = await file.read()
    suffix = Path(file.filename or "backup.csv").suffix or ".csv"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(content)
        tmp.close()
        try:
            inserted = migration.importar_csv_simple(Path(tmp.name), mode=mode)
        except Exception as exc:
            raise HTTPException(422, f"Error importando CSV: {exc}")
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except OSError:
            pass
    return BackupImportResponse(inserted=inserted, errors=[])


@router.post("/admin/cleanup", response_model=CleanupResponse)
def admin_cleanup(req: CleanupRequest) -> CleanupResponse:
    """Borra datos. scope='ledger' → LEDGER+CIERRES+SNAPSHOTS+notas+análisis.
    scope='full' → además CAT_MAESTROS y re-siembra categorías por defecto.
    Exige `confirm` == frase exacta."""
    if req.confirm.strip() != _CLEANUP_PHRASE:
        raise HTTPException(400, f'Escribe exactamente "{_CLEANUP_PHRASE}" para confirmar.')

    reseeded = 0
    with db.get_connection() as conn:
        for table in ("LEDGER", "CIERRES_MENSUALES", "SNAPSHOTS_MENSUALES",
                      "PERIOD_NOTES", "AI_ANALYSIS"):
            conn.execute(f"DELETE FROM {table}")
        if req.scope == "full":
            conn.execute("DELETE FROM CAT_MAESTROS")
            import setup_db  # scripts/setup_db.py
            setup_db.insert_default_categories(conn)
            reseeded = conn.execute("SELECT COUNT(*) FROM CAT_MAESTROS").fetchone()[0]
        conn.commit()

    # Invalidar cachés en disco de la capa de dominio.
    if hasattr(db, "_clear_ledger_cache"):
        db._clear_ledger_cache()

    return CleanupResponse(
        ok=True,
        detail=f"Limpieza '{req.scope}' completada.",
        reseeded=reseeded,
    )
