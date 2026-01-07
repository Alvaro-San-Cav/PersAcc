"""
Página de Chat Search - PersAcc
Asistente conversacional con acceso a la base de datos financiera.
"""
import streamlit as st
from datetime import datetime, date
import json
from typing import List, Dict, Any

from src.i18n import t
from src.llm_service import is_llm_enabled, get_llm_config, chat_with_tools
from src.database import (
    get_all_ledger_entries, get_all_categorias, 
    get_ledger_by_month, get_ledger_by_year
)
from src.models import TipoMovimiento
from src.config import format_currency


def render_chat_search():
    """Renderiza la interfaz de chat search."""
    st.markdown(f'<div class="main-header"><h1>{t("chat_search.title")}</h1></div>', unsafe_allow_html=True)
    st.markdown(f"*{t('chat_search.subtitle')}*")
    
    # Verificar si LLM está configurado
    if not is_llm_enabled():
        st.warning(t("chat_search.llm_not_configured"))
        return
    
    # Mostrar modelo activo
    llm_config = get_llm_config()
    model_name = llm_config.get('model_tier', 'desconocido')
    st.caption(f"🤖 Modelo activo: **{model_name}**")
    
    # Inicializar historial de chat en session_state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # Controles superiores: limpiar chat y modo debug
    col1, col2, col3 = st.columns([4, 2, 1])
    
    with col2:
        debug_mode = st.toggle(
            "🔍 Modo Debug", 
            value=st.session_state.get('debug_mode', False),
            help="Ver qué está decidiendo el LLM y cómo extrae parámetros",
            key="debug_mode_toggle"
        )
        # Guardar en session state
        st.session_state['debug_mode'] = debug_mode
    
    with col3:
        if st.button(t("chat_search.clear_button"), use_container_width=True):
            st.session_state.chat_messages = []
            if 'last_search_trace' in st.session_state:
                del st.session_state['last_search_trace']
            if 'last_search_context' in st.session_state:
                del st.session_state['last_search_context']
            st.rerun()
    
    # Mostrar trace de búsqueda si modo debug está activo
    if debug_mode and 'last_search_trace' in st.session_state:
        with st.expander("🔬 **Trace de Búsqueda (Debug)**", expanded=False):
            trace = st.session_state.last_search_trace
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.markdown(f"**Mensaje:** `{trace.get('message', 'N/A')[:50]}...`")
                st.markdown(f"**Herramienta:** `{trace.get('tool_name', 'N/A')}`")
                st.markdown(f"**Extracción:** `{trace.get('extracted_by', 'N/A')}`")
            
            with col_d2:
                st.markdown(f"**Parámetros:** `{trace.get('params', {})}`")
                st.markdown(f"**Estación detectada:** `{trace.get('season_detected') or 'ninguna'}`")
                st.markdown(f"**Timestamp:** `{trace.get('timestamp', 'N/A')}`")
            
            # Errores de validación (si los hay)
            if trace.get('validation_errors'):
                st.error("**Errores de validación:**")
                for err in trace['validation_errors']:
                    st.markdown(f"- {err}")
            else:
                st.success("✅ Sin errores de validación")
            
            # Mostrar JSON completo
            st.json(trace)

    
    # Mostrar historial de chat
    chat_container = st.container()
    
    with chat_container:
        if not st.session_state.chat_messages:
            st.info(t("chat_search.no_messages"))
        else:
            for message in st.session_state.chat_messages:
                role_label = t("chat_search.you") if message["role"] == "user" else t("chat_search.assistant")
                avatar = "🧑" if message["role"] == "user" else "🤖"
                
                with st.chat_message(message["role"], avatar=avatar):
                    st.markdown(f"**{role_label}**")
                    st.markdown(message["content"])
    
    # Input de chat
    user_input = st.chat_input(t("chat_search.input_placeholder"))
    
    if user_input:
        # Añadir mensaje del usuario
        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Procesar pregunta
        _process_question(user_input)
        st.rerun()


def _process_question(question: str):
    """
    Procesa una pregunta del usuario y genera una respuesta.
    
    Args:
        question: Pregunta del usuario
    """
    # Mostrar indicadores de progreso multi-etapa
    status_placeholder = st.empty()
    
    try:
        # Fase 1: Análisis LLM
        with status_placeholder:
            with st.spinner("🧠 Analizando tu pregunta..."):
                import time
                time.sleep(0.5)  # Dar feedback visual
                
                # Obtener contexto previo si existe
                context = st.session_state.get('last_search_context', None)
                
                # Fase 2: Búsqueda
                st.empty()
        
        with status_placeholder:
            with st.spinner("🔍 Buscando en tus datos..."):
                # Llamar al LLM con herramientas
                response = chat_with_tools(question, _get_available_tools(), context)
        
        status_placeholder.empty()
            
        # Añadir respuesta del asistente
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": response
        })
    except Exception as e:
        error_msg = f"{t('chat_search.error')}: {str(e)}"
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": error_msg
        })


