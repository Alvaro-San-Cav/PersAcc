"""
Página de Histórico Anual - PersAcc
Renderiza la interfaz de historico.
"""
import streamlit as st
from datetime import date, datetime
from collections import defaultdict
import requests
import plotly.graph_objects as go

from src.models import TipoMovimiento
from src.database import (
    get_all_categorias, get_ledger_by_month, is_mes_cerrado,
    get_ledger_by_year, get_available_years,
    get_ai_analysis, save_ai_analysis,
    get_period_notes, save_period_notes
)
from src.business_logic import (
    calcular_kpis, calcular_kpis_anuales, get_word_counts, 
    get_top_entries, calculate_curious_metrics, es_entrada_salario
)
from src.config import format_currency, get_currency_symbol, load_config
from src.i18n import t
from src.llm_service import (
    is_llm_enabled, get_llm_config, analyze_financial_period
)


def _get_formatted_month_label(mes_str):
    """Devuelve la etiqueta formateada 'YYYY-MM - Mes' para un mes dado."""
    try:
        mes_date = datetime.strptime(mes_str, "%Y-%m")
        mes_nombre = mes_date.strftime("%B").capitalize()
        return f"{mes_str} - {mes_nombre}"
    except Exception:
        return mes_str

def _reset_to_year_view():
    """Callback para volver a la vista anual. Se ejecuta ANTES del rerun."""
    target_val = t('historico.full_year')
    st.session_state["hist_mes_sel"] = target_val
    st.session_state["hist_mes_sel_widget"] = target_val

def _handle_chart_selection():
    """Procesa la selección del gráfico al inicio del script, antes de renderizar widgets."""
    if "year_evolution_chart" in st.session_state:
        selection = st.session_state["year_evolution_chart"]
        if selection and selection.get("selection") and selection["selection"].get("points"):
            point = selection["selection"]["points"][0]
            if "x" in point:
                clicked_month = point["x"]
                new_val = _get_formatted_month_label(clicked_month)
                
                # Actualizar si es diferente (evitar loops si ya está seleccionado)
                if st.session_state.get("hist_mes_sel") != new_val:
                    st.session_state["hist_mes_sel"] = new_val
                    st.session_state["hist_mes_sel_widget"] = new_val

def render_historico():
    """Renderiza el dashboard de análisis anual con estadísticas detalladas."""
    # 0. Procesar eventos de navegación (Clicks en gráficos) ANTES de renderizar nada
    _handle_chart_selection()
    
    st.markdown(f'<div class="main-header"><h1>{t("historico.title")}</h1></div>', unsafe_allow_html=True)
    
    # Obtener años disponibles (incluir año actual)
    today = date.today()
    anios_con_datos = get_available_years()
    if today.year not in anios_con_datos:
        anios_con_datos.insert(0, today.year)
    anios_con_datos = sorted(anios_con_datos, reverse=True)
    
    if not anios_con_datos:
        st.info(t('historico.no_data'))
        return
    
    # Selectores separados: Año y Mes
    col1, col2 = st.columns(2)
    
    with col1:
        anio_sel = st.selectbox(
            t('historico.year_selector'),
            options=anios_con_datos,
            index=0,
            key="hist_anio_sel"
        )
    
    # Obtener meses con datos para el año seleccionado
    entries_anio = get_ledger_by_year(anio_sel)
    meses_con_datos = sorted(set(e.mes_fiscal for e in entries_anio))
    
    # Crear opciones de mes con nombres
    opciones_mes = [t('historico.full_year')]  # Primera opción: año completo
    meses_nombres = {}
    for mes in meses_con_datos:
        opcion = _get_formatted_month_label(mes)
        opciones_mes.append(opcion)
        meses_nombres[opcion] = mes
    
    with col2:
        # Shadow Key Pattern para permitir actualizaciones programáticas
        # Inicializar estado si no existe
        if "hist_mes_sel" not in st.session_state:
            st.session_state["hist_mes_sel"] = opciones_mes[0] # Full year
        
        # Sincronizar widget -> state usando callback en on_change
        
        # Calcular índice para mantener sincronía
        try:
            current_idx = opciones_mes.index(st.session_state["hist_mes_sel"])
        except ValueError:
            current_idx = 0
            st.session_state["hist_mes_sel"] = opciones_mes[0]

        mes_opcion = st.selectbox(
            t('historico.period_selector'),
            options=opciones_mes,
            index=current_idx,
            key="hist_mes_sel_widget",
            on_change=_update_hist_mes_sel
        )
        
        # No actualizamos manualmente st.session_state["hist_mes_sel"] aquí
        # porque ya lo maneja el callback o la lógica de inicialización
    
    # Determinar si es vista de mes o año
    if mes_opcion == t('historico.full_year'):
        mes_sel = None
    else:
        mes_sel = meses_nombres.get(mes_opcion)
    
    st.markdown("---")
    
    # Obtener datos según selección
    with st.spinner(t('historico.loading_data')):
        if mes_sel:
            # Vista de mes específico
            entries = get_ledger_by_month(mes_sel)
            render_month_view(entries, mes_sel, anio_sel)
        else:
            # Vista de año completo
            entries = get_ledger_by_year(anio_sel)
            render_year_view(entries, anio_sel)


