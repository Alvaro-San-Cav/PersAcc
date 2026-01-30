"""
Página de Proyecciones - PersAcc
Análisis predictivo de finanzas personales con ML.
"""
import streamlit as st
from datetime import date
import plotly.graph_objects as go
import plotly.express as px

from src.ai.ml_engine import (
    project_salaries, 
    project_investments, 
    generate_insights,
    get_projection_summary
)
from src.config import get_currency_symbol, format_currency
from src.i18n import t
from src.database import get_available_years


def render_proyecciones():
    """Renderiza la página de proyecciones."""
    st.markdown(f'<div class="main-header"><h1>{t("proyecciones.title")}</h1></div>', unsafe_allow_html=True)
    
    # Verificar si hay datos suficientes
    available_years = get_available_years()
    if not available_years:
        st.warning(t("proyecciones.no_data"))
        st.info(t("proyecciones.no_data_hint"))
        return
    
    # Selector de rango de años
    current_year = date.today().year
    
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        start_year = st.selectbox(
            t("proyecciones.from_year"),
            options=list(range(min(available_years), current_year + 1)),
            index=len(range(min(available_years), current_year + 1)) - 1,
            key="proj_start_year"
        )
    with col2:
        end_year = st.selectbox(
            t("proyecciones.to_year"),
            options=list(range(current_year, current_year + 6)),
            index=5,  # Default: +5 años
            key="proj_end_year"
        )
    
    years_ahead = end_year - current_year
    
    # Botón para refrescar proyecciones (limpia caché)
    col_refresh, _ = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Recalcular", help="Fuerza el recálculo de proyecciones con los últimos datos"):
            # Limpiar caché de session_state
            keys_to_delete = [k for k in st.session_state.keys() if k.startswith('projections_')]
            for k in keys_to_delete:
                del st.session_state[k]
            # Limpiar caché de funciones
            get_projection_summary.clear()
            generate_insights.clear()
            st.rerun()
    
    st.markdown("---")
    
    
    # Obtener proyecciones (con caché)
    cache_key = f"projections_{start_year}_{end_year}"
    if cache_key not in st.session_state:
        with st.spinner(t("proyecciones.calculating")):
            st.session_state[cache_key] = get_projection_summary(years_ahead)
    
    projections = st.session_state[cache_key]
    
    # === SECCIÓN: PROYECCIÓN DE SALARIOS ===
    st.markdown(f"### 💰 {t('proyecciones.salary_section')}")
    
    salary_data = projections['salaries']
    
    if salary_data.get('error'):
        st.warning(salary_data['error'])
    else:
        # Métricas de salario
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            trend_icon = "📈" if salary_data['trend'] == 'up' else ("📉" if salary_data['trend'] == 'down' else "➡️")
            trend_key = f"proyecciones.trend_{salary_data['trend']}"
            st.metric(
                t("proyecciones.trend"),
                f"{trend_icon} {t(trend_key)}"
            )
        
        with col_m2:
            # Mostrar promedio histórico real del año actual si existe
            if salary_data.get('current_year_historical_avg', 0) > 0:
                avg_salary = salary_data['current_year_historical_avg']
                st.metric(
                    t("proyecciones.avg_salary_current"), 
                    format_currency(avg_salary),
                    help=t("proyecciones.current_year_avg_explanation")
                )
            elif current_year in salary_data['projected']:
                avg_salary = salary_data['projected'][current_year]['monthly_avg']
                st.metric(
                    t("proyecciones.avg_salary_current"), 
                    format_currency(avg_salary),
                    help=t("proyecciones.current_year_avg_explanation")
                )
        
        with col_m3:
            r2 = salary_data.get('r2_score', salary_data['confidence'] / 100)
            st.metric(
                t("proyecciones.confidence"), 
                f"{salary_data['confidence']}%",
                help=t("proyecciones.confidence_explanation") + f" (R² = {r2:.2f})"
            )
        
        # Calcular crecimiento interanual promedio
        projected_years = sorted([y for y in salary_data['projected'].keys() if y >= current_year])
        if len(projected_years) > 1:
            first_year_total = salary_data['projected'][projected_years[0]]['annual_total']
            last_year_total = salary_data['projected'][projected_years[-1]]['annual_total']
            years_diff = projected_years[-1] - projected_years[0]
            if years_diff > 0 and first_year_total > 0:
                avg_growth_rate = ((last_year_total / first_year_total) ** (1 / years_diff) - 1) * 100
                st.info(f"📊 {t('proyecciones.interannual_growth')}: **{avg_growth_rate:.1f}%**")
            else:
                st.info(f"📊 {t('proyecciones.interannual_growth')}: {t('proyecciones.no_growth_detected')}")
        
        # Gráfico de proyección de salarios
        fig_salary = _create_salary_chart(salary_data, current_year, end_year)
        st.plotly_chart(fig_salary, use_container_width=True)
        
        # Tabla resumen por año (sin columna delta)
        with st.expander(t("proyecciones.yearly_breakdown")):
            # Nota explicativa para el año actual
            if current_year in salary_data['projected']:
                year_info = salary_data['projected'][current_year]
                if 'historical_months' in year_info and year_info['historical_months'] > 0:
                    st.info(
                    t('proyecciones.current_year_note', 
                      year=current_year, 
                      historical_months=year_info['historical_months'], 
                      projected_months=year_info.get('projected_months', 0))
                )
            
            _render_yearly_table_simple(
                salary_data['projected'], 
                t("proyecciones.salary"),
                salary_data.get('current_year_historical_avg', 0)
            )
    
    st.markdown("---")
    
    # === SECCIÓN: PROYECCIÓN DE INVERSIONES ===
    st.markdown(f"### 💎 {t('proyecciones.investment_section')}")
    
    inv_data = projections['investments']
    
    if inv_data.get('error'):
        st.warning(inv_data['error'])
    else:
        # Métricas de inversión
        col_i1, col_i2, col_i3 = st.columns(3)
        
        with col_i1:
            savings_rate = inv_data.get('savings_rate', 0) * 100
            st.metric(t("proyecciones.savings_rate"), f"{savings_rate:.1f}%")
        
        with col_i2:
            if end_year in inv_data['projected']:
                total_inv = inv_data['projected'][end_year]['annual_total']
                st.metric(t("proyecciones.projected_annual", year=end_year), format_currency(total_inv))
        
        with col_i3:
            # Inversión acumulada proyectada
            total_projected = sum(
                data['annual_total'] 
                for year, data in inv_data['projected'].items() 
                if year > current_year
            )
            st.metric(t("proyecciones.total_projected"), format_currency(total_projected))
        
        # Explicación del método de cálculo
        if inv_data.get('calculation_method') == 'income_projection_based':
            st.info(f"ℹ️ {t('proyecciones.investment_calc_explanation', rate=f'{savings_rate:.1f}')}")
        
        # Gráfico de proyección de inversiones
        fig_inv = _create_investment_chart(inv_data, current_year, end_year)
        st.plotly_chart(fig_inv, use_container_width=True)
        
        # Tabla resumen por año (sin columna delta)
        with st.expander(t("proyecciones.yearly_breakdown")):
            _render_yearly_table_simple(inv_data['projected'], t('proyecciones.investment'))
    
    st.markdown("---")
    
    # === SECCIÓN: PROYECCIÓN DE GASTOS ===
    st.markdown(f"### 📉 {t('proyecciones.expenses_section')}")
    
    exp_data = projections.get('expenses', {})
    
    if exp_data.get('error'):
        st.warning(exp_data['error'])
    else:
        # Métricas de gastos
        col_e1, col_e2, col_e3 = st.columns(3)
        
        with col_e1:
            trend = exp_data.get('trend', 'unknown')
            trend_icon = "📈" if trend == 'up' else ("📉" if trend == 'down' else "➡️")
            trend_key = f"proyecciones.trend_{trend}"
            st.metric(
                t("proyecciones.trend"),
                f"{trend_icon} {t(trend_key)}"
            )
        
        with col_e2:
            if current_year in exp_data.get('projected', {}):
                avg_exp = exp_data['projected'][current_year]['monthly_avg']
                st.metric(t("proyecciones.avg_expenses_current"), format_currency(avg_exp))
        
        with col_e3:
            st.metric(t("proyecciones.confidence"), f"{exp_data.get('confidence', 0)}%")
        
        # Calcular crecimiento interanual promedio
        projected_years = sorted([y for y in exp_data.get('projected', {}).keys() if y >= current_year])
        if len(projected_years) > 1:
            first_year_total = exp_data['projected'][projected_years[0]]['annual_total']
            last_year_total = exp_data['projected'][projected_years[-1]]['annual_total']
            years_diff = projected_years[-1] - projected_years[0]
            if years_diff > 0 and first_year_total > 0:
                avg_growth_rate = ((last_year_total / first_year_total) ** (1 / years_diff) - 1) * 100
                st.info(f"📊 {t('proyecciones.interannual_growth')}: **{avg_growth_rate:.1f}%**")
            else:
                st.info(f"📊 {t('proyecciones.interannual_growth')}: {t('proyecciones.no_growth_detected')}")
        
        # Gráfico de proyección de gastos
        if exp_data.get('projected'):
            fig_exp = _create_expense_chart(exp_data, current_year, end_year)
            st.plotly_chart(fig_exp, use_container_width=True)
        
        # Tabla resumen por año (sin columna delta)
        with st.expander(t("proyecciones.yearly_breakdown")):
            _render_yearly_table_simple(exp_data.get('projected', {}), t("proyecciones.expenses"))
    
    st.markdown("---")
    
    # === SECCIÓN: INSIGHTS ===
    st.markdown(f"### 🔮 {t('proyecciones.insights_section')}")
    
    insights = projections['insights']
    
    if not insights:
        st.info(t("proyecciones.no_insights"))
    else:
        for insight in insights:
            _render_insight(insight)