def _get_available_tools() -> List[Dict[str, Any]]:
    """
    Define las herramientas disponibles para el LLM.
    
    Returns:
        Lista de herramientas con sus definiciones y funciones
    """
    return [
        {
            "name": "search_expenses_by_concept",
            "description": "Busca gastos que coincidan con un concepto específico (búsqueda parcial, case-insensitive)",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": "Texto a buscar en el concepto del gasto (ej: 'regalo', 'restaurante', 'alcohol')"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Año para filtrar (opcional). Si no se especifica, busca en todos los años"
                    },
                    "month": {
                        "type": "integer",
                        "description": "Mes para filtrar (1-12, opcional)"
                    }
                },
                "required": ["concept"]
            },
            "function": search_expenses_by_concept
        },
        {
            "name": "search_expenses_by_category",
            "description": "Busca gastos de una categoría específica",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {
                        "type": "string",
                        "description": "Nombre de la categoría (ej: 'Restaurantes', 'Ocio', 'Transporte')"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Año para filtrar (opcional)"
                    },
                    "month": {
                        "type": "integer",
                        "description": "Mes para filtrar (1-12, opcional)"
                    }
                },
                "required": ["category_name"]
            },
            "function": search_expenses_by_category
        },
        {
            "name": "get_total_by_type",
            "description": "Obtiene el total de movimientos por tipo (gasto, ingreso, inversión)",
            "parameters": {
                "type": "object",
                "properties": {
                    "movement_type": {
                        "type": "string",
                        "enum": ["GASTO", "INGRESO", "INVERSION"],
                        "description": "Tipo de movimiento"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Año para filtrar (opcional)"
                    },
                    "month": {
                        "type": "integer",
                        "description": "Mes para filtrar (1-12, opcional)"
                    }
                },
                "required": ["movement_type"]
            },
            "function": get_total_by_type
        },
        {
            "name": "get_top_expenses",
            "description": "Obtiene los N gastos más grandes en un período",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Número de gastos a retornar (default: 10)"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Año para filtrar (opcional)"
                    },
                    "month": {
                        "type": "integer",
                        "description": "Mes para filtrar (1-12, opcional)"
                    }
                },
                "required": []
            },
            "function": get_top_expenses
        },
        {
            "name": "get_category_breakdown",
            "description": "Obtiene el desglose de gastos por categoría en un período",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Año para filtrar (opcional)"
                    },
                    "month": {
                        "type": "integer",
                        "description": "Mes para filtrar (1-12, opcional)"
                    }
                },
                "required": []
            },
            "function": get_category_breakdown
        },
        {
            "name": "get_savings_rate",
            "description": "Calcula la tasa de ahorro (inversión / ingresos) en un período",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "Año para filtrar (opcional)"
                    },
                    "month": {
                        "type": "integer",
                        "description": "Mes para filtrar (1-12, opcional)"
                    }
                },
                "required": []
            },
            "function": get_savings_rate
        }
    ]


# ============================================================================
# FUNCIONES DE HERRAMIENTAS (TOOLS)
# ============================================================================