def _update_hist_mes_sel():
    """Callback para actualizar el estado del mes seleccionado desde el widget"""
    st.session_state["hist_mes_sel"] = st.session_state["hist_mes_sel_widget"]


def _render_period_notes(period_type: str, period_identifier: str, readonly: bool = False):
    """Renderiza la sección de notas del usuario."""
    # Intentar cargar notas existentes
    try:
        current_notes = get_period_notes(period_type, period_identifier) or ""
    except Exception:
        current_notes = ""
        
    if readonly:
        st.markdown(f"### {t('historico.notes_title', period=period_identifier)}")
        if current_notes:
            with st.container(border=True):
                st.markdown(current_notes, unsafe_allow_html=True)
        else:
            st.info(t('historico.no_notes', period=period_identifier))
        return

    # Mostrar notificación si viene de un guardado exitoso
    toast_key = f"toast_notes_{period_type}_{period_identifier}"
    if st.session_state.get(toast_key):
        st.success(t('historico.notes_success', period=period_identifier))
        st.session_state[toast_key] = False

    st.markdown(f"### {t('historico.notes_title', period=period_identifier)}")
    
    try:
        from streamlit_quill import st_quill
        quill_available = True
    except ImportError:
        quill_available = False
    
    if quill_available:
        # Editor de texto enriquecido
        content = st_quill(
            value=current_notes,
            placeholder="Escribe tus anotaciones, conclusiones o recordatorios...",
            html=True,
            toolbar=[
                [{'header': [1, 2, 3, False]}],
                ['bold', 'italic', 'underline', 'strike'],
                [{'list': 'ordered'}, {'list': 'bullet'}],
                [{'color': []}, {'background': []}],
                ['clean']
            ],
            key=f"quill_{period_type}_{period_identifier}"
        )
        
        if st.button(f"💾 Guardar Notas", key=f"btn_save_{period_type}_{period_identifier}", type="primary"):
            save_period_notes(period_type, period_identifier, content if content else "")
            st.session_state[toast_key] = True
            st.rerun()
    else:
        # Fallback texto plano
        with st.form(f"form_notes_{period_type}_{period_identifier}"):
            new_notes = st.text_area(
                "Tus anotaciones:",
                value=current_notes,
                height=150
            )
            if st.form_submit_button("Guardar"):
                save_period_notes(period_type, period_identifier, new_notes)
                st.session_state[toast_key] = True
                st.rerun()


