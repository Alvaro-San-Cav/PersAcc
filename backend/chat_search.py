"""
Búsqueda en lenguaje natural sobre el ledger.

Reimplementación limpia (sin Streamlit) de la lógica de src/ui/search_assistant_new.py:
extrae parámetros con Ollama (chat API, formato JSON) y ejecuta la búsqueda
directamente sobre la DB, devolviendo entradas estructuradas + un resumen.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

import requests

from src.database import get_all_ledger_entries, get_all_categorias
from src.models import TipoMovimiento
from src.constants import STOPWORDS_ES
from src.ai import llm_service as llm

TOOLS_SPEC = [
    {"name": "search_expenses_by_concept",
     "desc": "Buscar gastos por texto/concepto. Params: concept (string), year (int), month (int)"},
    {"name": "search_expenses_by_category",
     "desc": "Buscar por categoría. Params: category_name (string), year (int), month (int)"},
    {"name": "get_top_expenses",
     "desc": "Ver gastos más grandes. Params: limit (int), year (int), month (int)"},
]


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    suffixes = ["cion", "sion", "mente", "ando", "iendo", "ado", "ido", "oso", "osa", "eno", "ena", "es", "s"]
    out = []
    for word in re.findall(r"\w+", text):
        if len(word) > 4:
            for suf in suffixes:
                if word.endswith(suf) and len(word) - len(suf) >= 3:
                    word = word[: -len(suf)]
                    break
        out.append(word)
    return " ".join(out)


def _tokens(text: str) -> list[str]:
    stop = {_normalize(w) for w in STOPWORDS_ES if w}
    return [w for w in _normalize(text).split() if w not in stop and len(w) > 1]


def _fuzzy(a: str, b: str, threshold: float = 0.75) -> bool:
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def extract_params(query: str) -> dict:
    """Extrae {tool, params} desde la pregunta usando Ollama. Lanza RuntimeError si falla."""
    if not llm.check_ollama_running():
        raise RuntimeError("Ollama no está en ejecución.")

    cfg = llm.get_llm_config()
    model = cfg.get("model_chat", cfg.get("model_analysis", "phi3"))
    now = datetime.now()
    system = f"""Eres un experto en extracción de datos financieros. Convierte la pregunta en JSON.
FECHA ACTUAL: {now.strftime('%Y-%m-%d')} (Mes: {now.month}, Año: {now.year})
HERRAMIENTAS:
{json.dumps(TOOLS_SPEC, indent=2, ensure_ascii=False)}
REGLAS:
1. Devuelve SOLO JSON válido.
2. En 'concept' extrae solo la palabra clave (sin preposiciones).
3. "año pasado" -> year: {now.year - 1}. "enero 2023" -> month:1, year:2023.
FORMATO: {{"tool": "...", "params": {{"concept": "...", "category_name": "...", "year": 0, "month": 0}}}}"""

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": query}],
        "stream": False, "format": "json", "options": {"temperature": 0.1},
    }
    if "qwen" in model.lower():
        payload["think"] = False

    urls = llm.get_ollama_urls()
    resp = requests.post(urls["chat"], json=payload, timeout=120)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "{}")
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if not content.startswith("{"):
        m = re.search(r"\{.*\}", content, re.DOTALL)
        content = m.group(0) if m else "{}"
    data = json.loads(content)
    params = data.get("params", {}) or {}
    # Limpiar ceros/vacíos que el modelo pone por defecto
    for k in ("year", "month"):
        if not params.get(k):
            params.pop(k, None)
    for k in ("concept", "category_name"):
        if not params.get(k):
            params.pop(k, None)
    return {"tool": data.get("tool", "search_expenses_by_concept"), "params": params}


def _entry_dict(e, cats) -> dict:
    return {
        "id": e.id, "fecha_real": e.fecha_real.isoformat(),
        "tipo_movimiento": e.tipo_movimiento.value,
        "categoria_nombre": cats.get(e.categoria_id, ""),
        "concepto": e.concepto or "", "importe": e.importe,
        "relevancia_code": e.relevancia_code.value if e.relevancia_code else None,
    }


def run_search(tool: str, params: dict) -> dict:
    """Ejecuta la búsqueda y devuelve {summary, count, total, entries}."""
    entries = get_all_ledger_entries()
    cats = {c.id: c.nombre for c in get_all_categorias()}
    year = params.get("year")
    month = params.get("month")

    def by_date(items):
        if year:
            items = [e for e in items if e.fecha_real.year == int(year)]
        if month:
            items = [e for e in items if e.fecha_real.month == int(month)]
        return items

    gastos = by_date([e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO])

    if tool == "search_expenses_by_category":
        name = (params.get("category_name") or "").lower()
        matched = [e for e in gastos if name and name in cats.get(e.categoria_id, "").lower()]
        label = f"Gastos en «{params.get('category_name', '')}»"
    elif tool == "get_top_expenses":
        limit = int(params.get("limit", 10) or 10)
        matched = sorted(gastos, key=lambda x: x.importe, reverse=True)[:limit]
        label = f"Top {limit} gastos"
    else:  # search_expenses_by_concept
        concept = params.get("concept", "")
        keywords = _tokens(concept) or [_normalize(concept)]
        matched = [e for e in gastos if e.concepto and all(kw in _normalize(e.concepto) for kw in keywords)]
        if not matched:  # fallback fuzzy
            scored = []
            for e in gastos:
                if not e.concepto:
                    continue
                ew = _tokens(e.concepto)
                hits = sum(1 for kw in keywords if any(_fuzzy(kw, w) for w in ew))
                if hits:
                    scored.append((e, hits))
            matched = [e for e, _ in sorted(scored, key=lambda x: x[1], reverse=True)]
        label = f"Gastos con «{concept}»"

    matched = sorted(matched, key=lambda x: x.importe, reverse=True)
    total = sum(e.importe for e in matched)
    return {
        "summary": f"{label}: {len(matched)} movimientos",
        "count": len(matched),
        "total": total,
        "entries": [_entry_dict(e, cats) for e in matched],
    }
