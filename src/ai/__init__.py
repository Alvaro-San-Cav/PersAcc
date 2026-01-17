"""
Módulo de Inteligencia Artificial para PersAcc.

Este paquete contiene todos los componentes relacionados con IA:
- llm_service: Servicio de LLM/Ollama para análisis de texto
- prompts: Plantillas de prompts para LLM
- ml_engine: Motor de Machine Learning para proyecciones

Uso:
    from src.ai import llm_service, ml_engine
    from src.ai.prompts import QUICK_SUMMARY_ES
"""

# Re-exportar funciones principales para facilitar imports
from src.ai.llm_service import (
    is_llm_enabled,
    check_ollama_running,
    get_available_models,
    generate_quick_summary,
    analyze_financial_period,
    get_llm_config
)

from src.ai.ml_engine import (
    project_salaries,
    project_investments,
    project_expenses,
    generate_insights,
    get_projection_summary
)