def search_expenses_by_concept(concept: str, year: int = None, month: int = None) -> str:
    """Busca gastos que coincidan con un concepto."""
    entries = get_all_ledger_entries()
    cats_dict = {c.id: c.nombre for c in get_all_categorias()}
    
    import re
    import unicodedata
    from difflib import SequenceMatcher
    
    def normalize_text(text: str) -> str:
        """Normaliza texto para búsqueda: minúsculas, sin acentos, stemming básico."""
        if not text:
            return ""
        # 1. Minúsculas
        text = text.lower()
        # 2. Eliminar acentos (á→a, ñ→n, etc.)
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        # 3. Stemming básico español (sufijos comunes)
        suffixes = ['cion', 'sion', 'mente', 'ando', 'iendo', 'ado', 'ido', 'oso', 'osa', 'eno', 'ena', 'es', 's']
        words = re.findall(r'\w+', text)
        stemmed = []
        for word in words:
            if len(word) > 4:  # Solo aplicar a palabras largas
                for suffix in suffixes:
                    if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                        word = word[:-len(suffix)]
                        break
            stemmed.append(word)
        return ' '.join(stemmed)
    
    def tokenize(text: str) -> list:
        """Tokeniza texto normalizado, quitando stop words."""
        stop_words = {"el", "la", "los", "las", "un", "una", "de", "del", "al", "en", "para", "por", "y", "que", "con"}
        words = normalize_text(text).split()
        return [w for w in words if w not in stop_words and len(w) > 1]
    
    def fuzzy_match(word1: str, word2: str, threshold: float = 0.75) -> bool:
        """Búsqueda SOFT: compara dos palabras con similitud difusa.
        
        Ejemplos:
        - "helado" vs "helados" → True (0.93 similarity)
        - "uber" vs "ubers" → True (0.89 similarity)  
        - "restaurante" vs "restaurant" → True (0.95 similarity)
        """
        # Si son iguales (ya normalizadas), match perfecto
        if word1 == word2:
            return True
        
        # Si una contiene a la otra (stems), match
        if word1 in word2 or word2 in word1:
            return True
        
        # Calcular similitud con SequenceMatcher
        similarity = SequenceMatcher(None, word1, word2).ratio()
        return similarity >= threshold
    
    # Preparar keywords de búsqueda
    keywords = tokenize(concept)
    
    # Si se especificó año, quitarlo de las keywords
    if year:
        keywords = [w for w in keywords if w != str(year)]
        
    if not keywords:
        keywords = [normalize_text(concept)]
    
    import streamlit as st
    st.toast(f"🔎 Búsqueda SOFT: {', '.join(keywords)}")

    
    # Filtrar por tipo
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    
    # Filtrar por año/mes PRIMERO (reduce el conjunto de datos)
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    
    # TIER 1: Búsqueda exacta (AND logic: todos los términos)
    matching = []
    for e in expenses:
        if not e.concepto:
            continue
        entry_normalized = normalize_text(e.concepto)
        if all(kw in entry_normalized for kw in keywords):
            matching.append((e, 1.0))  # Score perfecto
    
    # TIER 2: Búsqueda FUZZY (palabras similares)
    if not matching:
        for e in expenses:
            if not e.concepto:
                continue
            
            entry_words = tokenize(e.concepto)
            
            # Contar cuántas keywords tienen match fuzzy
            fuzzy_matches = 0
            for kw in keywords:
                if any(fuzzy_match(kw, entry_word) for entry_word in entry_words):
                    fuzzy_matches += 1
            
            # Si al menos una keyword hace match fuzzy, incluir
            if fuzzy_matches > 0:
                score = fuzzy_matches / len(keywords)
                matching.append((e, score))
        
        # Ordenar por score descendente
        matching = sorted(matching, key=lambda x: x[1], reverse=True)
    
    # TIER 3: Búsqueda muy relajada (ANY keyword parcial)
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
        # Mostrar sugerencias de lo que hay en el período
        sample_concepts = list(set([e.concepto[:30] for e in expenses if e.concepto]))[:5]
        hint = ""
        if sample_concepts:
            hint = f"\n\nAlgunos conceptos disponibles: {', '.join(sample_concepts)}"
        return f"No se encontraron gastos similares a '{concept}' (ni siquiera con búsqueda flexible){hint}"
    
    # Extraer solo entries (quitar scores)
    matched_entries = [entry for entry, score in matching]
    
    total = sum(e.importe for e in matched_entries)
    result = f"Encontrados {len(matched_entries)} gastos con '{concept}' (búsqueda flexible):\n\n"
    result += f"**Total: {format_currency(total)}**\n\n"
    result += "Detalles:\n"
    
    for e in sorted(matched_entries, key=lambda x: x.importe, reverse=True)[:10]:
        cat_name = cats_dict.get(e.categoria_id, "Sin categoría")
        result += f"- {e.fecha_real.strftime('%d/%m/%Y')}: {e.concepto[:50]} - {format_currency(e.importe)} ({cat_name})\n"
    
    if len(matched_entries) > 10:
        result += f"\n... y {len(matched_entries) - 10} más"
    
    return result


def search_expenses_by_category(category_name: str, year: int = None, month: int = None) -> str:
    """Busca gastos de una categoría específica."""
    entries = get_all_ledger_entries()
    categories = get_all_categorias()
    
    # Buscar categoría (case-insensitive, búsqueda parcial)
    matching_cats = [c for c in categories if category_name.lower() in c.nombre.lower()]
    
    if not matching_cats:
        available_cats = ", ".join([c.nombre for c in categories])
        return f"No se encontró la categoría '{category_name}'. Categorías disponibles: {available_cats}"
    
    cat = matching_cats[0]
    
    # Filtrar gastos
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO and e.categoria_id == cat.id]
    
    # Filtrar por año/mes
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    
    if not expenses:
        return f"No se encontraron gastos en la categoría '{cat.nombre}'"
    
    total = sum(e.importe for e in expenses)
    result = f"Gastos en **{cat.nombre}**:\n\n"
    result += f"**Total: {format_currency(total)}** ({len(expenses)} movimientos)\n\n"
    result += "Mayores gastos:\n"
    
    for e in sorted(expenses, key=lambda x: x.importe, reverse=True)[:10]:
        result += f"- {e.fecha_real.strftime('%d/%m/%Y')}: {e.concepto[:50]} - {format_currency(e.importe)}\n"
    
    if len(expenses) > 10:
        result += f"\n... y {len(expenses) - 10} más"
    
    return result


