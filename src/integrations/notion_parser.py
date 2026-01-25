"""
Parser y mapper para entradas de Notion.
Sugiere categorías y relevancias usando IA cuando no se especifican.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import date

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry, Categoria
from src.database import get_categorias_by_tipo
from src.config import load_config

logger = logging.getLogger(__name__)


# Mapeo de tipos Notion a TipoMovimiento
TIPO_MAPPING = {
    "Gasto": TipoMovimiento.GASTO,
    "gasto": TipoMovimiento.GASTO,
    "GASTO": TipoMovimiento.GASTO,
    "Ingreso": TipoMovimiento.INGRESO,
    "ingreso": TipoMovimiento.INGRESO,
    "INGRESO": TipoMovimiento.INGRESO,
    "Inversión": TipoMovimiento.INVERSION,
    "Inversion": TipoMovimiento.INVERSION,
    "inversión": TipoMovimiento.INVERSION,
    "inversion": TipoMovimiento.INVERSION,
    "INVERSION": TipoMovimiento.INVERSION,
    "Ahorro": TipoMovimiento.INVERSION,
    "ahorro": TipoMovimiento.INVERSION,
    "Traspaso Entrada": TipoMovimiento.TRASPASO_ENTRADA,
    "traspaso entrada": TipoMovimiento.TRASPASO_ENTRADA,
    "Traspaso Salida": TipoMovimiento.TRASPASO_SALIDA,
    "traspaso salida": TipoMovimiento.TRASPASO_SALIDA,
}


def map_tipo_movimiento(tipo_str: str) -> TipoMovimiento:
    """
    Mapea el string de tipo de Notion a TipoMovimiento con matching flexible.
    
    Args:
        tipo_str: Valor del campo Tipo en Notion (puede incluir emojis)
        
    Returns:
        TipoMovimiento correspondiente (default: GASTO)
    """
    if not tipo_str:
        return TipoMovimiento.GASTO
    
    # Primero intenta match directo
    if tipo_str in TIPO_MAPPING:
        return TIPO_MAPPING[tipo_str]
    
    # Limpiar: quitar emojis, espacios extra, etc.
    import re
    tipo_clean = re.sub(r'[^\w\s]', '', tipo_str).strip().lower()
    
    # Buscar match con palabras clave flexibles
    if 'traspaso' in tipo_clean and 'entrada' in tipo_clean:
        return TipoMovimiento.TRASPASO_ENTRADA
    elif 'traspaso' in tipo_clean and 'salida' in tipo_clean:
        return TipoMovimiento.TRASPASO_SALIDA
    elif 'ingreso' in tipo_clean or 'income' in tipo_clean or 'entrada' in tipo_clean:
        return TipoMovimiento.INGRESO
    elif 'inversion' in tipo_clean or 'ahorro' in tipo_clean or 'saving' in tipo_clean or 'inversión' in tipo_clean:
        return TipoMovimiento.INVERSION
    elif 'gasto' in tipo_clean or 'expense' in tipo_clean or 'pago' in tipo_clean:
        return TipoMovimiento.GASTO
    
    # Si no coincide nada, default a Gasto
    logger.warning(f"Tipo '{tipo_str}' no reconocido, usando Gasto por defecto")
    return TipoMovimiento.GASTO


def find_best_category(
    concepto: str,
    tipo: TipoMovimiento,
    categoria_hint: str = ""
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
        import re
        
        # Normalizar hint (quitar emojis, espacios extra, etc.)
        hint_clean = re.sub(r'[^\w\s]', '', categoria_hint).strip().lower()
        
        if not hint_clean:
            return None
        
        # 1. Match exacto (ignorando mayúsculas)
        for cat in categorias:
            cat_clean = re.sub(r'[^\w\s]', '', cat.nombre).strip().lower()
            if cat_clean == hint_clean:
                return cat.id
        
        # 2. Match parcial (uno contiene al otro)
        for cat in categorias:
            cat_clean = re.sub(r'[^\w\s]', '', cat.nombre).strip().lower()
            if hint_clean in cat_clean or cat_clean in hint_clean:
                return cat.id
        
        # 3. Match por palabras individuales (al menos 50% de coincidencia)
        hint_words = set(hint_clean.split())
        best_match_id = None
        best_match_score = 0.0
        
        for cat in categorias:
            cat_clean = re.sub(r'[^\w\s]', '', cat.nombre).strip().lower()
            cat_words = set(cat_clean.split())
            
            # Calcular Jaccard similarity
            if hint_words and cat_words:
                intersection = len(hint_words & cat_words)
                union = len(hint_words | cat_words)
                similarity = intersection / union if union > 0 else 0
                
                if similarity > best_match_score and similarity >= 0.5:
                    best_match_score = similarity
                    best_match_id = cat.id
        
        if best_match_id:
            return best_match_id
        
        # Si no hay match suficientemente bueno, log y continuar
        logger.info(f"Categoría '{categoria_hint}' no encontrada en {tipo.value}, usuario deberá elegir")
    
    # Intentar con IA si está disponible
    config = load_config()
    llm_config = config.get('llm', {})
    
    if llm_config.get('enabled', False):
        suggested_id = _suggest_category_with_ai(concepto, tipo, categorias)
        if suggested_id:
            return suggested_id
    
    # Fallback: buscar por keywords en el concepto
    concepto_lower = concepto.lower()
    for cat in categorias:
        cat_words = cat.nombre.lower().split()
        for word in cat_words:
            if len(word) > 3 and word in concepto_lower:
                return cat.id
    
    # No se encontró match - retornar None para que el usuario elija
    return None


def _suggest_category_with_ai(
    concepto: str,
    tipo: TipoMovimiento,
    categorias: List[Categoria]
) -> Optional[int]:
    """
    Usa Ollama para sugerir la mejor categoría.
    
    Returns:
        ID de la categoría sugerida o None
    """
    try:
        from src.ai.ollama_client import get_ollama_client
        
        client = get_ollama_client()
        if not client.is_available():
            return None
        
        cat_names = [f"- {cat.nombre}" for cat in categorias]
        cat_list = "\n".join(cat_names)
        
        prompt = f"""Dado el siguiente concepto de {tipo.value.lower()}:
