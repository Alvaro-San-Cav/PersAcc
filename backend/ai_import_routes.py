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
    cat_by_name = {c.nombre.lower(): c for c in db.get_all_categorias()}
    to_insert: list[LedgerEntry] = []
    skipped = 0

    for item in req.entries:
        cat = cat_by_name.get((item.categoria_sugerida or "").lower())
        if not cat:
            skipped += 1
            continue
        try:
            tipo = TipoMovimiento(item.tipo_movimiento)
        except ValueError:
            skipped += 1
            continue
        try:
            fecha = date.fromisoformat(item.fecha)
        except ValueError:
            skipped += 1
            continue
        if db.is_mes_cerrado(bl.calcular_mes_fiscal(fecha)):
            skipped += 1
            continue

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

    inserted = db.batch_insert_ledger_entries(to_insert) if to_insert else 0
    return ImportCommitResponse(inserted=inserted, skipped=skipped)


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
_NOTION_TIPO_MAP = {
    "gasto": "GASTO", "ingreso": "INGRESO",
    "inversión": "INVERSION_AHORRO", "inversion": "INVERSION_AHORRO",
    "ahorro": "INVERSION_AHORRO",
}


@router.get("/notion/status", response_model=NotionStatus)
def notion_status() -> NotionStatus:
    try:
        from src.integrations.notion import get_notion_client
        client = get_notion_client()
        if not client.is_configured():
            return NotionStatus(configured=False, ok=False, detail="Notion no configurado.")
        ok, detail = client.test_connection()
        return NotionStatus(configured=True, ok=ok, detail=detail)
    except Exception as exc:
        return NotionStatus(configured=False, ok=False, detail=str(exc))


@router.get("/notion/pending-count", response_model=dict)
def notion_pending_count() -> dict:
    """Nº de entradas nuevas (no duplicadas) pendientes en Notion. 0 si no aplica.
    Ligero para el banner de arranque; degrada a 0 ante cualquier error."""
    try:
        from src.integrations.notion import get_notion_client
        client = get_notion_client()
        if not client.is_configured():
            return {"count": 0, "configured": False}
        raw = client.get_all_entries()
        existing = _existing_keys_all()
        count = 0
        for it in raw:
            fecha = it.get("fecha")
            fecha_str = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha or "")
            importe = abs(float(it.get("importe", 0)))
            if (round(importe, 2), fecha_str) not in existing:
                count += 1
        return {"count": count, "configured": True}
    except Exception:
        return {"count": 0, "configured": False}


@router.post("/notion/preview", response_model=ImportPreviewResponse)
def notion_preview() -> ImportPreviewResponse:
    from src.integrations.notion import get_notion_client
    client = get_notion_client()
    if not client.is_configured():
        raise HTTPException(400, "Notion no está configurado.")
    try:
        raw = client.get_all_entries()
    except Exception as exc:
        raise HTTPException(502, f"Error consultando Notion: {exc}")

    existing = _existing_keys_all()
    entries: list[ImportEntry] = []
    for it in raw:
        fecha = it.get("fecha")
        fecha_str = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha or "")
        tipo = _NOTION_TIPO_MAP.get(str(it.get("tipo", "")).strip().lower(), "GASTO")
        importe = abs(float(it.get("importe", 0)))
        dup = (round(importe, 2), fecha_str) in existing
        entries.append(ImportEntry(
            fecha=fecha_str, concepto=str(it.get("concepto", "")),
            importe=importe, tipo_movimiento=tipo,
            categoria_sugerida=it.get("categoria") or None,
            confianza=1.0, is_duplicate=dup,
        ))
    return ImportPreviewResponse(file_type="Notion", entries=entries)


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
