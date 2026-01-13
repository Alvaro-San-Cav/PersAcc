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
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict

from . import llm_prompts
from .config import get_currency_symbol
from .constants import (
    LLM_TIMEOUT_QUICK, LLM_TIMEOUT_LONG, 
    LLM_MAX_RESPONSE_LENGTH, LLM_MAX_MOVEMENTS_DISPLAY
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ollama API endpoint
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

# Model configurations - reference for common models
# Users can use ANY model name from Ollama directly in config.json
MODEL_TIERS = {
    "light": {
        "model_name": "tinyllama",
        "size_gb": 0.6,
        "ram_gb": 4,
        "quality": "⭐⭐",
        "pull_command": "ollama pull tinyllama"
    },
    "standard": {
        "model_name": "phi3",
        "size_gb": 2.3,
        "ram_gb": 6,
        "quality": "⭐⭐⭐",
        "pull_command": "ollama pull phi3"
    },
    "quality": {
        "model_name": "mistral",
        "size_gb": 4.1,
        "ram_gb": 8,
        "quality": "⭐⭐⭐⭐",
        "pull_command": "ollama pull mistral"
    },
    "premium": {
        "model_name": "llama3",
        "size_gb": 4.7,
        "ram_gb": 12,
        "quality": "⭐⭐⭐⭐⭐",
        "pull_command": "ollama pull llama3"
    }
}

# ============================================================================
# SEARCH CONTEXT & UTILITIES
# ============================================================================

@dataclass
class SearchContext:
    """Tracks conversation context for better multi-turn understanding and debugging."""
    tool_name: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    extracted_by: str = "none"  # "llm", "regex", "default"
    validation_errors: List[str] = field(default_factory=list)
    season_detected: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "extracted_by": self.extracted_by,
            "validation_errors": self.validation_errors,
            "season_detected": self.season_detected
        }


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
        response = requests.get(OLLAMA_TAGS_URL, timeout=2)
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
        response = requests.get(OLLAMA_TAGS_URL, timeout=5)
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
        model_name = llm_config.get('model_tier', 'tinyllama')
        
        # Verify model exists
        available_models = get_available_models()
        if not available_models:
            return f"[DEBUG: Sin modelos - ejecuta 'ollama pull phi3']" if DEBUG else ""
        
        if model_name not in available_models:
            return f"[DEBUG: Modelo '{model_name}' no encontrado. Disponibles: {', '.join(available_models[:3])}]" if DEBUG else ""
        
        # Build expense details text
        expense_text = ""
        if expense_items:
            top_expenses = sorted(expense_items, key=lambda x: x.get('importe', 0), reverse=True)[:5]
            expense_lines = [f"- {e.get('concepto', 'Gasto')}: {e.get('importe', 0):.2f}€ ({e.get('categoria', '')})" for e in top_expenses]
            expense_text = "\n".join(expense_lines)
        
        # Build prompt with more commentary focus
        if lang == "es":
            prompt = f"""Eres un asesor financiero con sentido del humor. Analiza estos datos del mes y haz un comentario gracioso pero útil (2-3 frases, máximo 50 palabras).

Resumen del mes:
- Ingresos: {income:.2f}€
- Gastos totales: {expenses:.2f}€  
- Balance: {balance:.2f}€

Principales gastos:
{expense_text if expense_text else "Sin gastos registrados"}

Instrucciones:
- Haz comentarios ingeniosos sobre los gastos específicos si los hay
- El balance normalmente es positivo, así que no comentes sobre él a menos que sea negativo. Si los gastos son muy altos pero el balance sigue siendo positivo, puedes mencionarlo como algo positivo (ej: "¡Qué gastos de Navidad y Reyes! 🎄 ¡Pero el balance sigue siendo positivo! 💰").
- Usa máximo 1-2 emojis
- Sé directo y conciso
- No uses introducciones como "Vaya" o "Bueno"
- Responde SOLO el comentario, nada más"""
        else:
            prompt = f"""You're a financial advisor with a sense of humor. Analyze this month's data and make a witty but useful comment (2-3 sentences, max 50 words).

Month summary:
- Income: €{income:.2f}
- Total expenses: €{expenses:.2f}
- Balance: €{balance:.2f}

Top expenses:
{expense_text if expense_text else "No expenses recorded"}

Instructions:
- Make witty comments about specific expenses if available
- The balance is normally positive, so do not comment on it unless it is negative. Exception: if expenses are very high, you can highlight that the balance remains positive (e.g., "What holiday spending! 🎄 But the balance is still positive! 💰").
- Use maximum 2-3 emojis
- Be direct and concise
- Don't use introductions like "Well" or "So"
- Reply ONLY with the comment, nothing else"""
        
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
        
        # Call API - shorter timeout for quick summary
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=LLM_TIMEOUT_QUICK)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
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
                # Debug: show thinking content if available (v2 - with think:False)
                if result.get("thinking"):
                    thinking_preview = result.get("thinking", "")[:150]
                    return f"[v2 think:False={is_qwen}] thinking={thinking_preview}" if DEBUG else ""
                return f"[v2] Respuesta vacía" if DEBUG else ""
        else:
            return f"[DEBUG: Error HTTP {response.status_code} de Ollama]" if DEBUG else ""
        
    except requests.exceptions.Timeout:
        return "[DEBUG: Timeout - el modelo tardó más de 15s]" if DEBUG else ""
    except Exception as e:
        return f"[DEBUG: Error - {str(e)[:100]}]" if DEBUG else ""


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
    
    Args:
        data: Financial data dictionary with keys like:
            - income: Total income
            - expenses: Total expenses
            - balance: Net balance
            - investment: Investment amount
            - savings_percent: Savings percentage
            - period: Period identifier (e.g., "2024", "January 2024")
        period_type: "year" or "month"
        lang: Language code ("es" or "en")
        model_tier: Model tier to use (or direct model name)
        max_tokens: Maximum tokens for response
        movements: Optional list of individual movements (entries)
        
    Returns:
        Generated commentary text
        
    Raises:
        ConnectionError: If Ollama is not running
        ValueError: If model is not available
    """
    # Check if Ollama is running
    if not check_ollama_running():
        raise ConnectionError(
            "Ollama no está ejecutándose. "
            "Instala Ollama desde https://ollama.com/download y asegúrate de que esté corriendo."
        )
    
    # Determine model name - can be a tier or direct model name
    if model_tier in MODEL_TIERS:
        model_config = MODEL_TIERS[model_tier]
        model_name = model_config["model_name"]
    else:
        # Use as direct model name
        model_name = model_tier
    
    # Get available models
    available_models = get_available_models()
    
    # Check if exact model or any version is available
    model_available = any(model_name in model for model in available_models)
    
    if not model_available:
        # Suggest first available model if any
        if available_models:
            raise ValueError(
                f"El modelo '{model_name}' no está descargado.\n"
                f"Modelos disponibles: {', '.join(available_models[:5])}\n"
                f"Cambia 'model_tier' en config.json a uno de estos nombres."
            )
        else:
            raise ValueError(
                f"No hay modelos descargados en Ollama.\n"
                f"Ejecuta: ollama pull tinyllama (o cualquier otro modelo)"
            )
    
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
        
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=LLM_TIMEOUT_LONG  # Timeout configurable desde constants
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
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


def _build_spanish_prompt(data: Dict[str, Any], period_type: str, movements: list = None) -> str:
    """Build Spanish language prompt for financial analysis."""
    now = datetime.now()
    period = data.get("period", "período desconocido")
    
    # Prepare template variables
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
            template_vars['period_context'] = f" (AÑO EN CURSO - datos hasta {now.strftime('%B %Y')})"
    else:
        try:
            period_date = datetime.strptime(str(period), "%Y-%m")
            is_current_period = (period_date.year == now.year and period_date.month == now.month)
            if is_current_period:
                template_vars['period_context'] = f" (MES EN CURSO - datos hasta el día {now.day})"
        except Exception:
            pass
    
    # Select appropriate template
    if period_type == "year":
        template = llm_prompts.SPANISH_YEAR_CURRENT if is_current_period else llm_prompts.SPANISH_YEAR_CLOSED
    else:
        template = llm_prompts.SPANISH_MONTH_CURRENT if is_current_period else llm_prompts.SPANISH_MONTH_CLOSED
    
    return template.format(**template_vars)


def _build_english_prompt(data: Dict[str, Any], period_type: str, movements: list = None) -> str:
    """Build English language prompt for financial analysis."""
    now = datetime.now()
    period = data.get("period", "unknown period")
    
    # Prepare template variables
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
            template_vars['period_context'] = f" (CURRENT YEAR - data through {now.strftime('%B %Y')})"
    else:
        try:
            period_date = datetime.strptime(str(period), "%Y-%m")
            is_current_period = (period_date.year == now.year and period_date.month == now.month)
            if is_current_period:
                template_vars['period_context'] = f" (CURRENT MONTH - data through day {now.day})"
        except Exception:
            pass
    
    # Select appropriate template
    if period_type == "year":
        template = llm_prompts.ENGLISH_YEAR_CURRENT if is_current_period else llm_prompts.ENGLISH_YEAR_CLOSED
    else:
        template = llm_prompts.ENGLISH_MONTH_CURRENT if is_current_period else llm_prompts.ENGLISH_MONTH_CLOSED
    
    return template.format(**template_vars)


def is_llm_enabled() -> bool:
    """
    Check if LLM is enabled in configuration.
    
    Returns:
        True if LLM is enabled, False otherwise
    """
    try:
        config_path = Path(__file__).parent.parent / "data" / "config.json"
        if not config_path.exists():
            return False
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
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
        config_path = Path(__file__).parent.parent / "data" / "config.json"
        if not config_path.exists():
            return {"enabled": False, "model_tier": "light", "max_tokens": 400}
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        return config.get("llm", {
            "enabled": False,
            "model_tier": "light",
            "max_tokens": 400
        })
    except Exception as e:
        logger.error(f"Error reading LLM config: {e}")
        return {"enabled": False, "model_tier": "light", "max_tokens": 400}


def get_model_info(model_tier: str = "light") -> Dict[str, Any]:
    """
    Get information about a model tier.
    
    Args:
        model_tier: Model tier name
        
    Returns:
        Dictionary with model information
    """
    return MODEL_TIERS.get(model_tier, MODEL_TIERS["light"])


def _validate_and_normalize_params(
    tool_name: str,
    params: Dict[str, Any],
    user_message: str
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validates and normalizes parameters with current date context.
    
    Args:
        tool_name: Name of the tool being called
        params: Raw parameters extracted by LLM or regex
        user_message: Original user message for season detection
        
    Returns:
        Tuple of (normalized_params, validation_errors)
    """
    # VALID TOOLS & PARAMETERS
    TOOL_PARAMS = {
        "search_expenses_by_concept": ["concept", "year", "month"],
        "search_expenses_by_category": ["category_name", "year", "month"],
        "get_top_expenses": ["limit", "year", "month"],
        "get_category_breakdown": ["year", "month"],
        "get_savings_rate": ["year", "month"],
        "get_total_by_type": ["movement_type", "year", "month"]
    }
    
    normalized = params.copy()
    errors = []
    
    # FILTER: Remove unknown parameters to prevent TypeError in tool functions
    if tool_name in TOOL_PARAMS:
        allowed = set(TOOL_PARAMS[tool_name])
        # Also keep any params that might be used by _validate (none currently but safe to keep known logic params if we had any)
        # But strictly for the tool function call, we must filter.
        keys_to_remove = [k for k in normalized.keys() if k not in allowed]
        if keys_to_remove:
            logger.warning(f"Removing invalid parameters for {tool_name}: {keys_to_remove}")
            for k in keys_to_remove:
                del normalized[k]
    
    now = datetime.now()
    
    # Detect season in the message
    season_detected = detect_season_in_text(user_message)
    
    # Handle season-based queries
    if season_detected and "year" in normalized:
        season_year = normalized["year"]
        season_months = SEASON_TO_MONTHS[season_detected]
        
        # For winter, if year is mentioned as 2025 but we're in 2026,
        # it means winter 2024-2025 (Dec 2024, Jan-Feb 2025)
        if season_detected == "invierno" and season_year < now.year:
            # Winter spans two years: Dec of (year-1) and Jan-Feb of year
            # We'll adjust the year to query the correct range
            # For now, set year to the latter year (Jan-Feb)
            logger.info(f"Season '{season_detected}' detected for year {season_year}. "
                       f"Winter spans {season_year-1}-{season_year}.")
            # Don't set month filter - let the tool handle all winter months
            # Remove month if present to avoid conflicts
            if "month" in normalized:
                del normalized["month"]
        
        logger.info(f"Season detected: {season_detected} → months {season_months}")
    
    # Validate year parameter
    if "year" in normalized:
        year = normalized["year"]
        
        # Check if year is in the future
        if year > now.year:
            errors.append(f"No puedo consultar datos del futuro (año {year}). "
                         f"El año actual es {now.year}.")
        
        # Check if year is too far in the past (before 2000)
        if year < 2000:
            errors.append(f"El año {year} parece incorrecto. ¿Quisiste decir {now.year}?")
    
    # Validate month parameter
    if "month" in normalized:
        month = normalized["month"]
        
        # Check valid range
        if not (1 <= month <= 12):
            errors.append(f"Mes inválido: {month}. Debe estar entre 1 y 12.")
        
        # Check if month is in the future for current year
        if "year" in normalized and normalized["year"] == now.year:
            if month > now.month:
                errors.append(f"No puedo consultar datos del futuro (mes {month}/{now.year}). "
                             f"Estamos en {now.month}/{now.year}.")
    
    # Validate concept (if present)
    if "concept" in normalized:
        concept = normalized["concept"].strip()
        if len(concept) < 2:
            errors.append(f"El concepto de búsqueda '{concept}' es demasiado corto. "
                         "Intenta con al menos 2 caracteres.")
        # Normalize concept: remove extra spaces
        normalized["concept"] = " ".join(concept.split())
    
    # Validate limit (for get_top_expenses)
    if "limit" in normalized:
        limit = normalized["limit"]
        if not isinstance(limit, int) or limit < 1:
            errors.append(f"Límite inválido: {limit}. Debe ser un número positivo.")
            normalized["limit"] = 10  # Default
        elif limit > 100:
            errors.append(f"Límite muy alto: {limit}. Ajustado a 100.")
            normalized["limit"] = 100
    
    return normalized, errors


