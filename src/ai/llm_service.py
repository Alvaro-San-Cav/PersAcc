"""
LLM Service for Financial Analysis using Ollama

This module handles local LLM integration via Ollama for generating intelligent
commentary on financial data. Ollama must be installed and running locally.

Installation:
1. Download Ollama from https://ollama.com/download
2. Install Ollama
3. Pull a model: ollama pull phi3 (or tinyllama, mistral, llama3, gemma3, qwen3)
4. Ollama runs automatically on http://localhost:11434
"""

import json
import requests
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict

from src.ai import prompts as llm_prompts
from src.config import get_currency_symbol
from src.constants import (
    LLM_TIMEOUT_QUICK, LLM_TIMEOUT_LONG, 
    LLM_MAX_RESPONSE_LENGTH
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_ollama_urls():
    """Gets Ollama API URLs based on current configuration."""
    config = get_llm_config()
    base_url = config.get("base_url", "http://localhost:11434").rstrip("/")
    return {
        "api": f"{base_url}/api/generate",
        "tags": f"{base_url}/api/tags"
    }

# NOTE: Models are now detected dynamically from Ollama.
# The config stores the actual model name (e.g., 'qwen3:8b', 'phi3', 'llama3').
# MODEL_TIERS is kept only for backward compatibility with old configs
# that may have 'light', 'standard', etc. as model_tier value.
MODEL_TIERS = {
    "light": "tinyllama",
    "standard": "phi3",
    "quality": "mistral",
    "premium": "llama3"
}

# ============================================================================
# SEARCH CONTEXT & UTILITIES
# ============================================================================


# Season to months mapping (Northern Hemisphere - Spain)
SEASON_TO_MONTHS = {
    "invierno": [12, 1, 2],
    "primavera": [3, 4, 5],
    "verano": [6, 7, 8],
    "otoño": [9, 10, 11],
    "otono": [9, 10, 11],  # Without accent
    "winter": [12, 1, 2],
    "spring": [3, 4, 5],
    "summer": [6, 7, 8],
    "fall": [9, 10, 11],
    "autumn": [9, 10, 11]
}


def get_current_season() -> str:
    """Returns current season name in Spanish."""
    month = datetime.now().month
    if month in [12, 1, 2]:
        return "invierno"
    elif month in [3, 4, 5]:
        return "primavera"
    elif month in [6, 7, 8]:
        return "verano"
    else:
        return "otoño"


def detect_season_in_text(text: str) -> Optional[str]:
    """Detects season keywords in text, returns canonical name."""
    text_lower = text.lower()
    for season in SEASON_TO_MONTHS.keys():
        if season in text_lower:
            # Return canonical Spanish name
            if season in ["winter", "invierno"]:
                return "invierno"
            elif season in ["spring", "primavera"]:
                return "primavera"
            elif season in ["summer", "verano"]:
                return "verano"
            elif season in ["fall", "autumn", "otoño", "otono"]:
                return "otoño"
    return None


def check_ollama_running() -> bool:
    """
    Check if Ollama is running and accessible.
    
    Returns:
        True if Ollama is running, False otherwise
    """
    try:
        urls = get_ollama_urls()
        response = requests.get(urls["tags"], timeout=2)
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Ollama not accessible: {e}")
        return False


def get_available_models() -> list:
    """
    Get list of models available in Ollama.
    
    Returns:
        List of model names
    """
    try:
        urls = get_ollama_urls()
        response = requests.get(urls["tags"], timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        return []
    except Exception as e:
        logger.error(f"Error getting Ollama models: {e}")
        return []


def check_model_available(model_name: str) -> bool:
    """
    Check if a specific model is available in Ollama.
    
    Args:
        model_name: Name of the model to check
        
    Returns:
        True if model is available, False otherwise
    """
    available = get_available_models()
    # Check if model name matches (including version tags like :latest)
    return any(model_name in model for model in available)


def _generate_fallback_message(expenses: float, expense_items: list, lang: str = "es") -> str:
    """
    Generate a fallback message when LLM fails or returns empty.
    
    Args:
        expenses: Total expenses
        expense_items: List of expense items
        lang: Language code
        
    Returns:
        Contextual fallback message
    """
    num_expenses = len(expense_items) if expense_items else 0
    
    if lang == "es":
        if expenses == 0 or num_expenses == 0:
            return "💰 ¡Mes muy tranquilo! Casi sin gastos registrados."
        elif num_expenses <= 2:
            return "✨ Muy pocos gastos este mes. ¡Excelente control!"
        elif num_expenses <= 5:
            return "👍 Gastos bajo control. Buen trabajo."
        else:
            return "📊 Mes activo con varios movimientos."
    else:  # English
        if expenses == 0 or num_expenses == 0:
            return "💰 Very quiet month! Almost no expenses recorded."
        elif num_expenses <= 2:
            return "✨ Very few expenses this month. Excellent control!"
        elif num_expenses <= 5:
            return "👍 Expenses under control. Good job."
        else:
            return "📊 Active month with several movements."


def generate_quick_summary(income: float, expenses: float, balance: float, lang: str = "es", expense_items: list = None) -> str:
    """
    Generate a quick, witty commentary about current month finances.
    
    Args:
        income: Total income so far  
        expenses: Total expenses so far
        balance: Current balance
        lang: Language ('es' or 'en')
        expense_items: Optional list of expense dicts with 'categoria', 'concepto', 'importe'
    
    Returns:
        A short, funny commentary (1-2 sentences)
    """
    # DEBUG MODE: Set to False for production
    DEBUG = False
    
    if not is_llm_enabled():
        return "[DEBUG: LLM no habilitado]" if DEBUG else ""
    
    try:
        # Check if Ollama is running
        if not check_ollama_running():
            return "[DEBUG: Ollama no está corriendo - ejecuta 'ollama serve']" if DEBUG else ""
        
        llm_config = get_llm_config()
        model_name = llm_config.get('model_summary', llm_config.get('model_tier', 'tinyllama'))
        
        # Resolve model with fallback
        available_models = get_available_models()
        resolved_model = _resolve_model_name(model_name, available_models)
        
        if not resolved_model:
            return f"[DEBUG: Sin modelos - ejecuta 'ollama pull phi3']" if DEBUG else ""
            
        model_name = resolved_model
        
        # Build expense details text
        expense_text = ""
        if expense_items:
            top_expenses = sorted(expense_items, key=lambda x: x.get('importe', 0), reverse=True)[:5]
            expense_lines = [f"- {e.get('concepto', 'Gasto')}: {e.get('importe', 0):.2f}€ ({e.get('categoria', '')})" for e in top_expenses]
            expense_text = "\n".join(expense_lines)
        
        # Build prompt using centralized templates
        expense_text_final = expense_text if expense_text else ("Sin gastos registrados" if lang == "es" else "No expenses recorded")
        
        if lang == "es":
            prompt = llm_prompts.QUICK_SUMMARY_ES.format(
                income=income,
                expenses=expenses,
                balance=balance,
                expense_text=expense_text_final
            )
        else:
            prompt = llm_prompts.QUICK_SUMMARY_EN.format(
                income=income,
                expenses=expenses,
                balance=balance,
                expense_text=expense_text_final
            )
        
        # Check if this is a Qwen model (needs think: false to disable thinking mode)
        is_qwen = 'qwen' in model_name.lower()
        
        # Build options
        options = {
            "temperature": 0.9,
            "num_predict": 200,  # More tokens for longer commentary
            "num_ctx": 1024,
        }
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": options
        }
        
        # For Qwen3 models, add think: false at root level (not inside options)
        if is_qwen:
            payload["think"] = False
        
        urls = get_ollama_urls()
        response = requests.post(urls["api"], json=payload, timeout=LLM_TIMEOUT_QUICK)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
            # Limpiar tags de think si están presentes
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            
            # Limpiar y limitar longitud
            if text:
                text = text.split('\n')[0].strip()
                # Remove quotes if present
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                if len(text) > LLM_MAX_RESPONSE_LENGTH:
                    text = text[:(LLM_MAX_RESPONSE_LENGTH-3)] + "..."
                return text
            else:
                # LLM returned empty - provide fallback message
                if not DEBUG:
                    return _generate_fallback_message(expenses, expense_items, lang)
                # Debug: show thinking content if available (v2 - with think:False)
                if result.get("thinking"):
                    thinking_preview = result.get("thinking", "")[:150]
                    return f"[v2 think:False={is_qwen}] thinking={thinking_preview}"
                return "[v2] Respuesta vacía"
        else:
            if not DEBUG:
                return _generate_fallback_message(expenses, expense_items, lang)
            return f"[DEBUG: Error HTTP {response.status_code} de Ollama]"
        
    except requests.exceptions.Timeout:
        if not DEBUG:
            return _generate_fallback_message(expenses, expense_items, lang)
        return "[DEBUG: Timeout - el modelo tardó más de 15s]"
    except Exception as e:
        if not DEBUG:
            return _generate_fallback_message(expenses, expense_items, lang)
        return f"[DEBUG: Error - {str(e)[:100]}]"


def _resolve_model_name(requested_name: str, available_models: list = None) -> str:
    """
    Returns the best available model.
    1. If `requested_name` is in available -> use it.
    2. If not, use first available model.
    3. If no models available -> None.
    """
    if available_models is None:
        if not check_ollama_running():
            return None
        available_models = get_available_models()
    
    if not available_models:
        return None
        
    # 1. Exact match / Partial match logic could be added here if names are complex
    # But for now, simple check
    if requested_name in available_models:
        return requested_name
        
    # 2. Check for partial matches (e.g. "llama3" matching "llama3:latest")
    for m in available_models:
        if requested_name in m:
            return m

    # 3. Fallback to first available
    logger.warning(f"Model '{requested_name}' not found. Using fallback: '{available_models[0]}'")
    return available_models[0]


def analyze_financial_period(
    data: Dict[str, Any],
    period_type: str,
    lang: str = "es",
    model_tier: str = "light",
    max_tokens: int = 800,
    movements: list = None
) -> str:
    """
    Generate AI commentary for a financial period using Ollama.
    """
    # Check if Ollama is running
    if not check_ollama_running():
        raise ConnectionError(
            "Ollama no está ejecutándose. "
            "Instala Ollama desde https://ollama.com/download y asegúrate de que esté corriendo."
        )
    
    # Determine model name - can be a legacy tier or direct model name. model_analysis takes priority over model_tier.
    model_name = model_tier
    if model_tier in MODEL_TIERS:
        # Legacy tier name -> convert to model name
        model_name = MODEL_TIERS[model_tier]
    
    # Get available models
    available_models = get_available_models()
    
    # Resolve model with fallback
    resolved_model = _resolve_model_name(model_name, available_models)
    
    if not resolved_model:
        raise ValueError(
            f"No hay modelos descargados en Ollama.\n"
            f"Ejecuta: ollama pull tinyllama (o cualquier otro modelo)"
        )
    
    # Update model_name to the actually resolved one
    model_name = resolved_model
    
    # Build prompt based on language
    if lang == "es":
        prompt = _build_spanish_prompt(data, period_type, movements)
        system_instruction = "IMPORTANTE: Responde SIEMPRE en ESPAÑOL. No uses inglés bajo ninguna circunstancia."
    else:
        prompt = _build_english_prompt(data, period_type, movements)
        system_instruction = "IMPORTANT: ALWAYS respond in ENGLISH. Do not use Spanish under any circumstances."
    
    # Prepend language instruction to prompt
    full_prompt = f"{system_instruction}\n\n{prompt}"
    
    # Check if this is a Qwen model
    is_qwen = 'qwen' in model_name.lower()
    
    # Log prompt size for debugging
    logger.info(f"Prompt size: {len(full_prompt)} chars, movements: {len(movements) if movements else 0}")
    
    # Call Ollama API
    try:
        # Build options
        options = {
            "temperature": 0.8,
            "top_p": 0.95,
            "num_predict": max_tokens,
            "num_ctx": 4096,
            "num_thread": 8,
            "repeat_penalty": 1.1
        }
        
        payload = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": options
        }
        
        # For Qwen3 models, add think: false at root level (not inside options)
        if is_qwen:
            payload["think"] = False
        
        # No añadimos stop sequences para evitar cortar respuestas prematuramente
        
        logger.info(f"Generating analysis with {model_name} (max {max_tokens} tokens)...")
        logger.info(f"Prompt length: {len(full_prompt)} characters")
        
        urls = get_ollama_urls()
        response = requests.post(
            urls["api"],
            json=payload,
            timeout=LLM_TIMEOUT_LONG  # Timeout configurable desde constants
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
            # Limpiar tags de think si están presentes
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            
            # Log detailed response info
            logger.info(f"Response received: {len(text)} characters")
            logger.debug(f"Full Ollama response: {result}")
            
            if not text:
                error_details = f"Prompt length: {len(full_prompt)} chars, "
                error_details += f"Model: {model_name}, "
                error_details += f"Full result keys: {list(result.keys())}"
                
                logger.warning(f"Empty response from Ollama. {error_details}")
                logger.warning(f"Result done: {result.get('done')}, done_reason: {result.get('done_reason')}")
                
                # Provide user-friendly error message
                raise Exception(
                    f"Ollama devolvió una respuesta vacía.\n\n"
                    f"**Posibles causas:**\n"
                    f"1. El modelo '{model_name}' no puede generar una respuesta válida\n"
                    f"2. El prompt es muy largo ({len(full_prompt)} caracteres)\n"
                    f"3. El modelo necesita más tokens (actual: {max_tokens})\n\n"
                    f"**Soluciones:**\n"
                    f"- Prueba con otro modelo en Configuración\n"
                    f"- Reduce la cantidad de movimientos a analizar\n"
                    f"- Intenta de nuevo (a veces es temporal)"
                )
            
            return text
        else:
            error_msg = response.json().get("error", "Unknown error")
            logger.error(f"Ollama API error (status {response.status_code}): {error_msg}")
            raise Exception(f"Ollama API error: {error_msg}")
            
    except requests.exceptions.Timeout:
        raise Exception(
            f"Timeout esperando respuesta de Ollama (>3 minutos). "
            f"El modelo '{model_name}' puede estar sobrecargado o ser muy grande. "
            f"Intenta con un modelo más ligero en Configuración."
        )
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "No se pudo conectar con Ollama. "
            "Asegúrate de que Ollama esté ejecutándose."
        )
    except Exception as e:
        if "devolvió una respuesta vacía" not in str(e):
            logger.error(f"Error calling Ollama: {e}")
        raise


