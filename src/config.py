"""
Módulo de configuración persistente.
Lee y escribe configuraciones desde/hacia data/config.json.
"""
import json
from pathlib import Path
from typing import Any

# Ruta del archivo de configuración
CONFIG_PATH = Path(__file__).parent.parent / "data" / "config.json"

# Configuración por defecto (si no existe el archivo)
DEFAULT_CONFIG = {
    "language": "es",  # "es" o "en"
    "currency": "EUR",  # "EUR", "USD", "GBP", etc.
    "enable_relevance": True,  # Activar/desactivar análisis de relevancia
    "enable_retentions": True, # Activar/desactivar retenciones de inversión automáticas
    "enable_consequences": False, # Activar/desactivar cuenta de consecuencias
    "consequences_rules": [], # Lista de reglas [{id, name, active, filters, action}]
    "retenciones": {
        "pct_remanente_default": 0,
        "pct_salario_default": 20
    },
    "cierre": {
        "metodo_saldo": "antes_salario"  # "antes_salario" o "despues_salario"
    },
    "conceptos_default": {
        "salario": "Nómina mensual",
        "alcohol": "Cerveza/Copas"
    },
    "importes_default": {},  # category_key -> default amount (float)
    "relevancias_default": {}  # category_key -> default relevance code (NE, LI, SUP, TON)
}


def load_config() -> dict:
    """
    Carga la configuración desde el archivo JSON.
    Si el archivo no existe, crea uno con valores por defecto.
    """
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        # Merge con defaults para asegurar que existen todas las claves
        merged = DEFAULT_CONFIG.copy()
        for key, value in config.items():
            if isinstance(value, dict) and key in merged:
                merged[key].update(value)
            else:
                merged[key] = value
        return merged
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Guarda la configuración en el archivo JSON."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_config_value(key_path: str, default: Any = None) -> Any:
    """
    Obtiene un valor de configuración usando notación de puntos.
    Ejemplo: get_config_value('retenciones.pct_salario_default')
    """
    config = load_config()
    keys = key_path.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def set_config_value(key_path: str, value: Any) -> None:
    """
    Establece un valor de configuración usando notación de puntos.
    Ejemplo: set_config_value('retenciones.pct_salario_default', 25)
    """
    config = load_config()
    keys = key_path.split('.')
    current = config
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    save_config(config)


# Mapeo de códigos de divisa a símbolos
CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "CHF": "₣",
    "JPY": "¥",
    "CNY": "¥",
    "MXN": "$",
    "ARS": "$",
    "COP": "$",
    "BRL": "R$"
}


def get_currency_symbol() -> str:
    """Obtiene el símbolo de la divisa configurada."""
    config = load_config()
    currency_code = config.get('currency', 'EUR')
    return CURRENCY_SYMBOLS.get(currency_code, currency_code)


def format_currency(amount: float, decimals: int = 2) -> str:
    """
    Formatea un importe con el símbolo de divisa configurado.
    Ejemplo: format_currency(1234.56) -> "1,234.56 €"
    """
    symbol = get_currency_symbol()
    if decimals == 0:
        formatted = f"{amount:,.0f}"
    else:
        formatted = f"{amount:,.{decimals}f}"
    return f"{formatted} {symbol}"