"{concepto}"

¿Cuál de estas categorías es la más apropiada?
{cat_list}

Responde SOLO con el nombre exacto de la categoría, sin explicación."""
        
        response = client.generate(prompt, max_tokens=50)
        
        if response:
            response_clean = response.strip().strip('"').strip("'")
            for cat in categorias:
                if cat.nombre.lower() == response_clean.lower():
                    return cat.id
                    
    except Exception as e:
        logger.debug(f"Error usando IA para sugerir categoría: {e}")
    
    return None


def suggest_relevancia(
    concepto: str,
    categoria_nombre: str = ""
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
    
    if llm_config.get('enabled', False):
        suggested = _suggest_relevancia_with_ai(concepto, categoria_nombre)
        if suggested:
            return suggested
    
    # Fallback: heurísticas simples
    concepto_lower = concepto.lower()
    
    # Palabras clave para cada tipo
    necesario_keywords = ['factura', 'luz', 'agua', 'gas', 'alquiler', 'hipoteca', 
                          'seguro', 'médico', 'farmacia', 'transporte', 'metro', 'bus']
    superfluo_keywords = ['capricho', 'impulso', 'innecesario']
    tonteria_keywords = ['error', 'multa', 'penalización', 'recargo']
    
    for kw in necesario_keywords:
        if kw in concepto_lower:
            return RelevanciaCode.NE
    
    for kw in tonteria_keywords:
        if kw in concepto_lower:
            return RelevanciaCode.TON
    
    for kw in superfluo_keywords:
        if kw in concepto_lower:
            return RelevanciaCode.SUP
    
    # Default: LI (me gusta / disfrute consciente)
    return RelevanciaCode.LI


def _suggest_relevancia_with_ai(
    concepto: str,
    categoria_nombre: str
) -> Optional[RelevanciaCode]:
    """
    Usa Ollama para sugerir relevancia.
    
    Returns:
        RelevanciaCode sugerido o None
    """
    try:
        from src.ai.ollama_client import get_ollama_client
        
        client = get_ollama_client()
        if not client.is_available():
            return None
        
        prompt = f"""Clasifica este gasto según su relevancia psicológica:
Concepto: "{concepto}"
Categoría: "{categoria_nombre or 'No especificada'}"

Opciones:
- NE: Necesario/Inevitable (facturas, transporte al trabajo, comida básica)
- LI: Me gusta/Disfrute consciente (ocio planificado, hobbies)
- SUP: Superfluo/Optimizable (podría haber sido más barato)
- TON: Tontería/Error de gasto (compras impulsivas, multas evitables)

Responde SOLO con el código: NE, LI, SUP o TON"""
        
        response = client.generate(prompt, max_tokens=10)
        
        if response:
            code = response.strip().upper()
            try:
                return RelevanciaCode(code)
            except ValueError:
                pass
                
    except Exception as e:
        logger.debug(f"Error usando IA para sugerir relevancia: {e}")
    
    return None


def create_proposed_entry(
    notion_entry: Dict[str, Any],
    categoria_id: Optional[int] = None,
    relevancia: Optional[RelevanciaCode] = None
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
    tipo = map_tipo_movimiento(notion_entry.get('tipo', 'Gasto'))
    
    # Resolver categoría si no se proporcionó
    if categoria_id is None:
        categoria_id = find_best_category(
            notion_entry.get('concepto', ''),
            tipo,
            notion_entry.get('categoria', '')
        )
    
    # Resolver relevancia solo para gastos
    if relevancia is None and tipo == TipoMovimiento.GASTO:
        # Primero verificar si viene desde Notion
        relevancia_notion = notion_entry.get('relevancia', '')
        if relevancia_notion:
            # Mapear string a RelevanciaCode
            relevancia_mapping = {
                'NE': RelevanciaCode.NE,
                'LI': RelevanciaCode.LI,
                'SUP': RelevanciaCode.SUP,
                'TON': RelevanciaCode.TON,
            }
            relevancia = relevancia_mapping.get(relevancia_notion.upper())
        
        # Si no viene de Notion, sugerir con IA/heurísticas
        if relevancia is None:
            relevancia = suggest_relevancia(
                notion_entry.get('concepto', ''),
                notion_entry.get('categoria', '')
            )
    
    return {
        'notion_id': notion_entry.get('id'),
        'fecha': notion_entry.get('fecha', date.today()),
        'tipo_movimiento': tipo,
        'categoria_id': categoria_id,
        'concepto': notion_entry.get('concepto', ''),
        'importe': notion_entry.get('importe', 0.0),
        'relevancia_code': relevancia if tipo == TipoMovimiento.GASTO else None,
        'categoria_nombre_sugerida': notion_entry.get('categoria', '')
    }
