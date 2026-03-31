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
        color: {_DARK_TEXT} !important;
    }}

    /* Header de Streamlit */
    [data-testid="stHeader"] {{
        background-color: {_DARK_BG} !important;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div {{
        background-color: {_DARK_SECONDARY} !important;
        color: {_DARK_TEXT} !important;
    }}

    /* Texto general — todos los nodos de texto */
    .stApp p, .stApp span, .stApp label,
    .stApp div, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp li, .stApp td, .stApp th,
    [data-testid="stText"],
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── TEXT INPUTS ───────────────────────────────────── */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTextAreaInput"] textarea,
    textarea {{
        background-color: {_DARK_SECONDARY} !important;
        color: {_DARK_TEXT} !important;
        border-color: {_DARK_BORDER} !important;
    }}

    /* ── SELECTBOX ─────────────────────────────────────── */
    /* Contenedor del select */
    [data-testid="stSelectbox"] > div > div,
    [data-baseweb="select"] > div,
    [data-baseweb="select"] {{
        background-color: {_DARK_SECONDARY} !important;
        color: {_DARK_TEXT} !important;
        border-color: {_DARK_BORDER} !important;
    }}
    /* Texto dentro del select (valor seleccionado) */
    [data-baseweb="select"] span,
    [data-baseweb="select"] div,
    [data-baseweb="select"] [data-testid="stMarkdownContainer"] {{
        color: {_DARK_TEXT} !important;
        background-color: transparent !important;
    }}
    /* Input interno del select */
    [data-baseweb="select"] input {{
        color: {_DARK_TEXT} !important;
        background-color: transparent !important;
        caret-color: {_DARK_TEXT} !important;
    }}
    /* Placeholder */
    [data-baseweb="select"] [placeholder] {{
        color: #888aa8 !important;
    }}

    /* ── MULTISELECT ───────────────────────────────────── */
    [data-testid="stMultiSelect"] > div > div,
    [data-baseweb="multi-select"] {{
        background-color: {_DARK_SECONDARY} !important;
        color: {_DARK_TEXT} !important;
        border-color: {_DARK_BORDER} !important;
    }}
    [data-baseweb="tag"] {{
        background-color: #2a2a40 !important;
        color: {_DARK_TEXT} !important;
    }}

    /* ── DROPDOWN / POPOVER (lista de opciones) ────────── */
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"],
    [data-baseweb="list"],
    ul[role="listbox"],
    li[role="option"] {{
        background-color: #1e1e32 !important;
        color: {_DARK_TEXT} !important;
    }}
    li[role="option"]:hover {{
        background-color: #2a2a44 !important;
    }}
    li[role="option"][aria-selected="true"] {{
        background-color: #2a2a44 !important;
        color: {_DARK_TEXT} !important;
    }}
    /* Texto dentro de opciones del dropdown */
    [data-baseweb="menu"] span,
    [data-baseweb="menu"] div,
    [data-baseweb="list"] span,
    [data-baseweb="list"] div {{
        color: {_DARK_TEXT} !important;
        background-color: transparent !important;
    }}

    /* ── RADIO BUTTONS ─────────────────────────────────── */
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] span,
    [data-testid="stRadio"] p {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── CHECKBOXES ────────────────────────────────────── */
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] span,
    [data-testid="stCheckbox"] p {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── TOGGLES ───────────────────────────────────────── */
    [data-testid="stToggle"] label,
    [data-testid="stToggle"] span,
    [data-testid="stToggle"] p {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── SLIDER ────────────────────────────────────────── */
    [data-testid="stSlider"] label,
    [data-testid="stSlider"] span,
    [data-testid="stSlider"] p {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── TABS ──────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: #a0a0b8 !important;
        background-color: transparent !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        color: {_DARK_TEXT} !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background-color: {_DARK_BG} !important;
    }}

    /* ── EXPANDERS ─────────────────────────────────────── */
    [data-testid="stExpander"] {{
        background-color: {_DARK_SECONDARY} !important;
        border-color: {_DARK_BORDER} !important;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary p {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── CONTAINERS CON BORDE ──────────────────────────── */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {_DARK_SECONDARY} !important;
        border-color: {_DARK_BORDER} !important;
    }}

    /* ── MÉTRICA ───────────────────────────────────────── */
    [data-testid="stMetric"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}
    [data-testid="stMetricLabel"] p,
    [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"] {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── DATAFRAMES / TABLAS ───────────────────────────── */
    [data-testid="stDataFrame"] iframe,
    [data-testid="data-grid-canvas"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}
    [data-testid="stTable"] table {{
        background-color: {_DARK_SECONDARY} !important;
        color: {_DARK_TEXT} !important;
    }}
    [data-testid="stTable"] th,
    [data-testid="stTable"] td {{
        color: {_DARK_TEXT} !important;
        border-color: {_DARK_BORDER} !important;
    }}

    /* ── ALERTS / INFO BOXES ───────────────────────────── */
    [data-testid="stAlert"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] div {{
        color: {_DARK_TEXT} !important;
    }}

    /* ── TOOLTIPS ──────────────────────────────────────── */
    [data-testid="stTooltipContent"],
    [class*="tooltip"] > div {{
        background-color: #2a2a44 !important;
        color: {_DARK_TEXT} !important;
    }}

    /* ── FORM / SUBMIT BUTTON ──────────────────────────── */
    [data-testid="stForm"] {{
        background-color: {_DARK_SECONDARY} !important;
        border-color: {_DARK_BORDER} !important;
    }}

    /* ── FONDO TABS SECUNDARIOS ────────────────────────── */
    [data-testid="stVerticalBlock"] > [data-testid="element-container"] > div[class*="stMetric"] {{
        background-color: {_DARK_SECONDARY} !important;
    }}

    /* ── DIVIDER ───────────────────────────────────────── */
    hr {{
        border-color: {_DARK_BORDER} !important;
    }}
    </style>
    """ if dark_mode else ""

    st_instance.markdown(css, unsafe_allow_html=True)
    if dark_css:
        st_instance.markdown(dark_css, unsafe_allow_html=True)
