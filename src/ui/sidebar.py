"""
Sidebar component - Quick Add form.
Renderiza el formulario de entrada rápida de transacciones en el sidebar.
"""
import streamlit as st
from datetime import date

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry, RELEVANCIA_DESCRIPTIONS
from src.database import (
    get_all_categorias, insert_ledger_entry, is_mes_cerrado, get_category_usage_stats
)
from src.business_logic import calcular_fecha_contable, calcular_mes_fiscal
from src.config import load_config
from src.i18n import t, get_language, set_language, get_language_flag


def render_sidebar():
    """Renderiza el formulario Quick Add en el sidebar."""
    with st.sidebar:
        # LOGO
        import os
        if os.path.exists("assets/logo.ico"):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                st.image("assets/logo.ico", width=250)
            st.markdown("---")
            
        # ============================================================================
        # QUICK ADD FORM
        # ============================================================================
        st.markdown(f"## {t('sidebar.quick_add.title')}")
        st.markdown("---")

        # ============================================================================
        # 0. FECHA (Moved to top for context-aware sorting)
        # ============================================================================
        
        # Calcular fecha por defecto según el mes seleccionado
        mes_global = st.session_state.get('mes_global', None)
        mes_actual = date.today().strftime("%Y-%m")
        
        if mes_global and mes_global != mes_actual:
            # Si el mes seleccionado es distinto del actual, usar el día 1 de ese mes
            year, month = map(int, mes_global.split('-'))
            fecha_default = date(year, month, 1)
        else:
            # Si es el mes actual o no hay mes seleccionado, usar la fecha actual
            fecha_default = date.today()
        
        if "quick_date" not in st.session_state:
            st.session_state["quick_date"] = fecha_default

        fecha = st.date_input(
            f"📅 {t('sidebar.quick_add.date_label')}", 
            value=st.session_state["quick_date"],
            key="quick_date_widget"
        )
        
        st.markdown("---")
        
        # Obtener categorías
        categorias = get_all_categorias()
        if not categorias:
            st.warning(t('sidebar.quick_add.validation.no_categories_setup'))
            return
        
        # PASO 1: Seleccionar TIPO DE MOVIMIENTO primero
        tipo_opciones = {
            t('sidebar.types.expense'): TipoMovimiento.GASTO,
            t('sidebar.types.income'): TipoMovimiento.INGRESO,
            t('sidebar.types.transfer_in'): TipoMovimiento.TRASPASO_ENTRADA,
            t('sidebar.types.transfer_out'): TipoMovimiento.TRASPASO_SALIDA,
            t('sidebar.types.investment'): TipoMovimiento.INVERSION
        }
        
        tipo_seleccionado = st.radio(
            f"**{t('sidebar.quick_add.type_label')}**",
            options=list(tipo_opciones.keys()),
            horizontal=True,
            key="tipo_mov_sel"
        )
        tipo_mov = tipo_opciones[tipo_seleccionado]
                
        # PASO 2: Filtrar categorías por tipo seleccionado
        categorias_filtradas = [c for c in categorias if c.tipo_movimiento == tipo_mov]
        
        # ORDENAR CATEGORIAS INTELIGENTEMENTE
        # 1. Uso en mismo mes de años anteriores (history)
        # 2. Uso en año actual (curr_year)
        # 3. Alfabético
        stats = get_category_usage_stats(tipo_mov, fecha.month, fecha.year)
        
        def sort_key(c):
            s = stats.get(c.id, {'history': 0, 'curr_year': 0})
            # Negativo para orden descendente
            return (-s['history'], -s['curr_year'], c.nombre)
            
        categorias_filtradas.sort(key=sort_key)
        
        cat_dict = {c.nombre: c for c in categorias_filtradas}
        cat_nombres = list(cat_dict.keys())
        
        if not cat_nombres:
            st.warning(t('sidebar.quick_add.validation.no_categories_type', type=tipo_seleccionado))
            return
        
        # Selector de categoría (ya filtrado)
        selectbox_key = f"cat_{tipo_mov.value}"
        categoria_nombre = st.selectbox(
            f"📁 {t('sidebar.quick_add.category_label')}",
            options=cat_nombres,
            key=selectbox_key
        )
        
        categoria_sel = cat_dict.get(categoria_nombre)
        
        # Obtener configuración
        config = load_config()
        enable_relevance = config.get('enable_relevance', True)
        
        # Obtener valores por defecto desde config
        conceptos_default = config.get('conceptos_default', {})
        importes_default = config.get('importes_default', {})
        relevancias_default = config.get('relevancias_default', {})
        
        cat_key = categoria_nombre.lower().replace(" ", "_")
        concepto_default = conceptos_default.get(cat_key, "")
        importe_default = importes_default.get(cat_key, 0.0)
        relevancia_default = relevancias_default.get(cat_key, "")
        
        # Usar una key de tracking separada (NO la del widget)
        # para detectar cambios de categoría
        tracking_key = f"tracked_cat_{tipo_mov.value}"
        tracked_categoria = st.session_state.get(tracking_key, None)
        
        # Determinar si debemos aplicar defaults
        should_reset_defaults = False
        
        # Detectar cambio: tracked != actual
        if tracked_categoria != categoria_nombre:
            should_reset_defaults = True
        
        if st.session_state.get("reset_concepto_flag", False):
            should_reset_defaults = True
            st.session_state["reset_concepto_flag"] = False
        
        # Aplicar defaults DIRECTAMENTE a las keys de los widgets
        if should_reset_defaults:
            st.session_state["concepto_input_widget"] = concepto_default
            st.session_state["quick_amount_widget"] = importe_default
            # Actualizar tracking DESPUÉS de aplicar defaults
            st.session_state[tracking_key] = categoria_nombre
        
        # Concepto 
        concepto = st.text_input(
            f"📝 {t('sidebar.quick_add.concept_label')}", 
            placeholder=t('sidebar.quick_add.concept_placeholder'),
            key="concepto_input_widget"
        )
        
        # Selector de relevancia (solo para GASTO)
        relevancia = None
        flag_liquidez = False
        
        if tipo_mov == TipoMovimiento.GASTO:
            if enable_relevance:
                st.markdown(f"**{t('sidebar.quick_add.relevance_label')}**")
                
                # Aplicar default de relevancia directamente a session_state
                relevancia_options = ["NE", "LI", "SUP", "TON"]
                if should_reset_defaults and relevancia_default in relevancia_options:
                    st.session_state["relevancia_sel"] = relevancia_default
                
                relevancia_code = st.radio(
                    "Relevancia",
                    options=relevancia_options,
                    format_func=lambda x: f"{x} - {RELEVANCIA_DESCRIPTIONS[RelevanciaCode(x)]}",
                    horizontal=True,
                    label_visibility="collapsed",
                    key="relevancia_sel"
                )
                relevancia = RelevanciaCode(relevancia_code)
            else:
                # Si está desactivado, asignar valor neutro o None
                relevancia = None
            
            
        elif tipo_mov == TipoMovimiento.INGRESO:
            flag_liquidez = st.checkbox(
                f"⚡ {t('sidebar.quick_add.liquidity_flag')}",
                help=t('sidebar.quick_add.liquidity_help'),
                key="flag_liquidez_sel"
            )
        
        
        # FORMULARIO para los datos de la transacción
        # Se elimina st.form para quitar el texto "Press enter to submit"
        
        # Fecha movida al inicio
        # Mantenemos la variable 'fecha' que ya fue asignada arriba

        
        # Aplicar resultado de calculadora ANTES de crear el widget (si hay flag pendiente)
        if st.session_state.get("calc_apply_result_flag", False):
            st.session_state["quick_amount_widget"] = st.session_state.get("calc_pending_value", 0.0)
            st.session_state["calc_apply_result_flag"] = False
            st.session_state["calc_result"] = None
        
        # Importe (el valor se actualiza en el bloque should_reset_defaults arriba)
        # No usamos value= porque Streamlit lee directamente de st.session_state[key]
        importe = st.number_input(
            f"💵 {t('sidebar.quick_add.amount_label')}", 
            min_value=0.00,
            step=0.01, 
            format="%.2f",
            key="quick_amount_widget"
        )
        
        # ============================================================================
        # CALCULADORA RÁPIDA (Desplegable)
        # ============================================================================
        with st.expander(f"🧮 {t('sidebar.quick_add.calculator_title')}", expanded=False):
            # CSS para centrar iconos en botones de la calculadora
            st.markdown("""
            <style>
            /* Centrar texto en todos los botones del sidebar */
            section[data-testid="stSidebar"] button {
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
            }
            section[data-testid="stSidebar"] button p,
            section[data-testid="stSidebar"] button span,
            section[data-testid="stSidebar"] button div {
                text-align: center !important;
                width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
                display: block !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Inicializar valores de la calculadora en session_state
            if "calc_num1" not in st.session_state:
                st.session_state["calc_num1"] = 0.0
            if "calc_num2" not in st.session_state:
                st.session_state["calc_num2"] = 0.0
            if "calc_result" not in st.session_state:
                st.session_state["calc_result"] = None
            
            calc_col1, calc_col2 = st.columns(2)
            with calc_col1:
                num1 = st.number_input(
                    t('sidebar.quick_add.calc_num1'),
                    value=st.session_state["calc_num1"],
                    step=0.01,
                    format="%.2f",
                    key="calc_input_num1"
                )
            with calc_col2:
                num2 = st.number_input(
                    t('sidebar.quick_add.calc_num2'),
                    value=st.session_state["calc_num2"],
                    step=0.01,
                    format="%.2f",
                    key="calc_input_num2"
                )
            
            # Botones de operaciones
            op_col1, op_col2, op_col3, op_col4 = st.columns(4)
            
            result = None
            with op_col1:
                if st.button("➕", key="calc_add", use_container_width=True):
                    result = num1 + num2
            with op_col2:
                if st.button("➖", key="calc_sub", use_container_width=True):
                    result = num1 - num2
            with op_col3:
                if st.button("✖️", key="calc_mul", use_container_width=True):
                    result = num1 * num2
            with op_col4:
                if st.button("➗", key="calc_div", use_container_width=True):
                    if num2 != 0:
                        result = num1 / num2
                    else:
                        st.error(t('sidebar.quick_add.calc_div_zero'))
            
            # Actualizar resultado si se calculó
            if result is not None:
                st.session_state["calc_result"] = result
                st.session_state["calc_num1"] = num1
                st.session_state["calc_num2"] = num2
            
            # Mostrar resultado
            if st.session_state["calc_result"] is not None:
                st.markdown(f"**{t('sidebar.quick_add.calc_result')}:** `{st.session_state['calc_result']:.2f}`")
                
                # Botón para transferir resultado al importe (usa flag para evitar error de Streamlit)
                if st.button(f"📥 {t('sidebar.quick_add.calc_use_result')}", key="calc_use", use_container_width=True):
                    st.session_state["calc_pending_value"] = abs(st.session_state["calc_result"])
                    st.session_state["calc_apply_result_flag"] = True
                    st.rerun()
        
        # Botón submit
        submitted = st.button(
            t('sidebar.quick_add.submit_button'), 
            use_container_width=True,
            type="primary"
        )
        
        if submitted:
            # Recuperar valores de los widgets (por si acaso)
            # Nota: concepto ya está en concepto_input
            
            if not concepto.strip():
                st.error(t('sidebar.quick_add.validation.concept_required'))
            elif importe <= 0:
                st.error(t('sidebar.quick_add.validation.amount_positive'))
            elif tipo_mov == TipoMovimiento.GASTO and enable_relevance and relevancia is None:
                st.error(t('sidebar.quick_add.validation.relevance_required'))
            else:
                # Calcular fechas
                fecha_contable = calcular_fecha_contable(fecha, tipo_mov, flag_liquidez, concepto=concepto)
                mes_fiscal = calcular_mes_fiscal(fecha_contable)
                
                # Verificar si el mes está cerrado
                if is_mes_cerrado(mes_fiscal):
                    st.error(t('sidebar.quick_add.validation.month_closed', month=mes_fiscal))
                else:
                    # Crear entrada
                    entry = LedgerEntry(
                        id=None,
                        fecha_real=fecha,
                        fecha_contable=fecha_contable,
                        mes_fiscal=mes_fiscal,
                        tipo_movimiento=tipo_mov,
                        categoria_id=categoria_sel.id,
                        concepto=concepto.strip(),
                        importe=importe,
                        relevancia_code=relevancia,
                        flag_liquidez=flag_liquidez
                    )
                    
                    # Guardar
                    try:
                        insert_ledger_entry(entry)
                        st.success(t('sidebar.quick_add.success_message'))
                        
                        # Limpiar campos manualmente
                        # Usamos flag para resetear valores en el próximo rerun
                        st.session_state["reset_concepto_flag"] = True
                        st.session_state["concepto_value"] = concepto_default
                        st.session_state["importe_value"] = importe_default
                        
                        st.rerun()

                    except Exception as e:
                        st.error(t('sidebar.quick_add.validation.error', error=str(e)))
