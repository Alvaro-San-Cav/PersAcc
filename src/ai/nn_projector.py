"""
Modelo SARIMAX para Proyecciones Financieras.

Este módulo implementa un modelo SARIMAX (Seasonal ARIMA with eXogenous factors)
para proyecciones más robustas de gastos, ingresos y ahorros/inversiones.

SARIMAX es ideal para series temporales con pocos datos y estacionalidad.
"""

import numpy as np
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

import joblib

from src.database import get_all_ledger_entries, DEFAULT_DB_PATH
from src.models import TipoMovimiento

logger = logging.getLogger(__name__)

# Directorio para guardar modelos
MODELS_DIR = DEFAULT_DB_PATH.parent / "models"


class SARIMAXProjector:
    """
    Modelo SARIMAX para proyecciones financieras.
    
    SARIMAX captura tendencia y estacionalidad con pocos datos.
    Parámetros típicos: (1,1,1) x (1,1,1,12) para datos mensuales.
    """
    
    # Mapeo de tipos de proyección a TipoMovimiento
    TIPO_MAP = {
        'gasto': TipoMovimiento.GASTO,
        'ingreso': TipoMovimiento.INGRESO,
        'ahorro': TipoMovimiento.INVERSION,
    }
    
    def __init__(self, tipo: str):
        """
        Inicializa el proyector.
        
        Args:
            tipo: 'gasto', 'ingreso', o 'ahorro'
        """
        if tipo not in self.TIPO_MAP:
            raise ValueError(f"Tipo debe ser 'gasto', 'ingreso', o 'ahorro', no '{tipo}'")
        
        self.tipo = tipo
        self.tipo_movimiento = self.TIPO_MAP[tipo]
        self.model_fit = None
        self.is_trained = False
        self.train_date: Optional[datetime] = None
        self.metrics: Dict = {}
        self.monthly_data: Dict[str, float] = {}
        self.data_signature: Optional[Tuple[Tuple[str, float], ...]] = None
        
        # Paths de archivos
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.model_path = MODELS_DIR / f"{tipo}_sarimax_model.joblib"

    @staticmethod
    def _to_month_sort_key(month_key: str) -> Tuple[int, int]:
        """Convierte claves tipo YYYY-MM a una tupla ordenable (year, month)."""
        try:
            year_str, month_str = month_key.split("-", 1)
            return int(year_str), int(month_str)
        except Exception:
            # Fallback seguro si el formato no es estricto.
            return (9999, 12)

    @staticmethod
    def _next_month(month_key: str) -> str:
        """Devuelve el siguiente mes en formato YYYY-MM."""
        year, month = SARIMAXProjector._to_month_sort_key(month_key)
        month += 1
        if month > 12:
            month = 1
            year += 1
        return f"{year:04d}-{month:02d}"

    @staticmethod
    def _build_data_signature(monthly_data: Dict[str, float]) -> Tuple[Tuple[str, float], ...]:
        """Genera una firma estable para detectar cambios en los datos de entrenamiento."""
        sorted_items = sorted(
            monthly_data.items(),
            key=lambda item: SARIMAXProjector._to_month_sort_key(item[0])
        )
        return tuple((k, float(v)) for k, v in sorted_items)
    
    def _get_monthly_data(self) -> Dict[str, float]:
        """Obtiene datos agregados por mes."""
        entries = get_all_ledger_entries()
        filtered = [e for e in entries if e.tipo_movimiento == self.tipo_movimiento]
        
        monthly_data: Dict[str, float] = {}
        for e in filtered:
            monthly_data[e.mes_fiscal] = monthly_data.get(e.mes_fiscal, 0) + e.importe
        
        return monthly_data
    
    def train(self, force: bool = False) -> Dict:
        """
        Entrena el modelo SARIMAX con los datos actuales.
        
        Args:
            force: Si True, fuerza reentrenamiento
            
        Returns:
            Dict con resultados del entrenamiento
        """
        try:
            # Importar statsmodels aquí para evitar error si no está instalado
            try:
                from statsmodels.tsa.statespace.sarimax import SARIMAX
            except ImportError:
                return {
                    'success': False,
                    'error': 'statsmodels no está instalado. Ejecuta: pip install statsmodels'
                }
            
            self.monthly_data = self._get_monthly_data()
            current_signature = self._build_data_signature(self.monthly_data)

            if not force and self.load() and self.data_signature == current_signature:
                return {
                    'success': True,
                    'metrics': self.metrics,
                    'train_date': self.train_date.isoformat() if self.train_date else None,
                    'cached': True
                }
            
            if len(self.monthly_data) < 5:
                return {
                    'success': False,
                    'error': f'Datos insuficientes para {self.tipo} (mínimo 5 meses, tienes {len(self.monthly_data)})'
                }
            
            # Ordenar y preparar serie temporal
            sorted_months = sorted(
                self.monthly_data.keys(),
                key=self._to_month_sort_key
            )
            y = np.array([self.monthly_data[m] for m in sorted_months])
            
            # Determinar orden del modelo según cantidad de datos
            n_obs = len(y)
            
            if n_obs < 8:
                # Muy pocos datos: AR(1) puro primero (más estable), luego ARIMA(0,1,1).
                candidate_orders = [((1, 0, 0), (0, 0, 0, 0)), ((0, 1, 1), (0, 0, 0, 0))]
            elif n_obs < 12:
                candidate_orders = [((1, 1, 1), (0, 0, 0, 0)), ((1, 0, 1), (0, 0, 0, 0)), ((1, 0, 0), (0, 0, 0, 0))]
            elif n_obs < 24:
                candidate_orders = [((1, 1, 1), (1, 0, 0, 12)), ((1, 1, 0), (1, 0, 0, 12)), ((1, 1, 1), (0, 0, 0, 0))]
            else:
                candidate_orders = [((1, 1, 1), (1, 1, 1, 12)), ((1, 1, 0), (1, 1, 0, 12)), ((1, 1, 1), (1, 0, 0, 12))]

            last_error: Optional[Exception] = None
            chosen = None
            for order, seasonal_order in candidate_orders:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        model = SARIMAX(
                            y,
                            order=order,
                            seasonal_order=seasonal_order,
                            enforce_stationarity=False,
                            enforce_invertibility=False
                        )
                        self.model_fit = model.fit(disp=False, maxiter=1000)
                    chosen = (order, seasonal_order)
                    break
                except Exception as ex:
                    last_error = ex

            if chosen is None or self.model_fit is None:
                raise RuntimeError(f"No se pudo entrenar SARIMAX: {last_error}")

            order, seasonal_order = chosen
            
            # Calcular métricas
            fitted_values = np.asarray(self.model_fit.fittedvalues)
            residuals = y - fitted_values

            # SARIMAX con diferenciación (d≥1) produce NaN en los primeros periodos.
            # Filtrar posiciones válidas (ni y ni fitted_values son NaN, y |y| > 0).
            finite_mask = np.isfinite(residuals) & np.isfinite(fitted_values)
            abs_y = np.abs(y)
            valid_mask = finite_mask & (abs_y > 1e-8)

            if np.any(valid_mask):
                mape = np.mean(np.abs(residuals[valid_mask] / y[valid_mask])) * 100
            else:
                mape = 0.0

            # sMAPE más estable cerca de cero.
            if np.any(finite_mask):
                smape = np.mean(
                    (2.0 * np.abs(residuals[finite_mask]))
                    / (np.abs(y[finite_mask]) + np.abs(fitted_values[finite_mask]) + 1e-8)
                ) * 100
            else:
                smape = 0.0

            # MAE / RMSE solo sobre periodos con residuos válidos.
            if np.any(finite_mask):
                mae = float(np.mean(np.abs(residuals[finite_mask])))
                rmse = float(np.sqrt(np.mean(np.square(residuals[finite_mask]))))
            else:
                mae = 0.0
                rmse = 0.0

            # Pseudo-R²: proporción de varianza explicada por el modelo.
            # Clamp a [0, 1]: puede ser negativo si el modelo es peor que la media.
            y_valid = y[finite_mask] if np.any(finite_mask) else y
            ss_res = float(np.sum(np.square(residuals[finite_mask]))) if np.any(finite_mask) else 0.0
            ss_tot = float(np.sum(np.square(y_valid - np.mean(y_valid))))
            r2 = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 1e-8 else 0.0

            self.metrics = {
                'mape': min(mape, 100),  # Cap at 100%
                'smape': min(smape, 100),
                'mae': mae,
                'rmse': rmse,
                'r2': round(r2, 4),
                'n_samples': n_obs,
                'order': order,
                'seasonal_order': seasonal_order
            }
            
            self.is_trained = True
            self.train_date = datetime.now()
            self.data_signature = current_signature
            
            # Guardar modelo
            self.save()
            
            return {
                'success': True,
                'metrics': self.metrics,
                'train_date': self.train_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error entrenando modelo SARIMAX {self.tipo}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def predict(self, months_ahead: int = 12) -> Dict:
        """
        Genera proyecciones para los próximos N meses.
        
        Args:
            months_ahead: Número de meses a proyectar
            
        Returns:
            Dict con proyecciones mensuales y anuales
        """
        if not self.is_trained or self.model_fit is None:
            # Intentar cargar modelo guardado
            if not self.load():
                return {
                    'success': False,
                    'error': 'Modelo no entrenado'
                }
        
        if months_ahead <= 0:
            return {
                'success': False,
                'error': 'months_ahead debe ser mayor que 0'
            }

        try:
            # Generar predicciones
            forecast_result = self.model_fit.get_forecast(steps=months_ahead)
            forecast = forecast_result.predicted_mean
            conf_int = forecast_result.conf_int(alpha=0.20)  # Intervalo del 80%
            conf_int_values = np.asarray(conf_int)
            
            # Asegurar valores no negativos
            forecast = np.maximum(forecast, 0)
            
            # Organizar por año desde el mes siguiente al último dato histórico.
            if self.monthly_data:
                last_month = max(self.monthly_data.keys(), key=self._to_month_sort_key)
                start_month = self._next_month(last_month)
                start_year, start_month_num = self._to_month_sort_key(start_month)
            else:
                current_date = date.today()
                start_year, start_month_num = current_date.year, current_date.month

            projections_by_year: Dict[int, List[float]] = {}
            lower_by_year: Dict[int, List[float]] = {}
            upper_by_year: Dict[int, List[float]] = {}
            
            for i, value in enumerate(forecast):
                future_month = start_month_num + i
                future_year = start_year
                
                while future_month > 12:
                    future_month -= 12
                    future_year += 1
                
                if future_year not in projections_by_year:
                    projections_by_year[future_year] = []
                    lower_by_year[future_year] = []
                    upper_by_year[future_year] = []
                projections_by_year[future_year].append(float(value))
                lower_by_year[future_year].append(float(max(conf_int_values[i, 0], 0)))
                upper_by_year[future_year].append(float(max(conf_int_values[i, 1], 0)))
            
            # Calcular totales anuales
            annual_projections = {}
            for year, values in projections_by_year.items():
                annual_projections[year] = {
                    'monthly_values': values,
                    'monthly_avg': float(np.mean(values)),
                    'annual_total': float(np.sum(values)),
                    'annualized_total': float(np.mean(values) * 12),
                    'interval_80': {
                        'lower': lower_by_year[year],
                        'upper': upper_by_year[year]
                    }
                }
            
            return {
                'success': True,
                'projected': annual_projections,
                'historical': self.monthly_data,
                'model_metrics': self.metrics,
                'train_date': self.train_date.isoformat() if self.train_date else None
            }
            
        except Exception as e:
            logger.error(f"Error prediciendo con modelo SARIMAX {self.tipo}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def save(self):
        """Guarda el modelo en disco."""
        if not self.is_trained:
            return
        
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
        joblib.dump({
            'model_fit': self.model_fit,
            'is_trained': self.is_trained,
            'train_date': self.train_date,
            'metrics': self.metrics,
            'monthly_data': self.monthly_data,
            'data_signature': self.data_signature,
            'tipo': self.tipo
        }, self.model_path)
    
    def load(self) -> bool:
        """Carga el modelo desde disco."""
        if not self.model_path.exists():
            return False
        
        try:
            data = joblib.load(self.model_path)
            self.model_fit = data['model_fit']
            self.is_trained = data['is_trained']
            self.train_date = data['train_date']
            self.metrics = data['metrics']
            self.monthly_data = data.get('monthly_data', {})
            self.data_signature = data.get('data_signature')
            return True
        except Exception as e:
            logger.error(f"Error cargando modelo SARIMAX {self.tipo}: {e}")
            return False


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def get_or_create_projector(tipo: str) -> SARIMAXProjector:
    """Obtiene un proyector, cargándolo desde disco si existe."""
    projector = SARIMAXProjector(tipo)
    projector.load()
    return projector


def retrain_all_models() -> Dict[str, Dict]:
    """Reentrena todos los modelos SARIMAX."""
    results = {}
    for tipo in ['gasto', 'ingreso', 'ahorro']:
        projector = SARIMAXProjector(tipo)
        results[tipo] = projector.train(force=True)
    return results


def get_all_models_status() -> Dict[str, Dict]:
    """Obtiene el estado de todos los modelos."""
    status = {}
    for tipo in ['gasto', 'ingreso', 'ahorro']:
        projector = SARIMAXProjector(tipo)
        loaded = projector.load()
        status[tipo] = {
            'is_trained': projector.is_trained,
            'train_date': projector.train_date.isoformat() if projector.train_date else None,
            'metrics': projector.metrics if loaded else {},
            'model_exists': projector.model_path.exists()
        }
    return status
