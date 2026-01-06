"""
Página de Histórico Anual - PersAcc
Renderiza la interfaz de historico.
"""
import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import csv
from io import StringIO

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry, CierreMensual, Categoria
from src.database import (
    get_all_categorias, get_categorias_by_tipo, get_ledger_by_month,
    get_all_ledger_entries, get_latest_snapshot, update_categoria,
    get_category_counts, delete_categoria, deactivate_categoria,
    insert_categoria, DEFAULT_DB_PATH, delete_ledger_entry,
    update_ledger_entry, get_all_meses_fiscales_cerrados,
    is_mes_cerrado, get_connection
)
from src.business_logic import (
    calcular_fecha_contable, calcular_mes_fiscal, calcular_kpis,
    calcular_kpis_relevancia, ejecutar_cierre_mes,
    calcular_kpis_anuales, get_word_counts, get_top_entries,
    calculate_curious_metrics
)
from src.config import format_currency, get_currency_symbol
from src.i18n import t


def render_historico():
    """Renderiza el dashboard de análisis anual con estadísticas detalladas."""
    from src.database import get_ledger_by_year, get_available_years, get_all_categorias, get_ledger_by_month
    from src.business_logic import calcular_kpis_anuales, calcular_kpis
    import plotly.graph_objects as go
    from collections import defaultdict
    
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
        try:
            mes_date = datetime.strptime(mes, "%Y-%m")
            mes_nombre = mes_date.strftime("%B").capitalize()
            opcion = f"{mes} - {mes_nombre}"
        except:
            opcion = mes
        opciones_mes.append(opcion)
        meses_nombres[opcion] = mes
    
    with col2:
        mes_opcion = st.selectbox(
            t('historico.period_selector'),
            options=opciones_mes,
            index=0,
            key="hist_mes_sel"
        )
    
    # Determinar si es vista de mes o año
    if mes_opcion == t('historico.full_year'):
        mes_sel = None
    else:
        mes_sel = meses_nombres.get(mes_opcion)
    
    st.markdown("---")
    
    # Obtener datos según selección
    if mes_sel:
        # Vista de mes específico
        entries = get_ledger_by_month(mes_sel)
        render_month_view(entries, mes_sel, anio_sel)
    else:
        # Vista de año completo
        entries = get_ledger_by_year(anio_sel)
        render_year_view(entries, anio_sel)


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
        st.info(f"No hay entradas para {mes_sel}")
        return
    
    # Botón para volver
    if st.button(t('historico.back_to_year')):
        st.session_state["hist_selected_month"] = None
        st.rerun()
    
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
            fig_cat = go.Figure(data=[go.Bar(
                x=[x[1] for x in sorted_cats],
                y=[x[0] for x in sorted_cats],
                orientation='h',
                marker_color='#ff6b6b'
            )])
            fig_cat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                height=max(250, len(gastos_cat) * 25),
                yaxis=dict(autorange="reversed"),
                margin=dict(l=120, r=20, t=20, b=20)
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
                fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white', height=350)
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
    st.dataframe(data, use_container_width=True, hide_index=True, height=400)


def render_year_view(entries, anio_sel):
    """Renderiza la vista de un año completo."""
    from src.business_logic import calcular_kpis_anuales, get_word_counts, get_top_entries, calculate_curious_metrics
    import plotly.graph_objects as go
    from collections import defaultdict
    from src.config import load_config
    
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
            chart_event = st.plotly_chart(fig_evo, use_container_width=True, key="year_evolution_chart", on_select="rerun")
            
            # Procesar click en el gráfico
            if chart_event and chart_event.selection and chart_event.selection.points:
                clicked_point = chart_event.selection.points[0]
                if 'x' in clicked_point:
                    clicked_month = clicked_point['x']
                    st.session_state["hist_selected_month"] = clicked_month
                    st.rerun()
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
                fig_cat = go.Figure(data=[go.Bar(
                    x=[x[1] for x in sorted_cats],
                    y=[x[0] for x in sorted_cats],
                    orientation='h',
                    marker_color='#ff6b6b'
                )])
                fig_cat.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='white',
                    height=max(300, len(gastos_cat) * 30),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=150)
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
                    fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white', height=400)
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

