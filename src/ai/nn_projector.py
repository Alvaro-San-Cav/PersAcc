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
from typing import Dict, List, Optional
import logging

import joblib

from src.database import get_all_ledger_entries, DEFAULT_DB_PATH
from src.models import TipoMovimiento

logger = logging.getLogger(__name__)

# Directorio para guardar modelos
MODELS_DIR = DEFAULT_DB_PATH.parent / "models"

# Suprimir warnings de convergencia de statsmodels
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)


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
        self.model = None
        self.model_fit = None
        self.is_trained = False
        self.train_date: Optional[datetime] = None
        self.metrics: Dict = {}
        self.monthly_data: Dict[str, float] = {}
        
        # Paths de archivos
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.model_path = MODELS_DIR / f"{tipo}_sarimax_model.joblib"
    
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
            
            if len(self.monthly_data) < 4:
                return {
                    'success': False,
                    'error': f'Datos insuficientes para {self.tipo} (mínimo 4 meses, tienes {len(self.monthly_data)})'
                }
            
            # Ordenar y preparar serie temporal
            sorted_months = sorted(self.monthly_data.keys())
            y = np.array([self.monthly_data[m] for m in sorted_months])
            
            # Determinar orden del modelo según cantidad de datos
            n_obs = len(y)
            
            if n_obs < 6:
                # Muy pocos datos: modelo simple sin estacionalidad
                order = (1, 0, 0)
                seasonal_order = (0, 0, 0, 0)
            elif n_obs < 12:
                # Pocos datos: ARIMA simple
                order = (1, 1, 1)
                seasonal_order = (0, 0, 0, 0)
            elif n_obs < 24:
                # Datos moderados: SARIMA con estacionalidad básica
                order = (1, 1, 1)
                seasonal_order = (1, 0, 0, 12)
            else:
                # Suficientes datos: SARIMA completo
                order = (1, 1, 1)
                seasonal_order = (1, 1, 1, 12)
            
            # Entrenar modelo
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.model = SARIMAX(
                    y,
                    order=order,
                    seasonal_order=seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
                self.model_fit = self.model.fit(disp=False, maxiter=200)
            
            # Calcular métricas
            fitted_values = self.model_fit.fittedvalues
            residuals = y - fitted_values
            
            # MAPE (Mean Absolute Percentage Error)
            mape = np.mean(np.abs(residuals / (y + 1e-10))) * 100
            
            # MAE
            mae = np.mean(np.abs(residuals))
            
            self.metrics = {
                'mape': min(mape, 100),  # Cap at 100%
                'mae': mae,
                'n_samples': n_obs,
                'order': order,
                'seasonal_order': seasonal_order
            }
            
            self.is_trained = True
            self.train_date = datetime.now()
            
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
        
        try:
            # Generar predicciones
            forecast = self.model_fit.forecast(steps=months_ahead)
            
            # Asegurar valores no negativos
            forecast = np.maximum(forecast, 0)
            
            # Organizar por año
            current_date = date.today()
            projections_by_year: Dict[int, List[float]] = {}
            
            for i, value in enumerate(forecast):
                future_month = current_date.month + i
                future_year = current_date.year
                
                while future_month > 12:
                    future_month -= 12
                    future_year += 1
                
                if future_year not in projections_by_year:
                    projections_by_year[future_year] = []
                projections_by_year[future_year].append(float(value))
            
            # Calcular totales anuales
            annual_projections = {}
            for year, values in projections_by_year.items():
                annual_projections[year] = {
                    'monthly_values': values,
                    'monthly_avg': np.mean(values),
                    'annual_total': np.sum(values) if len(values) == 12 else np.mean(values) * 12
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
