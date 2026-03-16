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

# Forzar limpieza de cache (evita error "Failed to fetch dynamically imported module")
if "first_run" not in st.session_state:
    st.session_state.first_run = True
    st.cache_data.clear()
    st.cache_resource.clear()

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






# ============================================================================
# NAVEGACIÓN PRINCIPAL
# ============================================================================

def main():
    # Establecer el mes abierto por defecto al inicio (antes del primer render)
    if 'mes_global' not in st.session_state:
        from src.database import get_all_meses_fiscales_cerrados
        from src.business_logic import calcular_mes_fiscal
        from datetime import date, timedelta
        
        cerrados = get_all_meses_fiscales_cerrados()
        if cerrados:
            # Calcular el primer mes abierto (siguiente al último cerrado)
            ultimo_cerrado = sorted([c.mes_fiscal for c in cerrados])[-1]
            y, m = map(int, ultimo_cerrado.split('-'))
            dt_ultimo = date(y, m, 1)
            next_month_date = (dt_ultimo + timedelta(days=32)).replace(day=1)
            mes_abierto = next_month_date.strftime("%Y-%m")
            st.session_state['mes_global'] = mes_abierto
        else:
            # Si no hay cierres, usar el mes actual
            st.session_state['mes_global'] = calcular_mes_fiscal(date.today())
    
    # Flag para saber si es primera carga
    is_first_load = 'first_load_done' not in st.session_state
    
    # Loading screen simple (solo primera carga)
    if is_first_load:
        import time
        import base64
        
        loading_ph = st.empty()
        
        # Cargar logo
        try:
            with open("assets/logo.ico", "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode()
            logo_html = f'<img src="data:image/x-icon;base64,{logo_b64}" width="100" style="display: block; margin: 20px auto;">'
        except Exception:
            logo_html = ""
        
        loading_slogan = t('loading_slogan')
        
        with loading_ph.container():
            st.markdown(f"""
            <div style="
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: white; z-index: 999999;
                display: flex; flex-direction: column;
                align-items: center; justify-content: center;
            ">
                <h1 style="color: #333; font-family: sans-serif; margin-bottom: 0;">PersAcc</h1>
                {logo_html}
                <p style="color: #666; font-size: 1.2em; font-weight: 500;">{loading_slogan}</p>
                <div style="width: 300px; height: 4px; background: #f0f0f0; border-radius: 2px; overflow: hidden; margin-top: 20px;">
                    <div style="width: 100%; height: 100%; background: #4CAF50; animation: progress 2s linear forwards;"></div>
                </div>
                <style>@keyframes progress {{ from {{ width: 0%; }} to {{ width: 100%; }} }}</style>
            </div>
            """, unsafe_allow_html=True)
        
        time.sleep(3)
        loading_ph.empty()
        st.session_state['first_load_done'] = True
    
    # Verificar entradas pendientes en Notion (solo una vez por sesión)
    if not st.session_state.get('notion_startup_check_done', False):
        st.session_state['notion_startup_check_done'] = True
        
        # Recargar config para tener los valores más recientes
        fresh_config = load_config()
        notion_config = fresh_config.get('notion', {})
        if (notion_config.get('enabled') and 
            notion_config.get('check_on_startup', True) and
            notion_config.get('api_token') and
            notion_config.get('database_id')):
            from src.ui.notion_sync import check_and_show_notion_sync
            check_and_show_notion_sync()

    # ==========================================
    # NAVEGACIÓN CON LAZY LOADING (PARTE SUPERIOR)
    # ==========================================
    
    # Controlar si mostramos Cargar Datos (requiere LLM)
    from src.ai.llm_service import is_llm_enabled
    mostrar_carga = is_llm_enabled()
    
    # Definir opciones de navegación
    nav_options = [
        t('navigation.ledger'),        # 0: Ledger (default)
        t('navigation.cierre'),        # 1: Cierre de Mes
    ]
    if mostrar_carga:
        nav_options.append(t('navigation.cargar_datos'))
        
    nav_options.extend([
        t('navigation.historico'),
        t('navigation.proyecciones'),
        t('navigation.chat_search'),
        t('navigation.utilidades')
    ])
    
    # Índices estáticos para el mapeo posterior
    # Para mantener el código limpio de if/else anidados, comprobamos el contenido del array:
    
    # Inicializar sección activa
    if 'active_section' not in st.session_state:
        st.session_state.active_section = nav_options[0]  # Ledger por defecto
    
    # Navegación horizontal en la parte superior del contenido principal
    selected_section = st.radio(
        label="🧭 Navegación",
        options=nav_options,
        index=nav_options.index(st.session_state.active_section) if st.session_state.active_section in nav_options else 0,
        key="nav_radio",
        horizontal=True,
        label_visibility="collapsed"
    )
    
    # Actualizar estado
    st.session_state.active_section = selected_section
    
    st.markdown("---")
    
    # ==========================================
    # RENDERIZADO DE LA APP
    # ==========================================
    
    # Sidebar Quick Add (lazy import)
    from src.ui.sidebar import render_sidebar
    render_sidebar()
    
    # ==========================================
    # LAZY LOADING: Solo importa y renderiza la sección activa
    # ==========================================
    
    if selected_section == nav_options[0]:  # Ledger
        from src.ui.analisis import render_analisis
        render_analisis()
    
    elif selected_section == nav_options[1]:  # Cierre
        from src.ui.cierre import render_cierre
        render_cierre()
    
    elif selected_section == t('navigation.cargar_datos'):  # Cargar Datos
        from src.ui.cargar_datos import render_cargar_datos
        render_cargar_datos()
    
    elif selected_section == t('navigation.historico'):  # Histórico
        from src.ui.historico import render_historico
        render_historico()
    
    elif selected_section == t('navigation.proyecciones'):  # Proyecciones
        from src.ui.proyecciones import render_proyecciones
        render_proyecciones()
    
    elif selected_section == t('navigation.chat_search'):  # Asistente IA
        from src.ui.search_assistant_new import render_chat_search
        render_chat_search()
    
    elif selected_section == t('navigation.utilidades'):  # Utilidades
        from src.ui.utilidades import render_utilidades
        render_utilidades()


if __name__ == "__main__":
    main()
