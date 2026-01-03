"""
Página Manual - PersAcc (Español)
Renderiza el manual completo de uso de la aplicación.
"""
import streamlit as st


def render_manual():
    """Renderiza el manual de uso completo de la aplicación en español."""
    st.markdown('<div class="main-header"><h1>📖 Manual de Uso - PersAcc</h1></div>', unsafe_allow_html=True)
    
    # ============================================================================
    # INTRODUCCIÓN
    # ============================================================================
    st.markdown("""
    ## 🎯 ¿Qué es PersAcc?
    
    **PersAcc** es un sistema de contabilidad personal con cierre mensual, retenciones automáticas y análisis de calidad del gasto.
    
    ### Características Principales
    
    - ✅ **Cierre de Mes Automático** - Wizard que calcula retenciones y abre el siguiente mes
    - ✅ **Retenciones Configurables** - Define % de ahorro sobre remanente y nómina
    - ✅ **Clasificación de Gastos** - Sistema NE/LI/SUP/TON para analizar hábitos
    - ✅ **Tabla Editable** - Modifica movimientos con validación de meses cerrados
    - ✅ **Dashboard Histórico** - KPIs anuales y evolución mensual
    - ✅ **Multi-idioma** - Español e Inglés
    - ✅ **Multi-divisa** - Configura tu moneda (€, $, £, etc.)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # FLUJO DE CIERRE DE MES
    # ============================================================================
    st.markdown("""
    ## 🔒 Cierre de Mes
    
    El cierre mensual es el corazón de PersAcc.
    
    ### ¿Cuándo cerrar?
    
    Una vez recibes el salario del mes siguiente (aunque sea el día 28), inicia el cierre del mes en curso.
    
    ### Pasos del Wizard
    
    1. **Ve a "Cierre de Mes"** - El sistema detecta automáticamente el próximo mes a cerrar
    
    2. **Ingresa el saldo del banco** - El valor exacto que aparece en tu cuenta
       - *Modo tradicional*: Saldo **antes** de cobrar la nómina
       - *Modo alternativo*: Saldo **después** de cobrar (configurable en ajustes)
    
    3. **Indica el salario** - El importe bruto de la nómina
    
    4. **Configura retenciones**:
       - **% Retención Remanente**: Del dinero sobrante antes del salario
       - **% Retención Salario**: Del nuevo salario recibido
    
    5. **Ejecuta el cierre** - El sistema:
       - Crea entradas de inversión automáticas
       - Genera el salario como ingreso en el nuevo mes
       - Cambia automáticamente al mes siguiente
    
    ### Resultado
    
    Mes cerrado e inmutable + próximo mes listo con saldo inicial correcto.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # AÑADIR MOVIMIENTOS
    # ============================================================================
    st.markdown("""
    ## ➕ Añadir Movimientos
    
    ### Quick Add (Sidebar)
    
    El formulario rápido en la barra lateral permite registrar gastos en segundos:
    
    1. Selecciona el **tipo** (Gasto, Ingreso, Inversión, Traspaso)
    2. Elige la **categoría**
    3. Escribe el **concepto**
    4. Selecciona **relevancia** (solo para gastos)
    5. Indica **fecha** e **importe**
    6. Click en **Guardar**
    
    > 💡 **Tip**: Si seleccionas un mes diferente al actual, la fecha por defecto será el día 1 de ese mes.
    
    ### Tabla Editable
    
    En la pestaña "Ledger" puedes editar movimientos existentes:
    - Modificar categoría, concepto, importe y relevancia
    - Seleccionar y eliminar múltiples entradas
    - Los meses cerrados están protegidos contra edición
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # RELEVANCIA DEL GASTO
    # ============================================================================
    st.markdown("""
    ## 🎯 Relevancia del Gasto
    
    Clasifica cada gasto para analizar tu comportamiento:
    
    | Código | Significado | Ejemplos |
    |--------|-------------|----------|
    | **NE** | Necesario | Comida, alquiler, facturas |
    | **LI** | Me gusta | Cenas con amigos, gym, hobbies |
    | **SUP** | Superfluo | Ropa extra, decoración |
    | **TON** | Tontería | Compras impulsivas, suscripciones no usadas |
    
    ### Objetivo
    
    Analizar qué % de tus gastos va a cada categoría. Ideal:
    - NE: 50-60%
    - LI: 20-30%
    - SUP: 10-15%
    - TON: < 5%
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CONFIGURACIÓN
    # ============================================================================
    st.markdown("""
    ## ⚙️ Configuración
    
    Accede desde **Utilidades → Configuración**.
    
    ### Opciones disponibles
    
    | Ajuste | Descripción |
    |--------|-------------|
    | **Idioma** | Español o Inglés |
    | **Divisa** | EUR, USD, GBP, y más |
    | **% Retención Remanente** | Valor por defecto para el wizard |
    | **% Retención Salario** | Valor por defecto para el wizard |
    | **Método de Cierre** | Antes o después de cobrar nómina |
    | **Conceptos default** | Texto sugerido por categoría |
    
    ### Archivo de configuración
    
    Se guarda automáticamente en `data/config.json`.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # UTILIDADES
    # ============================================================================
    st.markdown("""
    ## 🔧 Utilidades
    
    ### Exportar CSV
    Descarga todas las entradas del LEDGER en formato CSV para backup.
    
    ### Importar Legacy
    Importa datos desde archivos CSV (gastos, ingresos, inversiones).
    
    ### Limpiar BD
    - Borrar entradas y cierres (mantiene categorías)
    - Reset total (regenera todo desde cero)
    
    ### Gestión Categorías
    Añade, edita o elimina categorías. Las que tienen historial se archivan en lugar de borrarse.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # TIPS
    # ============================================================================
    st.markdown("""
    ## 💡 Tips
    
    1. **Registra gastos diariamente** - 2 minutos por la mañana
    2. **Revisa semanalmente** - Corrige categorías si es necesario
    3. **Cierra al recibir nómina** - No esperes al día 1
    4. **Exporta mensualmente** - Mantén un backup en la nube
    5. **Usa conceptos específicos** - "Mercadona" en lugar de "Compra"
    
    ---
    
    **Versión**: 1.2 | **Stack**: Streamlit + SQLite + Python
    """)