def _build_movements_text(movements: list, period_type: str) -> str:
    """Build formatted movements text based on period type."""
    if not movements or len(movements) == 0:
        return ""
    
    if period_type == "year":
        # Para análisis anual: resumen agregado por categoría
        cat_totals = defaultdict(lambda: {'count': 0, 'total': 0.0})
        
        for mov in movements:
            categoria = mov.get('categoria', 'Sin categoría')
            importe = mov.get('importe', 0)
            cat_totals[categoria]['count'] += 1
            cat_totals[categoria]['total'] += importe
        
        movements_text = f"\n\n📋 RESUMEN POR CATEGORÍA ({len(movements)} movimientos):\n"
        # Ordenar por valor absoluto del total
        sorted_cats = sorted(cat_totals.items(), key=lambda x: abs(x[1]['total']), reverse=True)
        
        for categoria, data_cat in sorted_cats:
            count = data_cat['count']
            total = data_cat['total']
            currency = get_currency_symbol()
            signo = "+" if total >= 0 else ""
            movements_text += f"• {categoria}: {count} mov, {signo}{total:.2f}{currency}\n"
    else:
        # Para análisis mensual: lista de movimientos individuales (hasta 30)
        currency = get_currency_symbol()
        movements_text = "\n\n📋 MOVIMIENTOS REGISTRADOS:\n"
        for i, mov in enumerate(movements[:30], 1):
            tipo = mov.get('tipo', '?')
            categoria = mov.get('categoria', '?')
            concepto = mov.get('concepto', '?')[:30]
            importe = mov.get('importe', 0)
            fecha = mov.get('fecha', '?')
            movements_text += f"{i}. {fecha} | {tipo} | {categoria} | {concepto} | {importe:.2f}{currency}\n"
        
        if len(movements) > 30:
            movements_text += f"\n... y {len(movements) - 30} movimientos más\n"
    
    return movements_text


