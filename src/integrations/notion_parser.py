"""
Parser y mapper para entradas de Notion.
Sugiere categorías y relevancias usando IA cuando no se especifican.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import date

from src.models import TipoMovimiento, RelevanciaCode, Categoria
from src.database import get_categorias_by_tipo
from src.config import load_config
from src.integrations.notion import normalize_text, normalize_relevancia

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipo mapping — canonical forms only (case-insensitive via normalize_text)
# ---------------------------------------------------------------------------

_CANONICAL_TIPOS: Dict[str, TipoMovimiento] = {
    "gasto": TipoMovimiento.GASTO,
    "expense": TipoMovimiento.GASTO,
    "pago": TipoMovimiento.GASTO,
    "ingreso": TipoMovimiento.INGRESO,
    "income": TipoMovimiento.INGRESO,
    "inversion": TipoMovimiento.INVERSION,
    "inversion ahorro": TipoMovimiento.INVERSION,
    "ahorro": TipoMovimiento.INVERSION,
    "saving": TipoMovimiento.INVERSION,
    "savings": TipoMovimiento.INVERSION,
    "investment": TipoMovimiento.INVERSION,
    "traspaso entrada": TipoMovimiento.TRASPASO_ENTRADA,
    "transfer in": TipoMovimiento.TRASPASO_ENTRADA,
    "traspaso salida": TipoMovimiento.TRASPASO_SALIDA,
    "transfer out": TipoMovimiento.TRASPASO_SALIDA,
}

# Keyword fragments used as a last-resort fallback when no canonical match
_TIPO_KEYWORDS: Dict[str, TipoMovimiento] = {
    "traspaso": None,  # sentinel — resolved using "entrada"/"salida" context
    "ingreso": TipoMovimiento.INGRESO,
    "income": TipoMovimiento.INGRESO,
    "entrada": TipoMovimiento.INGRESO,
    "inversion": TipoMovimiento.INVERSION,
    "ahorro": TipoMovimiento.INVERSION,
    "saving": TipoMovimiento.INVERSION,
    "gasto": TipoMovimiento.GASTO,
    "expense": TipoMovimiento.GASTO,
    "pago": TipoMovimiento.GASTO,
}

# ---------------------------------------------------------------------------
# Default heuristic keywords for relevancia suggestion (extensible via config)
# ---------------------------------------------------------------------------

_DEFAULT_RELEVANCIA_KEYWORDS: Dict[str, List[str]] = {
    "NE": [
        'factura', 'luz', 'agua', 'gas', 'alquiler', 'hipoteca',
        'seguro', 'medico', 'médico', 'farmacia', 'transporte', 'metro', 'bus',
        'bill', 'rent', 'insurance', 'medical', 'pharmacy', 'transport',
    ],
    "SUP": [
        'capricho', 'impulso', 'innecesario', 'unnecessary', 'impulse',
    ],
    "TON": [
        'error', 'multa', 'penalización', 'penalizacion', 'recargo',
        'fine', 'penalty', 'late fee',
    ],
}


def _get_relevancia_keywords() -> Dict[str, List[str]]:
    """Returns relevancia keyword lists, merging defaults with config overrides."""
    keywords = {k: list(v) for k, v in _DEFAULT_RELEVANCIA_KEYWORDS.items()}
    try:
        config = load_config()
        custom = config.get('notion', {}).get('relevancia_keywords', {})
        if isinstance(custom, dict):
            for code, words in custom.items():
                code_upper = code.upper()
                if code_upper in keywords and isinstance(words, list):
                    keywords[code_upper].extend(
                        w for w in words if isinstance(w, str) and w.strip()
                    )
    except Exception:
        pass
    return keywords


# ---------------------------------------------------------------------------
# Tipo mapping
# ---------------------------------------------------------------------------

def _build_tipo_mapping(config: Optional[Dict[str, Any]] = None) -> Dict[str, TipoMovimiento]:
    """
    Construye mapeo de tipos a partir del mapeo canónico + aliases opcionales en config.

    Config opcional soportada:
    notion.tipo_aliases: {
        "GASTO": ["Expense", "Cost"],
        "INGRESO": ["Income"],
        "INVERSION_AHORRO": ["Savings", "Investment"],
        "TRASPASO_ENTRADA": ["Transfer In"],
        "TRASPASO_SALIDA": ["Transfer Out"]
    }
    """
    # Start from canonical forms (already normalized keys)
    mapping = dict(_CANONICAL_TIPOS)

    if not config:
        return mapping

    notion_cfg = config.get("notion", {}) if isinstance(config, dict) else {}
    aliases = notion_cfg.get("tipo_aliases", {}) if isinstance(notion_cfg, dict) else {}
    if not isinstance(aliases, dict):
        return mapping

    enum_by_key = {
        "GASTO": TipoMovimiento.GASTO,
        "INGRESO": TipoMovimiento.INGRESO,
        "INVERSION_AHORRO": TipoMovimiento.INVERSION,
        "INVERSION": TipoMovimiento.INVERSION,
        "TRASPASO_ENTRADA": TipoMovimiento.TRASPASO_ENTRADA,
        "TRASPASO_SALIDA": TipoMovimiento.TRASPASO_SALIDA,
    }

    for key, values in aliases.items():
        tipo_enum = enum_by_key.get(str(key).upper())
        if not tipo_enum:
            continue
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for raw in values:
            if isinstance(raw, str) and raw.strip():
                # Store both original and normalized forms
                mapping[raw.strip()] = tipo_enum
                mapping[normalize_text(raw)] = tipo_enum

    return mapping


def map_tipo_movimiento(
    tipo_str: str,
    tipo_mapping: Optional[Dict[str, TipoMovimiento]] = None,
) -> TipoMovimiento:
    """
    Mapea el string de tipo de Notion a TipoMovimiento con matching flexible.

    Args:
        tipo_str: Valor del campo Tipo en Notion (puede incluir emojis)
        tipo_mapping: Mapeo personalizado (si None, usa canónicos)

    Returns:
        TipoMovimiento correspondiente (default: GASTO)
    """
    if not tipo_str:
        return TipoMovimiento.GASTO

    mapping = tipo_mapping or _CANONICAL_TIPOS

    # 1) Match directo
    if tipo_str in mapping:
        return mapping[tipo_str]

    # 2) Match normalizado
    tipo_clean = normalize_text(tipo_str)
    if tipo_clean in mapping:
        return mapping[tipo_clean]

    # 3) Buscar en todas las claves normalizadas del mapping
    for raw_key, mapped_tipo in mapping.items():
        if normalize_text(raw_key) == tipo_clean:
            return mapped_tipo

    # 4) Keyword fallback — manejar traspasos como caso especial
    if 'traspaso' in tipo_clean or 'transfer' in tipo_clean:
        if 'entrada' in tipo_clean or 'in' in tipo_clean.split():
            return TipoMovimiento.TRASPASO_ENTRADA
        elif 'salida' in tipo_clean or 'out' in tipo_clean.split():
            return TipoMovimiento.TRASPASO_SALIDA

    for keyword, tipo_enum in _TIPO_KEYWORDS.items():
        if tipo_enum is not None and keyword in tipo_clean:
            return tipo_enum

    # 5) Default
    logger.warning("Tipo '%s' no reconocido, usando Gasto por defecto", tipo_str)
    return TipoMovimiento.GASTO


# ---------------------------------------------------------------------------
# Category matching
# ---------------------------------------------------------------------------

def find_best_category(
    concepto: str,
    tipo: TipoMovimiento,
    categoria_hint: str = "",
) -> Optional[int]:
    """
    Encuentra la mejor categoría matching para el concepto con fuzzy matching.

    1. Si hay categoria_hint, busca match exacto, parcial o fuzzy
    2. Si no hay match, intenta usar IA (si disponible)
    3. Si nada funciona, retorna None para que el usuario elija

    Args:
        concepto: Texto del concepto
        tipo: Tipo de movimiento
        categoria_hint: Nombre de categoría sugerido desde Notion

    Returns:
        ID de la categoría o None si no hay categorías o no hay match
    """
    categorias = get_categorias_by_tipo(tipo)

    if not categorias:
        return None

    # Si hay hint, buscar match con diferentes niveles de tolerancia
    if categoria_hint:
        hint_clean = normalize_text(categoria_hint)

        if not hint_clean:
            return None

        # 1. Match exacto (normalizado)
        for cat in categorias:
            if normalize_text(cat.nombre) == hint_clean:
                return cat.id

        # 2. Match parcial (uno contiene al otro)
        for cat in categorias:
            cat_clean = normalize_text(cat.nombre)
            if hint_clean in cat_clean or cat_clean in hint_clean:
                return cat.id

        # 3. Match por palabras individuales (Jaccard >= 50%)
        hint_words = set(hint_clean.split())
        best_match_id = None
        best_match_score = 0.0

        for cat in categorias:
            cat_words = set(normalize_text(cat.nombre).split())
            if hint_words and cat_words:
                intersection = len(hint_words & cat_words)
                union = len(hint_words | cat_words)
                similarity = intersection / union if union > 0 else 0
                if similarity > best_match_score and similarity >= 0.5:
                    best_match_score = similarity
                    best_match_id = cat.id

        if best_match_id:
            return best_match_id

        logger.info(
            "Categoría '%s' no encontrada en %s, usuario deberá elegir",
            categoria_hint, tipo.value,
        )

    # Intentar con IA si está disponible
    config = load_config()
    llm_config = config.get('llm', {})
    lang = config.get('language', 'es')

    if llm_config.get('enabled', False):
        suggested_id = _suggest_category_with_ai(concepto, tipo, categorias, lang=lang)
        if suggested_id:
            return suggested_id

    # Fallback: buscar por keywords en el concepto
    concepto_norm = normalize_text(concepto)
    for cat in categorias:
        for word in normalize_text(cat.nombre).split():
            if len(word) > 3 and word in concepto_norm:
                return cat.id

    return None


# ---------------------------------------------------------------------------
# AI suggestions
# ---------------------------------------------------------------------------

def _clean_ai_response(text: str) -> str:
    """Limpia respuesta de modelos LLM: quita tags <think>, comillas, whitespace."""
    if not text:
        return ""
    # Quitar bloques <think>...</think> (Qwen)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip().strip('"').strip("'").strip()


def _suggest_category_with_ai(
    concepto: str,
    tipo: TipoMovimiento,
    categorias: List[Categoria],
    lang: str = "es",
) -> Optional[int]:
    """
    Usa Ollama para sugerir la mejor categoría.

    Returns:
        ID de la categoría sugerida o None
    """
    try:
        from src.ai.llm_service import is_llm_enabled, get_llm_config, get_ollama_urls
        import requests
    except ImportError:
        logger.debug("requests o llm_service no disponible para sugerencia IA")
        return None

    try:
        if not is_llm_enabled():
            return None

        config = get_llm_config()
        model_name = config.get("model_chat", config.get("model_tier", "phi3"))
        urls = get_ollama_urls()

        cat_names = [f"- {cat.nombre}" for cat in categorias]
        cat_list = "\n".join(cat_names)

        if lang == "en":
            prompt = f"""Given the following {tipo.value.lower()} concept:
    "{concepto}"

    Which category is the best match?
    {cat_list}

    Reply ONLY with the exact category name, no explanation."""
        else:
            prompt = f"""Dado el siguiente concepto de {tipo.value.lower()}:
    "{concepto}"

    ¿Cuál de estas categorías es la más apropiada?
    {cat_list}

    Responde SOLO con el nombre exacto de la categoría, sin explicación."""

        # Check for Qwen model
        is_qwen = 'qwen' in model_name.lower()

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 50,
            },
        }
        if is_qwen:
            payload["think"] = False

        response = requests.post(urls["api"], json=payload, timeout=5)

        if response.status_code == 200:
            result = response.json()
            response_text = _clean_ai_response(result.get("response", ""))
            # Fuzzy match against category names (normalizado)
            response_norm = normalize_text(response_text)
            for cat in categorias:
                if normalize_text(cat.nombre) == response_norm:
                    return cat.id
            # Partial match fallback
            for cat in categorias:
                cat_norm = normalize_text(cat.nombre)
                if response_norm and (response_norm in cat_norm or cat_norm in response_norm):
                    return cat.id
        else:
            logger.debug("Respuesta no OK de Ollama sugiriendo categoría: %s", response.status_code)

    except Exception as e:
        logger.debug("Error usando IA para sugerir categoría: %s", e)

    return None


# ---------------------------------------------------------------------------
# Relevancia suggestion
# ---------------------------------------------------------------------------

def suggest_relevancia(
    concepto: str,
    categoria_nombre: str = "",
) -> RelevanciaCode:
    """
    Sugiere un código de relevancia para un gasto.

    Args:
        concepto: Texto del concepto
        categoria_nombre: Nombre de la categoría (opcional)

    Returns:
        RelevanciaCode sugerido (default: LI)
    """
    config = load_config()
    llm_config = config.get('llm', {})
    lang = config.get('language', 'es')

    if llm_config.get('enabled', False):
        suggested = _suggest_relevancia_with_ai(concepto, categoria_nombre, lang=lang)
        if suggested:
            return suggested

    # Fallback: heurísticas con keywords (configurables)
    concepto_lower = concepto.lower()
    keywords = _get_relevancia_keywords()

    for kw in keywords.get("NE", []):
        if kw in concepto_lower:
            return RelevanciaCode.NE

    for kw in keywords.get("TON", []):
        if kw in concepto_lower:
            return RelevanciaCode.TON

    for kw in keywords.get("SUP", []):
        if kw in concepto_lower:
            return RelevanciaCode.SUP

    # Default: LI (me gusta / disfrute consciente)
    return RelevanciaCode.LI


def _suggest_relevancia_with_ai(
    concepto: str,
    categoria_nombre: str,
    lang: str = "es",
) -> Optional[RelevanciaCode]:
    """
    Usa Ollama para sugerir relevancia.

    Returns:
        RelevanciaCode sugerido o None
    """
    try:
        from src.ai.llm_service import is_llm_enabled, get_llm_config, get_ollama_urls
        import requests
    except ImportError:
        logger.debug("requests o llm_service no disponible para sugerencia IA")
        return None

    try:
        if not is_llm_enabled():
            return None

        config = get_llm_config()
        model_name = config.get("model_chat", config.get("model_tier", "phi3"))
        urls = get_ollama_urls()

        if lang == "en":
            prompt = f"""Classify this expense by psychological relevance:
    Concept: "{concepto}"
    Category: "{categoria_nombre or 'Not specified'}"

    Options:
    - NE: Necessary/Inevitable (bills, commuting, basic food)
    - LI: I like it/Conscious enjoyment (planned leisure, hobbies)
    - SUP: Superfluous/Optimizable (it could have been cheaper)
    - TON: Nonsense/Spending mistake (impulse buys, avoidable fines)

    Reply ONLY with the code: NE, LI, SUP or TON"""
        else:
            prompt = f"""Clasifica este gasto según su relevancia psicológica:
    Concepto: "{concepto}"
    Categoría: "{categoria_nombre or 'No especificada'}"

    Opciones:
    - NE: Necesario/Inevitable (facturas, transporte al trabajo, comida básica)
    - LI: Me gusta/Disfrute consciente (ocio planificado, hobbies)
    - SUP: Superfluo/Optimizable (podría haber sido más barato)
    - TON: Tontería/Error de gasto (compras impulsivas, multas evitables)

    Responde SOLO con el código: NE, LI, SUP o TON"""

        is_qwen = 'qwen' in model_name.lower()

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 10,
            },
        }
        if is_qwen:
            payload["think"] = False

        response = requests.post(urls["api"], json=payload, timeout=3)

        if response.status_code == 200:
            result = response.json()
            raw_code = _clean_ai_response(result.get("response", "")).upper()
            # Intentar extraer código con normalize_relevancia
            code = normalize_relevancia(raw_code)
            if code:
                try:
                    return RelevanciaCode(code)
                except ValueError:
                    pass
            # Fallback: intentar directo
            try:
                return RelevanciaCode(raw_code)
            except ValueError:
                pass
        else:
            logger.debug("Respuesta no OK de Ollama sugiriendo relevancia: %s", response.status_code)

    except Exception as e:
        logger.debug("Error usando IA para sugerir relevancia: %s", e)

    return None


# ---------------------------------------------------------------------------
# Entry builder
# ---------------------------------------------------------------------------

def create_proposed_entry(
    notion_entry: Dict[str, Any],
    categoria_id: Optional[int] = None,
    relevancia: Optional[RelevanciaCode] = None,
) -> Dict[str, Any]:
    """
    Crea una propuesta de entrada para el Ledger a partir de datos de Notion.

    Args:
        notion_entry: Diccionario con datos de Notion
        categoria_id: ID de categoría (si ya se resolvió)
        relevancia: Código de relevancia (si ya se resolvió)

    Returns:
        Diccionario con todos los campos necesarios para crear un LedgerEntry
    """
    config = load_config()
    tipo_mapping = _build_tipo_mapping(config)
    tipo = map_tipo_movimiento(notion_entry.get('tipo', 'Gasto'), tipo_mapping=tipo_mapping)

    # Resolver categoría si no se proporcionó
    if categoria_id is None:
        categoria_id = find_best_category(
            notion_entry.get('concepto', ''),
            tipo,
            notion_entry.get('categoria', ''),
        )

    # Resolver relevancia solo para gastos
    if relevancia is None and tipo == TipoMovimiento.GASTO:
        # Primero verificar si viene desde Notion
        relevancia_notion = notion_entry.get('relevancia', '')
        if relevancia_notion:
            # Usar normalize_relevancia para parsear flexiblemente
            code = normalize_relevancia(relevancia_notion)
            if code:
                relevancia_mapping = {
                    'NE': RelevanciaCode.NE,
                    'LI': RelevanciaCode.LI,
                    'SUP': RelevanciaCode.SUP,
                    'TON': RelevanciaCode.TON,
                }
                relevancia = relevancia_mapping.get(code)

        # Si no viene de Notion, sugerir con IA/heurísticas
        if relevancia is None:
            relevancia = suggest_relevancia(
                notion_entry.get('concepto', ''),
                notion_entry.get('categoria', ''),
            )

    return {
        'notion_id': notion_entry.get('id'),
        'fecha': notion_entry.get('fecha', date.today()),
        'tipo_movimiento': tipo,
        'categoria_id': categoria_id,
        'concepto': notion_entry.get('concepto', ''),
        'importe': notion_entry.get('importe', 0.0),
        'relevancia_code': relevancia if tipo == TipoMovimiento.GASTO else None,
        'categoria_nombre_sugerida': notion_entry.get('categoria', ''),
    }