def _create_salary_chart(data: dict, current_year: int, end_year: int) -> go.Figure:
    """Crea gráfico de proyección de salarios con fechas en eje X."""
    fig = go.Figure()
    
    # Datos históricos
    historical = data.get('historical', {})
    hist_dates = []
    hist_values = []
    
    if historical:
        hist_months = sorted(historical.keys())
        hist_dates = hist_months  # Ya están en formato YYYY-MM
        hist_values = [historical[m] for m in hist_months]
        
        fig.add_trace(go.Scatter(
            x=hist_dates,
            y=hist_values,
            mode='lines+markers',
            name=t('proyecciones.chart_historical'),
            line=dict(color='#00ff88', width=2),
            marker=dict(size=6),
            hovertemplate='%{x}<br>%{y:,.0f} ' + get_currency_symbol() + '<extra></extra>'
        ))
    
    # Datos proyectados
    projected = data.get('projected', {})
    if projected:
        proj_values = []
        proj_dates = []
        
        for year in sorted(projected.keys()):
            if year >= current_year:
                monthly = projected[year].get('monthly_values', [])
                # Calcular el mes inicial para este año
                if year == current_year and hist_dates:
                    # Continuamos desde el último mes histórico
                    last_hist = hist_dates[-1]
                    last_year, last_month = int(last_hist[:4]), int(last_hist[5:7])
                    start_month = last_month + 1
                    start_year = last_year
                    if start_month > 12:
                        start_month = 1
                        start_year += 1
                else:
                    start_month = 1
                    start_year = year
                
                for i, val in enumerate(monthly):
                    month = start_month + i
                    y = start_year
                    while month > 12:
                        month -= 12
                        y += 1
                    proj_dates.append(f"{y}-{month:02d}")
                    proj_values.append(val)
        
        fig.add_trace(go.Scatter(
            x=proj_dates,
            y=proj_values,
            mode='lines',
            name=t('proyecciones.chart_projected'),
            line=dict(color='#8a2be2', width=2, dash='dash'),
            fill='tonexty' if historical else None,
            fillcolor='rgba(138, 43, 226, 0.1)',
            hovertemplate='%{x}<br>%{y:,.0f} ' + get_currency_symbol() + '<extra></extra>'
        ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        margin=dict(t=30, b=30, l=50, r=30),
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(showgrid=False, title=t('proyecciones.axis_months'), tickangle=-45, dtick="M6"),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title=get_currency_symbol())
    )
    
    return fig


