"""
Script para extraer automáticamente las funciones render de app.py a módulos separados.
"""
from pathlib import Path
import re

# Leer app.py
app_path = Path("c:/Proyectos/FIN/PersAcc/app.py")
content = app_path.read_text(encoding='utf-8')

# Definir las funciones a extraer con sus líneas (según el outline)
functions_to_extract = {
    "render_cierre": (56, 335, "cierre.py", "Página de Cierre de Mes - PersAcc"),
    "render_historico": (342, 626, "historico.py", "Página de Histórico Anual - PersAcc"),
    "render_utilidades": (683, 1122, "utilidades.py", "Página de Utilidades - PersAcc"),
}

# Leer todas las líneas
lines = content.split('\n')

# Procesar cada función
for func_name, (start, end, filename, description) in functions_to_extract.items():
    print(f"Extrayendo {func_name} (líneas {start}-{end}) → {filename}")
    
    # Extraer código de la función (ajustar índices: líneas son 1-indexed)
    func_lines = lines[start-1:end]
    func_code = '\n'.join(func_lines)
    
    # Crear contenido del módulo
    module_content = f'''"""
{description}
Renderiza la interfaz de {func_name.replace('render_', '')}.
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


{func_code}
'''
    
    # Guardar módulo
    output_path = Path(f"c:/Proyectos/FIN/PersAcc/src/ui/{filename}")
    output_path.write_text(module_content, encoding='utf-8')
    print(f"✅ Creado: {output_path}")

print("\n✅ Extracción completada!")
