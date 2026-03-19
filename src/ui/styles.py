"""
Módulo de estilos CSS centralizados para PersAcc.
Define todos los estilos personalizados de la aplicación.
"""
from src.constants import PRIMARY_COLOR, COLOR_RELEVANCIA_NE, COLOR_RELEVANCIA_LI, COLOR_RELEVANCIA_SUP, COLOR_RELEVANCIA_TON

# Colores del tema oscuro (override sobre base light de Streamlit)
_DARK_BG        = "#0f0f1a"
_DARK_SECONDARY = "#1a1a2e"
_DARK_TEXT      = "#e0e0e0"
_DARK_BORDER    = "rgba(255,255,255,0.08)"


def apply_custom_css(st_instance, dark_mode: bool = False):
    """
    Aplica CSS personalizado a la aplicación Streamlit.

    Args:
        st_instance: Instancia de Streamlit (normalmente 'st')
        dark_mode:   Si True, inyecta overrides de tema oscuro sobre el base light.
    """
    css = f"""
    <style>
    /* ── Fuente premium ─────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif !important;
    }}

    /* ── Header principal ────────────────────────────────────────────── */
    .main-header {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #16162a 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(255,255,255,0.07);
    }}

    .main-header h1 {{
        color: white !important;
        margin: 0;
        font-size: 1.9rem;
        font-weight: 700;
        letter-spacing: -0.3px;
    }}

    /* ── Tarjetas KPI ────────────────────────────────────────────────── */
    .kpi-card {{
        background: linear-gradient(145deg, #24243e 0%, #1a1a2e 100%);
        padding: 1.2rem 1rem;
        border-radius: 10px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.08);
        border-left: 3px solid {PRIMARY_COLOR};
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        flex: 1;
    }}

    .kpi-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(233, 69, 96, 0.18);
    }}

    .kpi-label {{
        font-size: 0.78rem;
        color: #a0a0b8;
        margin-bottom: 0.45rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 500;
    }}

    .kpi-value {{
        font-size: 1.5rem;
        font-weight: 700;
        color: white;
        letter-spacing: -0.5px;
    }}

    /* Ensure markdown container stretches for KPI cards */
    div[data-testid="stVerticalBlock"] > div.element-container:has(.kpi-card) {{
        height: 100%;
        display: flex;
        flex-direction: column;
    }}
    div[data-testid="stMarkdownContainer"]:has(.kpi-card),
    div[data-testid="stMarkdown"]:has(.kpi-card),
    div.st-emotion-cache-6c7yup:has(.kpi-card) {{
        height: 100%;
        display: flex;
        flex-direction: column;
        flex: 1;
    }}

    /* ── Tabs ────────────────────────────────────────────────────────── */
    button[data-baseweb="tab"] {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1rem !important;
        transition: color 0.15s ease;
    }}

    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {PRIMARY_COLOR} !important;
        border-bottom: 2px solid {PRIMARY_COLOR} !important;
    }}

    /* ── Botones primarios ───────────────────────────────────────────── */
    div[data-testid="stButton"] > button[kind="primary"] {{
        border-radius: 8px !important;
        font-weight: 600 !important;
        letter-spacing: 0.2px;
        transition: opacity 0.15s ease, box-shadow 0.15s ease !important;
    }}

    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        opacity: 0.88;
        box-shadow: 0 4px 14px rgba(233, 69, 96, 0.35) !important;
    }}

    /* ── Sidebar ─────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {{
        border-right: 1px solid rgba(255,255,255,0.06);
    }}

    section[data-testid="stSidebar"] .streamlit-expanderContent button {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 8px !important;
        min-height: 42px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }}
    section[data-testid="stSidebar"] .streamlit-expanderContent button p {{
        margin: 0 !important;
        font-size: 16px !important;
    }}

    /* ── Colores de relevancia ───────────────────────────────────────── */
    .relevancia-ne  {{ color: {COLOR_RELEVANCIA_NE}; }}
    .relevancia-li  {{ color: {COLOR_RELEVANCIA_LI}; }}
    .relevancia-sup {{ color: {COLOR_RELEVANCIA_SUP}; }}
    .relevancia-ton {{ color: {COLOR_RELEVANCIA_TON}; }}
    </style>
    """

    # ── Dark mode override (inyectado encima del CSS base) ────────────────────
    dark_css = f"""
    <style>
    /* Dark mode — override del tema light de Streamlit */

    /* Fondo principal */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {{
        background-color: {_DARK_BG} !important;
    }}

    /* Header de Streamlit */
    [data-testid="stHeader"] {{
        background-color: {_DARK_BG} !important;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div {{
        background-color: {_DARK_SECONDARY} !important;
    }}

    /* Fondo secundario (contenedores, expanders, tabs) */
    [data-testid="stVerticalBlock"] > [data-testid="element-container"] > div[class*="stMetric"],
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}

    /* Texto general */
    .stApp, .stApp p, .stApp span, .stApp label,
    .stApp div, .stApp h1, .stApp h2, .stApp h3,
    [data-testid="stText"] {{
        color: {_DARK_TEXT} !important;
    }}

    /* Inputs */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] {{
        background-color: {_DARK_SECONDARY} !important;
        color: {_DARK_TEXT} !important;
        border-color: {_DARK_BORDER} !important;
    }}

    /* Selectbox dropdown */
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"] {{
        background-color: {_DARK_SECONDARY} !important;
        color: {_DARK_TEXT} !important;
    }}

    /* Dataframes y tablas */
    [data-testid="stDataFrame"] iframe,
    [data-testid="data-grid-canvas"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}

    /* Containers con borde */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {_DARK_SECONDARY} !important;
        border-color: {_DARK_BORDER} !important;
    }}

    /* Expanders */
    [data-testid="stExpander"] {{
        background-color: {_DARK_SECONDARY} !important;
        border-color: {_DARK_BORDER} !important;
    }}

    /* Métrica */
    [data-testid="stMetric"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}
    [data-testid="stMetricLabel"] p,
    [data-testid="stMetricValue"] {{
        color: {_DARK_TEXT} !important;
    }}
    </style>
    """ if dark_mode else ""

    st_instance.markdown(css, unsafe_allow_html=True)
    if dark_css:
        st_instance.markdown(dark_css, unsafe_allow_html=True)