def _create_investment_chart(data: dict, current_year: int, end_year: int) -> go.Figure:
    """Crea gráfico de proyección de inversiones."""
    fig = go.Figure()
    
    # Datos proyectados anuales como barras
    projected = data.get('projected', {})
    
    years = sorted([y for y in projected.keys() if y >= current_year])
    values = [projected[y]['annual_total'] for y in years]
    
    # Colorear barras: histórico vs proyectado
    colors = ['#00ff88' if y <= current_year else '#8a2be2' for y in years]
    
    fig.add_trace(go.Bar(
        x=years,
        y=values,
        marker_color=colors,
        text=[format_currency(v, decimals=0) for v in values],
        textposition='outside'
    ))
    
    # Línea de tendencia
    if len(values) > 1:
        import numpy as np
        x_trend = np.arange(len(years))
        z = np.polyfit(x_trend, values, 1)
        p = np.poly1d(z)
        trend_values = p(x_trend)
        
        fig.add_trace(go.Scatter(
            x=years,
            y=trend_values,
            mode='lines',
            name='Tendencia',
            line=dict(color='#ff6b6b', width=2, dash='dot')
        ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        margin=dict(t=30, b=30, l=50, r=30),
        height=300,
        showlegend=False,
        xaxis=dict(showgrid=False, title=t('proyecciones.axis_year'), tickmode='linear'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title=get_currency_symbol())
    )
    
    return fig


def _create_expense_chart(data: dict, current_year: int, end_year: int) -> go.Figure:
    """Crea gráfico de proyección de gastos con fechas en eje X."""
    fig = go.Figure()
    
    # Datos históricos
    historical = data.get('historical', {})
    hist_dates = []
    hist_values = []
    
    if historical:
        hist_months = sorted(historical.keys())
        hist_dates = hist_months  # Ya están en formato YYYY-MM
        hist_values = [historical[m] for m in hist_months]
        
        fig.add_trace(go.Scatter(
            x=hist_dates,
            y=hist_values,
            mode='lines+markers',
            name=t('proyecciones.chart_historical'),
            line=dict(color='#ff6b6b', width=2),
            marker=dict(size=6),
            hovertemplate='%{x}<br>%{y:,.0f} ' + get_currency_symbol() + '<extra></extra>'
        ))
    
    # Datos proyectados
    projected = data.get('projected', {})
    if projected:
        proj_values = []
        proj_dates = []
        
        for year in sorted(projected.keys()):
            if year >= current_year:
                monthly = projected[year].get('monthly_values', [])
                # Calcular el mes inicial para este año
                if year == current_year and hist_dates:
                    last_hist = hist_dates[-1]
                    last_year, last_month = int(last_hist[:4]), int(last_hist[5:7])
                    start_month = last_month + 1
                    start_year = last_year
                    if start_month > 12:
                        start_month = 1
                        start_year += 1
                else:
                    start_month = 1
                    start_year = year
                
                for i, val in enumerate(monthly):
                    month = start_month + i
                    y = start_year
                    while month > 12:
                        month -= 12
                        y += 1
                    proj_dates.append(f"{y}-{month:02d}")
                    proj_values.append(val)
        
        fig.add_trace(go.Scatter(
            x=proj_dates,
            y=proj_values,
            mode='lines',
            name=t('proyecciones.chart_projected'),
            line=dict(color='#ff9966', width=2, dash='dash'),
            fill='tonexty' if historical else None,
            fillcolor='rgba(255, 107, 107, 0.1)',
            hovertemplate='%{x}<br>%{y:,.0f} ' + get_currency_symbol() + '<extra></extra>'
        ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        margin=dict(t=30, b=30, l=50, r=30),
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(showgrid=False, title=t('proyecciones.axis_months'), tickangle=-45, dtick="M6"),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title=get_currency_symbol())
    )
    
    return fig


def _render_yearly_table_simple(projected: dict, label: str, current_year_historical_avg: float = 0):
    """Renderiza tabla de proyecciones anuales SIN columna delta.
    
    Args:
        projected: Dict con proyecciones por año
        label: Etiqueta para las columnas
        current_year_historical_avg: Promedio histórico real del año actual (si existe)
    """
    import pandas as pd
    from datetime import date
    
    if not projected:
        return
    
    data = []
    sorted_years = sorted(projected.keys())
    current_year = date.today().year
    
    for year in sorted_years:
        info = projected[year]
        
        # Para el año actual, usar dato histórico real para monthly_avg si existe
        # pero SIEMPRE usar la proyección del modelo para annual_total (12 meses completos)
        if year == current_year and current_year_historical_avg > 0:
            monthly_avg = current_year_historical_avg
            annual_total = info['annual_total']  # Usar proyección del modelo para total anual
        else:
            monthly_avg = info['monthly_avg']
            annual_total = info['annual_total']
        
        row = {
            t("proyecciones.year_col"): year,
            f"{label} {t('proyecciones.monthly_avg_suffix')}": format_currency(monthly_avg),
            f"{label} {t('proyecciones.annual_total_suffix')}": format_currency(annual_total)
        }
        
        # Si hay información de savings rate usado, mostrarla (para inversiones)
        if 'savings_rate_used' in info:
            row[t("proyecciones.savings_rate")] = f"{info['savings_rate_used'] * 100:.1f}%"
        
        data.append(row)
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_insight(insight: dict):
    """Renderiza un insight individual."""
    type_colors = {
        'positive': 'rgba(0, 255, 136, 0.1)',
        'warning': 'rgba(255, 107, 107, 0.1)',
        'info': 'rgba(138, 43, 226, 0.1)'
    }
    
    border_colors = {
        'positive': '#00ff88',
        'warning': '#ff6b6b',
        'info': '#8a2be2'
    }
    
    bg_color = type_colors.get(insight['type'], type_colors['info'])
    border_color = border_colors.get(insight['type'], border_colors['info'])
    
    st.markdown(f"""
    <div style="
        background: {bg_color};
        border-left: 4px solid {border_color};
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 12px;
    ">
        <strong>{insight['icon']} {insight['title']}</strong><br>
        {insight['message']}
    </div>
    """, unsafe_allow_html=True)