def _llm_extract_tool_and_params(user_message: str, available_tools: List[Dict[str, Any]], context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Usa el LLM para extraer la herramienta y parámetros de la pregunta del usuario.
    
    Returns:
        Dict con {tool_name: str, params: Dict} o None si falla
    """
    if not check_ollama_running():
        logger.warning("Ollama not running, falling back to regex extraction")
        return None
    
    llm_config = get_llm_config()
    model_name = llm_config.get('model_tier', 'phi3')
    
    # Construir descripción de herramientas
    tools_desc = []
    for tool in available_tools:
        params_desc = ", ".join([f"{k} ({v.get('type', 'any')})" for k, v in tool.get('parameters', {}).get('properties', {}).items()])
        tools_desc.append(f"- {tool['name']}: {tool.get('description', '')} | Parámetros: {params_desc}")
    
    tools_text = "\n".join(tools_desc)
    
    # Contexto previo
    context_text = ""
    if context:
        context_text = f"\nCONTEXTO PREVIO:\n- Herramienta anterior: {context.get('tool', 'ninguna')}\n- Parámetros: {context.get('params', {})}\n"
    
    # TEMPORAL CONTEXT - Critical for date understanding
    now = datetime.now()
    current_season = get_current_season()
    
    # Información sobre estaciones para este año específico
    season_info = (
        f"- Invierno {now.year-1}-{now.year}: Diciembre {now.year-1}, Enero-Febrero {now.year}\n"
        f"- Primavera {now.year}: Marzo, Abril, Mayo\n"
        f"- Verano {now.year}: Junio, Julio, Agosto\n"
        f"- Otoño {now.year}: Septiembre, Octubre, Noviembre\n"
        f"- Invierno {now.year}-{now.year+1}: Diciembre {now.year}, Enero-Febrero {now.year+1}"
    )
    
    # Prompt
    prompt = f"""Eres un asistente financiero que analiza preguntas sobre finanzas personales.

HERRAMIENTAS DISPONIBLES:
{tools_text}

PREGUNTA DEL USUARIO:
"{user_message}"
{context_text}
CONTEXTO TEMPORAL CRÍTICO (presta mucha atención a esto):
- Fecha actual COMPLETA: {now.strftime('%Y-%m-%d')} ({now.strftime('%d de %B de %Y')})
- Año actual: {now.year}
- Mes actual: {now.month} ({now.strftime('%B')})
- Estación actual: {current_season}
- Día del mes: {now.day}

ESTACIONES DEL AÑO (hemisferio norte):
{season_info}

REGLAS DE INTERPRETACIÓN TEMPORAL:
1. Si mencionan "invierno de 2025" y estamos en 2026, se refieren al PASADO (dic 2024 - feb 2025)
2. Si mencionan "este mes", usar mes={now.month} y year={now.year}
3. Si mencionan "este año", usar year={now.year}
4. Si mencionan una estación + año, mapear a los meses correctos de esa estación
5. NUNCA extraigas fechas futuras - validar que year <= {now.year}

INSTRUCCIONES:
1. Identifica la herramienta más apropiada para responder la pregunta
2. Extrae TODOS los parámetros necesarios del mensaje del usuario
3. Si la pregunta parece ser un follow-up y hay contexto previo, hereda los parámetros temporales (year, month) si no se especifican nuevos
4. Si ninguna herramienta es apropiada (ej: pregunta off-topic), retorna {{"tool": null}}

IMPORTANTE: Retorna SOLO un objeto JSON válido en este formato exacto (sin explicaciones adicionales):
{{"tool": "nombre_herramienta", "params": {{"param1": valor1, "param2": "valor2"}}}}

Ejemplo 1:
Pregunta: "cuanto gasté en pan este mes?"
Respuesta: {{"tool": "search_expenses_by_concept", "params": {{"concept": "pan", "year": {now.year}, "month": {now.month}}}}}

Ejemplo 2:
Pregunta: "cuanto gasté en ubers en invierno de 2025" (cuando estamos en {now.year})
Respuesta: {{"tool": "search_expenses_by_concept", "params": {{"concept": "uber", "year": 2025}}}}

Ejemplo 3:
Pregunta: "pero cuantos son de navidad?" (con contexto year=2024)
Respuesta: {{"tool": "search_expenses_by_concept", "params": {{"concept": "navidad", "year": 2024}}}}

Tu respuesta:"""

    try:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Baja temperatura para respuestas consistentes
                "num_predict": 200
            }
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
            # Extraer JSON de la respuesta
            # El LLM podría incluir texto antes/después del JSON
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                extracted = json.loads(json_str)
                
                logger.info(f"LLM extracted: {extracted}")
                return extracted
            else:
                logger.warning(f"No JSON found in LLM response: {text}")
                return None
    except Exception as e:
        logger.error(f"Error in LLM extraction: {e}")
        return None


def _llm_format_response(user_message: str, tool_result: str) -> str:
    """
    Usa el LLM para formatear el resultado de la herramienta en lenguaje natural.
    
    Returns:
        Respuesta formateada o el resultado original si falla
    """
    if not check_ollama_running():
        return tool_result
    
    llm_config = get_llm_config()
    model_name = llm_config.get('model_tier', 'phi3')
    
    prompt = f"""Eres un asistente financiero amigable y profesional.

PREGUNTA ORIGINAL DEL USUARIO:
"{user_message}"

RESULTADO DE LA BÚSQUEDA:
{tool_result}

INSTRUCCIONES CRÍTICAS:
1. VERIFICA que el resultado responda a la pregunta original
2. Si el resultado NO coincide con la pregunta (ej: preguntaron por "helados" pero el resultado da totales generales), DI EXPLÍCITAMENTE que hubo un error y explica qué salió mal
3. Si el resultado es correcto, conviértelo en una respuesta natural y conversacional
4. Usa emojis apropiados (💰, 📊, 🔍, 💸, etc.) pero con moderación
5. Sé conciso pero informativo
6. Si el resultado indica que no se encontró nada, sugiere alternativas o reformular la pregunta
7. Mantén un tono profesional pero cercano

IMPORTANTE: Si detectas que el resultado no tiene sentido con la pregunta, empieza tu respuesta con:
"⚠️ Parece que hubo un problema con la búsqueda..."

Tu respuesta:"""

    try:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 300
            }
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=20)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
            if text:
                logger.info(f"LLM formatted response successfully")
                return text
            else:
                return tool_result
    except Exception as e:
        logger.error(f"Error in LLM formatting: {e}")
        return tool_result


def chat_with_tools(user_message: str, available_tools: List[Dict[str, Any]], context: Dict[str, Any] = None) -> str:
    """
    Procesa un mensaje del usuario con acceso a herramientas/funciones.
    
    Esta es una implementación simplificada que:
    1. Analiza la pregunta del usuario
    2. Determina qué herramienta(s) usar
    3. Ejecuta las herramientas necesarias
    4. Genera una respuesta natural basada en los resultados
    
    Args:
        user_message: Mensaje/pregunta del usuario
        available_tools: Lista de herramientas disponibles con sus definiciones
        context: Contexto de la conversación previa (opcional)
        
    Returns:
        Respuesta del asistente
    """
    if not is_llm_enabled():
        return "El servicio de LLM no está habilitado. Por favor, actívalo en Utilidades > Configuración de IA."
    
    # Initialize search context
    search_ctx = SearchContext(message=user_message)
    
    # Import streamlit para guardar contexto en session_state
    # NOTE: Esto acopla este servicio a Streamlit - considerar refactorizar en el futuro
    import streamlit as st
    
    try:
        # PASO 1: Extraer herramienta y parámetros usando LLM
        llm_extraction = _llm_extract_tool_and_params(user_message, available_tools, context)
        
        if llm_extraction and llm_extraction.get('tool'):
            # LLM extraction exitosa
            tool_name = llm_extraction.get('tool')
            params = llm_extraction.get('params', {})
            search_ctx.extracted_by = "llm"
            
            # Si tool es null, es una pregunta off-topic
            if tool_name is None or tool_name == "null":
                return (
                    "🤖 Soy el asistente financiero de **PersAcc**. No tengo información sobre eso, "
                    "pero puedo ayudarte con tus finanzas personales.\n\n"
                    "**Prueba preguntas como:**\n"
                    "- ¿Cuánto gasté en restaurantes este mes?\n"
                    "- ¿Cuáles son mis mayores gastos del 2024?\n"
                    "- ¿Cuál es mi tasa de ahorro?\n"
                    "- Busca gastos de *[concepto]*"
                )
            
            # Buscar la herramienta
            tool_to_use = next((t for t in available_tools if t['name'] == tool_name), None)
            
            if not tool_to_use:
                logger.warning(f"LLM returned unknown tool: {tool_name}")
                # Fallback a método antiguo
                tool_to_use = _select_tool(user_message, available_tools)
                params = _extract_parameters(user_message, tool_to_use, context) if tool_to_use else {}
                search_ctx.extracted_by = "regex_fallback"
        else:
            # Fallback a método antiguo si LLM falla
            logger.info("Falling back to regex-based extraction")
            tool_to_use = _select_tool(user_message, available_tools)
            search_ctx.extracted_by = "regex"
            
            if not tool_to_use:
                return (
                    "🤖 Soy el asistente financiero de **PersAcc**. No tengo información sobre eso, "
                    "pero puedo ayudarte con tus finanzas personales.\n\n"
                    "**Prueba preguntas como:**\n"
                    "- ¿Cuánto gasté en restaurantes este mes?\n"
                    "- ¿Cuáles son mis mayores gastos del 2024?\n"
                    "- ¿Cuál es mi tasa de ahorro?\n"
                    "- Busca gastos de *[concepto]*"
                )
            
            params = _extract_parameters(user_message, tool_to_use, context)
        
        # PASO 1.5: Validar y normalizar parámetros
        search_ctx.tool_name = tool_to_use['name']
        search_ctx.season_detected = detect_season_in_text(user_message)
        
        validated_params, validation_errors = _validate_and_normalize_params(
            tool_to_use['name'],
            params,
            user_message
        )
        
        search_ctx.params = validated_params
        search_ctx.validation_errors = validation_errors
        
        # Si hay errores críticos de validación, retornar mensaje de error
        if validation_errors:
            error_msg = "⚠️ **Problemas con tu consulta:**\n\n"
            for i, error in enumerate(validation_errors, 1):
                error_msg += f"{i}. {error}\n"
            error_msg += "\n Por favor, reformula tu pregunta."
            
            # Guardar trace para debugging
            st.session_state['last_search_trace'] = search_ctx.to_dict()
            
            return error_msg
        
        # PASO 2: Ejecutar la herramienta
        tool_function = tool_to_use["function"]
        raw_result = tool_function(**validated_params)
        
        # Guardar contexto para preguntas de seguimiento
        st.session_state['last_search_context'] = {
            'tool': tool_to_use['name'],
            'params': validated_params,
            'message': user_message
        }
        
        # Guardar trace completo para debugging
        st.session_state['last_search_trace'] = search_ctx.to_dict()
        
        # PASO 3: Formatear respuesta usando LLM
        formatted_result = _llm_format_response(user_message, raw_result)
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"Error in chat_with_tools: {e}")
        
        # Guardar error trace
        search_ctx.validation_errors.append(f"Error de ejecución: {str(e)}")
        st.session_state['last_search_trace'] = search_ctx.to_dict()
        
        return f"Lo siento, hubo un error al procesar tu consulta: {str(e)}"


def _select_tool(user_message: str, available_tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Selecciona la herramienta más apropiada basándose en el mensaje del usuario.
    
    Esta es una implementación basada en palabras clave (simple pero efectiva).
    En una versión más avanzada, se usaría el LLM para seleccionar la herramienta.
    """
    message_lower = user_message.lower()
    import re
    
    # PRIORITY 0: Detectar si mencionan una CATEGORÍA conocida
    known_categories = [
        "transporte", "restaurante", "restaurantes", "ocio", "comida", 
        "casa", "vivienda", "salud", "deporte", "viajes", "ropa", 
        "tecnologia", "tecnología", "educacion", "educación", "regalo", "regalos",
        "alcohol", "entretenimiento", "suscripc"
    ]
    
    for category in known_categories:
        pattern = r'\b' + re.escape(category) + r'\b'
        if re.search(pattern, message_lower):
            logger.info(f"Category detected: '{category}' → search_expenses_by_category")
            return next((t for t in available_tools if t["name"] == "search_expenses_by_category"), None)
    
    # PRIORITY 1: Si mencionan un concepto específico (NO categoría)
    
    # Patrones que indican búsqueda de concepto específico
    concept_indicators = [
        r'en\s+(\w+)',  # "en helados", "en uber"
        r'de\s+(\w+)',  # "de restaurantes"
        r'para\s+(\w+)',  # "para regalos"
        r'gast[eéo]\s+en\s+(\w+)',  # "gasté en X", "gasto en Y"
    ]
    
    has_specific_concept = False
    for pattern in concept_indicators:
        match = re.search(pattern, message_lower)
        if match:
            # Check if what follows "en/de/para" is not a time word
            word_after = match.group(1)
            time_words = ["enero", "febrero", "marzo", "abril", "mayo", "junio", 
                         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
                         "invierno", "primavera", "verano", "otoño", "este", "esta", "el"]
            # También verificar que no sea categoría conocida
            known_categories_check = ["transporte", "restaurante", "ocio", "comida", "casa", "salud", "deporte", "viajes", "ropa", "alcohol"]
            if word_after not in time_words and word_after not in known_categories_check:
                has_specific_concept = True
                break
    
    # Si hay concepto específico, usar search_expenses_by_concept
    if has_specific_concept:
        return next((t for t in available_tools if t["name"] == "search_expenses_by_concept"), None)
    
    # PRIORITY 2: Mapeo de palabras clave a herramientas específicas
    keyword_mapping = {
        "search_expenses_by_category": [" categoría", " categoria", " restaurante ", " ocio ", " transporte ", " alcohol ", " comida "],
        "get_top_expenses": ["mayor", "mayores", "top", "más grande", "mas grande", "principales", "top "],
        "get_category_breakdown": ["desglose", "distribución", "distribucion", "por categoría", "por categoria"],
        "get_savings_rate": ["tasa de ahorro", "ahorro", " inversión", " inversion", "ahorrado", "invertido"],
        # get_total_by_type solo si es MUY genérico
        "get_total_by_type": ["total de gastos", "total de ingresos", "cuanto gaste en total", "suma de gastos"]
    }
    
    # Buscar herramienta por palabras clave (excluyendo search_expenses_by_concept que ya se chequeó)
    for tool in available_tools:
        tool_name = tool["name"]
        if tool_name == "search_expenses_by_concept":
            continue  # Ya se chequeó arriba
        
        keywords = keyword_mapping.get(tool_name, [])
        
        if any(keyword in message_lower for keyword in keywords):
            return tool
    
    # PRIORITY 3: Fallback a search_expenses_by_concept para cualquier pregunta de gasto
    # con palabras clave generales
    if any(word in message_lower for word in ["gast", "compra", "pag", "cuanto", "cuánto"]):
        return next((t for t in available_tools if t["name"] == "search_expenses_by_concept"), None)
    
    return None


def _extract_parameters(user_message: str, tool: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Extrae parámetros del mensaje del usuario para la herramienta seleccionada.
    
    Esta es una implementación basada en regex y palabras clave.
    Si hay contexto previo, hereda parámetros cuando la pregunta es de seguimiento.
    """
    import re
    from datetime import datetime
    
    params = {}
    message_lower = user_message.lower()
    
    # Detectar si es una pregunta de seguimiento (corta, sin año/mes explícito)
    is_followup = False
    if context and len(user_message.split()) < 6:  # Pregunta corta
        followup_indicators = ["pero", "y ", "solo", "cuantos", "cuales", "que", "ahora"]
        if any(ind in message_lower for ind in followup_indicators):
            is_followup = True
    
    # Extraer año
    year_match = re.search(r'\b(20\d{2})\b', user_message)
    if year_match:
        params["year"] = int(year_match.group(1))
    
    # Extraer mes
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }
    for mes_nombre, mes_num in meses.items():
        if mes_nombre in message_lower:
            params["month"] = mes_num
            break
    
    # Detectar referencias temporales
    now = datetime.now()
    
    if "esta semana" in message_lower or "semana actual" in message_lower:
        # Para simplificar, usar mes actual
        params["year"] = now.year
        params["month"] = now.month
    elif "este mes" in message_lower or "mes actual" in message_lower:
        params["year"] = now.year
        params["month"] = now.month
    elif "este año" in message_lower or "año actual" in message_lower:
        params["year"] = now.year
    elif "año pasado" in message_lower or "el año pasado" in message_lower or "last year" in message_lower or "el año anterior" in message_lower:
        # Año pasado = current year - 1
        params["year"] = now.year - 1
        logger.info(f"Detected 'año pasado' → year={now.year - 1}")
    elif "mes pasado" in message_lower:
        last_month = now.month - 1
        params["month"] = 12 if last_month == 0 else last_month
        params["year"] = now.year if last_month > 0 else now.year - 1
    
    # Si es follow-up y no encontramos año/mes, heredar del contexto
    if is_followup and context:
        prev_params = context.get('params', {})
        if 'year' not in params and 'year' in prev_params:
            params['year'] = prev_params['year']
        if 'month' not in params and 'month' in prev_params:
            params['month'] = prev_params['month']
    
    # Parámetros específicos por herramienta
    tool_name = tool["name"]
    
    if tool_name == "search_expenses_by_concept":
        # Extraer concepto - buscar palabras clave después de preposiciones
        concept_patterns = [
            r'(?:gast[eéó]|compré?|pagué?)\s+en\s+([^?,.\d]+)',  # "gasté en helados"
            r'en\s+([^?,.\d]+?)\s+(?:el|este|este|año|mes)',  # "en helados el año pasado"
            r'en\s+([^?,.\d]+)',  # "en helados"
            r'de\s+([^?,.\d]+)',  # "de restaurantes"
            r'para\s+([^?,.\d]+)',  # "para regalos"
        ]
        
        # Time/stop words to exclude from concept
        time_words = {"enero", "febrero", "marzo", "abril", "mayo", "junio",
                     "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
                     "invierno", "primavera", "verano", "otoño", "este", "esta", "año", "mes",
                     "el", "la", "los", "las", "pasado", "actual", "anterior"}
        
        for pattern in concept_patterns:
            match = re.search(pattern, message_lower)
            if match:
                raw_concept = match.group(1).strip()
                # Clean concept: remove articles and time words
                concept_words = raw_concept.split()
                cleaned_words = [w for w in concept_words if w not in time_words and len(w) > 1]
                
                if cleaned_words:
                    concept = " ".join(cleaned_words)
                    params["concept"] = concept
                    logger.info(f"Extracted concept: '{concept}' from pattern: {pattern}")
                    break
        
        # Fallback: si no se extrajo concepto con regex, limpiar palabras clave y usar el resto
        if "concept" not in params:
            # Remove common query words
            clean_msg = re.sub(r'\b(cuanto|cuánto|me|costo|costó|cuesta|vale|precio|que|qué|el|la|encuentra|busca|gastos?|de|en|un|una|del|al|año|pasado|este|esta|mes)\b', '', message_lower)
            potential_concept = clean_msg.strip()
            if potential_concept and len(potential_concept) > 1:
                params["concept"] = potential_concept
                logger.info(f"Fallback concept extraction: '{potential_concept}'")
    
    elif tool_name == "search_expenses_by_category":
        # Extraer nombre de categoría
        category_keywords = ["restaurante", "ocio", "transporte", "alcohol", "comida", "casa", "salud"]
        for keyword in category_keywords:
            if keyword in message_lower:
                params["category_name"] = keyword.capitalize()
                break
    
    elif tool_name == "get_total_by_type":
        # Determinar tipo de movimiento
        if any(word in message_lower for word in ["gast", "gasto", "gastos"]):
            params["movement_type"] = "GASTO"
        elif any(word in message_lower for word in ["ingres", "ingreso", "ingresos", "cobr"]):
            params["movement_type"] = "INGRESO"
        elif any(word in message_lower for word in ["inver", "inversion", "inversiones", "ahorr"]):
            params["movement_type"] = "INVERSION"
        else:
            # Default a GASTO si no se especifica (más común en preguntas de "cuánto")
            params["movement_type"] = "GASTO"
    
    elif tool_name == "get_top_expenses":
        # Extraer límite si se menciona
        limit_match = re.search(r'\b(\d+)\b', user_message)
        if limit_match:
            params["limit"] = int(limit_match.group(1))
        else:
            params["limit"] = 10
    
    return params


