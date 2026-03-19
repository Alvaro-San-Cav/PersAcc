"""
Sidebar component - Quick Add form.
Renderiza el formulario de entrada rápida de transacciones en el sidebar.
"""
import streamlit as st
from datetime import date
from pathlib import Path

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry
from src.database import (
    get_all_categorias, insert_ledger_entry, is_mes_cerrado, get_category_usage_stats
)
from src.business_logic import calcular_fecha_contable, calcular_mes_fiscal
from src.config import load_config
from src.i18n import t


def render_sidebar():
    """Renderiza el formulario Quick Add en el sidebar."""
    with st.sidebar:
        # LOGO
        if Path("assets/logo.ico").exists():
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
        
        # Si cambia el mes global, reajustar la fecha por defecto para ese contexto.
        last_mes_key = "sidebar_last_mes_global"
        if st.session_state.get(last_mes_key) != mes_global:
            st.session_state["quick_date_widget"] = fecha_default
            st.session_state[last_mes_key] = mes_global

        if "quick_date_widget" not in st.session_state:
            st.session_state["quick_date_widget"] = fecha_default

        fecha = st.date_input(
            f"📅 {t('sidebar.quick_add.date_label')}", 
            key="quick_date_widget"
        )
        
        st.markdown("---")
        
        # Obtener categorías
        categorias = get_all_categorias()
        if not categorias:
            st.warning(t('sidebar.quick_add.validation.no_categories_setup'))
            return
        
        # ── Sección 1: Tipo de movimiento + Categoría ────────────────────
        with st.container(border=True):
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
            stats = get_category_usage_stats(tipo_mov, fecha.month, fecha.year)

            def sort_key(c):
                s = stats.get(c.id, {'history': 0, 'curr_year': 0})
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
        
        # Key para rastrear si el usuario ha editado manualmente el concepto
        user_edited_concepto_key = "user_edited_concepto"
        
        # Obtener el valor actual del concepto en el widget
        current_concepto = st.session_state.get("concepto_input_widget", "")
        
        # Determinar si debemos aplicar defaults
        should_reset_defaults = False
        should_reset_concepto = False
        
        # Detectar cambio: tracked != actual
        if tracked_categoria != categoria_nombre:
            should_reset_defaults = True
            
            # Determinar si el concepto actual es un default o fue escrito por el usuario
            # Solo resetear concepto si NO fue editado manualmente por el usuario
            if not st.session_state.get(user_edited_concepto_key, False):
                # El usuario no ha editado manualmente, podemos aplicar el nuevo default
                should_reset_concepto = True
            else:
                # El usuario SÍ editó manualmente, verificar si el concepto actual 
                # coincide con algún default conocido (en cuyo caso sí podemos cambiarlo)
                all_conceptos_default = list(conceptos_default.values())
                if current_concepto in all_conceptos_default or current_concepto.strip() == "":
                    should_reset_concepto = True
                # Si no coincide con ningún default y no está vacío, mantener el valor del usuario
        
        # Reset explícito después de guardar una transacción
        if st.session_state.get("reset_concepto_flag", False):
            should_reset_defaults = True
            should_reset_concepto = True
            st.session_state["reset_concepto_flag"] = False
            # Limpiar el flag de edición manual al guardar
            st.session_state[user_edited_concepto_key] = False
        
        # Aplicar defaults DIRECTAMENTE a las keys de los widgets
        if should_reset_defaults:
            # Solo resetear concepto si corresponde
            if should_reset_concepto:
                st.session_state["concepto_input_widget"] = concepto_default
                # Resetear flag de edición manual cuando aplicamos un default
                st.session_state[user_edited_concepto_key] = False
            st.session_state["quick_amount_widget"] = importe_default
            # Actualizar tracking DESPUÉS de aplicar defaults
            st.session_state[tracking_key] = categoria_nombre
        
        # Callback para detectar cuando el usuario edita el concepto manualmente
        def on_concepto_change():
            st.session_state[user_edited_concepto_key] = True
        
        # ── Sección 2: Concepto, Relevancia e Importe ────────────────────
        with st.container(border=True):
            # Concepto
            concepto = st.text_input(
                f"📝 {t('sidebar.quick_add.concept_label')}",
                placeholder=t('sidebar.quick_add.concept_placeholder'),
                key="concepto_input_widget",
                on_change=on_concepto_change
            )

            # Selector de relevancia (solo para GASTO)
            relevancia = None
            flag_liquidez = False

            if tipo_mov == TipoMovimiento.GASTO:
                if enable_relevance:
                    st.markdown(f"**{t('sidebar.quick_add.relevance_label')}**")

                    relevancia_options = ["NE", "LI", "SUP", "TON"]
                    if should_reset_defaults and relevancia_default in relevancia_options:
                        st.session_state["relevancia_sel"] = relevancia_default

                    relevancia_code = st.radio(
                        t('sidebar.quick_add.relevance_label'),
                        options=relevancia_options,
                        format_func=lambda x: f"{x} - {t(f'sidebar.quick_add.relevance_descriptions.{x}')}",
                        horizontal=True,
                        label_visibility="collapsed",
                        key="relevancia_sel"
                    )
                    relevancia = RelevanciaCode(relevancia_code)
                else:
                    relevancia = None

            elif tipo_mov == TipoMovimiento.INGRESO:
                flag_liquidez = st.checkbox(
                    f"⚡ {t('sidebar.quick_add.liquidity_flag')}",
                    help=t('sidebar.quick_add.liquidity_help'),
                    key="flag_liquidez_sel"
                )

            # Aplicar resultado de calculadora ANTES de crear el widget (si hay flag pendiente)
            if st.session_state.get("calc_apply_result_flag", False):
                st.session_state["quick_amount_widget"] = st.session_state.get("calc_pending_value", 0.0)
                st.session_state["calc_apply_result_flag"] = False
                st.session_state["calc_result"] = None

            # Importe
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
            # CSS para estilo de calculadora profesional
            st.markdown("""
            <style>
            /* Centrar texto en botones de la calculadora (excluye el header del expander) */
            section[data-testid="stSidebar"] .streamlit-expanderContent button {
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
                padding: 8px !important;
                min-height: 42px !important;
                font-size: 16px !important;
                font-weight: 600 !important;
            }
            section[data-testid="stSidebar"] .streamlit-expanderContent button p {
                margin: 0 !important;
                font-size: 16px !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Inicializar estado de la calculadora
            if "calc_display" not in st.session_state:
                st.session_state["calc_display"] = 0.0
            if "calc_operand" not in st.session_state:
                st.session_state["calc_operand"] = None
            if "calc_operation" not in st.session_state:
                st.session_state["calc_operation"] = None
            if "calc_new_number" not in st.session_state:
                st.session_state["calc_new_number"] = True
            if "calc_display_widget" not in st.session_state:
                st.session_state["calc_display_widget"] = 0.0
            
            # Procesar acciones pendientes ANTES de crear el widget
            if "calc_pending_action" in st.session_state:
                action = st.session_state["calc_pending_action"]
                
                if action["type"] == "append_digit":
                    digit = action["digit"]
                    if st.session_state["calc_new_number"]:
                        st.session_state["calc_display"] = float(digit)
                        st.session_state["calc_new_number"] = False
                    else:
                        current = st.session_state["calc_display"]
                        if current == int(current):
                            st.session_state["calc_display"] = current * 10 + digit
                        else:
                            current_str = f"{current:.10f}".rstrip('0')
                            if '.' in current_str:
                                decimal_places = len(current_str.split('.')[1])
                                st.session_state["calc_display"] = current + (digit / (10 ** (decimal_places + 1)))
                            else:
                                st.session_state["calc_display"] = current * 10 + digit
                
                elif action["type"] == "clear_all":
                    st.session_state["calc_display"] = 0.0
                    st.session_state["calc_operand"] = None
                    st.session_state["calc_operation"] = None
                    st.session_state["calc_new_number"] = True
                
                elif action["type"] == "operation":
                    op = action["op"]
                    current = st.session_state["calc_display"]
                    
                    if st.session_state["calc_operand"] is not None and st.session_state["calc_operation"] and not st.session_state["calc_new_number"]:
                        prev = st.session_state["calc_operand"]
                        if st.session_state["calc_operation"] == "add":
                            result = prev + current
                        elif st.session_state["calc_operation"] == "sub":
                            result = prev - current
                        elif st.session_state["calc_operation"] == "mul":
                            result = prev * current
                        elif st.session_state["calc_operation"] == "div":
                            result = prev / current if current != 0 else 0
                        else:
                            result = current
                        
                        st.session_state["calc_display"] = result
                        st.session_state["calc_operand"] = result
                    else:
                        st.session_state["calc_operand"] = current
                    
                    st.session_state["calc_operation"] = op
                    st.session_state["calc_new_number"] = True
                
                elif action["type"] == "equals":
                    if st.session_state["calc_operand"] is not None and st.session_state["calc_operation"]:
                        current = st.session_state["calc_display"]
                        prev = st.session_state["calc_operand"]
                        
                        if st.session_state["calc_operation"] == "add":
                            result = prev + current
                        elif st.session_state["calc_operation"] == "sub":
                            result = prev - current
                        elif st.session_state["calc_operation"] == "mul":
                            result = prev * current
                        elif st.session_state["calc_operation"] == "div":
                            if current != 0:
                                result = prev / current
                            else:
                                st.error(t('sidebar.quick_add.calc_div_zero'))
                                result = 0
                        else:
                            result = current
                        
                        st.session_state["calc_display"] = result
                        st.session_state["calc_operand"] = None
                        st.session_state["calc_operation"] = None
                        st.session_state["calc_new_number"] = True
                
                # IMPORTANTE: Sincronizar con el widget key antes de limpar
                st.session_state["calc_display_widget"] = st.session_state["calc_display"]
                
                # Limpiar acción pendiente
                del st.session_state["calc_pending_action"]
            
            # Mostrar operación pendiente si existe
            operation_text = ""
            if st.session_state["calc_operation"] and st.session_state["calc_operand"] is not None:
                op_symbol = {"add": "+", "sub": "-", "mul": "×", "div": "÷"}
                operation_text = f"{st.session_state['calc_operand']:.2f} {op_symbol.get(st.session_state['calc_operation'], '?')}"
            
            # Display con operación pendiente
            if operation_text:
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 8px 15px 5px 15px; border-radius: 8px 8px 0 0;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>
                    <div style='color: rgba(255,255,255,0.7); font-size: 12px; 
                               text-align: right; min-height: 16px;'>{operation_text}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Display editable (number input)
            st.number_input(
                "Display",
                step=0.01,
                format="%.2f",
                key="calc_display_widget",
                label_visibility="collapsed"
            )
            
            # Sincronizar calc_display con el valor actual del widget
            # Esto asegura que el botón "usar como importe" siempre lea el valor correcto
            st.session_state["calc_display"] = st.session_state["calc_display_widget"]
            
            # Grid de botones 4x4
            # Fila 1: 7, 8, 9, ÷
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("7", key="calc_7", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 7}
                    st.rerun()
            with col2:
                if st.button("8", key="calc_8", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 8}
                    st.rerun()
            with col3:
                if st.button("9", key="calc_9", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 9}
                    st.rerun()
            with col4:
                if st.button("➗", key="calc_div", use_container_width=True, type="secondary"):
                    st.session_state["calc_pending_action"] = {"type": "operation", "op": "div"}
                    st.rerun()
            
            # Fila 2: 4, 5, 6, ×
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("4", key="calc_4", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 4}
                    st.rerun()
            with col2:
                if st.button("5", key="calc_5", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 5}
                    st.rerun()
            with col3:
                if st.button("6", key="calc_6", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 6}
                    st.rerun()
            with col4:
                if st.button("✖️", key="calc_mul", use_container_width=True, type="secondary"):
                    st.session_state["calc_pending_action"] = {"type": "operation", "op": "mul"}
                    st.rerun()
            
            # Fila 3: 1, 2, 3, -
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("1", key="calc_1", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 1}
                    st.rerun()
            with col2:
                if st.button("2", key="calc_2", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 2}
                    st.rerun()
            with col3:
                if st.button("3", key="calc_3", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 3}
                    st.rerun()
            with col4:
                if st.button("➖", key="calc_sub", use_container_width=True, type="secondary"):
                    st.session_state["calc_pending_action"] = {"type": "operation", "op": "sub"}
                    st.rerun()
            
            # Fila 4: AC, 0, =, +
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("AC", key="calc_ac", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "clear_all"}
                    st.rerun()
            with col2:
                if st.button("0", key="calc_0", use_container_width=True):
                    st.session_state["calc_pending_action"] = {"type": "append_digit", "digit": 0}
                    st.rerun()
            with col3:
                if st.button("=", key="calc_eq", use_container_width=True, type="primary"):
                    st.session_state["calc_pending_action"] = {"type": "equals"}
                    st.rerun()
            with col4:
                if st.button("➕", key="calc_add", use_container_width=True, type="secondary"):
                    st.session_state["calc_pending_action"] = {"type": "operation", "op": "add"}
                    st.rerun()
            
            # Botón para usar el resultado
            st.markdown("---")
            if st.button(f"📥 {t('sidebar.quick_add.calc_use_result')}", key="calc_use", use_container_width=True):
                # Usar flags porque el widget de importe se crea ANTES de la calculadora
                # Los flags se procesan en líneas 203-207 antes de crear el widget
                st.session_state["calc_pending_value"] = abs(float(st.session_state["calc_display"]))
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
                    try:
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
                        insert_ledger_entry(entry)
                        st.success(t('sidebar.quick_add.success_message'))
                        
                        # Limpiar campos manualmente
                        # Usamos flag para resetear valores en el próximo rerun
                        st.session_state["reset_concepto_flag"] = True
                        
                        st.rerun()

                    except Exception as e:
                        st.error(t('sidebar.quick_add.validation.error', error=str(e)))
