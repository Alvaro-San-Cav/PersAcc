"""
Módulo de estilos CSS centralizados para PersAcc.
Define todos los estilos personalizados de la aplicación.
"""
import streamlit as st
from src.constants import (
    PRIMARY_COLOR, SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR, INFO_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, BG_LIGHT, BG_TRANSPARENT,
    COLOR_RELEVANCIA_NE, COLOR_RELEVANCIA_LI, COLOR_RELEVANCIA_SUP, COLOR_RELEVANCIA_TON
)


def apply_custom_css(st_instance):
    """
    Aplica CSS personalizado a la aplicación Streamlit.
    
    Args:
        st_instance: Instancia de Streamlit (normalmente 'st')
    """
    css = f"""
    <style>
    /* Header principal */
    .main-header {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #1e1e2e 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    
    .main-header h1 {{
        color: white !important;
        margin: 0;
        font-size: 2rem;
    }}
    
    /* Tarjetas KPI */
    .kpi-card {{
        background: linear-gradient(135deg, #2d2d44 0%, #1e1e2e 100%);
        padding: 1.2rem;
        border-radius: 8px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
        transition: transform 0.2s;
    }}
    
    .kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }}
    
    .kpi-label {{
        font-size: 0.85rem;
        color: #e0e0e0;
        margin-bottom: 0.5rem;
    }}
    
    .kpi-value {{
        font-size: 1.5rem;
        font-weight: bold;
        color: white;
    }}
    
    /* Colores de relevancia */
    .relevancia-ne {{
        color: {COLOR_RELEVANCIA_NE};
    }}
    
    .relevancia-li {{
        color: {COLOR_RELEVANCIA_LI};
    }}
    
    .relevancia-sup {{
        color: {COLOR_RELEVANCIA_SUP};
    }}
    
    .relevancia-ton {{
        color: {COLOR_RELEVANCIA_TON};
    }}
    </style>
    """
    
    st_instance.markdown(css, unsafe_allow_html=True)
