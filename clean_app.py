"""
Script para limpiar app.py eliminando las funciones ya extraídas.
"""
from pathlib import Path

# Leer app.py
app_path = Path("c:/Proyectos/FIN/PersAcc/app.py")
lines = app_path.read_text(encoding='utf-8').split('\n')

# Las funciones a eliminar están en estas líneas (según outline actualizado):
# render_cierre: 60-339
# render_historico: 346-630
# render_utilidades: 687-1126  
# render_manual: 637-684

# Identificar qué líneas mantener
# Mantenemos: 1-55 (config e imports) y 1127+ (main y resto)

# Nueva estructura:
# 1-55: Configuración e imports
# 56+: NAVEGACIÓN PRINCIPAL y main()

header_lines = lines[:55]  # Hasta antes de "# ============================================================================"

# Buscar donde empieza la sección "NAVEGACIÓN PRINCIPAL"
nav_start_idx = None
for i, line in enumerate(lines):
    if "# NAVEGACIÓN PRINCIPAL" in line:
        nav_start_idx = i - 2  # Incluir líneas vacías antes
        break

if nav_start_idx:
    footer_lines = lines[nav_start_idx:]
else:
    # Fallback: buscar def main()
    for i, line in enumerate(lines):
        if line.strip().startswith("def main()"):
            footer_lines = lines[i-5:]  # Incluir comentario y líneas vacías
            break

# Ensamblar nuevo app.py
new_content = '\n'.join(header_lines + ['\n', ''] + footer_lines)

# Guardar
app_path.write_text(new_content, encoding='utf-8')
print(f"✅ app.py limpiado!")
print(f"   Líneas originales: {len(lines)}")
print(f"   Líneas nuevas: {len(header_lines) + len(footer_lines)}")
