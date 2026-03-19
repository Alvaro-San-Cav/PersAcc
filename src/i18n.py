"""
Sistema de internacionalización (i18n) para PersAcc.
Soporta múltiples idiomas mediante archivos JSON de traducción.
"""
import json
import streamlit as st
from pathlib import Path
from typing import Any

# Directorio de traducciones
LOCALES_DIR = Path(__file__).parent.parent / "locales"
DEFAULT_LANGUAGE = "es"
SUPPORTED_LANGUAGES = ["es", "en"]


def load_translations(lang: str) -> dict:
    """
    Carga el archivo de traducción para el idioma dado.
    
    Args:
        lang: Código del idioma (es, en, etc.)
        
    Returns:
        Diccionario con las traducciones
    """
    file_path = LOCALES_DIR / f"{lang}.json"
    if not file_path.exists():
        return {}

    try:
        return json.loads(file_path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError):
        # Fallback seguro: no romper la UI por un archivo de idioma dañado.
        return {}


def get_language() -> str:
    """
    Obtiene el idioma actual desde session_state.
    
    Returns:
        Código del idioma actual
    """
    lang = st.session_state.get('language', DEFAULT_LANGUAGE)
    if not isinstance(lang, str):
        lang = DEFAULT_LANGUAGE
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    st.session_state.language = lang
    return lang


def set_language(lang: str):
    """
    Establece el idioma actual en session_state.
    
    Args:
        lang: Código del idioma a establecer
    """
    if lang in SUPPORTED_LANGUAGES:
        st.session_state.language = lang
        # Limpiar caché de traducciones al cambiar idioma
        for supported_lang in SUPPORTED_LANGUAGES:
            key = f'translations_{supported_lang}'
            if key in st.session_state:
                del st.session_state[key]


def t(key: str, **kwargs) -> Any:
    """
    Traduce una clave al idioma actual.
    Soporta interpolación de variables via kwargs.
    
    Args:
        key: Clave de traducción (ej: "sidebar.quick_add.title")
        **kwargs: Variables para interpolar en la traducción
        
    Returns:
        Texto traducido
        
    Examples:
        >>> t("common.save")
        "Guardar"
        >>> t("analisis.movements.count", count=5)
        "5 movimientos"
    """
    lang = get_language()
    
    # Cargar traducciones (cacheadas en session_state)
    cache_key = f'translations_{lang}'
    if cache_key not in st.session_state:
        st.session_state[cache_key] = load_translations(lang)
    
    translations = st.session_state[cache_key]
    
    # Navegar claves anidadas (ej: "sidebar.quick_add.title")
    keys = key.split('.')
    value = translations
    
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
            if value is None:
                # Fallback: retornar la clave original si no se encuentra
                return key
        else:
            return key
    
    # Si es una lista, devolverla directamente sin interpolar
    if isinstance(value, list):
        return value
    
    # Convertir a string si es necesario (pero no listas)
    if not isinstance(value, (str, list)):
        return key
    
    # Interpolación de variables (solo para strings)
    if kwargs and isinstance(value, str):
        try:
            value = value.format(**kwargs)
        except (KeyError, ValueError):
            # Si falla la interpolación, retornar sin interpolar
            pass
    
    return value


def get_available_languages() -> list:
    """
    Obtiene la lista de idiomas disponibles.
    
    Returns:
        Lista de códigos de idioma soportados
    """
    return SUPPORTED_LANGUAGES


def get_language_name(lang_code: str) -> str:
    """
    Obtiene el nombre completo de un idioma.
    
    Args:
        lang_code: Código del idioma
        
    Returns:
        Nombre del idioma
    """
    names = {
        "es": "Español",
        "en": "English"
    }
    return names.get(lang_code, lang_code.upper())


def get_language_flag(lang_code: str) -> str:
    """
    Obtiene el emoji de bandera para un idioma.
    
    Args:
        lang_code: Código del idioma
        
    Returns:
        Emoji de bandera
    """
    flags = {
        "es": "ES",
        "en": "EN"
    }
    return flags.get(lang_code, "🌐")


def get_salary_keywords() -> list:
    """
    Obtiene las palabras clave para identificar salarios según el idioma actual.
    Usa las traducciones definidas en historico.salary_search_keywords.
    
    Returns:
        Lista de palabras clave en minúsculas para búsqueda
        
    Examples:
        >>> get_salary_keywords()  # Con idioma español
        ['salario', 'nómina', 'nomina', 'paga extra']
    """
    keywords = t('historico.salary_search_keywords')
    
    # Si la traducción no existe o devuelve la clave, usar valores por defecto multiidioma
    if isinstance(keywords, str) or not isinstance(keywords, list):
        # Fallback: usar palabras clave de ambos idiomas
        return ["salario", "nómina", "nomina", "paga extra", "sueldo", "paga",
                "salary", "payroll", "wage", "pay", "bonus"]
    
    # Convertir todas a minúsculas para búsqueda case-insensitive
    return [kw.lower() for kw in keywords]
