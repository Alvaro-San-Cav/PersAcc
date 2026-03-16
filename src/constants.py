"""
Constantes del sistema PersAcc.
Centraliza valores mágicos y configuraciones para facilitar mantenimiento.
"""

from stop_words import get_stop_words

# ============================================================================
# CATEGORÍAS ESPECIALES
# ============================================================================

# Nombres de categorías con significado especial en el sistema
CATEGORIA_SALARIO = "Salario"
CATEGORIA_INVERSION_SALARIO = "Inversion/Ahorro retención de salario"
CATEGORIA_INVERSION_REMANENTE = "Inversion/Ahorro retención de remanente"
CATEGORIA_INVERSION_EXTRA = "Inversion/Ahorro extra"

# ============================================================================
# PALABRAS CLAVE DE DETECCIÓN
# ============================================================================

# Stop words para análisis de texto en español (librería con fallback local)
try:
    STOPWORDS_ES = set(get_stop_words("es"))
except Exception:
    STOPWORDS_ES = {
        "de", "la", "el", "en", "y", "a", "los", "del", "las", "un", "una",
        "por", "que", "para", "con", "sin", "sobre", "tras", "entre", "al"
    }

# ============================================================================
# COLORES UI - TEMA PRINCIPAL
# ============================================================================

PRIMARY_COLOR = "#e94560"

# ============================================================================
# COLORES DE RELEVANCIA (Calidad del Gasto)
# ============================================================================

# Colores para cada tipo de relevancia
COLOR_RELEVANCIA_NE = "#00c853"    # Necesario - Verde
COLOR_RELEVANCIA_LI = "#448aff"    # Me gusta - Azul
COLOR_RELEVANCIA_SUP = "#ffab00"   # Superfluo - Amarillo
COLOR_RELEVANCIA_TON = "#ff5252"   # Tontería - Rojo

# ============================================================================
# CONFIGURACIÓN UI
# ============================================================================

# Límites y configuraciones de visualización
MIN_WORD_LENGTH = 3  # Longitud mínima de palabra para análisis
DEFAULT_WORD_LIMIT = 20  # Número de palabras a mostrar en análisis

# Alturas de elementos UI (en píxeles)
DATAFRAME_HEIGHT_MEDIUM = 400

# ============================================================================
# CONFIGURACIÓN LLM
# ============================================================================

# Timeouts para llamadas a Ollama (en segundos)
# - QUICK: Para resúmenes de una línea y verificaciones de estado
# - LONG: Para análisis financieros profundos que requieren más procesamiento
LLM_TIMEOUT_QUICK = 15     # Resúmenes rápidos: max 15s
LLM_TIMEOUT_LONG = 180     # Análisis completos: max 3 minutos

# Límites de texto para LLM
# - MAX_RESPONSE_LENGTH: Evita respuestas demasiado largas en UI
# - MAX_MOVEMENTS_DISPLAY: Limita datos enviados al LLM para eficiencia
LLM_MAX_RESPONSE_LENGTH = 200  # Caracteres máximos en respuesta
LLM_MAX_MOVEMENTS_DISPLAY = 30  # Máximo movimientos a incluir en prompt
