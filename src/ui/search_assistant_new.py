"""
Asistente de Búsqueda - PersAcc
UI con formulario editable para parámetros de búsqueda.
"""
import streamlit as st
from datetime import datetime, date
import json
import re
import unicodedata
from typing import List, Dict, Any
from collections import defaultdict
from difflib import SequenceMatcher

from src.i18n import t
from src.ai.llm_service import is_llm_enabled, get_llm_config
from src.database import get_all_ledger_entries, get_all_categorias
from src.models import TipoMovimiento
from src.config import format_currency


def render_chat_search():
    """Renderiza el Asistente de Búsqueda con formulario editable."""
    st.markdown(f'<div class="main-header"><h1>{t("chat_search.title")}</h1></div>', unsafe_allow_html=True)
    st.markdown(f"*{t('chat_search.subtitle')}*")
    
    if not is_llm_enabled():
        st.warning(t("chat_search.llm_not_configured"))
        return
    
    llm_config = get_llm_config()
    st.caption(t("chat_search.active_model", model=llm_config.get('model_tier', 'desconocido')))
    
    if 'search_params' not in st.session_state:
        st.session_state.search_params = None
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    
    st.markdown("---")
    
    # Input + Analizar
    col1, col2 = st.columns([5, 1])
    with col1:
        query = st.text_input("🔍", placeholder=t("chat_search.input_placeholder"), key="q_in", label_visibility="collapsed")
    with col2:
        st.write(""); st.write("")
        if st.button(t("chat_search.analyze_button"), use_container_width=True, type="primary") and query:
            with st.spinner(t("chat_search.thinking")):
                _extract_params(query)
    
    st.markdown("---")
    
    # Formulario
    if st.session_state.search_params:
        _render_form()
    
    # Resultados
    if st.session_state.search_results:
        st.markdown(f"### {t('chat_search.results_title')}")
        if st.button(t('chat_search.new_search')):
            st.session_state.search_params = None
            st.session_state.search_results = None
            st.rerun()
        st.markdown(st.session_state.search_results['result'])


