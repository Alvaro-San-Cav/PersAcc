"""
Página Manual - PersAcc
Renderiza el manual completo de uso de la aplicación con documentación detallada.
"""
import streamlit as st


def render_manual():
    """Renderiza el manual de uso completo de la aplicación."""
    st.markdown('<div class="main-header"><h1>📖 Manual Completo de PersAcc</h1></div>', unsafe_allow_html=True)
    
    # ============================================================================
    # INTRODUCCIÓN
    # ============================================================================
    st.markdown("""
    ## 🎯 ¿Qué es PersAcc y para qué sirve?
    
    **PersAcc** (Personal Accounting) es un sistema de contabilidad personal diseñado para tener control total sobre tus finanzas mensuales. A diferencia de aplicaciones simples de registro de gastos, PersAcc implementa una **metodología contable completa** que te permite:
    
    - **Cerrar meses fiscales** de forma ordenada, creando snapshots inmutables de tu situación financiera
    - **Automatizar el ahorro e inversión** mediante retenciones configurables al cerrar cada mes
    - **Clasificar gastos por relevancia** (Necesario, Me gusta, Superfluo, Tontería) para analizar tu comportamiento financiero
    - **Mantener histórico completo e inmutable** de todos tus movimientos financieros con integridad referencial
    
    **Filosofía central**: El sistema asume que eres disciplinado con el ahorro. Al cerrar cada mes, defines qué porcentaje del saldo sobrante y de tu próxima nómina destinas a inversión/ahorro. Estas cantidades se registran automáticamente como movimientos, reduciendo tu "saldo operativo" (el dinero realmente disponible para gastar).
    
    PersAcc **NO** es:
    - ❌ Un gestor de inversiones (no trackea rendimientos de activos)
    - ❌ Un presupuestador rígido (no limita gastos por categoría)
    - ❌ Una app bancaria (no se conecta a tu banco ni hace pagos)
    
    PersAcc **SÍ** es:
    - ✅ Tu libro contable personal en formato digital
    - ✅ Un sistema de cierre mensual con retenciones automáticas
    - ✅ Una herramienta de análisis de hábitos de gasto
    - ✅ Tu fuente única de verdad sobre tu situación financiera mensual
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # FLUJO DE CIERRE DE MES
    # ============================================================================
    st.markdown("""
    ## 🔒 Flujo de Cierre de Mes (El Corazón del Sistema)
    
    El cierre de mes es el proceso más importante de PersAcc. Cuando cierras un mes:
    1. Se "congela" toda la información de ese periodo (no podrás editarla)
    2. Se calculan automáticamente las retenciones de ahorro/inversión
    3. Se genera la entrada de tu próxima nómina en el nuevo mes
    4. Se abre automáticamente el mes siguiente con el saldo inicial correcto
    
    ### 📅 Mecánica Detallada del Cierre
    
    #### Paso previo: Verificación
    - **Linealidad estricta**: Solo puedes cerrar meses en orden. Si cierras Enero, después DEBES cerrar Febrero (no puedes saltarte a Marzo)
    - **Una sola oportunidad**: Una vez cerrado un mes, es inmutable. Si te equivocas, necesitas contactar soporte o modificar la BD directamente
    
    #### Paso 1: Capturar Saldo Real del Banco
    **¿Qué ingresas?** El dinero que **realmente tienes** en tu cuenta bancaria **en este momento**, ANTES de cobrar la próxima nómina.
    
    **Ejemplo práctico**:
    - Hoy es 31 de Enero
    - Miras tu cuenta bancaria: 1,245.67 €
    - Introduces: `1245.67`
    
    **¿Por qué es importante?** Este valor se usa para:
    - Verificar que tus registros coinciden con la realidad
    - Calcular el "remanente" (dinero sobrante del mes)
    - Detectar discrepancias entre lo contabilizado y lo real
    
    #### Paso 2: Configurar Nueva Nómina
    **¿Qué ingresas?** El importe **bruto** de la nómina que vas a cobrar próximamente (para el mes siguiente).
    
    **Ejemplo práctico**:
    - Tu nómina es de 2,500 € al mes
    - Introduces: `2500`
    
    **¿Qué hace el sistema?**
    - Creará una entrada de tipo INGRESO en la categoría "Salario" con fecha 01/MM+1
    - Este ingreso ya aparecerá en el nuevo mes que se abre tras el cierre
    
    #### Paso 3: Definir Retenciones
    
    **Retención de Remanente** (dinero que sobró este mes):
    - El sistema calcula: `Remanente = Saldo Real - Suma de todos los gastos/inversiones del mes`
    - Tú decides qué % retener (ej: 50% de 300€ = 150€ a inversión)
    - Se crea automáticamente una entrada de INVERSIÓN en categoría "Inversión retención de remanente" con fecha fin del mes actual
    
    **Retención de Salario** (de la nómina nueva):
    - Tú decides qué % de la nómina destinar a ahorro/inversión (ej: 20% de 2,500€ = 500€)
    - Se crea automáticamente una entrada de INVERSIÓN en categoría "Inversión retención de salario" con fecha 01/MM+1 (mes siguiente)
    
    **Ejemplo visual**:
    ```
    Saldo inicial Enero: 500 €
    Nómina Enero: +2,500 €
    Gastos Enero: -2,100 €
    Inversiones Enero: -200 €
    -------------------------
    Saldo real al 31 Ene: 700 € (lo que ves en el banco)
    
    Remanente calculado: 700 - (próximas retenciones) = 700 €
    
    Cierras con:
    - Retención remanente: 50% → 350 € a "Inversión retención remanente" (31/Ene)
    - Retención salario: 20% → 500 € a "Inversión retención de salario" (01/Feb)
    
    Mes Febrero inicia con:
    - Saldo inicial: 350 € (700 - 350 retenido)
    - Nómina: +2,500 € (01/Feb)
    - Inversión retención: -500 € (01/Feb)
    - Saldo operativo disponible: 2,350 €
    ```
    
    #### Paso 4: Confirmación y Ejecución
    Al confirmar el cierre:
    1. ✅ Se marca el mes como CERRADO (inmutable)
    2. 📊 Se crea un snapshot del mes con todos los KPIs calculados
    3. 💰 Se genera la entrada de nómina en el nuevo mes
    4. 📈 Se generan las entradas de inversión por retenciones
    5. 🔓 Se abre automáticamente el mes siguiente para empezar a registrar gastos
    
    ### ⚠️ Errores Comunes al Cerrar
    
    **Error 1**: "El saldo real no coincide con lo contabilizado"
    - **Causa**: Olvidaste registrar algunos gastos o ingresos
    - **Solución**: Antes de cerrar, revisa la tabla de movimientos del mes. Añade las transacciones faltantes
    
    **Error 2**: "Cerré con % de retención equivocado"
    - **Causa**: Te confundiste en los porcentajes
    - **Solución preventiva**: Usa la pestaña "Utilidades → Configuración" para establecer tus % defaults. El wizard los sugerirá automáticamente
    
    **Error 3**: "Olvidé cerrar un mes y ahora tengo el orden mal"
    - **Causa**: Sistema de cierre lineal estricto
    - **Solución**: Debes cerrar los meses en orden. Si saltaste uno, retrocede y ciérralo primero
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CONFIGURACIÓN DE DEFAULTS
    # ============================================================================
    st.markdown("""
    ## ⚙️ Configuración de Valores por Defecto
    
    ### ¿Para qué sirven los defaults?
    
    Los valores por defecto te ahorran tiempo al registrar transacciones frecuentes y al cerrar meses. PersAcc almacena tu configuración en `data/config.json`.
    
    ### Cómo configurar (paso a paso)
    
    1. **Accede a configuración**:
       - Ve a la pestaña "🔧 Utilidades"
       - Selecciona el sub-tab "⚙️ Configuración"
    
    2. **Retenciones por defecto**:
       - **% Retención Remanente**: Valor sugerido al cerrar mes (ej: 50%)
       - **% Retención Nómina**: Valor sugerido para inversión de salario (ej: 20%)
       
       Estos valores aparecerán pre-rellenados en el wizard de cierre, pero siempre puedes cambiarlos manualmente.
    
    3. **Conceptos por defecto por categoría**:
       
       Para cada categoría activa, puedes definir un texto que se auto-rellená en el campo "Concepto" al usar Quick Add.
       
       **Ejemplo útil**:
       - Categoría "Comida" → Concepto default: "Supermercado"
       - Categoría "Transporte" → Concepto default: "Gasolina"
       - Categoría "Restaurantes" → Concepto default: "Comida fuera"
       
       **Beneficio**: Al seleccionar la categoría "Comida", el campo concepto ya tendrá "Supermercado". Si es otra cosa, simplemente editas el texto.
    
    4. **Guardar cambios**:
       - Click en "💾 Guardar Configuración"
       - Los cambios se aplican inmediatamente (no necesitas reiniciar la app)
    
    ### Archivo de configuración
    
    Si prefieres editar manualmente, el archivo está en:
    ```
    PersAcc/
    └── data/
        └── config.json
    ```
    
    Formato JSON:
    ```json
    {
      "retenciones": {
        "pct_remanente_default": 50,
        "pct_salario_default": 20
      },
      "conceptos_default": {
        "comida": "Supermercado",
        "restaurantes": "Comida fuera",
        "transporte": "Gasolina"
      }
    }
    ```
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # IMPORTACIÓN DE DATOS
    # ============================================================================
    st.markdown("""
    ## 📥 Importación de Datos desde Otras Fuentes
    
    ### ¿Qué puedes importar?
    
    PersAcc permite importar datos legacy desde archivos CSV. Esto es útil si:
    - Migras desde otra app de finanzas (Excel, YNAB, Mint, etc.)
    - Tienes extractos bancarios en CSV
    - Quieres hacer un "bulk import" de movimientos históricos
    
    ### Formatos Soportados (CSV)
    
    #### Formato 1: GASTOS
    ```csv
    DATE,CONCEPT,CATEGORY,RELEVANCE,AMOUNT
    01/01/2025,Supermercado Carrefour,Comida,NE,45.30
    05/01/2025,Cena con amigos,Restaurantes,LI,32.50
    10/01/2025,Netflix,Suscripciones,SUP,13.99
    ```
    
    **Descripción de columnas**:
    - `DATE`: Fecha en formato DD/MM/YYYY
    - `CONCEPT`: Texto libre describiendo el gasto
    - `CATEGORY`: Nombre de la categoría (debe existir en tu BD)
    - `RELEVANCE`: Código de relevancia (`NE`, `LI`, `SUP`, `TON`)
    - `AMOUNT`: Importe en euros (usa `.` para decimales)
    
    #### Formato 2: INGRESOS
    ```csv
    DATE,CONCEPT,AMOUNT
    01/01/2025,Nómina Enero,2500.00
    15/01/2025,Freelance proyecto X,450.00
    ```
    
    **Descripción**:
    - Solo 3 columnas (los ingresos no tienen relevancia)
    - El sistema asignará automáticamente la categoría según el concepto (usa keywords como "nómina", "freelance", etc.)
    
    #### Formato 3: INVERSIONES
    ```csv
    DATE,CONCEPT,AMOUNT,CATEGORY
    01/05/2025,Aportación Fondo M,500.00,Inversion
    15/05/2025,Compra ETF,200.00,Inversion
    ```
    
    ### ¿Qué hace el sistema con los datos importados?
    
    1. **Parsea el CSV**: Lee el archivo y extrae cada fila
    2. **Detecta categorías**: 
       - Si la categoría del CSV existe en tu BD → la usa
       - Si no existe → intenta matching aproximado o crea una nueva
    3. **Calcula fechas contables**: Aplica el "Salary Shifter" si corresponde
    4. **Calcula mes fiscal**: Asigna cada movimiento al mes correcto
    5. **Inserta en LEDGER**: Cada fila se convierte en una entrada de libro diario
    6. **Validación**: Rechaza filas con errores (fechas inválidas, importes negativos, etc.)
    
    ### Cómo importar (paso a paso)
    
    1. **Prepara tu CSV**:
       - Asegúrate de que sigue uno de los formatos soportados
       - Codificación: UTF-8 (importante para caracteres especiales)
       - Separador: coma (`,`)
    
    2. **Accede a importación**:
       - Pestaña "🔧 Utilidades" → Sub-tab "📥 Importar Legacy"
    
    3. **Selecciona tipo**:
       - "🔴 Gastos", "🟢 Ingresos", o "🟣 Inversiones"
    
    4. **Sube tu archivo**:
       - Click en "Browse files" o arrastra el CSV
    
    5. **Preview**:
       - El sistema muestra las primeras 5 filas
       - Verifica que se vean correctamente
    
    6. **Ejecuta importación**:
       - Click en "🚀 Ejecutar Importación"
       - El sistema usa `migration.py` internamente
       - Verás un log de las operaciones realizadas
    
    ### 🤖 Propuesta: Importación Asistida por LLM
    
    **Problema actual**: Si tus datos vienen en un formato diferente (ej: extracto bancario con columnas raras), tienes que reformatearlos manualmente.
    
    **Solución propuesta**: Usar un LLM (GPT-4, Claude, etc.) para transformar automáticamente tus datos al formato esperado.
    
    **Cómo funcionaría**:
    
    1. **Subes tu archivo raw** (puede estar en cualquier formato CSV)
    
    2. **El sistema usa un LLM** para:
       - Analizar las columnas disponibles
       - Detectar qué columna es fecha, importe, descripción, etc.
       - Mapear a categorías existentes basándose en las descripciones
       - Inferir relevancia (NE/LI/SUP/TON) basándose en el gasto
       - Generar el CSV en formato correcto
    
    3. **Previsualizas** el resultado antes de importar
    
    4. **Confirmas** y se importa automáticamente
    
    **Ejemplo de prompt para el LLM**:
    ```
    Tengo estas categorías disponibles:
    - Comida (GASTO)
    - Restaurantes (GASTO)
    - Transporte (GASTO)
    - Nómina (INGRESO)
    
    Mi CSV raw tiene estas columnas:
    Fecha | Descripción | Cargo | Abono
    
    Transforma cada fila al formato:
    DATE,CONCEPT,CATEGORY,RELEVANCE,AMOUNT
    
    Aplica estas reglas:
    - Si "Descripción" contiene palabras como "supermercado", "mercadona" → Categoría "Comida", Relevancia "NE"
    - Si contiene "restaurante", "bar" → Categoría "Restaurantes", Relevancia "LI"
    - Usa la columna "Cargo" para gastos, "Abono" para ingresos
    ```
    
    **Implementación técnica** (para desarrolladores):
    - Añadir endpoint en `migration.py`: `--llm-assisted`
    - Integrar API de OpenAI/Anthropic
    - UI en Streamlit para configurar API key
    - Coste estimado: ~$0.01 por cada 100 filas procesadas
    
    ### Errores comunes al importar
    
    **Error**: "Categoría 'X' no encontrada"
    - **Solución**: Crea primero la categoría en "🔧 Utilidades → Gestión Categorías"
    
    **Error**: "Fecha inválida en línea 5"
    - **Solución**: Verifica que las fechas estén en formato DD/MM/YYYY
    
    **Error**: "Importe debe ser positivo"
    - **Solución**: Los importes siempre son positivos. El tipo (GASTO vs INGRESO) define el signo
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CONCEPTOS AVANZADOS
    # ============================================================================
    st.markdown("""
    ## 🧠 Conceptos Avanzados
    
    ### Mes Fiscal
    
    El **mes fiscal** en PersAcc coincide con el mes natural (calendario). Cada transacción se registra en el mes en que ocurre realmente.
    
    **Ejemplo**:
    - Una transacción del 28/Enero → se contabiliza en Enero
    - Una transacción del 01/Febrero → se contabiliza en Febrero
    
    ### Relevancia del Gasto
    
    **NE (Necesario)**:
    - Gastos esenciales para vivir
    - Ejemplos: comida, alquiler, facturas, transporte al trabajo
    
    **LI (Me gusta)**:
    - Gastos que te aportan felicidad/bienestar
    - Ejemplos: cenas con amigos, hobbies, gym, libros
    
    **SUP (Superfluo)**:
    - No esenciales pero justificables ocasionalmente
    - Ejemplos: ropa nueva, decoración, upgrades innecesarios
    
    **TON (Tontería)**:
    - Gastos impulsivos o arrepentidos
    - Ejemplos: compras por aburrimiento, suscripciones no usadas
    
    **Objetivo**: Analizar qué % de tus gastos va a cada categoría. Idealmente:
    - NE: 50-60%
    - LI: 20-30%
    - SUP: 10-15%
    - TON: < 5%
    
    ### Integridad Referencial
    
    **¿Qué significa?** Los meses cerrados son inmutables. Si intentas editar/borrar un movimiento de un mes cerrado, el sistema lo rechaza.
    
    **¿Por qué?** Garantiza que tus snapshots mensuales siempre reflejen la realidad de ese momento. No puedes "hacer trampa" modificando el pasado.
    
    **Excepción**: Si REALMENTE necesitas modificar datos pasados (error crítico), debes:
    1. Reabrir el mes manualmente en la BD
    2. Hacer los cambios
    3. Volver a cerrarlo
    4. Recalcular todos los snapshots posteriores
    
    (No hay UI para esto porque es peligroso - requiere acceso directo a SQLite)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # TIPS Y BEST PRACTICES
    # ============================================================================
    st.markdown("""
    ## 💡 Tips y Mejores Prácticas
    
    ### Workflow Diario Recomendado
    
    1. **Por la mañana** (2 min):
       - Revisa recibos/notificaciones bancarias del día anterior
       - Registra gastos usando Quick Add
    
    2. **Fin de semana** (5 min):
       - Revisa la tabla de movimientos del mes
       - Corrige categorías o relevancia si es necesario
       - Verifica que no te falta nada
    
    3. **Fin de mes** (10 min):
       - Compara  saldo real del banco con el "Saldo Actual" en PersAcc
       - Si coinciden o están cerca → Cierra el mes
       - Si hay discrepancia → Busca las transacciones faltantes
    
    ### Maximiza el Uso de Defaults
    
    - Configura conceptos default para tus 10 categorías más usadas
    - Ajusta los % de retención defaults al nivel que quieres mantener
    - Usa Quick Add para el 90% de transacciones (formulario rápido)
    - Usa la tabla editable solo para correcciones
    
    ### Exporta Regularmente
    
    - Una vez al mes, exporta tu LEDGER completo a CSV
    - Guárdalo en la nube (Google Drive, Dropbox)
    - Es tu backup si algo falla con la BD
    
    ### Análisis Mensual
    
    Después de cerrar cada mes, revisa:
    - **Balance**: ¿Ahorraste o gastaste más de lo que ingresó?
    - **Calidad del gasto**: ¿Qué % fue NE vs TON?
    - **Categorías top**: ¿Dónde se fue más dinero?
    - **Tendencias**: Compara con meses anteriores en la pestaña "Histórico"
    
    ### Categorización Inteligente
    
    **Mal ejemplo**:
    - 50 categorías ultra específicas ("Café Starbucks", "Café local", "Café máquina"...)
    
    **Buen ejemplo**:
    - 15-20 categorías generales ("Restaurantes & Cafés")
    - Usa el campo "Concepto" para detalles específicos
    
    **Beneficio**: Gráficos y análisis más claros
    
    ---
    
    ## 📞 Soporte y Recursos
    
    - **Código fuente**: [GitHub - PersAcc](https://github.com/tu-repo) _(si es open source)_
    - **Base de datos**: SQLite en `data/finanzas.db`
    - **Logs**: Los errores aparecen en la consola donde ejecutas `streamlit run app.py`
    
    **Versión actual**: 2.0  
    **Última actualización**: Enero 2026
    
    ---
    
    _¿Faltan temas en este manual? ¡Contribuye mejorando la documentación!_
    """)
