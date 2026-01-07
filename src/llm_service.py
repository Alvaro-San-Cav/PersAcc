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
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

from . import llm_prompts
from .config import get_currency_symbol

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


def generate_quick_summary(income: float, expenses: float, balance: float, lang: str = "es") -> str:
    """
    Generate a quick, witty one-liner summary about current month status.
    
    Args:
        income: Total income so far  
        expenses: Total expenses so far
        balance: Current balance
        lang: Language ('es' or 'en')
    
    Returns:
        A short, funny summary (max 150 chars)
    """
    # DEBUG MODE: Return messages instead of empty
    DEBUG = True
    
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
        
        # Build ultra-short prompt
        if lang == "es":
            prompt = f"""Eres un asesor financiero gracioso. Resume en UNA SOLA FRASE corta y divertida (máximo 20 palabras) cómo va el mes:
Ingresos: {income:.2f}€
Gastos: {expenses:.2f}€  
Balance: {balance:.2f}€

Responde SOLO la frase, sin intro. Sé directo y usa emojis."""
        else:
            prompt = f"""You're a witty financial advisor. Summarize in ONE SHORT funny sentence (max 20 words) how the month is going:
Income: €{income:.2f}
Expenses: €{expenses:.2f}
Balance: €{balance:.2f}

Just the sentence, no intro. Be direct and use emojis."""
        
        # Special handling for Qwen3 models
        if 'qwen' in model_name.lower():
            prompt = f"""<|im_start|>system
Eres un asesor financiero gracioso y conciso.<|im_end|>
<|im_start|>user
{prompt}<|im_end|>
<|im_start|>assistant
"""
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.9,
                "num_predict": 100,
                "num_ctx": 512,
            }
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
            # Limpiar y limitar longitud
            if text:
                text = text.split('\n')[0].strip()
                if len(text) > 200:
                    text = text[:197] + "..."
                return text
            else:
                return f"[DEBUG: Respuesta vacía de Ollama con modelo {model_name}]" if DEBUG else ""
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
    
    # Special handling for Qwen3 models - they require chat template format
    if 'qwen' in model_name.lower():
        full_prompt = f"""<|im_start|>system
Eres un experto asesor financiero personal. Analiza datos financieros y proporciona recomendaciones estratégicas claras y accionables.<|im_end|>
<|im_start|>user
{full_prompt}<|im_end|>
<|im_start|>assistant
"""
    
    # Log prompt size for debugging
    logger.info(f"Prompt size: {len(full_prompt)} chars, movements: {len(movements) if movements else 0}")
    
    # Call Ollama API
    try:
        payload = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.95,
                "num_predict": max_tokens,
                "num_ctx": 4096,
                "num_thread": 8,
                "repeat_penalty": 1.1
            }
        }
        
        # No añadimos stop sequences para evitar cortar respuestas prematuramente
        
        logger.info(f"Generating analysis with {model_name} (max {max_tokens} tokens)...")
        logger.info(f"Prompt length: {len(full_prompt)} characters")
        
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=180  # 3 minutos - modelos grandes pueden tardar más
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
        except:
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
        except:
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

