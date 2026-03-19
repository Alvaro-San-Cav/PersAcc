"""
Página de Cargar Datos - PersAcc
Importa movimientos bancarios de ficheros legacy (AEB Norma 43, SEPA, Excel),
los analiza con IA y permite grabarlos en la base de datos.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from typing import Optional

import streamlit as st

from src.config import load_config
from src.i18n import t
from src.database import get_all_categorias, get_all_ledger_entries, insert_ledger_entry
from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry
from src.business_logic import calcular_mes_fiscal
from src.ai.file_parser import parse_file, FileType
from src.ai.llm_service import (
    is_llm_enabled, check_ollama_running, classify_bank_transactions
)

logger = logging.getLogger(__name__)

# Umbral de confianza para separar entradas "bien clasificadas" de las que "revisar"
CONFIDENCE_THRESHOLD = 0.75

# Tipos de movimiento válidos como texto → enum
_TIPO_MAP = {
    "GASTO": TipoMovimiento.GASTO,
    "INGRESO": TipoMovimiento.INGRESO,
    "TRASPASO_ENTRADA": TipoMovimiento.TRASPASO_ENTRADA,
    "TRASPASO_SALIDA": TipoMovimiento.TRASPASO_SALIDA,
    "INVERSION_AHORRO": TipoMovimiento.INVERSION,
}

_TIPOS_DISPLAY = {
    TipoMovimiento.GASTO: "🔴 Gasto",
    TipoMovimiento.INGRESO: "🟢 Ingreso",
    TipoMovimiento.INVERSION: "🟣 Inversión/Ahorro",
    TipoMovimiento.TRASPASO_ENTRADA: "🔵 Traspaso Entrada",
    TipoMovimiento.TRASPASO_SALIDA: "🟠 Traspaso Salida",
}

_REL_OPTIONS = ["NE", "LI", "SUP", "TON", ""]


def render_cargar_datos():
    """Función principal de la sección Cargar Datos."""
    st.markdown(
        f'<div class="main-header"><h1>{t("cargar_datos.title")}</h1></div>',
        unsafe_allow_html=True,
    )
    st.caption(t("cargar_datos.subtitle"))
    st.markdown("---")

    # Estado de sesión
    if "cd_results" not in st.session_state:
        st.session_state["cd_results"] = None
    if "cd_file_text" not in st.session_state:
        st.session_state["cd_file_text"] = None
    if "cd_file_type" not in st.session_state:
        st.session_state["cd_file_type"] = None

    # Si ya hay resultados, mostrar fase de revisión/grabación
    if st.session_state["cd_results"] is not None:
        _render_results()
        return

    # Fase 1: Upload + Preview
    _render_upload_phase()


# ---------------------------------------------------------------------------
# FASE 1 — Subida de fichero y preview
# ---------------------------------------------------------------------------

def _render_upload_phase():
    col_up, col_info = st.columns([2, 1])

    with col_up:
        uploaded = st.file_uploader(
            t("cargar_datos.upload_label"),
            type=["csb", "aeb", "txt", "n43", "xlsx", "xls"],
            help=t("cargar_datos.upload_types"),
            key="cd_uploader",
        )

    with col_info:
        st.markdown("#### Formatos soportados")
        st.markdown(
            """
