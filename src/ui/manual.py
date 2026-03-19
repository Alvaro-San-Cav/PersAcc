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
    
    -  **Cierre de Mes Automático** - Wizard que calcula retenciones y abre el siguiente mes
    -  **Retenciones Configurables** - Define % de ahorro sobre remanente y nómina
    -  **Clasificación de Gastos** - Sistema NE/LI/SUP/TON para analizar hábitos
    -  **Ordenamiento Inteligente** - Categorías se ordenan por uso histórico
    -  **Conceptos Automáticos** - Auto-completa conceptos según categoría
    -  **Cuenta de Consecuencias** - Reglas automáticas para costes ocultos
    -  **Tabla Editable** - Modifica movimientos con validación de meses cerrados
    -  **Dashboard Histórico** - KPIs anuales y evolución mensual
    -  **🤖 IA con Ollama** - Comentarios inteligentes y análisis profundo
    -  **📈 Proyecciones ML** - Predicciones de gastos e inversiones/ahorros
    -  **💬 Chat Asistente** - Pregunta sobre tus finanzas en lenguaje natural
    -  **📝 Anotaciones** - Notas personales por período
    -  **Multi-idioma** - Español e Inglés
    -  **Multi-divisa** - Configura tu moneda (€, $, £, etc.)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # AÑADIR MOVIMIENTOS
    # ============================================================================
    st.markdown("""
    ## ➕ Añadir Movimientos
    
    ### Quick Add (Sidebar)
    
    El formulario rápido en la barra lateral permite registrar gastos en segundos:
    
    1. **Fecha** - Selecciona el día del movimiento
       > 💡 **Tip**: Si seleccionas un mes diferente al actual en la navegación principal, la fecha por defecto será el día 1 de ese mes.
    
    2. **Tipo** - Selecciona entre:
       - **Gasto** - Cualquier salida de dinero
       - **Ingreso** - Entradas de dinero (salarios, regalos, etc.)
       - **Inversión/Ahorro** - Ahorros o inversiones
       - **Traspaso Entrada/Salida** - Movimientos entre cuentas
    
    3. **Categoría** - Elige la categoría apropiada
       > 🌟 **NUEVO**: Las categorías se ordenan inteligentemente según tu historial:
       > - **Primero**: Categorías más usadas en este mes en años anteriores
       > - **Segundo**: Categorías más usadas este año
       > - **Tercero**: Orden alfabético
    
    4. **Concepto** - Describe el movimiento
       > 🌟 **NUEVO**: El concepto se auto-completa si has configurado un valor por defecto para esa categoría.
       > Configúralo en: **Utilidades → Configuración → Conceptos default**
    
    5. **Relevancia** (solo para gastos) - Clasifica la calidad del gasto
    
    6. **Importe** - Introduce la cantidad
    
    7. **Guardar** - Click en el botón para registrar
    
    ### Tabla Editable (Ledger)
    
    En la pestaña "Ledger" puedes editar movimientos existentes:
    
    - ✏️ **Edición inline**: Click en cualquier celda para modificar categoría, concepto, importe o relevancia
    - 🗑️ **Eliminación múltiple**: Selecciona varias filas y elimínalas de golpe
    - 🔒 **Protección**: Los meses cerrados están bloqueados contra edición
    
    > ⚠️ **Importante**: No puedes editar ni eliminar entradas de meses cerrados.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # RELEVANCIA DEL GASTO
    # ============================================================================
    st.markdown("""
    ## 🎯 Relevancia del Gasto
    
    Clasifica cada gasto para analizar tu comportamiento de consumo:
    
    | Código | Significado | Ejemplos |
    |--------|-------------|----------|
    | **NE** | Necesario | Comida, alquiler, facturas, transporte |
    | **LI** | Me gusta | Cenas con amigos, gym, hobbies, ocio |
    | **SUP** | Superfluo | Ropa extra, decoración, caprichos |
    | **TON** | Tontería | Compras impulsivas, suscripciones no usadas |
    
    ### Objetivo
    
    Analizar qué % de tus gastos va a cada categoría. **Distribución ideal**:
    - NE: 50-60%
    - LI: 20-30%
    - SUP: 10-15%
    - TON: < 5%
    
    > 💡 **Tip**: Puedes desactivar el análisis de relevancia en **Configuración** si no lo usas.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CUENTA DE CONSECUENCIAS
    # ============================================================================
    st.markdown("""
    ## 🧮 Cuenta de Consecuencias
    
    > 🌟 **Funcionalidad avanzada**: Rastrea costes ocultos automáticamente.
    
    ### ¿Qué es?
    
    Un sistema de reglas que aplica automáticamente "consecuencias" (costes adicionales) a tus gastos durante el cierre de mes.
    
    ### Casos de uso
    
    **Ejemplo 1: Impuestos**
    - Regla: Todos los gastos **SUP** tienen un 10% de "impuesto psicológico"
    - Efecto: Si gastas 100€ en SUP, el sistema contabiliza 10€ extra de consecuencia
    
    **Ejemplo 2: Penalización por tonterías**
    - Regla: Cada gasto **TON** genera un 50% de penalización
    - Efecto: Incentiva reducir gastos innecesarios
    
    ### Configuración
    
    1. **Activa la funcionalidad**: **Utilidades → Configuración → Cuenta de Consecuencias**
    2. **Crea reglas**: **Utilidades → Consecuencias**
    
    Cada regla tiene:
    - **Nombre**: Identificador de la regla
    - **Filtros** (opcionales):
      - Relevancia (NE/LI/SUP/TON)
      - Categoría específica
      - Concepto (contiene texto)
    - **Acción**:
      - **Porcentaje**: X% del gasto filtrado
      - **Cantidad fija**: X€ por cada gasto que cumpla el filtro
    
    ### ¿Cuándo se aplica?
    
    Al ejecutar el **Cierre de Mes**, el sistema:
    1. Evalúa todas las reglas activas
    2. Calcula las consecuencias totales
    3. Crea una entrada de **Inversión/Ahorro** automática con ese importe
    4. Puedes verlo en el resumen del cierre
    
    > 💡 **Tip**: Usa esta funcionalidad para forzar ahorro extra basado en tus hábitos.
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
    
    5. **Revisa las consecuencias** (si está activado):
       - El sistema muestra el total de consecuencias calculado según tus reglas
       - Esto se sumará automáticamente como inversión/ahorro
    
    6. **Ejecuta el cierre** - El sistema:
       - Crea entradas de inversión/ahorro automáticas (retenciones + consecuencias)
       - Genera el salario como ingreso en el nuevo mes
       - Marca el mes como CERRADO e inmutable
       - Cambia automáticamente al mes siguiente
    
    ### Resultado
    
    Mes cerrado e inmutable + próximo mes listo con saldo inicial correcto.
    
    > 💡 **Tip**: Puedes desactivar las retenciones automáticas en **Configuración** si prefieres gestionarlas manualmente.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CONFIGURACIÓN
    # ============================================================================
    st.markdown("""
    ## ⚙️ Configuración
    
    Accede desde **Utilidades → Configuración**.
    
    ### Opciones disponibles
    
    #### 🌐 Idioma & Divisa
    
    | Ajuste | Opciones |
    |--------|----------|
    | **Idioma** | Español, English |
    | **Divisa** | EUR, USD, GBP, CHF, JPY, MXN |
    
    #### 🎛️ Funcionalidades (Toggles)
    
    | Toggle | Descripción |
    |--------|-------------|
    | **🌙 Modo Oscuro** | Tema oscuro aplicado a toda la interfaz |
    | **Análisis de Relevancia** | Sistema NE/LI/SUP/TON |
    | **Retenciones Automáticas** | Inversiones/Ahorros automáticos en cierre |
    | **Cuenta de Consecuencias** | Sistema de reglas avanzado |
    | **🤖 Análisis con IA** | Comentarios inteligentes con Ollama |
    
    #### 🤖 Configuración de IA (Ollama)
    
    > Requiere [Ollama](https://ollama.com/download) instalado y ejecutándose.
    
    Puedes asignar un **modelo diferente por tarea**:
    
    | Tarea | Recomendación |
    |-------|---------------|
    | **Análisis Histórico** | Modelos pesados (mistral, qwen3:8b) |
    | **Asistente Chat** | Modelos medios/pesados |
    | **Resúmenes Dashboard** | Modelos ligeros/rápidos (tinyllama, phi3) |
    | **Carga de Ficheros** | Modelos medios/pesados |
    
    > 💡 **Tip**: Usa modelos ligeros para resúmenes y modelos pesados para análisis profundo.
    
    #### 💰 Retenciones
    
    | Ajuste | Descripción |
    |--------|-------------|
    | **% Retención Remanente** | Valor por defecto para el wizard (0-100%) |
    | **% Retención Salario** | Valor por defecto para el wizard (0-100%) |
    
    #### 🏦 Enlace al Banco
    
    Configura la URL de tu banca online. Aparecerá un botón de acceso rápido en la barra lateral.
    
    #### 📊 Método de Cierre
    
    | Método | Descripción |
    |--------|-------------|
    | **Antes de salario** | Introduces el saldo ANTES de cobrar la nómina (recomendado) |
    | **Después de salario** | Introduces el saldo DESPUÉS de cobrar |
    
    #### 📲 Integración con Notion
    
    Conecta PersAcc con una base de datos de Notion para importar movimientos:
    
    | Ajuste | Descripción |
    |--------|-------------|
    | **Activar Notion** | Toggle para habilitar la integración |
    | **API Token** | Token de tu integración Notion (notion.so/my-integrations) |
    | **Database ID** | UUID de tu base de datos Notion |
    | **Comprobar al inicio** | Verificar automáticamente si hay entradas pendientes al abrir la app |
    
    #### 📂 Carga Automática (Deduplicación)
    
    Controla cómo se detectan duplicados al cargar ficheros bancarios:
    
    | Ajuste | Descripción |
    |--------|-------------|
    | **Deduplicación activa** | Filtrar automáticamente entradas ya existentes |
    | **Solo mismo tipo** | Comparar solo movimientos del mismo tipo |
    | **Tolerancia importe** | Diferencia máxima aceptada (€) |
    | **Ventana de fechas** | Días de margen para considerar duplicado |
    | **Umbral texto** | Similitud mínima en concepto |
    | **Puntuación mínima** | Score total mínimo para marcar como duplicado |
    | **Ignorar fuera del período** | Descartar movimientos de meses anteriores |
    
    #### 📝 Valores por Defecto
    
    Configura valores automáticos para cada categoría:
    
    | Tipo | Descripción |
    |------|-------------|
    | **Conceptos default** | Texto que se auto-completa al seleccionar la categoría |
    | **Importes default** | Cantidad que se rellena automáticamente |
    | **Relevancias default** | Código NE/LI/SUP/TON predeterminado |
    
    > 💡 **Tip**: Configura valores por defecto para gastos recurrentes y ahorra tiempo.
    
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
    Descarga todas las entradas del LEDGER en formato CSV para backup o análisis externo.
    
    ### Importar Legacy
    Importa datos desde archivos CSV antiguos:
    - **Gastos**: DATE, CONCEPT, CATEGORY, RELEVANCE, AMOUNT
    - **Ingresos**: DATE, CONCEPT, AMOUNT
    - **Inversiones/Ahorros**: DATE, CONCEPT, AMOUNT, CATEGORY
    
    ### Limpiar BD
    - **Opción 1**: Borrar entradas y cierres (mantiene categorías)
    - **Opción 2**: Reset total (regenera todo desde cero)
    
    > ⚠️ **Importante**: Estas acciones son irreversibles. Exporta un backup antes.
    
    ### Gestión Categorías
    - Añade, edita o elimina categorías
    - Las categorías con historial se archivan en lugar de borrarse
    - Puedes cambiar el tipo de movimiento (GASTO→INVERSIÓN/AHORRO, etc.)
    - **Descripción IA** (opcional): Añade una descripción a cada categoría para que la IA clasifique mejor los movimientos al importar ficheros bancarios
    
    ### Consecuencias
    > Requiere activar en Configuración
    
    Gestiona tus reglas de consecuencias:
    - Crea/edita/elimina reglas
    - Activa/desactiva reglas específicas
    - Los cambios se aplican en el próximo cierre de mes
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # DASHBOARD Y ANÁLISIS
    # ============================================================================
    st.markdown("""
    ## 📊 Dashboard y Análisis
    
    ### Visión Mensual
    
    La pantalla principal muestra:
    - **KPIs del mes**: Ingresos, gastos, inversión/ahorro, saldo
    - **Tabla de movimientos**: Editable (si el mes está abierto)
    - **Análisis de relevancia**: Distribución NE/LI/SUP/TON
    
    ### Histórico
    
    Accede desde **Historial** para ver:
    
    #### 📈 Visión Global
    - KPIs acumulados del año
    - Evolución mensual (gráfico de áreas)
    - Comparativa año actual vs promedio histórico
    
    #### 🔍 Análisis Profundo
    - Top gastos del año
    - Evolución por categoría
    - Análisis de palabras más usadas en conceptos
    - Métricas curiosas (gasto promedio por día, etc.)
    
    #### 📋 Datos Detallados
    - Tabla completa de movimientos del año
    - Filtrable y exportable
    
    #### 📝 Anotaciones
    - Añade notas personales por mes o año
    - Recuerda decisiones, contexto o reflexiones
    - Se muestran en modo solo lectura al revisar períodos cerrados
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # INTELIGENCIA ARTIFICIAL
    # ============================================================================
    st.markdown("""
    ## 🤖 Inteligencia Artificial (Ollama)
    
    PersAcc incluye integración con IA local usando [Ollama](https://ollama.com).
    
    ### Requisitos
    
    1. **Instalar Ollama**: Descarga desde [ollama.com/download](https://ollama.com/download)
    2. **Descargar modelo**: Ejecuta `ollama pull phi3` (o tinyllama, mistral, llama3, qwen3)
    3. **Mantener Ollama ejecutándose**: El servidor local debe estar activo
    
    ### Funcionalidades IA
    
    #### 💬 Comentario del Ledger
    En la vista mensual, la IA genera un comentario ingenioso sobre tus finanzas del mes.
    
    #### 📊 Análisis de Período
    En Histórico, genera análisis profundo del mes o año seleccionado:
    - Evaluación de patrones de gasto
    - Recomendaciones personalizadas
    - Insights sobre categorías
    
    #### 💬 Chat Asistente
    Pregunta en lenguaje natural sobre tus finanzas:
    - "¿Cuánto gasté en restaurantes este mes?"
    - "¿Cuáles son mis mayores gastos del 2024?"
    - "Busca gastos de Uber"
    
    ### Configuración
    
    1. Activa en **Utilidades → Configuración → Análisis con IA**
    2. Selecciona el modelo en la sección **Configuración del Modelo IA**
    3. El indicador verde confirma que Ollama está funcionando
    
    > 💡 **Modelos recomendados**: phi3 (equilibrado), tinyllama (rápido), mistral (calidad)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # PROYECCIONES ML
    # ============================================================================
    st.markdown("""
    ## 📈 Proyecciones (Machine Learning)
    
    Accede desde la pestaña **Proyecciones** para ver predicciones basadas en tu historial.
    
    ### Modelo SARIMAX
    
    Las proyecciones usan **SARIMAX** (Seasonal ARIMA with eXogenous factors), un modelo estadístico robusto para series temporales con estacionalidad. El modelo se entrena automáticamente con tus datos y se guarda en caché (`data/models/`) para mayor velocidad.
    
    ### Tipos de Proyección
    
    #### 💰 Proyección de Ingresos
    - Evolución estimada del salario
    - Basada en histórico de ingresos
    
    #### 📊 Proyección de Inversiones/Ahorros
    - Crecimiento proyectado del capital invertido
    - Considera retenciones automáticas
    
    #### 📉 Proyección de Gastos
    - Predicción de gastos futuros
    - Análisis por categoría y temporalidad
    
    ### Insights Automáticos
    
    El sistema genera insights sobre tus patrones:
    - Tendencias de ahorro
    - Meses de mayor gasto
    - Evolución del patrimonio
    - Intervalos de confianza (80%) para cada predicción
    
    > ⚠️ **Nota**: Las proyecciones mejoran con más datos históricos. Se recomienda tener al menos 6 meses de historial (mínimo 4 meses para que el modelo entrene).
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # INTEGRACIÓN NOTION
    # ============================================================================
    st.markdown("""
    ## 📲 Integración con Notion
    
    PersAcc puede sincronizar movimientos desde una base de datos de Notion.
    
    ### Configuración
    
    1. **Crea una integración** en [notion.so/my-integrations](https://www.notion.so/my-integrations)
    2. **Comparte la base de datos** con tu integración (botón Compartir → invitar)
    3. **Configura en PersAcc**: **Utilidades → Configuración → Notion**
       - Introduce el **API Token** y el **Database ID** (UUID de la URL)
       - Activa la integración
    
    ### Propiedades esperadas en Notion
    
    | Propiedad | Tipo | Descripción |
    |-----------|------|-------------|
    | **Concepto** | title | Descripción del movimiento (requerido) |
    | **Importe** | number | Cantidad (requerido) |
    | **Tipo** | select | Gasto, Ingreso, Inversión, etc. |
    | **Categoría** | select/text | Categoría del movimiento |
    | **Relevancia** | select | NE, LI, SUP, TON |
    | **Fecha** | date | Fecha del movimiento |
    
    > 💡 Los nombres de las propiedades se adaptan automáticamente según el idioma configurado.
    
    ### Flujo de sincronización
    
    1. **Al abrir la app** (si "Comprobar al inicio" está activo), se buscan entradas pendientes
    2. Se muestra un diálogo con las entradas encontradas
    3. Para cada entrada puedes:
       - **✅ Importar**: La graba en el LEDGER y la elimina de Notion
       - **🗑️ Eliminar**: Solo la elimina de Notion
       - **⏭️ Omitir**: La deja en Notion (si editas campos, se actualizan en Notion)
    4. También puedes lanzar una **sincronización manual** desde Configuración
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CARGA DE DATOS BANCARIOS
    # ============================================================================
    st.markdown("""
    ## 📂 Carga de Datos Bancarios
    
    > 🌟 Requiere **IA activada** (Ollama funcionando).
    
    Importa movimientos directamente desde ficheros de tu banco.
    
    ### Formatos soportados
    
    | Formato | Extensiones | Notas |
    |---------|-------------|-------|
    | **AEB Norma 43** | `.csb`, `.aeb`, `.txt`, `.n43` | Estándar bancario español |
    | **AEB SEPA** | Mismas extensiones | Detección automática por divisa |
    | **Excel** | `.xlsx`, `.xls` | Primera hoja del archivo |
    
    ### Cómo funciona
    
    1. **Sube el fichero** desde la pestaña "Cargar Datos"
    2. **Previsualización**: Revisa que el contenido se ha parseado correctamente
    3. **Análisis con IA**: El modelo clasifica cada movimiento (tipo, categoría, concepto limpio, relevancia)
       - Se procesan en lotes de 5 movimientos para mayor precisión
       - Se muestra una barra de progreso con el estado
    4. **Revisión**: Los resultados se separan en:
       - ✅ **Bien clasificadas**: Confianza ≥ 75%
       - ⚠️ **A revisar**: Confianza < 75% (edita antes de grabar)
       - 🚫 **Ignoradas**: Duplicados detectados o fuera del período
    5. **Grabación**: Selecciona las entradas y grábalas en el LEDGER
    
    ### Motor de deduplicación
    
    El sistema detecta automáticamente posibles duplicados comparando con el LEDGER existente:
    - **Importe**: Coincidencia exacta o dentro de tolerancia
    - **Fecha**: Dentro de una ventana de días configurable
    - **Concepto**: Similitud de texto normalizado
    - **Score combinado**: Fórmula ponderada (75% importe + 20% fecha + 5% texto)
    
    > 💡 **Tip**: Ajusta los parámetros de deduplicación en **Configuración → Carga Automática** para adaptarlos a tu banco.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # TIPS Y MEJORES PRÁCTICAS
    # ============================================================================
    st.markdown("""
    ## 💡 Tips y Mejores Prácticas
    
    ### 📱 Uso Diario
    1. **Registra gastos diariamente** - 2 minutos por la mañana con el café
    2. **Usa conceptos específicos** - "Mercadona - Frutas" mejor que "Compra"
    3. **Aprovecha el auto-completado** - Configura conceptos default para ahorrar tiempo
    4. **Usa Notion** - Si prefieres apuntar desde el móvil, registra en Notion y sincroniza después
    
    ### 📅 Uso Semanal
    1. **Revisa el dashboard** - Verifica que todo esté bien categorizado
    2. **Corrige errores** - Usa la tabla editable si te equivocaste
    
    ### 🗓️ Uso Mensual
    1. **Cierra al recibir nómina** - No esperes al día 1 del mes siguiente
    2. **Exporta backup** - Descarga CSV antes de cerrar
    3. **Revisa análisis de relevancia** - Ajusta hábitos si es necesario
    4. **Carga el extracto del banco** - Usa "Cargar Datos" para importar el fichero bancario y verificar que no falta nada
    
    ### 🎯 Optimización
    1. **Ajusta las retenciones** - Según tus objetivos de ahorro
    2. **Experimenta con consecuencias** - Crea reglas que te motiven a mejorar
    3. **Desactiva lo que no uses** - Simplifica desactivando funciones innecesarias
    4. **Descripciones IA en categorías** - Añade descripciones para que la IA clasifique mejor los ficheros bancarios
    
    ### 🔒 Seguridad
    1. **Backup regular** - La base de datos está en `data/finanzas.db`
    2. **Control de versiones** - Considera usar Git para trackear cambios
    3. **Portabilidad** - Toda la configuración está en ficheros locales
    
    ---
    
    **Versión**: 3.1 | **Stack**: Streamlit + SQLite + Python + Ollama
    
    *¿Dudas o sugerencias? Abre un issue en el repositorio.*
    """)