def _build_prompt(data: Dict[str, Any], period_type: str, lang: str = "es", movements: list = None) -> str:
    """
    Build language-specific prompt for financial analysis.
    
    Args:
        data: Financial data dictionary
        period_type: "year" or "month"
        lang: Language code ("es" or "en")
        movements: List of movements to include
        
    Returns:
        Formatted prompt string
    """
    now = datetime.now()
    
    # Language-specific defaults
    default_period = "período desconocido" if lang == "es" else "unknown period"
    period = data.get("period", default_period)
    
    # Prepare template variables (same for all languages)
    template_vars = {
        'period': period,
        'income': data.get("income", 0),
        'expenses': data.get("expenses", 0),
        'balance': data.get("balance", 0),
        'investment': data.get("investment", 0),
        'savings_pct': data.get("savings_percent", 0),
        'movements_text': _build_movements_text(movements, period_type),
        'current_month': now.strftime('%B %Y'),
        'current_month_name': now.strftime('%B'),
        'current_day': now.day,
        'months_elapsed': now.month,
        'months_remaining': 12 - now.month,
        'days_remaining': 30 - now.day,
        'period_context': ""
    }
    
    # Determine if current period
    is_current_period = False
    if period_type == "year":
        is_current_period = (str(period) == str(now.year))
        if is_current_period:
            if lang == "es":
                template_vars['period_context'] = f" (AÑO EN CURSO - datos hasta {now.strftime('%B %Y')})"
            else:
                template_vars['period_context'] = f" (CURRENT YEAR - data through {now.strftime('%B %Y')})"
    else:
        try:
            period_date = datetime.strptime(str(period), "%Y-%m")
            is_current_period = (period_date.year == now.year and period_date.month == now.month)
            if is_current_period:
                if lang == "es":
                    template_vars['period_context'] = f" (MES EN CURSO - datos hasta el día {now.day})"
                else:
                    template_vars['period_context'] = f" (CURRENT MONTH - data through day {now.day})"
        except Exception:
            pass
    
    # Select appropriate template based on language and period
    if lang == "es":
        if period_type == "year":
            template = llm_prompts.SPANISH_YEAR_CURRENT if is_current_period else llm_prompts.SPANISH_YEAR_CLOSED
        else:
            template = llm_prompts.SPANISH_MONTH_CURRENT if is_current_period else llm_prompts.SPANISH_MONTH_CLOSED
    else:  # English
        if period_type == "year":
            template = llm_prompts.ENGLISH_YEAR_CURRENT if is_current_period else llm_prompts.ENGLISH_YEAR_CLOSED
        else:
            template = llm_prompts.ENGLISH_MONTH_CURRENT if is_current_period else llm_prompts.ENGLISH_MONTH_CLOSED
    
    return template.format(**template_vars)