def render_month_view(entries, mes_sel, anio_sel):
    """Renderiza la vista de un mes específico."""
    from src.business_logic import calcular_kpis
    import plotly.graph_objects as go
    from collections import defaultdict
    from src.config import load_config
    
    config = load_config()
    enable_relevance = config.get('enable_relevance', True)
    cats_dict = {c.id: c.nombre for c in get_all_categorias()}
    
    if not entries:
        st.info(t('historico.no_entries_month', month=mes_sel))
        return
    
    # Botón para volver usando Callback
    st.button(t('historico.back_to_year'), on_click=_reset_to_year_view)
    
    # Calcular KPIs del mes
    kpis = calcular_kpis(mes_sel)
    
    # KPIs del mes
    st.markdown(f"### {t('historico.month_summary')}: {mes_sel}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.income')}</div>
            <div class="kpi-value">{format_currency(kpis.get('total_ingresos', 0), 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.expenses')}</div>
            <div class="kpi-value" style="color: #ff6b6b;">{format_currency(kpis.get('total_gastos', 0), 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        balance = kpis.get('total_ingresos', 0) - kpis.get('total_gastos', 0)
        color = "#00ff88" if balance >= 0 else "#ff6b6b"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.balance')}</div>
            <div class="kpi-value" style="color: {color};">{format_currency(balance, 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.investment')}</div>
            <div class="kpi-value">{format_currency(kpis.get('total_inversion', 0), 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # AI Commentary Section (if enabled)
    if is_llm_enabled():
        _render_ai_commentary_section(
            period_type="month",
            period_identifier=mes_sel,
            kpis_data={
                "income": kpis.get('total_ingresos', 0),
                "expenses": kpis.get('total_gastos', 0),
                "balance": kpis.get('total_ingresos', 0) - kpis.get('total_gastos', 0),
                "investment": kpis.get('total_inversion', 0),
                "savings_percent": 0,  # Not calculated for months
                "period": mes_sel
            },
            entries=entries
        )
        st.markdown("---")
    
    
    # Sección de NOTAS del usuario (Solo Lectura)
    _render_period_notes("month", mes_sel, readonly=True)
    st.markdown("---")
    
    # Gráficos lado a lado
    col_cats, col_quality = st.columns(2)
    
    with col_cats:
        st.markdown(f"#### {t('historico.overview.expenses_by_category')}")
        gastos_cat = defaultdict(float)
        for e in entries:
            if e.tipo_movimiento == TipoMovimiento.GASTO:
                cat_name = cats_dict.get(e.categoria_id, f"Cat {e.categoria_id}")
                gastos_cat[cat_name] += e.importe
        
        if gastos_cat:
            import plotly.graph_objects as go
            sorted_cats = sorted(gastos_cat.items(), key=lambda x: x[1], reverse=True)
            
            # Donut Chart igual al del Ledger
            fig_cat = go.Figure(data=[go.Pie(
                labels=[x[0] for x in sorted_cats],
                values=[x[1] for x in sorted_cats],
                hole=0.4,
                textinfo='label+percent',
                textposition='inside',
                insidetextorientation='radial'
            )])
            
            fig_cat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                margin=dict(t=20, b=20, l=20, r=20),
                height=350,
                showlegend=False
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info(t('historico.overview.no_expenses'))
    
    with col_quality:
        if enable_relevance:
            st.markdown(f"#### {t('historico.overview.spending_quality')}")
            relevancia_data = defaultdict(float)
            for e in entries:
                if e.tipo_movimiento == TipoMovimiento.GASTO and e.relevancia_code:
                    relevancia_data[e.relevancia_code.value] += e.importe
            
            if relevancia_data:
                import plotly.graph_objects as go
                labels_map = {'NE': t('analisis.spending_quality.labels.necessary'), 'LI': t('analisis.spending_quality.labels.like'), 'SUP': t('analisis.spending_quality.labels.superfluous'), 'TON': t('analisis.spending_quality.labels.nonsense')}
                colors = {'NE': '#00c853', 'LI': '#448aff', 'SUP': '#ffab00', 'TON': '#ff5252'}
                fig_pie = go.Figure(data=[go.Pie(
                    labels=[labels_map.get(k, k) for k in relevancia_data.keys()],
                    values=list(relevancia_data.values()),
                    hole=0.5,
                    marker_colors=[colors.get(k, '#888') for k in relevancia_data.keys()]
                )])
                fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white', height=450)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.warning(t('historico.overview.no_quality_data'))
    
    st.markdown("---")
    
    # Tabla de entradas del mes
    st.markdown(f"#### {t('historico.data.title')}")
    data = []
    for e in entries:
        cat_name = cats_dict.get(e.categoria_id, f"Cat {e.categoria_id}")
        es_positivo = e.tipo_movimiento in [TipoMovimiento.INGRESO, TipoMovimiento.TRASPASO_ENTRADA]
        signo = "+" if es_positivo else "-"
        data.append({
            t('historico.data.columns.date'): e.fecha_real.strftime("%d/%m/%Y"),
            t('historico.data.columns.type'): e.tipo_movimiento.value,
            t('historico.data.columns.category'): cat_name,
            t('historico.data.columns.concept'): e.concepto[:60] if e.concepto else "",
            t('historico.data.columns.amount'): f"{signo}{format_currency(e.importe)}"
        })
    from src.constants import DATAFRAME_HEIGHT_MEDIUM
    st.dataframe(data, use_container_width=True, hide_index=True, height=DATAFRAME_HEIGHT_MEDIUM)


def render_year_view(entries, anio_sel):
    """Renderiza la vista de un año completo."""
    
    config = load_config()
    enable_relevance = config.get('enable_relevance', True)
    cats_dict = {c.id: c.nombre for c in get_all_categorias()}
    
    if not entries:
        st.info(t('historico.no_entries', year=anio_sel))
        return
    
    # Calcular KPIs
    kpis = calcular_kpis_anuales(anio_sel)
    
    # KPIs PRINCIPALES
    st.markdown(f"### {t('historico.year_summary')}")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.income')}</div>
            <div class="kpi-value">{format_currency(kpis['total_ingresos'], 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.expenses')}</div>
            <div class="kpi-value" style="color: #ff6b6b;">{format_currency(kpis['total_gastos'], 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        balance = kpis['total_ingresos'] - kpis['total_gastos']
        color = "#00ff88" if balance >= 0 else "#ff6b6b"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.balance')}</div>
            <div class="kpi-value" style="color: {color};">{format_currency(balance, 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.investment')}</div>
            <div class="kpi-value">{format_currency(kpis['total_inversion'], 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('historico.kpis.savings_percent')}</div>
            <div class="kpi-value">{kpis['pct_ahorro']:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # KPIs SECUNDARIOS (PROMEDIOS)
    st.markdown("---")
    st.markdown(f"**{t('historico.averages.title')}**")
    
    # Calcular meses activos para promedios correctos
    meses_activos = len(set(e.mes_fiscal for e in entries))
    if meses_activos == 0: meses_activos = 1
    
    avg_ingresos = kpis['total_ingresos'] / meses_activos
    avg_gastos = kpis['total_gastos'] / meses_activos
    
    # Calcular salario medio usando función centralizada
    current_cats = get_all_categorias()
    total_salario = sum(
        e.importe for e in entries 
        if es_entrada_salario(e, current_cats)
    )
    avg_salario = total_salario / meses_activos
    
    col_a1, col_a2, col_a3 = st.columns(3)
    
    with col_a1:
        st.metric(t('historico.averages.income'), format_currency(avg_ingresos, 0))
    
    with col_a2:
        st.metric(t('historico.averages.expenses'), format_currency(avg_gastos, 0))
        
    with col_a3:
        st.metric(t('historico.averages.salary'), format_currency(avg_salario, 0))
    
    st.markdown("---")
    
    # AI Commentary Section (if enabled)
    if is_llm_enabled():
        _render_ai_commentary_section(
            period_type="year",
            period_identifier=str(anio_sel),
            kpis_data={
                "income": kpis['total_ingresos'],
                "expenses": kpis['total_gastos'],
                "balance": kpis['total_ingresos'] - kpis['total_gastos'],
                "investment": kpis['total_inversion'],
                "savings_percent": kpis['pct_ahorro'],
                "period": str(anio_sel)
            },
            entries=entries
        )
        st.markdown("---")
    
    # GRÁFICOS EN TABS
    tab_overview, tab_analysis, tab_data = st.tabs([
        t('historico.tabs.overview'), t('historico.tabs.analysis'), t('historico.tabs.data')
    ])
    

    # === TAB 1: VISIÓN GLOBAL ===
    with tab_overview:
        
        # 1. Evolución Mensual (Full Width)
        st.markdown(f"#### {t('historico.overview.monthly_evolution')}")
        st.caption(t('historico.chart_click_hint'))
        
        mes_data = defaultdict(lambda: {"ingresos": 0, "gastos": 0, "inversion": 0})
        for e in entries:
            mes = e.mes_fiscal
            if e.tipo_movimiento == TipoMovimiento.INGRESO:
                mes_data[mes]["ingresos"] += e.importe
            elif e.tipo_movimiento == TipoMovimiento.GASTO:
                mes_data[mes]["gastos"] += e.importe
            elif e.tipo_movimiento == TipoMovimiento.INVERSION:
                mes_data[mes]["inversion"] += e.importe
        
        if mes_data:
            meses_ordenados = sorted(mes_data.keys())
            fig_evo = go.Figure()
            fig_evo.add_trace(go.Bar(name='Ingresos', x=meses_ordenados, y=[mes_data[m]["ingresos"] for m in meses_ordenados], marker_color='#00c853'))
            fig_evo.add_trace(go.Bar(name='Gastos', x=meses_ordenados, y=[mes_data[m]["gastos"] for m in meses_ordenados], marker_color='#ff6b6b'))
            fig_evo.add_trace(go.Bar(name='Inversión', x=meses_ordenados, y=[mes_data[m]["inversion"] for m in meses_ordenados], marker_color='#448aff'))
            fig_evo.update_layout(barmode='group', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=350)
            
            # Mostrar gráfico con event handler para clicks
            st.plotly_chart(fig_evo, use_container_width=True, key="year_evolution_chart", on_select="rerun")
        else:
            st.info(t('historico.overview.no_monthly_data'))

        st.divider()
        
        # 2. Grid para Gastos y Calidad
        col_cats, col_quality = st.columns(2)
        
        with col_cats:
            st.markdown(f"#### {t('historico.overview.expenses_by_category')}")
            gastos_cat = defaultdict(float)
            for e in entries:
                if e.tipo_movimiento == TipoMovimiento.GASTO:
                    cat_name = cats_dict.get(e.categoria_id, f"Cat {e.categoria_id}")
                    gastos_cat[cat_name] += e.importe
            
            if gastos_cat:
                sorted_cats = sorted(gastos_cat.items(), key=lambda x: x[1], reverse=True)
                
                # Donut Chart igual al del Ledger
                fig_cat = go.Figure(data=[go.Pie(
                    labels=[x[0] for x in sorted_cats],
                    values=[x[1] for x in sorted_cats],
                    hole=0.4,
                    textinfo='label+percent',
                    textposition='inside',
                    insidetextorientation='radial'
                )])
                
                fig_cat.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='white',
                    margin=dict(t=20, b=20, l=20, r=20),
                    height=400,
                    showlegend=False
                )
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.info(t('historico.overview.no_expenses'))

        with col_quality:
            if enable_relevance:
                st.markdown(f"#### {t('historico.overview.spending_quality')}")
                relevancia_data = defaultdict(float)
                for e in entries:
                    if e.tipo_movimiento == TipoMovimiento.GASTO and e.relevancia_code:
                        relevancia_data[e.relevancia_code.value] += e.importe
                
                if relevancia_data:
                    labels_map = {'NE': t('analisis.spending_quality.labels.necessary'), 'LI': t('analisis.spending_quality.labels.like'), 'SUP': t('analisis.spending_quality.labels.superfluous'), 'TON': t('analisis.spending_quality.labels.nonsense')}
                    colors = {'NE': '#00c853', 'LI': '#448aff', 'SUP': '#ffab00', 'TON': '#ff5252'}
                    fig_pie = go.Figure(data=[go.Pie(
                        labels=[labels_map.get(k, k) for k in relevancia_data.keys()],
                        values=list(relevancia_data.values()),
                        hole=0.5,
                        marker_colors=[colors.get(k, '#888') for k in relevancia_data.keys()]
                    )])
                    fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white', height=500)
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # Stats Mini
                    st.info(t('historico.overview.best_month', month=kpis.get('mejor_mes', 'N/A')))
                    st.error(t('historico.overview.worst_month', month=kpis.get('peor_mes', 'N/A')))
                else:
                    st.warning(t('historico.overview.no_quality_data'))
            else:
                 st.info(t('historico.overview.no_quality_data') + " (Relevance Disabled)")

    # === TAB 2: ANÁLISIS PROFUNDO ===
    with tab_analysis:
        tipo_analisis = st.radio(
            t('historico.analysis.select_type'),
            [t('historico.analysis.types.expenses'), t('historico.analysis.types.income'), t('historico.analysis.types.investments')],
            horizontal=True,
            key="analisis_radio"
        )
        
        if "Gastos" in tipo_analisis or "Expenses" in tipo_analisis:
            tipo_sel = TipoMovimiento.GASTO
            label_top = t('historico.analysis.types.expenses').replace('🔴 ', '')
            color_bar = '#ff6b6b'
        elif "Ingresos" in tipo_analisis or "Income" in tipo_analisis:
            tipo_sel = TipoMovimiento.INGRESO
            label_top = t('historico.analysis.types.income').replace('🟢 ', '')
            color_bar = '#00c853'
        else:
            tipo_sel = TipoMovimiento.INVERSION
            label_top = t('historico.analysis.types.investments').replace('🟣 ', '')
            color_bar = '#448aff'

        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            t('historico.analysis.tabs.word_frequency'),
            t('historico.analysis.tabs.top_entries', label=label_top),
            t('historico.analysis.tabs.curiosities')
        ])
        
        with sub_tab1:
            st.markdown(f"#### {t('historico.analysis.word_frequency_title', type=tipo_analisis)}")
            st.caption(t('historico.analysis.word_frequency_caption'))
            
            word_counts = get_word_counts(entries, filter_type=tipo_sel)
            if word_counts:
                sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:15]
                words = [w[0] for w in sorted_words]
                counts = [w[1] for w in sorted_words]
                
                fig_words = go.Figure(data=[go.Bar(
                    x=words, y=counts, marker_color=color_bar
                )])
                fig_words.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='white',
                    height=350,
                    margin=dict(l=20, r=20, t=20, b=20)
                )
                st.plotly_chart(fig_words, use_container_width=True)
            else:
                st.info(t('historico.analysis.no_text_data'))

        with sub_tab2:
            st.markdown(f"#### {t('historico.analysis.top_entries_title', label=label_top)}")
            top_expenses = get_top_entries(entries, filter_type=tipo_sel)
            if top_expenses:
                top_data = []
                for idx, e in enumerate(top_expenses, 1):
                    cat_name = cats_dict.get(e.categoria_id, "N/A")
                    top_data.append({
                        "Ranking": f"#{idx}",
                        t('historico.data.columns.date'): e.fecha_real.strftime("%d/%m/%Y"),
                        t('historico.data.columns.concept'): e.concepto,
                        t('historico.data.columns.category'): cat_name,
                        t('historico.data.columns.amount'): format_currency(e.importe)
                    })
                st.dataframe(top_data, use_container_width=True, hide_index=True)
            else:
                st.info(t('historico.analysis.no_records'))

        with sub_tab3:
            st.markdown(f"#### {t('historico.analysis.curiosities_title', type=tipo_analisis)}")
            curious = calculate_curious_metrics(entries, filter_type=tipo_sel)
            if curious:
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.metric(t('historico.analysis.curiosities_metrics.top_day'), f"{curious['dia_top_fecha']}")
                    st.metric(t('historico.analysis.curiosities_metrics.top_day_amount'), format_currency(curious['dia_top_importe']))
                with col_c2:
                    st.metric(t('historico.analysis.curiosities_metrics.daily_average'), format_currency(curious['promedio_dias_activos']))
                    st.metric(t('historico.analysis.curiosities_metrics.active_days'), f"{curious['dias_activos']}")
            else:
                st.info(t('historico.analysis.no_curiosities'))

    # === TAB 3: DATOS DETALLADOS ===
    with tab_data:
        st.markdown(f"#### {t('historico.data.title')}")
        data = []
        for e in entries:
            cat_name = cats_dict.get(e.categoria_id, f"Cat {e.categoria_id}")
            es_positivo = e.tipo_movimiento in [TipoMovimiento.INGRESO, TipoMovimiento.TRASPASO_ENTRADA]
            signo = "+" if es_positivo else "-"
            data.append({
                t('historico.data.columns.date'): e.fecha_real.strftime("%d/%m/%Y"),
                t('historico.data.columns.type'): e.tipo_movimiento.value,
                t('historico.data.columns.category'): cat_name,
                t('historico.data.columns.concept'): e.concepto[:60] if e.concepto else "",
                t('historico.data.columns.amount'): f"{signo}{format_currency(e.importe)}"
            })
        st.dataframe(data, use_container_width=True, hide_index=True, height=600)


def _render_ai_commentary_section(period_type: str, period_identifier: str, kpis_data: dict, entries=None):
    """
    Renders the AI commentary section for financial analysis.
    
    Args:
        period_type: "year" or "month"
        period_identifier: Year (e.g., "2024") or month (e.g., "2024-01")
        kpis_data: Dictionary with financial KPIs
        entries: List of ledger entries for the period (optional)
    """
    from src.i18n import t, get_language
    
    config = load_config()
    llm_config = get_llm_config()
    lang = get_language()
    
    # Try to load saved analysis from database
    saved_analysis = get_ai_analysis(period_type, period_identifier)
    
    # Create expandable section
    with st.expander(t('historico.ai_commentary_title'), expanded=False):
        # Show regenerate button if analysis exists, otherwise generate button
        col_btn, col_space = st.columns([1, 3])
        with col_btn:
            if saved_analysis:
                button_label = "🔄 " + t('historico.ai_regenerate_btn')
            else:
                button_label = t('historico.ai_generate_btn')
            
            generate_btn = st.button(
                button_label,
                key=f"ai_gen_{period_type}_{period_identifier}",
                use_container_width=True
            )
        
        # Session state key for storing commentary
        commentary_key = f"ai_commentary_{period_type}_{period_identifier}"
        
        # Load saved analysis if not in session state
        if commentary_key not in st.session_state and saved_analysis:
            st.session_state[commentary_key] = saved_analysis
        
        if generate_btn:
            # Show loading message
            with st.spinner(t('historico.ai_loading')):
                try:
                    # Import here to check availability
                    from src.llm_service import (
                        check_ollama_running, 
                        get_available_models
                    )
                    
                    # Check if Ollama is running
                    if not check_ollama_running():
                        st.error(
                            "❌ **Ollama no está ejecutándose**\n\n"
                            "1. Descarga Ollama: https://ollama.com/download\n"
                            "2. Instala y ejecuta Ollama\n"
                            "3. Vuelve aquí y genera el análisis"
                        )
                        return
                    
                    # Get available models
                    available_models = get_available_models()
                    if not available_models:
                        st.warning(
                            "⚠️ **No hay modelos descargados en Ollama**\n\n"
                            "Descarga un modelo ejecutando en terminal:\n"
                            "```\nollama pull tinyllama\n```\n"
                            "O cualquier otro: phi3, mistral, llama3, gemma2, etc."
                        )
                        return
                    
                    # Prepare movements list if entries are available
                    movements = []
                    if entries:
                        cats_dict = {c.id: c.nombre for c in get_all_categorias()}
                        for entry in entries:
                            # Determine sign based on movement type
                            es_positivo = entry.tipo_movimiento in [TipoMovimiento.INGRESO, TipoMovimiento.TRASPASO_ENTRADA]
                            importe_con_signo = float(entry.importe) if es_positivo else -float(entry.importe)
                            
                            movements.append({
                                'fecha': entry.fecha_real.strftime('%Y-%m-%d') if hasattr(entry.fecha_real, 'strftime') else str(entry.fecha_real),
                                'tipo': entry.tipo_movimiento.value if hasattr(entry.tipo_movimiento, 'value') else str(entry.tipo_movimiento),
                                'categoria': cats_dict.get(entry.categoria_id, f"Cat {entry.categoria_id}"),
                                'concepto': entry.concepto or "Sin concepto",
                                'importe': importe_con_signo
                            })
                    
                    # Generate commentary
                    model_tier = llm_config.get('model_tier', 'light')
                    commentary = analyze_financial_period(
                        data=kpis_data,
                        period_type=period_type,
                        lang=lang,
                        model_tier=model_tier,
                        max_tokens=llm_config.get('max_tokens', 300),
                        movements=movements if movements else None
                    )
                    
                    # Save to database
                    save_ai_analysis(
                        period_type=period_type,
                        period_identifier=period_identifier,
                        analysis_text=commentary,
                        model_used=model_tier,
                        lang=lang
                    )
                    
                    # Store in session state
                    st.session_state[commentary_key] = commentary
                    st.rerun()
                    
                except ConnectionError as e:
                    st.error(f"🔌 {str(e)}")
                except ValueError as e:
                    st.warning(f"⚠️ {str(e)}")
                except requests.exceptions.Timeout:
                    st.error(
                        "⏱️ **Timeout - El modelo tardó más de 3 minutos**\n\n"
                        f"Tu modelo actual: `{llm_config.get('model_tier', 'desconocido')}`\n\n"
                        "**Soluciones:**\n"
                        "1. Prueba con un modelo más rápido (tinyllama, phi3)\n"
                        "2. Reduce `max_tokens` en config.json (actual: " + str(llm_config.get('max_tokens', 600)) + ")\n"
                        "3. Espera y reintenta (Ollama puede estar ocupado)"
                    )
                except Exception as e:
                    st.error(t('historico.ai_error', error=str(e)))
        
        # Display commentary if available
        if commentary_key in st.session_state:
            st.markdown(st.session_state[commentary_key])
            # Show info if loaded from database
            if saved_analysis and not generate_btn:
                st.caption("💾 Análisis cargado desde la base de datos")
        else:
            st.info(f"👆 {t('historico.ai_generate_btn')}")
