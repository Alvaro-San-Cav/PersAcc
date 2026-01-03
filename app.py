"""
PersAcc - Sistema de Finanzas Personales
Interfaz Streamlit

Ejecutar con: streamlit run app.py
"""
import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry, RELEVANCIA_DESCRIPTIONS
from src.database import (
    get_all_categorias, get_categorias_by_tipo, insert_ledger_entry,
    get_ledger_by_month, get_all_ledger_entries, get_latest_snapshot,
    update_categoria, get_category_counts, delete_categoria, 
    deactivate_categoria, insert_categoria, DEFAULT_DB_PATH,
    delete_ledger_entry, update_ledger_entry
)
from src.business_logic import (
    calcular_fecha_contable, calcular_mes_fiscal,
    calcular_kpis, calcular_kpis_relevancia, ejecutar_cierre_mes,
    calcular_kpis_anuales, get_word_counts, get_top_entries,
    calculate_curious_metrics
)
from src.ui.styles import apply_custom_css
from src.constants import RELEVANCIA_COLORS

# ============================================================================
# CONFIGURACIÓN DE LA PÁGINA
# ============================================================================

st.set_page_config(
    page_title="PersAcc - Finanzas Personales",
    page_icon="logo.ico",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aplicar CSS personalizado
apply_custom_css(st)

# Hack para deshabilitar traducción de Google
st.markdown(
    """
    <meta name="google" content="notranslate">
    <style>
    .stApp {
        /* Prevent font shifting */
        -webkit-font-smoothing: antialiased;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# Importar componentes UI  
from src.ui.sidebar import render_sidebar
from src.ui.analisis import render_analisis
from src.ui.cierre import render_cierre
from src.ui.historico import render_historico
from src.ui.utilidades import render_utilidades
from src.ui.manual import render_manual
from src.i18n import t, set_language, get_language
from src.config import load_config

# Cargar idioma desde configuración al inicio
config = load_config()
preferred_lang = config.get('language', 'es')
current_lang = get_language()
if preferred_lang != current_lang:
    set_language(preferred_lang)




# ============================================================================
# NAVEGACIÓN PRINCIPAL
# ============================================================================

def main():
    # Sidebar siempre visible con Quick Add
    render_sidebar()
    
    # Navegación por tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        t('navigation.ledger'), 
        t('navigation.cierre'), 
        t('navigation.historico'),
        t('navigation.utilidades')
    ])
    
    with tab1:
        render_analisis()
    
    with tab2:
        render_cierre()
    
    with tab3:
        render_historico()
    
    with tab4:
        render_utilidades()


if __name__ == "__main__":
    main()
