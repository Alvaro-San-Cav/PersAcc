"""
Constantes del sistema PersAcc.
Centraliza valores mágicos y configuraciones para facilitar mantenimiento.
"""

# ============================================================================
# REGLAS DE NEGOCIO
# ============================================================================


# Porcentajes de retención por defecto
DEFAULT_PCT_RETENCION_REMANENTE = 0.20
DEFAULT_PCT_RETENCION_SALARIO = 0.30  # 30%

# ============================================================================
# CATEGORÍAS ESPECIALES
# ============================================================================

# Nombres de categorías con significado especial en el sistema
CATEGORIA_SALARIO = "Salario"
CATEGORIA_INVERSION_SALARIO = "Inversion retención de salario"
CATEGORIA_INVERSION_REMANENTE = "Inversion retención de remanente"
CATEGORIA_INVERSION_EXTRA = "Inversion extra"

# ============================================================================
# PALABRAS CLAVE DE DETECCIÓN
# ============================================================================

# Stop words para análisis de texto en español
STOPWORDS_ES = {
    "de", "la", "el", "en", "y", "a", "los", "del", "las", "un", "una",
    "por", "que", "para", "con", "sin", "sobre", "tras", "entre"
}

# ============================================================================
# COLORES UI - TEMA PRINCIPAL
# ============================================================================

# Colores primarios
PRIMARY_COLOR = "#e94560"
PRIMARY_COLOR_LIGHT = "#ff6b6b"
SUCCESS_COLOR = "#00c853"
SUCCESS_COLOR_LIGHT = "#00e676"
WARNING_COLOR = "#ffab00"
ERROR_COLOR = "#ff5252"
INFO_COLOR = "#448aff"

# Colores de texto
TEXT_PRIMARY = "#1f1f1f"
TEXT_SECONDARY = "#666666"
TEXT_WHITE = "white"

# Colores de fondo
BG_LIGHT = "#f8f9fa"
BG_TRANSPARENT = "rgba(0,0,0,0)"

# ============================================================================
# COLORES DE RELEVANCIA (Calidad del Gasto)
# ============================================================================

# Colores para cada tipo de relevancia
COLOR_RELEVANCIA_NE = "#00c853"    # Necesario - Verde
COLOR_RELEVANCIA_LI = "#448aff"    # Me gusta - Azul
COLOR_RELEVANCIA_SUP = "#ffab00"   # Superfluo - Amarillo
COLOR_RELEVANCIA_TON = "#ff5252"   # Tontería - Rojo

# Colores con transparencia para fondos
COLOR_RELEVANCIA_NE_BG = "rgba(0, 200, 100, 0.15)"
COLOR_RELEVANCIA_LI_BG = "rgba(100, 150, 255, 0.15)"
COLOR_RELEVANCIA_SUP_BG = "rgba(255, 200, 0, 0.15)"
COLOR_RELEVANCIA_TON_BG = "rgba(255, 80, 80, 0.15)"

# Mapeo de código a color
RELEVANCIA_COLORS = {
    "NE": COLOR_RELEVANCIA_NE,
    "LI": COLOR_RELEVANCIA_LI,
    "SUP": COLOR_RELEVANCIA_SUP,
    "TON": COLOR_RELEVANCIA_TON
}

RELEVANCIA_BG_COLORS = {
    "NE": COLOR_RELEVANCIA_NE_BG,
    "LI": COLOR_RELEVANCIA_LI_BG,
    "SUP": COLOR_RELEVANCIA_SUP_BG,
    "TON": COLOR_RELEVANCIA_TON_BG
}

# ============================================================================
# CONFIGURACIÓN UI
# ============================================================================

# Límites y configuraciones de visualización
MIN_WORD_LENGTH = 3  # Longitud mínima de palabra para análisis
DEFAULT_WORD_LIMIT = 20  # Número de palabras a mostrar en análisis
DEFAULT_TOP_ENTRIES = 10  # Número de entradas top a mostrar

# Alturas de elementos UI (en píxeles)
DATAFRAME_HEIGHT_SMALL = 300
DATAFRAME_HEIGHT_MEDIUM = 400
DATAFRAME_HEIGHT_LARGE = 600

# ============================================================================
# CONFIGURACIÓN LLM
# ============================================================================

# Timeouts para llamadas a Ollama (en segundos)
# - QUICK: Para resúmenes de una línea y verificaciones de estado
# - STANDARD: Para búsquedas de chat y extracción de parámetros
# - LONG: Para análisis financieros profundos que requieren más procesamiento
LLM_TIMEOUT_QUICK = 15     # Resúmenes rápidos: max 15s
LLM_TIMEOUT_STANDARD = 30  # Búsquedas/chat: max 30s
LLM_TIMEOUT_LONG = 180     # Análisis completos: max 3 minutos

# Límites de texto para LLM
# - MAX_RESPONSE_LENGTH: Evita respuestas demasiado largas en UI
# - MAX_MOVEMENTS_DISPLAY: Limita datos enviados al LLM para eficiencia
LLM_MAX_RESPONSE_LENGTH = 200  # Caracteres máximos en respuesta
LLM_MAX_MOVEMENTS_DISPLAY = 30  # Máximo movimientos a incluir en prompt

# ============================================================================
# FORMATOS
# ============================================================================

# Formato de mes fiscal
MES_FISCAL_FORMAT = "%Y-%m"

# Formato de fecha ISO
DATE_ISO_FORMAT = "%Y-%m-%d"