- **AEB Norma 43** (`.csb`, `.aeb`, `.txt`, `.n43`)
- **AEB SEPA** (detección automática)
- **Excel** (`.xlsx`, `.xls`)
            """
        )

    if not uploaded:
        st.info(t("cargar_datos.no_file"))
        return

    # Detectar tipo y parsear
    content_bytes = uploaded.read()
    file_type, file_text = parse_file(uploaded.name, content_bytes)

    st.markdown(
        t("cargar_datos.file_detected", name=uploaded.name, size=len(content_bytes))
    )
    st.markdown(f"{t('cargar_datos.file_type_label')} **{file_type.value}**")

    if file_type == FileType.UNKNOWN:
        st.warning(t("cargar_datos.file_type_unknown"))

    # Preview
    with st.expander(t("cargar_datos.preview_title"), expanded=True):
        st.caption(t("cargar_datos.preview_caption"))
        preview_lines = file_text.splitlines()[:60]
        st.text_area(
            label="",
            value="\n".join(preview_lines),
            height=320,
            disabled=True,
            key="cd_preview_area",
            label_visibility="collapsed",
        )
        if len(file_text.splitlines()) > 60:
            st.caption(f"... ({len(file_text.splitlines())} líneas en total, mostrando primeras 60)")

    st.markdown("---")

    # Botón de análisis
    llm_active = is_llm_enabled()
    ollama_ok = check_ollama_running() if llm_active else False

    if not llm_active:
        st.warning(t("cargar_datos.llm_disabled"))
    elif not ollama_ok:
        st.warning(t("cargar_datos.ollama_not_running"))

    analyze_disabled = not (llm_active and ollama_ok)

    if st.button(
        t("cargar_datos.analyze_button"),
        disabled=analyze_disabled,
        use_container_width=True,
        type="primary",
        help=t("cargar_datos.analyze_help"),
        key="cd_analyze_btn",
    ):
        _run_analysis(file_text, file_type)


def _run_analysis(file_text: str, file_type: FileType):
    """Llama al LLM y guarda resultados en session_state."""
    with st.spinner(t("cargar_datos.analyzing")):
        try:
            categorias = get_all_categorias()
            # Pasar tuplas de (nombre, tipo, desc) al prompt para dar contexto exacto
            cat_tuples = []
            for c in categorias:
                desc_text = f" - NOTA: {c.descripcion_ia}" if c.descripcion_ia else ""
                cat_tuples.append(f"{c.nombre} (Tipo: {c.tipo_movimiento.value}){desc_text}")
                
            # --- LOTES DE 5 LÍNEAS ---
            # Para evitar alucinaciones y timeouts en ficheros grandes, procesamos en bloques de 5.
            lines = [l for l in file_text.strip().split('\n') if l.strip()]
            
            # Filtrar posibles líneas vacías y agrupar de 5 en 5
            CHUNK_SIZE = 5
            chunks = ["\n".join(lines[i:i+CHUNK_SIZE]) for i in range(0, len(lines), CHUNK_SIZE)]
            
            results = []
            
            if chunks:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, chunk_text in enumerate(chunks):
                    status_text.text(f"Analizando lote {i+1} de {len(chunks)} con IA (5 movimientos/lote)...")
                    try:
                        chunk_results = classify_bank_transactions(
                            text_content=chunk_text,
                            file_type=file_type.name,
                            categorias=cat_tuples,
                        )
                        results.extend(chunk_results)
                    except Exception as e:
                        logger.error(f"Error procesando lote {i+1}: {e}")
                        # Continuamos con el siguiente lote aunque este falle
                        
                    progress_bar.progress((i + 1) / len(chunks))
                
                status_text.empty()
                progress_bar.empty()
            
            # POST-PROCESAMIENTO: Forzar el tipo de movimiento según la base de datos
            cat_by_name = {}
            for c in categorias:
                if c.nombre not in cat_by_name:
                    cat_by_name[c.nombre] = []
                cat_by_name[c.nombre].append(c)

            for res in results:
                cat_name = res.get("categoria_sugerida")
                if cat_name in cat_by_name:
                    match_cats = cat_by_name[cat_name]
                    if len(match_cats) == 1:
                        # Hay exactamente una categoría con este nombre, forzamos su tipo
                        res["tipo_movimiento"] = match_cats[0].tipo_movimiento.value
                    else:
                        # Hay varias categorías con este nombre (ej. una como GASTO y otra INGRESO)
                        # Fallback: usar el tipo del LLM o el primero de DB
                        llm_tipo = res.get("tipo_movimiento")
                        if not any(c.tipo_movimiento.value == llm_tipo for c in match_cats):
                            res["tipo_movimiento"] = match_cats[0].tipo_movimiento.value

            st.session_state["cd_results"] = results
            st.session_state["cd_file_text"] = file_text
            st.session_state["cd_file_type"] = file_type
            st.rerun()
        except Exception as e:
            st.error(t("cargar_datos.error_analysis", error=str(e)))


# ---------------------------------------------------------------------------
# FASE 3/4 — Revisión y grabación de entradas
# ---------------------------------------------------------------------------

def _render_results():
    results: list[dict] = st.session_state["cd_results"]

    if not results:
        st.warning("El análisis no devolvió ninguna entrada. Prueba con otro modelo o fichero.")
        if st.button(t("cargar_datos.reset_button"), key="cd_reset_empty"):
            _reset_state()
        return

    # Cargar categorías para los selectores
    categorias = get_all_categorias()
    cat_names_all = [c.nombre for c in categorias]
    cat_by_name = {c.nombre: c for c in categorias}

    # Configuración centralizada desde Utilidades > Configuración
    dedup_cfg = _load_automatic_load_config()
    filtered_results, ignored = _split_ignored_entries(results, dedup_cfg)

    # Métricas globales
    total = len(results)
    avg_conf = sum(r.get("confianza", 0) for r in filtered_results) / len(filtered_results) if filtered_results else 0
    good = [r for r in filtered_results if r.get("confianza", 0) >= CONFIDENCE_THRESHOLD]
    review = [r for r in filtered_results if r.get("confianza", 0) < CONFIDENCE_THRESHOLD]

    st.markdown(f"### {t('cargar_datos.results_title')}")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total movimientos", total)
    m2.metric("✅ Bien clasificadas", len(good))
    m3.metric("⚠️ A revisar", len(review))
    m4.metric("Confianza media", f"{avg_conf*100:.0f}%")
    m5.metric("🚫 Ignoradas", len(ignored))

    st.caption(
        t("cargar_datos.threshold_info",
          threshold=int(CONFIDENCE_THRESHOLD * 100))
    )
    st.markdown("---")

    tab_good, tab_review, tab_ignored = st.tabs([
        t("cargar_datos.tab_good", count=len(good)),
        t("cargar_datos.tab_review", count=len(review)),
        t("cargar_datos.tab_ignored", count=len(ignored)),
    ])

    with tab_good:
        if not good:
            st.info(t("cargar_datos.no_good_entries"))
        else:
            saved_good = _render_entries_editor(good, cat_names_all, cat_by_name, suffix="good")
            _render_save_button(saved_good, cat_by_name, suffix="good")

    with tab_review:
        if not review:
            st.success(t("cargar_datos.no_review_entries"))
        else:
            saved_rev = _render_entries_editor(review, cat_names_all, cat_by_name, suffix="review")
            _render_save_button(saved_rev, cat_by_name, suffix="review")

    with tab_ignored:
        if not ignored:
            st.info(t("cargar_datos.no_ignored_entries"))
        else:
            st.caption(t("cargar_datos.ignored_caption"))
            _render_ignored_entries(ignored)

    st.markdown("---")
    if st.button(t("cargar_datos.reset_button"), key="cd_reset_btn"):
        _reset_state()


def _render_entries_editor(
    entries: list[dict],
    cat_names: list[str],
    cat_by_name: dict,
    suffix: str,
) -> list[dict]:
    """
    Renderiza un editor de entradas y devuelve la lista (posiblemente editada).
    El st.data_editor de Streamlit gestiona la edición in-place.
    """
    import pandas as pd

    # Leer si el análisis de relevancia está habilitado
    enable_relevance = load_config().get("enable_relevance", True)

    tipo_options = [t.value for t in TipoMovimiento]
    tipo_display_map = {t.value: _TIPOS_DISPLAY.get(t, t.value) for t in TipoMovimiento}

    rows = []
    for e in entries:
        row = {
            t("cargar_datos.col_select"): True,
            t("cargar_datos.col_date"): e.get("fecha", ""),
            t("cargar_datos.col_type"): e.get("tipo_movimiento", "GASTO"),
            t("cargar_datos.col_category"): e.get("categoria_sugerida", cat_names[0] if cat_names else ""),
            t("cargar_datos.col_original_concept"): e.get("concepto_original", ""),
            t("cargar_datos.col_concept"): e.get("concepto", ""),
            t("cargar_datos.col_amount"): round(e.get("importe", 0.0), 2),
            t("cargar_datos.col_confidence"): int(e.get("confianza", 0) * 100),
        }
        if enable_relevance:
            row[t("cargar_datos.col_relevance")] = e.get("relevancia") or ""
        rows.append(row)

    df = pd.DataFrame(rows)
    col_select = t("cargar_datos.col_select")
    col_date = t("cargar_datos.col_date")
    col_type = t("cargar_datos.col_type")
    col_cat = t("cargar_datos.col_category")
    col_orig = t("cargar_datos.col_original_concept")
    col_concept = t("cargar_datos.col_concept")
    col_amount = t("cargar_datos.col_amount")
    col_rel = t("cargar_datos.col_relevance")
    col_conf = t("cargar_datos.col_confidence")

    column_config = {
        col_select: st.column_config.CheckboxColumn(
            col_select,
            help="Seleccionar para grabar",
            default=True,
            width="small",
        ),
        col_date: st.column_config.TextColumn(col_date, width="small"),
        col_type: st.column_config.SelectboxColumn(
            col_type,
            options=[tm.value for tm in TipoMovimiento],
            width="medium",
        ),
        col_cat: st.column_config.SelectboxColumn(
            col_cat,
            options=cat_names,
            width="medium",
        ),
        col_orig: st.column_config.TextColumn(col_orig, width="large"),
        col_concept: st.column_config.TextColumn(col_concept, width="large"),
        col_amount: st.column_config.NumberColumn(
            col_amount,
            step=0.01,
            format="%.2f",
            width="small",
        ),
        col_conf: st.column_config.ProgressColumn(
            col_conf,
            min_value=0,
            max_value=100,
            format="%d%%",
            width="small",
        ),
    }
    if enable_relevance:
        column_config[col_rel] = st.column_config.SelectboxColumn(
            col_rel,
            options=_REL_OPTIONS,
            width="small",
        )

    column_order = [
        col_select,
        col_date,
        col_type,
        col_cat,
        col_concept,
        col_amount,
    ]
    if enable_relevance:
        column_order.append(col_rel)
    column_order += [col_conf, col_orig]

    edited_df = st.data_editor(
        df,
        key=f"cd_editor_{suffix}",
        use_container_width=True,
        num_rows="fixed",
        column_config=column_config,
        column_order=column_order,
        disabled=[col_conf, col_orig],
        hide_index=True,
        height=min(400, 40 + len(rows) * 36),
    )

    # Convertir de vuelta a lista de dicts
    result = []
    for _, row in edited_df.iterrows():
        if row[col_select]:
            entry_out = {
                "fecha": row[col_date],
                "tipo_movimiento": row[col_type],
                "categoria_sugerida": row[col_cat],
                "concepto": row[col_concept],
                "importe": float(row[col_amount]),
                "relevancia": row[col_rel] if (enable_relevance and row.get(col_rel)) else None,
                "confianza": row[col_conf] / 100.0,
            }
            result.append(entry_out)
    return result


def _render_save_button(
    selected_entries: list[dict],
    cat_by_name: dict,
    suffix: str,
):
    """Botón de grabación y lógica de inserción en BD."""
    count = len(selected_entries)

    if count == 0:
        st.caption(t("cargar_datos.no_entries_selected"))
        return

    if st.button(
        t("cargar_datos.save_button", count=count),
        type="primary",
        use_container_width=True,
        key=f"cd_save_{suffix}",
    ):
        _save_entries(selected_entries, cat_by_name)


def _save_entries(entries: list[dict], cat_by_name: dict):
    """Itera las entradas seleccionadas y las graba en el LEDGER."""
    ok = 0
    errors = []

    progress = st.progress(0, text=t("cargar_datos.saving"))

    for i, entry in enumerate(entries):
        progress.progress((i + 1) / len(entries), text=t("cargar_datos.saving"))
        try:
            ledger_entry = _dict_to_ledger_entry(entry, cat_by_name)
            if ledger_entry:
                insert_ledger_entry(ledger_entry)
                ok += 1
        except Exception as e:
            errors.append(
                t("cargar_datos.save_error",
                  concepto=entry.get("concepto", "?"),
                  error=str(e))
            )
            logger.error(f"Error saving entry: {e} — {entry}")

    progress.empty()

    if errors:
        for err in errors:
            st.error(err)
        if ok > 0:
            st.warning(t("cargar_datos.save_partial", ok=ok, total=len(entries)))
        else:
            st.error("No se pudo grabar ninguna entrada. Revisa los errores.")
    else:
        st.success(t("cargar_datos.save_success", count=ok))
        # Reset state after successful save so user can load another file
        import time
        time.sleep(2)
        _reset_state()


def _dict_to_ledger_entry(entry: dict, cat_by_name: dict) -> Optional[LedgerEntry]:
    """Convierte un dict de análisis en un LedgerEntry, o None si hay error."""
    # Fecha
    fecha_str = entry.get("fecha", "")
    try:
        if fecha_str and len(fecha_str) >= 10:
            fecha = date.fromisoformat(fecha_str[:10])
        else:
            fecha = date.today()
    except ValueError:
        fecha = date.today()
        logger.warning(f"Invalid date '{fecha_str}', using today.")

    # Tipo de movimiento
    tipo_str = entry.get("tipo_movimiento", "GASTO").strip().upper()
    tipo = _TIPO_MAP.get(tipo_str, TipoMovimiento.GASTO)

    # Categoría
    cat_name = entry.get("categoria_sugerida", "").strip()
    categoria = cat_by_name.get(cat_name)
    if not categoria:
        # Fallback: primer categoría del tipo correcto
        all_cats = list(cat_by_name.values())
        matching = [c for c in all_cats if c.tipo_movimiento == tipo]
        if matching:
            categoria = matching[0]
        elif all_cats:
            categoria = all_cats[0]
        else:
            raise ValueError(f"No hay categorías disponibles en la BD")

    # Relevancia
    rel_str = (entry.get("relevancia") or "").strip().upper()
    relevancia = None
    if tipo == TipoMovimiento.GASTO and rel_str in ("NE", "LI", "SUP", "TON"):
        try:
            relevancia = RelevanciaCode(rel_str)
        except ValueError:
            relevancia = None

    importe = float(entry.get("importe", 0.0))
    concepto = entry.get("concepto", "Importado").strip() or "Importado"
    mes_fiscal = calcular_mes_fiscal(fecha)

    return LedgerEntry(
        id=None,
        fecha_real=fecha,
        fecha_contable=fecha,
        mes_fiscal=mes_fiscal,
        tipo_movimiento=tipo,
        categoria_id=categoria.id,
        concepto=concepto,
        importe=importe,
        relevancia_code=relevancia,
        flag_liquidez=False,
    )


def _reset_state():
    """Limpia el estado de sesión de la sección Cargar Datos."""
    for key in ["cd_results", "cd_file_text", "cd_file_type"]:
        st.session_state.pop(key, None)
    st.rerun()


def _load_automatic_load_config() -> dict:
    """Carga la configuración de deduplicación/filtro desde Utilidades > Configuración."""
    cfg = load_config().get("automatic_load", {})
    return {
        "enabled": bool(cfg.get("dedup_enabled", True)),
        "same_type_only": bool(cfg.get("same_type_only", True)),
        "amount_abs_tolerance": float(cfg.get("amount_abs_tolerance", 0.01)),
        "date_window_days": int(cfg.get("date_window_days", 3)),
        "text_similarity_threshold": float(cfg.get("text_similarity_threshold", 0.20)),
        "min_score": float(cfg.get("min_score", 0.40)),
        "min_rule_hits": int(cfg.get("min_rule_hits", 1)),
        "ignore_outside_current_period": bool(cfg.get("ignore_outside_current_period", True)),
    }


def _split_ignored_entries(entries: list[dict], cfg: dict) -> tuple[list[dict], list[dict]]:
    """Separa entradas a procesar vs entradas ignoradas por posible duplicado en LEDGER."""
    keep: list[dict] = []
    ignored: list[dict] = []

    # 1) Regla temporal: ignorar fuera del período actual (mes en curso)
    for raw_entry in entries:
        entry = dict(raw_entry)
        fecha = _parse_entry_date(entry.get("fecha", ""))
        if cfg.get("ignore_outside_current_period", True) and fecha and not _is_current_period(fecha):
            entry["_ignore_reason"] = "fuera del período actual"
            entry["_ignore_match_concept"] = ""
            ignored.append(entry)
        else:
            keep.append(entry)

    # 2) Si dedup está deshabilitado, devolvemos solo el filtro temporal
    if not cfg.get("enabled", True):
        return keep, ignored

    ledger_entries = get_all_ledger_entries()
    if not ledger_entries:
        return keep, ignored

    ledger_index = []
    for le in ledger_entries:
        ledger_index.append({
            "id": le.id,
            "fecha": le.fecha_real,
            "tipo": le.tipo_movimiento.value,
            "importe": float(le.importe),
            "concepto_norm": _normalize_text_for_match(le.concepto),
            "concepto": le.concepto,
        })

    dedup_keep: list[dict] = []

    for raw_entry in keep:
        entry = dict(raw_entry)
        maybe_dup = _find_best_duplicate(entry, ledger_index, cfg)
        if maybe_dup is None:
            dedup_keep.append(entry)
            continue

        entry["_ignore_reason"] = (
            f"score={maybe_dup['score']:.2f} | "
            f"match id={maybe_dup['ledger_id']} | "
            f"importe Δ={maybe_dup['amount_delta']:.2f} | "
            f"fecha Δ={maybe_dup['date_delta']}d | "
            f"texto={maybe_dup['text_similarity']:.2f}"
        )
        entry["_ignore_match_concept"] = maybe_dup.get("ledger_concept", "")
        ignored.append(entry)

    return dedup_keep, ignored


def _find_best_duplicate(entry: dict, ledger_index: list[dict], cfg: dict) -> Optional[dict]:
    """Busca el mejor candidato de duplicado por importe, fecha y similitud de texto."""
    importe = abs(float(entry.get("importe", 0.0) or 0.0))
    fecha = _parse_entry_date(entry.get("fecha", ""))
    tipo = (entry.get("tipo_movimiento") or "").strip().upper()
    concepto = entry.get("concepto_original") or entry.get("concepto") or ""
    concepto_norm = _normalize_text_for_match(concepto)

    amount_tol = max(float(cfg.get("amount_abs_tolerance", 0.01)), 0.0)
    date_window = max(int(cfg.get("date_window_days", 3)), 0)
    text_thr = float(cfg.get("text_similarity_threshold", 0.86))
    min_score = float(cfg.get("min_score", 0.82))
    min_rule_hits = int(cfg.get("min_rule_hits", 2))
    same_type_only = bool(cfg.get("same_type_only", True))

    best: Optional[dict] = None

    for ledger in ledger_index:
        if same_type_only and tipo and ledger["tipo"] != tipo:
            continue

        amount_delta = abs(importe - ledger["importe"])
        amount_ok = amount_delta <= amount_tol
        amount_exact = amount_delta <= 1e-6

        if fecha and ledger["fecha"]:
            date_delta = abs((fecha - ledger["fecha"]).days)
            date_ok = date_delta <= date_window
        else:
            date_delta = 9999
            date_ok = False

        text_similarity = SequenceMatcher(None, concepto_norm, ledger["concepto_norm"]).ratio() \
            if concepto_norm and ledger["concepto_norm"] else 0.0
        text_ok = text_similarity >= text_thr

        rule_hits = int(amount_ok) + int(date_ok) + int(text_ok)
        if amount_exact:
            # Coincidencia exacta de importe cuenta como evidencia extra.
            rule_hits += 1

        amount_score = 1.0 if amount_exact else (
            0.85 if amount_ok else max(0.0, 1.0 - (amount_delta / max(amount_tol, 0.01)))
        )
        date_score = 1.0 if date_ok else max(0.0, 1.0 - (date_delta / max(date_window, 1)))
        # Peso alto al importe y menor dependencia de texto.
        score = (0.75 * amount_score) + (0.20 * date_score) + (0.05 * text_similarity)

        if rule_hits < min_rule_hits or score < min_score:
            continue

        if best is None or score > best["score"]:
            best = {
                "ledger_id": ledger["id"],
                "ledger_concept": ledger["concepto"],
                "amount_delta": amount_delta,
                "amount_exact": amount_exact,
                "date_delta": date_delta if date_delta != 9999 else -1,
                "text_similarity": text_similarity,
                "score": score,
            }

    return best


def _parse_entry_date(value: str) -> Optional[date]:
    """Parse robusto de fecha para entradas provenientes del LLM."""
    try:
        if not value:
            return None
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _is_current_period(fecha: date) -> bool:
    """Devuelve True si la fecha pertenece al mes/año actual."""
    today = date.today()
    return fecha.year == today.year and fecha.month == today.month


def _normalize_text_for_match(text: str) -> str:
    """Normaliza texto para comparación aproximada de conceptos."""
    txt = (text or "").lower().strip()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-z0-9\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _render_ignored_entries(entries: list[dict]):
    """Tabla informativa de entradas ignoradas por duplicidad."""
    import pandas as pd

    rows = []
    for e in entries:
        rows.append({
            t("cargar_datos.col_date"): e.get("fecha", ""),
            t("cargar_datos.col_type"): e.get("tipo_movimiento", ""),
            t("cargar_datos.col_category"): e.get("categoria_sugerida", ""),
            t("cargar_datos.col_concept"): e.get("concepto", ""),
            t("cargar_datos.col_amount"): round(float(e.get("importe", 0.0) or 0.0), 2),
            t("cargar_datos.col_ignored_reason"): e.get("_ignore_reason", ""),
            t("cargar_datos.col_ignored_match"): e.get("_ignore_match_concept", ""),
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        height=min(400, 40 + len(rows) * 36),
    )