def _extract_params(query):
    """Extrae parámetros usando LLM con prompt específico (sin librería ollama)."""
    try:
        import requests
        import json
        from src.ai.llm_service import is_llm_enabled, get_llm_config, check_ollama_running, _validate_and_normalize_params, get_current_season
        
        # 1. Verificaciones previas
        if not is_llm_enabled():
            st.error(t('chat_search.llm_disabled'))
            return
        
        if not check_ollama_running():
            st.error(t('chat_search.ollama_not_running'))
            st.info(t('chat_search.ollama_hint'))
            return
            
        llm_config = get_llm_config()
        model = llm_config.get('model_tier') or 'phi3'
        
        st.success(t('chat_search.analyzing', model=model))
        
        # 2. Construir Prompt Robusto
        tools_spec = [
            {"name": "search_expenses_by_concept", "desc": "Buscar gastos por texto/concepto (ej: 'gastos en mery', 'compras en zara'). Params: concept (string), year (int), month (int/string)"},
            {"name": "search_expenses_by_category", "desc": "Buscar por categoría (ej: 'transporte', 'restaurantes'). Params: category_name (string), year (int), month (int)"},
            {"name": "get_top_expenses", "desc": "Ver gastos más grandes. Params: limit (int), year (int), month (int)"},
        ]
        
        now = datetime.now()
        season = get_current_season()
        
        system_prompt = f"""Eres un experto en extracción de datos financieros. Tu trabajo es convertir la pregunta del usuario en un objeto JSON.

FECHA ACTUAL: {now.strftime('%Y-%m-%d')} (Mes: {now.month}, Año: {now.year}, Estación: {season})

HERRAMIENTAS DISPONIBLES:
{json.dumps(tools_spec, indent=2)}

REGLAS CRÍTICAS:
1. Retorna SOLO un JSON válido. Nada más.
2. Para 'search_expenses_by_concept': en el campo 'concept', extrae SOLO el nombre clave. Elimina preposiciones como "en", "de", "para", "el". 
   Ejemplo: "gasto en mery" -> concept: "mery" (NO "mery en").
   Ejemplo: "comida en burger king" -> concept: "burger king".
   Ejemplo: "cuanto me deje en mery en febrero" -> concept: "mery".
3. Fechas:
   - "año pasado" -> year: {now.year - 1}
   - "mes pasado" -> month: {now.month - 1 if now.month > 1 else 12}, year: {now.year if now.month > 1 else now.year - 1}
   - "enero 2023" -> month: 1, year: 2023

FORMATO RESPUESTA:
{{
  "tool": "nombre_herramienta",
  "params": {{
    "concept": "...",
    "category_name": "...",
    "year": 2025,
    "month": 1
  }}
}}
"""
        
        # 3. Llamada directa a API Ollama (sin librería externa)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1}
        }
        
        try:
            response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            content = result.get('message', {}).get('content', '{}')
            
            # Parsear JSON
            data = json.loads(content)
            tool_name = data.get('tool')
            params = data.get('params', {})
            
            # Normalizar mes si viene como string
            if isinstance(params.get('month'), str):
                meses_dict = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, 
                              "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
                mes_lower = params['month'].lower()
                if mes_lower in meses_dict:
                    params['month'] = meses_dict[mes_lower]
            
        except Exception as e:
            st.error(f"Error llamando al modelo: {e}")
            return

        if not tool_name:
            st.error("❌ El modelo no identificó la herramienta")
            return
            
        # 4. Validar y Guardar
        validated, errors = _validate_and_normalize_params(tool_name, params, query)
        
        st.session_state.search_params = {
            'tool': tool_name, 
            'params': validated, 
            'query': query, 
            'errors': errors
        }
        
        if errors:
            st.warning(" | ".join(errors))
        else:
            st.success(f"✅ Interpretación: {tool_name}")
        
        st.rerun()

    except Exception as e:
        st.error(f"Error en extracción: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


def _render_form():
    """Renderiza formulario editable."""
    st.markdown("### 📝 Parámetros")
    st.caption("Revisa y modifica")
    p = st.session_state.search_params
    tool_map = {"search_expenses_by_concept": "Por concepto", "search_expenses_by_category": "Por categoría",
                "get_top_expenses": "Mayores gastos", "get_category_breakdown": "Desglose", "get_savings_rate": "Tasa ahorro"}
    idx = list(tool_map.keys()).index(p['tool']) if p['tool'] in tool_map else 0
    
    with st.form("form"):
        tipo = st.selectbox("Tipo:", list(tool_map.values()), index=idx)
        col1, col2 = st.columns(2)
        val, lim = None, 10
        with col1:
            if tipo == "Por concepto":
                val = st.text_input("Concepto:", p['params'].get('concept', ''))
            elif tipo == "Por categoría":
                cats = [c.nombre for c in get_all_categorias() if c.tipo_movimiento == TipoMovimiento.GASTO]
                # Buscar índice por nombre (case insensitive)
                cat_idx = 0
                extracted_cat = p['params'].get('category_name', '').lower()
                if extracted_cat:
                    for i, c in enumerate(cats):
                        if c.lower() == extracted_cat:
                            cat_idx = i
                            break
                val = st.selectbox(t('chat_search.category_label'), cats, index=cat_idx)
            elif tipo == "Mayores gastos":
                lim = st.number_input("Top:", value=p['params'].get('limit', 10), min_value=1)
        with col2:
            yr = st.number_input(t('chat_search.year_label'), value=p['params'].get('year', 0), min_value=0, max_value=datetime.now().year)
            meses = t('chat_search.months')
            mes_idx = p['params'].get('month', 0) or 0
            mes = st.selectbox(t('chat_search.month_label'), meses, index=mes_idx)
        
        if st.form_submit_button(t('chat_search.execute_button'), use_container_width=True, type="primary"):
            tool = {v: k for k, v in tool_map.items()}[tipo]
            params = {}
            if tipo == "Por concepto" and val:
                params['concept'] = val
            elif tipo == "Por categoría" and val:
                params['category_name'] = val
            elif tipo == "Mayores gastos":
                params['limit'] = lim
            if yr > 0:
                params['year'] = yr
            if mes != meses[0]:  # Check against "All"/"Todos" dynamically
                params['month'] = meses.index(mes)
            _execute(tool, params)


def _execute(tool, params):
    """Ejecuta búsqueda."""
    with st.spinner("🔍 Buscando..."):
        funcs = {"search_expenses_by_concept": search_expenses_by_concept, "search_expenses_by_category": search_expenses_by_category,
                 "get_top_expenses": get_top_expenses, "get_category_breakdown": get_category_breakdown, "get_savings_rate": get_savings_rate}
        try:
            result = funcs[tool](**params)
            st.session_state.search_results = {'tool': tool, 'params': params, 'result': result, 'ts': datetime.now()}
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")


def _get_available_tools():
    """Define herramientas para el LLM."""
    return [
        {"name": "search_expenses_by_concept", "description": "Busca gastos por concepto", 
         "parameters": {"type": "object", "properties": {"concept": {"type": "string"}, "year": {"type": "integer"}, "month": {"type": "integer"}}}},
        {"name": "search_expenses_by_category", "description": "Busca gastos por categoría",
         "parameters": {"type": "object", "properties": {"category_name": {"type": "string"}, "year": {"type": "integer"}, "month": {"type": "integer"}}}},
        {"name": "get_top_expenses", "description": "Top N gastos",
         "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}, "year": {"type": "integer"}, "month": {"type": "integer"}}}},
        {"name": "get_category_breakdown", "description": "Desglose por categoría",
         "parameters": {"type": "object", "properties": {"year": {"type": "integer"}, "month": {"type": "integer"}}}},
        {"name": "get_savings_rate", "description": "Calcula tasa de ahorro",
         "parameters": {"type": "object", "properties": {"year": {"type": "integer"}, "month": {"type": "integer"}}}}
    ]


# ================== TOOL FUNCTIONS ==================

def search_expenses_by_concept(concept: str, year: int = None, month: int = None) -> str:
    """Busca gastos por concepto con fuzzy matching."""
    entries = get_all_ledger_entries()
    cats_dict = {c.id: c.nombre for c in get_all_categorias()}
    
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        text = text.lower()
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        suffixes = ['cion', 'sion', 'mente', 'ando', 'iendo', 'ado', 'ido', 'oso', 'osa', 'eno', 'ena', 'es', 's']
        words = re.findall(r'\w+', text)
        stemmed = []
        for word in words:
            if len(word) > 4:
                for suffix in suffixes:
                    if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                        word = word[:-len(suffix)]
                        break
            stemmed.append(word)
        return ' '.join(stemmed)
    
    def tokenize(text: str) -> list:
        stop_words = {"el", "la", "los", "las", "un", "una", "de", "del", "al", "en", "para", "por", "y", "que", "con"}
        words = normalize_text(text).split()
        return [w for w in words if w not in stop_words and len(w) > 1]
    
    def fuzzy_match(word1: str, word2: str, threshold: float = 0.75) -> bool:
        if word1 == word2:
            return True
        if word1 in word2 or word2 in word1:
            return True
        similarity = SequenceMatcher(None, word1, word2).ratio()
        return similarity >= threshold
    
    keywords = tokenize(concept)
    if year:
        keywords = [w for w in keywords if w != str(year)]
    if not keywords:
        keywords = [normalize_text(concept)]
    
    st.toast(f"🔎 Búsqueda: {', '.join(keywords)}")
    
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    
    matching = []
    for e in expenses:
        if not e.concepto:
            continue
        entry_normalized = normalize_text(e.concepto)
        if all(kw in entry_normalized for kw in keywords):
            matching.append((e, 1.0))
    
    if not matching:
        for e in expenses:
            if not e.concepto:
                continue
            entry_words = tokenize(e.concepto)
            fuzzy_matches = 0
            for kw in keywords:
                if any(fuzzy_match(kw, entry_word) for entry_word in entry_words):
                    fuzzy_matches += 1
            if fuzzy_matches > 0:
                score = fuzzy_matches / len(keywords)
                matching.append((e, score))
        matching = sorted(matching, key=lambda x: x[1], reverse=True)
    
    if not matching:
        for e in expenses:
            if not e.concepto:
                continue
            entry_normalized = normalize_text(e.concepto)
            match_count = sum(1 for kw in keywords if kw in entry_normalized)
            if match_count > 0:
                matching.append((e, match_count / len(keywords)))
        matching = sorted(matching, key=lambda x: x[1], reverse=True)
    
    if not matching:
        sample_concepts = list(set([e.concepto[:30] for e in expenses if e.concepto]))[:5]
        hint = ""
        if sample_concepts:
            hint = f"\n\nAlgunos conceptos disponibles: {', '.join(sample_concepts)}"
        return f"No se encontraron gastos similares a '{concept}'{hint}"
    
    matched_entries = [entry for entry, score in matching]
    total = sum(e.importe for e in matched_entries)
    result = f"Encontrados {len(matched_entries)} gastos con '{concept}':\n\n"
    result += f"**Total: {format_currency(total)}**\n\n"
    result += "Detalles:\n"
    
    for e in sorted(matched_entries, key=lambda x: x.importe, reverse=True)[:10]:
        cat_name = cats_dict.get(e.categoria_id, "Sin categoría")
        result += f"- {e.fecha_real.strftime('%d/%m/%Y')}: {e.concepto[:50]} - {format_currency(e.importe)} ({cat_name})\n"
    
    if len(matched_entries) > 10:
        result += f"\n... y {len(matched_entries) - 10} más"
    
    return result


def search_expenses_by_category(category_name: str, year: int = None, month: int = None) -> str:
    """Busca gastos por categoría."""
    entries = get_all_ledger_entries()
    categories = get_all_categorias()
    matching_cats = [c for c in categories if category_name.lower() in c.nombre.lower()]
    if not matching_cats:
        available = ", ".join([c.nombre for c in categories])
        return f"No se encontró '{category_name}'. Disponibles: {available}"
    cat = matching_cats[0]
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO and e.categoria_id == cat.id]
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    if not expenses:
        return f"No se encontraron gastos en '{cat.nombre}'"
    total = sum(e.importe for e in expenses)
    result = f"Gastos en **{cat.nombre}**:\n\n**Total: {format_currency(total)}** ({len(expenses)} movimientos)\n\nMayores gastos:\n"
    for e in sorted(expenses, key=lambda x: x.importe, reverse=True)[:10]:
        result += f"- {e.fecha_real.strftime('%d/%m/%Y')}: {e.concepto[:50]} - {format_currency(e.importe)}\n"
    if len(expenses) > 10:
        result += f"\n... y {len(expenses) - 10} más"
    return result


def get_top_expenses(limit: int = 10, year: int = None, month: int = None) -> str:
    """Top N gastos."""
    entries = get_all_ledger_entries()
    catsdict = {c.id: c.nombre for c in get_all_categorias()}
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    if not expenses:
        return "No se encontraron gastos"
    top = sorted(expenses, key=lambda x: x.importe, reverse=True)[:limit]
    period = ""
    if year and month:
        period = f" de {month}/{year}"
    elif year:
        period = f" de {year}"
    result = f"**Top {len(top)} gastos{period}:**\n\n"
    for i, e in enumerate(top, 1):
        cat_name = catsdict.get(e.categoria_id, "Sin categoría")
        result += f"{i}. {e.fecha_real.strftime('%d/%m/%Y')}: {e.concepto[:40]} - **{format_currency(e.importe)}** ({cat_name})\n"
    return result


def get_category_breakdown(year: int = None, month: int = None) -> str:
    """Desglose por categoría."""
    entries = get_all_ledger_entries()
    cats_dict = {c.id: c.nombre for c in get_all_categorias()}
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    if not expenses:
        return "No se encontraron gastos"
    by_cat = defaultdict(float)
    for e in expenses:
        cat_name = cats_dict.get(e.categoria_id, "Sin categoría")
        by_cat[cat_name] += e.importe
    sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    total = sum(by_cat.values())
    period = ""
    if year and month:
        period = f" de {month}/{year}"
    elif year:
        period = f" de {year}"
    result = f"**Desglose por categoría{period}:**\n\nTotal gastos: {format_currency(total)}\n\n"
    for cat_name, amount in sorted_cats:
        pct = (amount / total * 100) if total > 0 else 0
        result += f"- **{cat_name}**: {format_currency(amount)} ({pct:.1f}%)\n"
    return result


def get_savings_rate(year: int = None, month: int = None) -> str:
    """Calcula tasa de ahorro."""
    entries = get_all_ledger_entries()
    filtered = entries
    if year:
        filtered = [e for e in filtered if e.fecha_real.year == year]
    if month:
        filtered = [e for e in filtered if e.fecha_real.month == month]
    if not filtered:
        return "No hay datos"
    total_income = sum(e.importe for e in filtered if e.tipo_movimiento == TipoMovimiento.INGRESO)
    total_investment = sum(e.importe for e in filtered if e.tipo_movimiento == TipoMovimiento.INVERSION)
    total_expense = sum(e.importe for e in filtered if e.tipo_movimiento == TipoMovimiento.GASTO)
    if total_income == 0:
        return "No hay ingresos registrados"
    savings_rate = (total_investment / total_income) * 100
    expense_rate = (total_expense / total_income) * 100
    period = ""
    if year and month:
        period = f" de {month}/{year}"
    elif year:
        period = f" de {year}"
    result = f"**Análisis financiero{period}:**\n\n"
    result += f"- Ingresos: {format_currency(total_income)}\n"
    result += f"- Gastos: {format_currency(total_expense)} ({expense_rate:.1f}%)\n"
    result += f"- Inversiones: {format_currency(total_investment)} ({savings_rate:.1f}%)\n"
    result += f"- Balance: {format_currency(total_income - total_expense)}\n\n"
    result += f"**Tasa de ahorro: {savings_rate:.1f}%**"
    return result
