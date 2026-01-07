"""
Motor de Machine Learning para Proyecciones Financieras.

Este módulo implementa modelos de predicción para:
- Proyección de salarios futuros
- Proyección de inversiones
- Insights y clasificación de patrones financieros
"""

import numpy as np
from datetime import date, datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.preprocessing import StandardScaler
import streamlit as st

from .database import get_all_ledger_entries, get_available_years, get_snapshots_by_year
from .models import TipoMovimiento, LedgerEntry


def _get_monthly_aggregates(entries: List[LedgerEntry], tipo: TipoMovimiento) -> Dict[str, float]:
    """
    Agrupa entradas por mes fiscal y suma importes.
    
    Returns:
        Dict con key='YYYY-MM' y value=suma de importes
    """
    monthly = defaultdict(float)
    for e in entries:
        if e.tipo_movimiento == tipo:
            monthly[e.mes_fiscal] += e.importe
    return dict(monthly)


def _prepare_time_series(monthly_data: Dict[str, float]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convierte datos mensuales a arrays para ML.
    
    Returns:
        X: array de índices temporales (0, 1, 2, ...)
        y: array de valores
    """
    if not monthly_data:
        return np.array([]).reshape(-1, 1), np.array([])
    
    # Ordenar por fecha
    sorted_months = sorted(monthly_data.keys())
    values = [monthly_data[m] for m in sorted_months]
    
    # Crear índices temporales
    X = np.arange(len(values)).reshape(-1, 1)
    y = np.array(values)
    
    return X, y


@st.cache_data(show_spinner=False)
def project_salaries(years_ahead: int = 5) -> Dict:
    """
    Proyecta salarios futuros basándose en datos históricos.
    
    Args:
        years_ahead: Número de años a proyectar
        
    Returns:
        Dict con:
        - 'historical': datos históricos mensuales
        - 'projected': proyecciones por año
        - 'trend': tendencia detectada ('up', 'down', 'stable')
        - 'confidence': nivel de confianza (0-100)
        - 'current_year_historical_avg': promedio real del año actual (si hay datos)
    """
    entries = get_all_ledger_entries()
    
    # Filtrar ingresos (salarios)
    monthly_income = _get_monthly_aggregates(entries, TipoMovimiento.INGRESO)
    
    if len(monthly_income) < 3:
        return {
            'historical': monthly_income,
            'projected': {},
            'trend': 'unknown',
            'confidence': 0,
            'error': 'Datos insuficientes (mínimo 3 meses)'
        }
    
    X, y = _prepare_time_series(monthly_income)
    
    # Modelo de regresión lineal para tendencia
    model = LinearRegression()
    model.fit(X, y)
    
    # Calcular tendencia
    slope = model.coef_[0]
    avg_salary = np.mean(y)
    
    if slope > avg_salary * 0.01:  # >1% crecimiento
        trend = 'up'
    elif slope < -avg_salary * 0.01:
        trend = 'down'
    else:
        trend = 'stable'
    
    # Score R² para confianza
    r2_score = model.score(X, y)
    confidence = max(0, min(100, int(r2_score * 100)))
    
    # Calcular promedio histórico real del año actual
    current_year = date.today().year
    current_year_months = [m for m in monthly_income.keys() if m.startswith(str(current_year))]
    current_year_historical_avg = 0
    current_year_historical_total = 0
    num_current_year_months = 0
    
    if current_year_months:
        current_year_values = [monthly_income[m] for m in sorted(current_year_months)]
        current_year_historical_avg = np.mean(current_year_values)
        current_year_historical_total = sum(current_year_values)
        num_current_year_months = len(current_year_months)
    
    # Proyectar años futuros
    projected = {}
    
    for year_offset in range(years_ahead + 1):
        year = current_year + year_offset
        
        if year == current_year and num_current_year_months > 0:
            # Para el año actual, combinar datos históricos reales + proyecciones futuras
            # Ya tenemos los datos históricos reales de los meses pasados
            year_predictions = []
            
            # Proyectar solo los meses que faltan del año actual
            months_to_project = 12 - num_current_year_months
            start_idx = len(y)  # Comenzar desde el siguiente mes después del histórico
            
            for month in range(months_to_project):
                future_idx = start_idx + month
                pred = model.predict([[future_idx]])[0]
                pred = max(0, pred)
                year_predictions.append(pred)
            
            # Total anual = histórico real + proyecciones futuras
            projected_future_total = sum(year_predictions)
            annual_total = current_year_historical_total + projected_future_total
            
            # Promedio mensual del año completo (histórico + proyectado)
            monthly_avg = annual_total / 12
            
            projected[year] = {
                'monthly_avg': monthly_avg,
                'annual_total': annual_total,
                'monthly_values': year_predictions,
                'historical_months': num_current_year_months,
                'projected_months': months_to_project
            }
        else:
            # Para años futuros, proyectar 12 meses completos
            start_idx = len(y) + ((year - current_year) * 12) - num_current_year_months
            year_predictions = []
            
            for month in range(12):
                future_idx = start_idx + month
                pred = model.predict([[future_idx]])[0]
                pred = max(0, pred)
                year_predictions.append(pred)
            
            projected[year] = {
                'monthly_avg': np.mean(year_predictions),
                'annual_total': np.sum(year_predictions),
                'monthly_values': year_predictions
            }
    
    return {
        'historical': monthly_income,
        'projected': projected,
        'trend': trend,
        'confidence': confidence,
        'slope_monthly': slope,
        'current_year_historical_avg': current_year_historical_avg,
        'r2_score': r2_score
    }


@st.cache_data(show_spinner=False)
def project_investments(years_ahead: int = 5) -> Dict:
    """
    Proyecta inversiones futuras basándose en proyecciones de ingresos y savings rate.
    
    Args:
        years_ahead: Número de años a proyectar
        
    Returns:
        Dict con proyecciones de inversión calculadas sobre ingresos proyectados
    """
    entries = get_all_ledger_entries()
    
    # Obtener inversiones e ingresos históricos
    monthly_inv = _get_monthly_aggregates(entries, TipoMovimiento.INVERSION)
    monthly_income = _get_monthly_aggregates(entries, TipoMovimiento.INGRESO)
    
    if len(monthly_inv) < 3 or len(monthly_income) < 3:
        return {
            'historical': monthly_inv,
            'projected': {},
            'savings_rate': 0,
            'confidence': 0,
            'error': 'Datos insuficientes (mínimo 3 meses)'
        }
    
    # Calcular tasa de ahorro histórica por mes (para detectar tendencia)
    common_months = sorted(set(monthly_inv.keys()) & set(monthly_income.keys()))
    monthly_savings_rates = []
    
    for month in common_months:
        if monthly_income[month] > 0:
            rate = monthly_inv[month] / monthly_income[month]
            monthly_savings_rates.append(rate)
    
    if not monthly_savings_rates:
        avg_savings_rate = 0
    else:
        avg_savings_rate = np.mean(monthly_savings_rates)
    
    # Detectar tendencia en savings rate (¿está creciendo o decreciendo?)
    savings_rate_trend = 0
    if len(monthly_savings_rates) >= 3:
        X_sr = np.arange(len(monthly_savings_rates)).reshape(-1, 1)
        y_sr = np.array(monthly_savings_rates)
        model_sr = LinearRegression()
        model_sr.fit(X_sr, y_sr)
        savings_rate_trend = model_sr.coef_[0]  # Cambio mensual en savings rate
    
    # Obtener proyección de ingresos
    salary_projection = project_salaries(years_ahead)
    
    if salary_projection.get('error'):
        return {
            'historical': monthly_inv,
            'projected': {},
            'savings_rate': avg_savings_rate,
            'confidence': 0,
            'error': 'No se pudo proyectar ingresos'
        }
    
    # Proyectar inversiones basándose en ingresos proyectados y savings rate
    current_year = date.today().year
    projected = {}
    
    for year_offset in range(years_ahead + 1):
        year = current_year + year_offset
        
        if year not in salary_projection['projected']:
            continue
        
        # Proyectar savings rate para este año (aplicando tendencia)
        projected_savings_rate = avg_savings_rate + (savings_rate_trend * 12 * year_offset)
        projected_savings_rate = max(0, min(1, projected_savings_rate))  # Limitar entre 0 y 1
        
        # Calcular inversión proyectada
        annual_income = salary_projection['projected'][year]['annual_total']
        annual_investment = annual_income * projected_savings_rate
        monthly_avg_investment = annual_investment / 12
        
        projected[year] = {
            'monthly_avg': monthly_avg_investment,
            'annual_total': annual_investment,
            'savings_rate_used': projected_savings_rate
        }
    
    # Calcular confianza basada en consistencia del savings rate
    if len(monthly_savings_rates) > 0:
        std_dev = np.std(monthly_savings_rates)
        # Confianza alta si el savings rate es consistente (baja desviación)
        confidence = max(0, min(100, int((1 - min(std_dev / avg_savings_rate if avg_savings_rate > 0 else 1, 1)) * 100)))
    else:
        confidence = 0
    
    return {
        'historical': monthly_inv,
        'projected': projected,
        'savings_rate': avg_savings_rate,
        'savings_rate_trend': savings_rate_trend,
        'confidence': confidence,
        'calculation_method': 'income_projection_based'
    }


@st.cache_data(show_spinner=False)
def analyze_expense_trends(recent_months: int = 6) -> Dict:
    """
    Analiza tendencias de gastos por categoría en los últimos N meses.
    
    Args:
        recent_months: Número de meses recientes a analizar (default: 6)
    
    Returns:
        Dict con análisis de tendencias de gastos
    """
    from datetime import datetime, timedelta
    entries = get_all_ledger_entries()
    
    # Filtrar solo últimos N meses
    cutoff_date = datetime.now() - timedelta(days=recent_months * 30)
    recent_entries = [e for e in entries if e.fecha_real >= cutoff_date.date()]
    
    # Agrupar gastos por categoría y mes
    cat_monthly = defaultdict(lambda: defaultdict(float))
    
    for e in recent_entries:
        if e.tipo_movimiento == TipoMovimiento.GASTO:
            cat_monthly[e.categoria_id][e.mes_fiscal] += e.importe
    
    trends = {}
    
    for cat_id, monthly_data in cat_monthly.items():
        # Solo analizar categorías que tienen al menos 2 meses de datos
        if len(monthly_data) < 2:
            continue
            
        X, y = _prepare_time_series(dict(monthly_data))
        
        if len(y) > 0:
            model = LinearRegression()
            model.fit(X, y)
            
            slope = model.coef_[0]
            avg = np.mean(y)
            
            # Calcular % de cambio
            if avg > 0:
                pct_change = (slope / avg) * 100
            else:
                pct_change = 0
            
            trends[cat_id] = {
                'avg_monthly': avg,
                'slope': slope,
                'pct_change_monthly': pct_change,
                'total_months': len(y),
                'is_active': len(monthly_data) >= recent_months // 2  # Activa si tiene datos en al menos la mitad de los meses
            }
    
    return trends


@st.cache_data(show_spinner=False)
def generate_insights() -> List[Dict]:
    """
    Genera insights financieros basados en análisis ML.
    
    Returns:
        Lista de insights con tipo, mensaje y severidad
    """
    from .database import get_all_categorias
    from .i18n import t
    
    # Get category names mapping
    cats = get_all_categorias()
    cat_names = {c.id: c.nombre for c in cats}
    
    insights = []
    
    # 1. Analizar proyección de salarios con más detalle
    salary_proj = project_salaries(1)
    if salary_proj.get('trend') == 'up':
        slope = salary_proj.get('slope_monthly', 0)
        yearly_increase = slope * 12
        insights.append({
            'type': 'positive',
            'icon': '📈',
            'title': t('proyecciones.insights.income_trend_positive.title'),
            'message': t('proyecciones.insights.income_trend_positive.message', 
                         increase=f"{yearly_increase:.0f}",
                         months=len(salary_proj.get('historical', {})),
                         confidence=salary_proj.get('confidence', 0))
        })
    elif salary_proj.get('trend') == 'down':
        slope = salary_proj.get('slope_monthly', 0)
        yearly_decrease = abs(slope * 12)
        insights.append({
            'type': 'warning',
            'icon': '📉',
            'title': t('proyecciones.insights.income_trend_negative.title'),
            'message': t('proyecciones.insights.income_trend_negative.message',
                         decrease=f"{yearly_decrease:.0f}")
        })
    elif salary_proj.get('trend') == 'stable':
        avg = np.mean(list(salary_proj.get('historical', {}).values())) if salary_proj.get('historical') else 0
        insights.append({
            'type': 'info',
            'icon': '➡️',
            'title': t('proyecciones.insights.income_trend_stable.title'),
            'message': t('proyecciones.insights.income_trend_stable.message',
                         avg=f"{avg:.0f}")
        })
    
    # 2. Analizar tasa de ahorro con recomendaciones
    inv_proj = project_investments(1)
    savings_rate = inv_proj.get('savings_rate', 0)
    
    if savings_rate >= 0.30:
        insights.append({
            'type': 'positive',
            'icon': '🏆',
            'title': t('proyecciones.insights.savings_rate_exceptional.title'),
            'message': t('proyecciones.insights.savings_rate_exceptional.message',
                         rate=f"{savings_rate*100:.1f}")
        })
    elif savings_rate >= 0.20:
        insights.append({
            'type': 'positive',
            'icon': '💪',
            'title': t('proyecciones.insights.savings_rate_excellent.title'),
            'message': t('proyecciones.insights.savings_rate_excellent.message',
                         rate=f"{savings_rate*100:.1f}")
        })
    elif savings_rate >= 0.10:
        deficit_to_20 = 0.20 - savings_rate
        insights.append({
            'type': 'info',
            'icon': '👍',
            'title': t('proyecciones.insights.savings_rate_good.title'),
            'message': t('proyecciones.insights.savings_rate_good.message',
                         rate=f"{savings_rate*100:.1f}",
                         deficit=f"{deficit_to_20*100:.0f}")
        })
    elif savings_rate > 0:
        insights.append({
            'type': 'warning',
            'icon': '⚠️',
            'title': t('proyecciones.insights.savings_rate_improvable.title'),
            'message': t('proyecciones.insights.savings_rate_improvable.message',
                         rate=f"{savings_rate*100:.1f}")
        })
    else:
        insights.append({
            'type': 'warning',
            'icon': '🚨',
            'title': t('proyecciones.insights.savings_rate_none.title'),
            'message': t('proyecciones.insights.savings_rate_none.message')
        })
    
    # 3. Analizar tendencias de gastos con nombres de categoría (solo datos recientes y categorías activas)
    expense_trends = analyze_expense_trends(recent_months=6)
    
    # Filtrar solo categorías activas (que se han usado recientemente)
    active_trends = {cat_id: data for cat_id, data in expense_trends.items() if data.get('is_active', True)}
    
    # Categorías con mayor crecimiento (>5% mensual)
    growing_cats = [(cat_id, data) for cat_id, data in active_trends.items() 
                    if data['pct_change_monthly'] > 5]
    
    if growing_cats:
        # Top 3 categorías en crecimiento
        sorted_growing = sorted(growing_cats, key=lambda x: x[1]['pct_change_monthly'], reverse=True)[:3]
        
        for cat_id, data in sorted_growing:
            cat_name = cat_names.get(cat_id, f"Categoría {cat_id}")
            avg_amount = data['avg_monthly']
            pct = data['pct_change_monthly']
            
            if pct > 20:
                severity = 'warning'
                icon = '🔴'
                title = t('proyecciones.insights.expense_skyrocketing.title', category=cat_name)
            else:
                severity = 'info'
                icon = '🔺'
                title = t('proyecciones.insights.expense_increasing.title', category=cat_name)
            
            insights.append({
                'type': severity,
                'icon': icon,
                'title': title,
                'message': t('proyecciones.insights.expense_growing.message',
                             pct=f"{pct:.1f}",
                             avg=f"{avg_amount:.0f}",
                             doubling_time=f"{70/pct:.0f}")
            })
    
    # Categorías con mayor descenso (bueno) - solo categorías activas
    decreasing_cats = [(cat_id, data) for cat_id, data in active_trends.items() 
                       if data['pct_change_monthly'] < -5]
    
    if decreasing_cats:
        top_decreasing = min(decreasing_cats, key=lambda x: x[1]['pct_change_monthly'])
        cat_id, data = top_decreasing
        cat_name = cat_names.get(cat_id, f"Categoría {cat_id}")
        insights.append({
            'type': 'positive',
            'icon': '📉',
            'title': t('proyecciones.insights.expense_decreasing.title', category=cat_name),
            'message': t('proyecciones.insights.expense_decreasing.message',
                         pct=f"{abs(data['pct_change_monthly']):.1f}")
        })
    
    # 4. Análisis de gasto total
    entries = get_all_ledger_entries()
    monthly_expenses = _get_monthly_aggregates(entries, TipoMovimiento.GASTO)
    monthly_income = _get_monthly_aggregates(entries, TipoMovimiento.INGRESO)
    
    if len(monthly_expenses) >= 3 and len(monthly_income) >= 3:
        # Ratio gastos/ingresos
        common_months = set(monthly_expenses.keys()) & set(monthly_income.keys())
        if common_months:
            expense_ratio = sum(monthly_expenses[m] for m in common_months) / sum(monthly_income[m] for m in common_months)
            
            if expense_ratio > 0.90:
                insights.append({
                    'type': 'warning',
                    'icon': '💸',
                    'title': t('proyecciones.insights.expense_ratio_high.title'),
                    'message': t('proyecciones.insights.expense_ratio_high.message',
                                 ratio=f"{expense_ratio*100:.0f}")
                })
            elif expense_ratio < 0.50:
                insights.append({
                    'type': 'positive',
                    'icon': '💰',
                    'title': t('proyecciones.insights.expense_ratio_excellent.title'),
                    'message': t('proyecciones.insights.expense_ratio_excellent.message',
                                 ratio=f"{expense_ratio*100:.0f}")
                })
    
    # 5. Si hay pocos datos, informar
    if len(entries) < 30 and len(insights) < 2:
        insights.append({
            'type': 'info',
            'icon': '📊',
            'title': t('proyecciones.insights.accumulating_data.title'),
            'message': t('proyecciones.insights.accumulating_data.message',
                         entries=len(entries))
        })
    
    return insights


@st.cache_data(show_spinner=False)
def project_expenses(years_ahead: int = 5) -> Dict:
    """
    Proyecta gastos totales futuros.
    
    Args:
        years_ahead: Número de años a proyectar
        
    Returns:
        Dict con proyecciones de gastos
    """
    from .i18n import t
    entries = get_all_ledger_entries()
    monthly_exp = _get_monthly_aggregates(entries, TipoMovimiento.GASTO)
    
    if len(monthly_exp) < 3:
        return {
            'historical': monthly_exp,
            'projected': {},
            'trend': 'unknown',
            'confidence': 0,
            'error': t('proyecciones.insights.insufficient_data_error')
        }
    
    X, y = _prepare_time_series(monthly_exp)
    
    model = LinearRegression()
    model.fit(X, y)
    
    slope = model.coef_[0]
    avg_expense = np.mean(y)
    
    if slope > avg_expense * 0.01:
        trend = 'up'
    elif slope < -avg_expense * 0.01:
        trend = 'down'
    else:
        trend = 'stable'
    
    r2_score = model.score(X, y)
    confidence = max(0, min(100, int(r2_score * 100)))
    
    current_year = date.today().year
    projected = {}
    
    for year_offset in range(years_ahead + 1):
        year = current_year + year_offset
        start_idx = len(y) + (year_offset * 12)
        year_predictions = []
        
        for month in range(12):
            future_idx = start_idx + month
            pred = model.predict([[future_idx]])[0]
            pred = max(0, pred)
            year_predictions.append(pred)
        
        projected[year] = {
            'monthly_avg': np.mean(year_predictions),
            'annual_total': np.sum(year_predictions),
            'monthly_values': year_predictions
        }
    
    return {
        'historical': monthly_exp,
        'projected': projected,
        'trend': trend,
        'confidence': confidence,
        'slope_monthly': slope
    }


@st.cache_data(show_spinner=False)
def get_projection_summary(years_ahead: int = 5) -> Dict:
    """
    Obtiene un resumen completo de todas las proyecciones.
    
    Args:
        years_ahead: Años a proyectar hacia adelante
        
    Returns:
        Dict con resumen de todas las proyecciones
    """
    return {
        'salaries': project_salaries(years_ahead),
        'investments': project_investments(years_ahead),
        'expenses': project_expenses(years_ahead),
        'insights': generate_insights(),
        'generated_at': datetime.now().isoformat()
    }