# Backward compatibility aliases
def _build_spanish_prompt(data: Dict[str, Any], period_type: str, movements: list = None) -> str:
    """Build Spanish language prompt for financial analysis. DEPRECATED: Use _build_prompt(lang='es')."""
    return _build_prompt(data, period_type, lang="es", movements=movements)


def _build_english_prompt(data: Dict[str, Any], period_type: str, movements: list = None) -> str:
    """Build English language prompt for financial analysis. DEPRECATED: Use _build_prompt(lang='en')."""
    return _build_prompt(data, period_type, lang="en", movements=movements)


def is_llm_enabled() -> bool:
    """
    Check if LLM is enabled in configuration.
    
    Returns:
        True if LLM is enabled, False otherwise
    """
    try:
        from src.config import load_config
        config = load_config()
        return config.get("llm", {}).get("enabled", False)
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        return False


def get_llm_config() -> Dict[str, Any]:
    """
    Get LLM configuration from config.json.
    
    Returns:
        Dictionary with LLM configuration
    """
    try:
        from src.config import load_config
        config = load_config()
        return config.get("llm", {
            "enabled": False,
            "model_analysis": "phi3",
            "model_chat": "phi3",
            "model_summary": "phi3",
            "max_tokens": 400
        })
    except Exception as e:
        logger.error(f"Error reading LLM config: {e}")
        return {"enabled": False, "model_analysis": "phi3", "model_chat": "phi3", "model_summary": "phi3", "max_tokens": 400}


