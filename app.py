"""
PersAcc - Sistema de Finanzas Personales
Interfaz Streamlit

Ejecutar con: streamlit run app.py
"""
import streamlit as st
from pathlib import Path
import sys

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.ui.styles import apply_custom_css
from src.i18n import t, set_language, get_language
from src.config import load_config

# Cargar idioma desde configuración al inicio (antes de set_page_config)
config = load_config()
preferred_lang = config.get('language', 'es')
current_lang = get_language()
if preferred_lang != current_lang:
    set_language(preferred_lang)

# ============================================================================
# CONFIGURACIÓN DE LA PÁGINA
# ============================================================================

st.set_page_config(
    page_title=t('page_title'),
    page_icon="assets/logo.ico",
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
from src.ui.proyecciones import render_proyecciones
from src.ui.search_assistant_new import render_chat_search
from src.ui.utilidades import render_utilidades
from src.ui.manual import render_manual




# ============================================================================
# NAVEGACIÓN PRINCIPAL
# ============================================================================

def main():
    # Placeholder para pantalla de carga (Overlay)
    loading_ph = st.empty()
    should_show_loader = 'first_load_done' not in st.session_state
    
    start_time = 0
    
    if should_show_loader:
        import base64
        import time
        
        start_time = time.time()
        
        # Cargar logo
        try:
            with open("assets/logo.ico", "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode()
            logo_html = f'<img src="data:image/x-icon;base64,{logo_b64}" width="100" style="display: block; margin: 20px auto;">'
        except Exception:
            logo_html = ""

        # Obtener tips de carga directamente del JSON
        import random
        from src.i18n import get_language, load_translations
        
        lang = get_language()
        translations = load_translations(lang)
        loading_tips = translations.get('loading_tips', ["Loading..."])
        random_tip = random.choice(loading_tips) if isinstance(loading_tips, list) else str(loading_tips)
        
        with loading_ph.container():
            st.markdown(f"""
            <div id="loading-overlay" style="
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: white; z-index: 999999;
                display: flex; flex-direction: column;
                align-items: center; justify-content: center;
            ">
                <h1 style="color: #333; font-family: sans-serif; margin-bottom: 0; text-align: center; margin-left: 20px;">PersAcc</h1>
                {logo_html}
                <p style="color: #666; font-size: 1.1em; text-align: center; max-width: 500px; padding: 0 20px;">{random_tip}</p>
                <div style="
                    width: 300px; height: 4px; background: #f0f0f0;
                    border-radius: 2px; overflow: hidden; margin-top: 20px;
                ">
                    <div style="
                        width: 100%; height: 100%; background: #4CAF50;
                        animation: progress 3s linear forwards;
                    "></div>
                </div>
                <style>
                @keyframes progress {{ from {{ width: 0%; }} to {{ width: 100%; }} }}
                </style>
            </div>
            """, unsafe_allow_html=True)
            
            # Brief pause to ensure browser renders the overlay
            time.sleep(0.1)

    # ==========================================
    # RENDERIZADO DE LA APP (BACKGROUND)
    # ==========================================
    
    # Sidebar siempre visible con Quick Add
    render_sidebar()
    
    # Track active tab for lazy loading
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 0
    
    # Navegación por tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        t('navigation.ledger'), 
        t('navigation.cierre'), 
        t('navigation.historico'),
        t('navigation.proyecciones'),
        t('navigation.chat_search'),
        t('navigation.utilidades')
    ])
    
    with tab1:
        render_analisis()
    
    with tab2:
        render_cierre()
    
    with tab3:
        render_historico()
    
    with tab4:
        render_proyecciones()
    
    with tab5:
        render_chat_search()
    
    with tab6:
        render_utilidades()
        
    # ==========================================
    # FINALIZACIÓN DE CARGA (immediate)
    # ==========================================
    if should_show_loader:
        # Remove overlay immediately when rendering is done
        loading_ph.empty()
        st.session_state['first_load_done'] = True


if __name__ == "__main__":
    main()