def get_total_by_type(movement_type: str, year: int = None, month: int = None) -> str:
    """Obtiene el total por tipo de movimiento."""
    entries = get_all_ledger_entries()
    
    # Mapear tipo
    tipo_map = {
        "GASTO": TipoMovimiento.GASTO,
        "INGRESO": TipoMovimiento.INGRESO,
        "INVERSION": TipoMovimiento.INVERSION
    }
    
    tipo = tipo_map.get(movement_type.upper())
    if not tipo:
        return f"Tipo de movimiento '{movement_type}' no válido"
    
    # Filtrar
    filtered = [e for e in entries if e.tipo_movimiento == tipo]
    
    if year:
        filtered = [e for e in filtered if e.fecha_real.year == year]
    if month:
        filtered = [e for e in filtered if e.fecha_real.month == month]
    
    if not filtered:
        return f"No se encontraron movimientos de tipo {movement_type}"
    
    total = sum(e.importe for e in filtered)
    period = ""
    if year and month:
        period = f" en {month}/{year}"
    elif year:
        period = f" en {year}"
    
    tipo_label = {"GASTO": "Gastos", "INGRESO": "Ingresos", "INVERSION": "Inversiones"}
    
    return f"**{tipo_label.get(movement_type, movement_type)}{period}:** {format_currency(total)} ({len(filtered)} movimientos)"


def get_top_expenses(limit: int = 10, year: int = None, month: int = None) -> str:
    """Obtiene los mayores gastos."""
    entries = get_all_ledger_entries()
    cats_dict = {c.id: c.nombre for c in get_all_categorias()}
    
    # Filtrar gastos
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    
    if not expenses:
        return "No se encontraron gastos"
    
    # Ordenar por importe
    top = sorted(expenses, key=lambda x: x.importe, reverse=True)[:limit]
    
    period = ""
    if year and month:
        period = f" de {month}/{year}"
    elif year:
        period = f" de {year}"
    
    result = f"**Top {len(top)} gastos{period}:**\n\n"
    
    for i, e in enumerate(top, 1):
        cat_name = cats_dict.get(e.categoria_id, "Sin categoría")
        result += f"{i}. {e.fecha_real.strftime('%d/%m/%Y')}: {e.concepto[:40]} - **{format_currency(e.importe)}** ({cat_name})\n"
    
    return result


def get_category_breakdown(year: int = None, month: int = None) -> str:
    """Obtiene desglose de gastos por categoría."""
    from collections import defaultdict
    
    entries = get_all_ledger_entries()
    cats_dict = {c.id: c.nombre for c in get_all_categorias()}
    
    # Filtrar gastos
    expenses = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    
    if year:
        expenses = [e for e in expenses if e.fecha_real.year == year]
    if month:
        expenses = [e for e in expenses if e.fecha_real.month == month]
    
    if not expenses:
        return "No se encontraron gastos"
    
    # Agrupar por categoría
    by_cat = defaultdict(float)
    for e in expenses:
        cat_name = cats_dict.get(e.categoria_id, "Sin categoría")
        by_cat[cat_name] += e.importe
    
    # Ordenar por importe
    sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    
    total = sum(by_cat.values())
    
    period = ""
    if year and month:
        period = f" de {month}/{year}"
    elif year:
        period = f" de {year}"
    
    result = f"**Desglose por categoría{period}:**\n\n"
    result += f"Total gastos: {format_currency(total)}\n\n"
    
    for cat_name, amount in sorted_cats:
        pct = (amount / total * 100) if total > 0 else 0
        result += f"- **{cat_name}**: {format_currency(amount)} ({pct:.1f}%)\n"
    
    return result


def get_savings_rate(year: int = None, month: int = None) -> str:
    """Calcula tasa de ahorro."""
    entries = get_all_ledger_entries()
    
    # Filtrar
    filtered = entries
    if year:
        filtered = [e for e in filtered if e.fecha_real.year == year]
    if month:
        filtered = [e for e in filtered if e.fecha_real.month == month]
    
    if not filtered:
        return "No hay datos para calcular la tasa de ahorro"
    
    total_income = sum(e.importe for e in filtered if e.tipo_movimiento == TipoMovimiento.INGRESO)
    total_investment = sum(e.importe for e in filtered if e.tipo_movimiento == TipoMovimiento.INVERSION)
    total_expense = sum(e.importe for e in filtered if e.tipo_movimiento == TipoMovimiento.GASTO)
    
    if total_income == 0:
        return "No hay ingresos registrados para calcular la tasa de ahorro"
    
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