def classify_bank_transactions(
    text_content: str,
    file_type: str,
    categorias: list,
    timeout: int = LLM_TIMEOUT_LONG
) -> list:
    """
    Classifies bank transactions from a parsed text file using the local LLM.

    Args:
        text_content: Parsed, human-readable bank statement text.
        file_type: One of 'AEB_NORMA43', 'AEB_SEPA', 'EXCEL', 'UNKNOWN'.
        categorias: List of category name strings available in the DB.
        timeout: Request timeout in seconds.

    Returns:
        List of dicts with keys: fecha, concepto, importe, tipo_movimiento,
        categoria_sugerida, relevancia, confianza.

    Raises:
        ConnectionError: If Ollama is not running.
        ValueError: If no models available or response cannot be parsed.
    """
    if not check_ollama_running():
        raise ConnectionError(
            "Ollama no está ejecutándose. "
            "Instala Ollama desde https://ollama.com/download y asegúrate de que esté corriendo."
        )

    llm_config = get_llm_config()
    model_name = llm_config.get("model_import", llm_config.get("model_analysis", "phi3"))
    available_models = get_available_models()
    resolved_model = _resolve_model_name(model_name, available_models)

    if not resolved_model:
        raise ValueError(
            "No hay modelos descargados en Ollama.\n"
            "Ejecuta: ollama pull phi3 (o cualquier otro modelo)"
        )

    model_name = resolved_model
    is_qwen = "qwen" in model_name.lower()

    # Select the right prompt template
    tipo_key = file_type.upper().replace(" ", "_").replace("/", "_").replace("-", "_")
    if "SEPA" in tipo_key:
        template = llm_prompts.IMPORT_SEPA_SYSTEM
    elif "EXCEL" in tipo_key:
        template = llm_prompts.IMPORT_EXCEL_SYSTEM
    else:  # AEB_NORMA43 or fallback
        template = llm_prompts.IMPORT_AEB43_SYSTEM

    categorias_text = "\n".join(f"- {c}" for c in categorias)

    prompt = template.format(
        categorias=categorias_text,
        output_schema=llm_prompts.IMPORT_OUTPUT_SCHEMA,
        contenido=text_content[:8000]  # Limit to avoid context overflow
    )

    logger.info(f"classify_bank_transactions: model={model_name}, file_type={file_type}, prompt_len={len(prompt)}")

    options = {
        "temperature": 0.1,
        "num_predict": 4096,
        "num_ctx": 8192,
        "num_thread": 8,
    }

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }

    if is_qwen:
        payload["think"] = False

    try:
        urls = get_ollama_urls()
        # Set timeout to None because parsing a full document can take many minutes
        response = requests.post(urls["api"], json=payload, timeout=None)
    except requests.exceptions.Timeout:
        raise Exception(
            f"Timeout esperando respuesta de Ollama. "
            f"El fichero puede ser demasiado grande o el modelo '{model_name}' muy lento. "
            "Prueba con un modelo más ligero o reduce el tamaño del fichero."
        )
    except requests.exceptions.ConnectionError:
        raise ConnectionError("No se pudo conectar con Ollama.")

    if response.status_code != 200:
        error_msg = response.json().get("error", "Unknown error")
        raise Exception(f"Ollama API error: {error_msg}")

    result = response.json()
    raw_text = result.get("response", "").strip()

    # Remove think tags if present (Qwen models)
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # Extract JSON array from the response (handle markdown fences)
    json_text = raw_text
    fence_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", json_text, re.DOTALL)
    if fence_match:
        json_text = fence_match.group(1)
    else:
        array_match = re.search(r"\[.*\]", json_text, re.DOTALL)
        if array_match:
            json_text = array_match.group(0)

    try:
        entries = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}\nRaw text:\n{raw_text[:500]}")
        raise ValueError(
            f"El modelo no devolvió un JSON válido.\nError: {e}\n\n"
            "Prueba con un modelo diferente (ej: phi3, llama3, gemma3) o reduce el fichero."
        )

    if not isinstance(entries, list):
        raise ValueError("La respuesta del modelo no es una lista JSON válida.")

    validated = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        try:
            cat_sug = str(item.get("categoria_sugerida", "")).strip()
            # Si el LLM devuelve el nombre con el sufijo que le pasamos "(Tipo: ...)", o la NOTA, lo quitamos todo
            cat_sug = re.sub(r"\s*\(Tipo:.*$", "", cat_sug, flags=re.IGNORECASE).strip()

            validated.append({
                "fecha": str(item.get("fecha", "")).strip(),
                "concepto_original": str(item.get("concepto_original", "")).strip(),
                "concepto": str(item.get("concepto", "")).strip(),
                "importe": float(item.get("importe", 0)),
                "tipo_movimiento": str(item.get("tipo_movimiento", "GASTO")).strip(),
                "categoria_sugerida": cat_sug,
                "relevancia": item.get("relevancia") or None,
                "confianza": max(0.0, min(1.0, float(item.get("confianza", 0.5)))),
            })
        except Exception as ex:
            logger.warning(f"Skipping invalid entry {item}: {ex}")
            continue

    logger.info(f"classify_bank_transactions: parsed {len(validated)} entries from {len(entries)} raw")
    return validated
