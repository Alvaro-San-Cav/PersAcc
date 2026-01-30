"""
Motor de Machine Learning para Proyecciones Financieras.

Este módulo implementa modelos de predicción para:
- Proyección de salarios futuros
- Proyección de inversiones
- Insights y clasificación de patrones financieros

Soporta tanto regresión lineal (fallback) como redes neuronales (preferido).
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

from src.database import get_all_ledger_entries, get_available_years, get_snapshots_by_year
from src.models import TipoMovimiento, LedgerEntry

# Importar módulo de redes neuronales
from src.ai.nn_projector import (
    get_or_create_projector,
    retrain_all_models as _nn_retrain_all,
    get_all_models_status as _nn_get_status
)

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
    Proyecta salarios futuros usando SARIMAX para capturar estacionalidad.
    
    Args:
        years_ahead: Número de años a proyectar
        
    Returns:
        Dict con proyecciones incluyendo estacionalidad (pagas extras, etc.)
    """
    import warnings
    
    entries = get_all_ledger_entries()
    monthly_income = _get_monthly_aggregates(entries, TipoMovimiento.INGRESO)
    
    if len(monthly_income) < 3:
        return {
            'historical': monthly_income,
            'projected': {},
            'trend': 'unknown',
            'confidence': 0,
            'error': 'Datos insuficientes (mínimo 3 meses)'
        }
    
    # Preparar datos
    sorted_months = sorted(monthly_income.keys())
    y = np.array([monthly_income[m] for m in sorted_months])
    n_obs = len(y)
    
    # Calcular tendencia con regresión lineal para estadísticas
    X = np.arange(n_obs).reshape(-1, 1)
    model_lr = LinearRegression()
    model_lr.fit(X, y)
    slope = model_lr.coef_[0]
    avg_salary = np.mean(y)
    r2_score = model_lr.score(X, y)
    
    if slope > avg_salary * 0.01:
        trend = 'up'
    elif slope < -avg_salary * 0.01:
        trend = 'down'
    else:
        trend = 'stable'
    
    confidence = max(0, min(100, int(r2_score * 100)))
    
    # Año actual info
    current_year = date.today().year
    current_month = date.today().month
    current_year_months = [m for m in monthly_income.keys() if m.startswith(str(current_year))]
    current_year_historical_avg = 0
    current_year_historical_total = 0
    num_current_year_months = len(current_year_months)
    
    if current_year_months:
        current_year_values = [monthly_income[m] for m in sorted(current_year_months)]
        current_year_historical_avg = np.mean(current_year_values)
        current_year_historical_total = sum(current_year_values)
    
    # Intentar usar SARIMAX para proyecciones con estacionalidad
    months_to_project = years_ahead * 12 + (12 - current_month + 1)
    projected_values = []
    use_sarimax = False
    
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        
        if n_obs >= 4:
            # Determinar parámetros según datos disponibles
            if n_obs >= 24:
                # Suficientes datos: SARIMA con estacionalidad completa
                order = (1, 1, 1)
                seasonal_order = (1, 1, 1, 12)
            elif n_obs >= 12:
                # Un año: estacionalidad parcial
                order = (1, 1, 1)
                seasonal_order = (1, 0, 0, 12)
            else:
                # Menos de un año: sin estacionalidad pero con tendencia
                order = (1, 1, 0)
                seasonal_order = (0, 0, 0, 0)
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = SARIMAX(
                    y,
                    order=order,
                    seasonal_order=seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
                model_fit = model.fit(disp=False, maxiter=200)
                forecast = model_fit.forecast(steps=months_to_project)
                projected_values = np.maximum(forecast, 0).tolist()
                use_sarimax = True
                
    except Exception as e:
        # Fallback a regresión lineal si SARIMAX falla
        use_sarimax = False
    
    if not use_sarimax:
        # Fallback: usar regresión lineal con patrón estacional manual
        # Detectar patrón de pagas extras (meses con valores > 1.5x promedio)
        monthly_pattern = {}
        for m in sorted_months:
            month_num = int(m.split('-')[1])
            if month_num not in monthly_pattern:
                monthly_pattern[month_num] = []
            monthly_pattern[month_num].append(monthly_income[m])
        
        seasonal_factors = {}
        for month_num in range(1, 13):
            if month_num in monthly_pattern:
                seasonal_factors[month_num] = np.mean(monthly_pattern[month_num]) / avg_salary
            else:
                seasonal_factors[month_num] = 1.0
        
        for i in range(months_to_project):
            future_idx = n_obs + i
            base_pred = model_lr.predict([[future_idx]])[0]
            future_month = ((current_month - 1 + i) % 12) + 1
            adjusted_pred = base_pred * seasonal_factors.get(future_month, 1.0)
            projected_values.append(max(0, adjusted_pred))
    
    # Organizar proyecciones por año
    projected = {}
    proj_idx = 0
    
    for year_offset in range(years_ahead + 1):
        year = current_year + year_offset
        
        if year == current_year and num_current_year_months > 0:
            # Año actual: combinar histórico real + proyecciones
            months_remaining = 12 - num_current_year_months
            year_predictions = projected_values[proj_idx:proj_idx + months_remaining]
            proj_idx += months_remaining
            
            projected_future_total = sum(year_predictions)
            annual_total = current_year_historical_total + projected_future_total
            monthly_avg = annual_total / 12
            
            projected[year] = {
                'monthly_avg': monthly_avg,
                'annual_total': annual_total,
                'monthly_values': year_predictions,
                'historical_months': num_current_year_months,
                'projected_months': months_remaining
            }
        else:
            # Años futuros completos
            year_predictions = projected_values[proj_idx:proj_idx + 12]
            proj_idx += 12
            
            if len(year_predictions) == 12:
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
        'r2_score': r2_score,
        'model_type': 'sarimax' if use_sarimax else 'linear_with_seasonality'
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
    Versión mejorada con métricas concretas y contexto.
    
    Returns:
        Lista de insights con tipo, mensaje y severidad
    """
    from src.database import get_all_categorias
    from src.i18n import t
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    # Get category names mapping
    cats = get_all_categorias()
    cat_names = {c.id: c.nombre for c in cats}
    
    insights = []
    entries = get_all_ledger_entries()
    
    # Preparar datos agregados
    monthly_income = _get_monthly_aggregates(entries, TipoMovimiento.INGRESO)
    monthly_expenses = _get_monthly_aggregates(entries, TipoMovimiento.GASTO)
    monthly_inv = _get_monthly_aggregates(entries, TipoMovimiento.INVERSION)
    
    # Media de ingresos mensuales
    avg_income = np.mean(list(monthly_income.values())) if monthly_income else 0
    avg_expenses = np.mean(list(monthly_expenses.values())) if monthly_expenses else 0
    avg_investment = np.mean(list(monthly_inv.values())) if monthly_inv else 0
    
    # 1. Insight de tendencia de ingresos
    salary_proj = project_salaries(1)
    n_months = len(salary_proj.get('historical', {}))
    
    if salary_proj.get('trend') == 'up':
        slope = salary_proj.get('slope_monthly', 0)
        yearly_increase = slope * 12
        monthly_increase = slope
        
        # Nota de variabilidad basada en confianza
        confidence = salary_proj.get('confidence', 0)
        if confidence < 50:
            variability_note = " ⚠️ Alta variabilidad mensual - tendencia orientativa."
        else:
            variability_note = ""
        
        insights.append({
            'type': 'positive',
            'icon': '📈',
            'title': t('proyecciones.insights.income_trend_positive.title'),
            'message': t('proyecciones.insights.income_trend_positive.message', 
                         increase=f"{yearly_increase:.0f}",
                         monthly_increase=f"{monthly_increase:.0f}",
                         months=n_months,
                         variability_note=variability_note)
        })
    elif salary_proj.get('trend') == 'down':
        slope = salary_proj.get('slope_monthly', 0)
        yearly_decrease = abs(slope * 12)
        insights.append({
            'type': 'warning',
            'icon': '⚠️',
            'title': t('proyecciones.insights.income_trend_negative.title'),
            'message': t('proyecciones.insights.income_trend_negative.message',
                         decrease=f"{yearly_decrease:.0f}",
                         current_avg=f"{avg_income:.0f}")
        })
    elif salary_proj.get('trend') == 'stable':
        insights.append({
            'type': 'info',
            'icon': '➡️',
            'title': t('proyecciones.insights.income_trend_stable.title'),
            'message': t('proyecciones.insights.income_trend_stable.message',
                         avg=f"{avg_income:.0f}",
                         months=n_months)
        })
    
    # 2. Insight de tasa de ahorro con proyecciones concretas
    inv_proj = project_investments(1)
    savings_rate = inv_proj.get('savings_rate', 0)
    monthly_investment = avg_income * savings_rate if avg_income > 0 else 0
    five_year_total = monthly_investment * 60  # 5 años * 12 meses
    
    if savings_rate >= 0.30:
        insights.append({
            'type': 'positive',
            'icon': '🏆',
            'title': t('proyecciones.insights.savings_rate_exceptional.title'),
            'message': t('proyecciones.insights.savings_rate_exceptional.message',
                         rate=f"{savings_rate*100:.1f}",
                         monthly_amount=f"{monthly_investment:.0f}",
                         five_year_total=f"{five_year_total:.0f}")
        })
    elif savings_rate >= 0.20:
        insights.append({
            'type': 'positive',
            'icon': '💪',
            'title': t('proyecciones.insights.savings_rate_excellent.title'),
            'message': t('proyecciones.insights.savings_rate_excellent.message',
                         rate=f"{savings_rate*100:.1f}",
                         monthly_amount=f"{monthly_investment:.0f}",
                         five_year_total=f"{five_year_total:.0f}")
        })
    elif savings_rate >= 0.10:
        deficit_rate = 0.20 - savings_rate
        deficit_amount = avg_income * deficit_rate if avg_income > 0 else 0
        insights.append({
            'type': 'info',
            'icon': '👍',
            'title': t('proyecciones.insights.savings_rate_good.title'),
            'message': t('proyecciones.insights.savings_rate_good.message',
                         rate=f"{savings_rate*100:.1f}",
                         monthly_amount=f"{monthly_investment:.0f}",
                         deficit_amount=f"{deficit_amount:.0f}")
        })
    elif savings_rate > 0:
        insights.append({
            'type': 'warning',
            'icon': '⚠️',
            'title': t('proyecciones.insights.savings_rate_improvable.title'),
            'message': t('proyecciones.insights.savings_rate_improvable.message',
                         rate=f"{savings_rate*100:.1f}",
                         monthly_amount=f"{monthly_investment:.0f}")
        })
    else:
        target_amount = avg_income * 0.10 if avg_income > 0 else 0
        insights.append({
            'type': 'warning',
            'icon': '🚨',
            'title': t('proyecciones.insights.savings_rate_none.title'),
            'message': t('proyecciones.insights.savings_rate_none.message',
                         target_amount=f"{target_amount:.0f}")
        })
    
    # 3. Análisis de gastos por categoría - buscar picos vs media O comparativa interanual
    now = datetime.now()
    current_month = now.strftime('%Y-%m')
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    same_month_last_year = f"{now.year - 1}-{now.month:02d}"
    
    # Agrupar gastos por categoría y mes
    cat_monthly = defaultdict(lambda: defaultdict(float))
    for e in entries:
        if e.tipo_movimiento == TipoMovimiento.GASTO:
            cat_monthly[e.categoria_id][e.mes_fiscal] += e.importe
    
    spike_insights = []
    for cat_id, monthly_data in cat_monthly.items():
        if len(monthly_data) < 3:
            continue
        
        cat_name = cat_names.get(cat_id, f"Categoría {cat_id}")
        avg_cat = np.mean(list(monthly_data.values()))
        
        # Obtener gasto del mes actual o último mes
        current_amount = monthly_data.get(current_month, monthly_data.get(last_month, 0))
        
        if current_amount <= 0 or avg_cat <= 0:
            continue
        
        # Comparar con media histórica
        diff_pct = ((current_amount - avg_cat) / avg_cat) * 100
        
        # Solo alertar si está >50% por encima de la media (evitar ruido normal)
        if diff_pct > 50:
            # Añadir contexto estacional si hay datos del año pasado
            context = ""
            if same_month_last_year in monthly_data:
                last_year_amount = monthly_data[same_month_last_year]
                if last_year_amount > 0:
                    yoy_diff = ((current_amount - last_year_amount) / last_year_amount) * 100
                    if abs(yoy_diff) < 20:
                        context = "Similar al año pasado (estacional)."
                    elif yoy_diff > 20:
                        context = f"Un {yoy_diff:.0f}% más que el año pasado."
            
            spike_insights.append({
                'type': 'info',
                'icon': '📊',
                'title': t('proyecciones.insights.expense_spike.title', category=cat_name),
                'message': t('proyecciones.insights.expense_spike.message',
                             current_amount=f"{current_amount:.0f}",
                             avg=f"{avg_cat:.0f}",
                             diff_pct=f"{diff_pct:.0f}",
                             context=context),
                'pct': diff_pct  # Para ordenar
            })
    
    # Solo mostrar top 3 picos más significativos
    spike_insights.sort(key=lambda x: x.get('pct', 0), reverse=True)
    for insight in spike_insights[:3]:
        del insight['pct']  # Limpiar campo auxiliar
        insights.append(insight)
    
    # 4. Categorías con reducción significativa
    expense_trends = analyze_expense_trends(recent_months=6)
    active_trends = {cat_id: data for cat_id, data in expense_trends.items() if data.get('is_active', True)}
    
    decreasing_cats = [(cat_id, data) for cat_id, data in active_trends.items() 
                       if data['pct_change_monthly'] < -10]  # Más estricto: -10%
    
    if decreasing_cats:
        top_decreasing = min(decreasing_cats, key=lambda x: x[1]['pct_change_monthly'])
        cat_id, data = top_decreasing
        cat_name = cat_names.get(cat_id, f"Categoría {cat_id}")
        
        # Calcular ahorro anual estimado
        avg_amount = data['avg_monthly']
        slope = data['slope']
        prev_avg = avg_amount + abs(slope) * 3  # Estimación de hace 3 meses
        yearly_savings = abs(slope) * 12
        
        insights.append({
            'type': 'positive',
            'icon': '📉',
            'title': t('proyecciones.insights.expense_decreasing.title', category=cat_name),
            'message': t('proyecciones.insights.expense_decreasing.message',
                         prev_avg=f"{prev_avg:.0f}",
                         current_avg=f"{avg_amount:.0f}",
                         yearly_savings=f"{yearly_savings:.0f}")
        })
    
    # 5. Análisis ratio gastos/ingresos con margen
    if len(monthly_expenses) >= 3 and len(monthly_income) >= 3:
        common_months = set(monthly_expenses.keys()) & set(monthly_income.keys())
        if common_months:
            total_exp = sum(monthly_expenses[m] for m in common_months)
            total_inc = sum(monthly_income[m] for m in common_months)
            expense_ratio = total_exp / total_inc if total_inc > 0 else 0
            monthly_margin = avg_income - avg_expenses
            
            if expense_ratio > 0.90:
                insights.append({
                    'type': 'warning',
                    'icon': '💸',
                    'title': t('proyecciones.insights.expense_ratio_high.title'),
                    'message': t('proyecciones.insights.expense_ratio_high.message',
                                 ratio=f"{expense_ratio*100:.0f}",
                                 margin=f"{monthly_margin:.0f}")
                })
            elif expense_ratio < 0.50:
                insights.append({
                    'type': 'positive',
                    'icon': '💰',
                    'title': t('proyecciones.insights.expense_ratio_excellent.title'),
                    'message': t('proyecciones.insights.expense_ratio_excellent.message',
                                 ratio=f"{expense_ratio*100:.0f}",
                                 margin=f"{monthly_margin:.0f}")
                })
    
    # 6. Insight de datos insuficientes
    if len(entries) < 30 and len(insights) < 2:
        n_months = len(set(e.mes_fiscal for e in entries))
        insights.append({
            'type': 'info',
            'icon': '📊',
            'title': t('proyecciones.insights.accumulating_data.title'),
            'message': t('proyecciones.insights.accumulating_data.message',
                         entries=len(entries),
                         months=n_months)
        })
    
    return insights


@st.cache_data(show_spinner=False)
def project_expenses(years_ahead: int = 5) -> Dict:
    """
    Proyecta gastos totales futuros usando SARIMAX.
    
    Args:
        years_ahead: Número de años a proyectar
        
    Returns:
        Dict con proyecciones de gastos
    """
    import warnings
    from src.i18n import t
    
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
    
    # Preparar datos
    sorted_months = sorted(monthly_exp.keys())
    y = np.array([monthly_exp[m] for m in sorted_months])
    n_obs = len(y)
    
    # Calcular tendencia con regresión lineal
    X = np.arange(n_obs).reshape(-1, 1)
    model_lr = LinearRegression()
    model_lr.fit(X, y)
    slope = model_lr.coef_[0]
    avg_expense = np.mean(y)
    r2_score = model_lr.score(X, y)
    
    if slope > avg_expense * 0.01:
        trend = 'up'
    elif slope < -avg_expense * 0.01:
        trend = 'down'
    else:
        trend = 'stable'
    
    confidence = max(0, min(100, int(r2_score * 100)))
    
    # Proyectar con SARIMAX
    current_year = date.today().year
    current_month = date.today().month
    months_to_project = years_ahead * 12 + (12 - current_month + 1)
    projected_values = []
    use_sarimax = False
    
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        
        if n_obs >= 4:
            if n_obs >= 24:
                order = (1, 1, 1)
                seasonal_order = (1, 1, 1, 12)
            elif n_obs >= 12:
                order = (1, 1, 1)
                seasonal_order = (1, 0, 0, 12)
            else:
                order = (1, 1, 0)
                seasonal_order = (0, 0, 0, 0)
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = SARIMAX(
                    y,
                    order=order,
                    seasonal_order=seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
                model_fit = model.fit(disp=False, maxiter=200)
                forecast = model_fit.forecast(steps=months_to_project)
                projected_values = np.maximum(forecast, 0).tolist()
                use_sarimax = True
                
    except Exception:
        use_sarimax = False
    
    if not use_sarimax:
        # Fallback a regresión lineal
        for i in range(months_to_project):
            future_idx = n_obs + i
            pred = model_lr.predict([[future_idx]])[0]
            projected_values.append(max(0, pred))
    
    # Organizar por año
    projected = {}
    proj_idx = 0
    
    for year_offset in range(years_ahead + 1):
        year = current_year + year_offset
        year_predictions = projected_values[proj_idx:proj_idx + 12]
        proj_idx += 12
        
        if len(year_predictions) == 12:
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
        'slope_monthly': slope,
        'model_type': 'sarimax' if use_sarimax else 'linear_regression'
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
        'models_status': get_nn_models_status(),
        'generated_at': datetime.now().isoformat()
    }


# ============================================================================
# FUNCIONES DE REDES NEURONALES
# ============================================================================

def retrain_nn_models() -> Dict[str, Dict]:
    """
    Reentrena todos los modelos de red neuronal.
    Invalida la caché de proyecciones para forzar recálculo.
    
    Returns:
        Dict con resultados por tipo: {'gasto': {...}, 'ingreso': {...}, 'ahorro': {...}}
    """
    # Limpiar caché de proyecciones
    project_salaries.clear()
    project_investments.clear()
    project_expenses.clear()
    get_projection_summary.clear()
    
    # Reentrenar modelos
    results = _nn_retrain_all()
    
    return results


def get_nn_models_status() -> Dict[str, Dict]:
    """
    Obtiene el estado de todos los modelos de red neuronal.
    
    Returns:
        Dict con estado por tipo: {'gasto': {...}, 'ingreso': {...}, 'ahorro': {...}}
    """
    return _nn_get_status()


def project_with_nn(tipo: str, years_ahead: int = 5) -> Optional[Dict]:
    """
    Intenta proyectar usando red neuronal.
    
    Args:
        tipo: 'gasto', 'ingreso', o 'ahorro'
        years_ahead: Años a proyectar
        
    Returns:
        Dict con proyecciones o None si el modelo no está disponible
    """
    projector = get_or_create_projector(tipo)
    
    if not projector.is_trained:
        return None
    
    months_ahead = years_ahead * 12
    result = projector.predict(months_ahead)
    
    if result.get('success'):
        return result
    
    return None
