"""
Sidebar component - Quick Add form.
Renderiza el formulario de entrada rápida de transacciones en el sidebar.
"""
import streamlit as st
from datetime import date

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry, RELEVANCIA_DESCRIPTIONS
from src.database import (
    get_all_categorias, insert_ledger_entry, is_mes_cerrado
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
        
        # Obtener categorías
        categorias = get_all_categorias()
        if not categorias:
            st.warning("No hay categorías. Ejecuta setup_db.py primero.")
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
        cat_dict = {c.nombre: c for c in categorias_filtradas}
        cat_nombres = list(cat_dict.keys())
        
        if not cat_nombres:
            st.warning(f"No hay categorías para {tipo_seleccionado}")
            return
        
        # Selector de categoría (ya filtrado)
        categoria_nombre = st.selectbox(
            f"📁 {t('sidebar.quick_add.category_label')}",
            options=cat_nombres,
            key=f"cat_{tipo_mov.value}"
        )
        
        categoria_sel = cat_dict.get(categoria_nombre)
        
        categoria_sel = cat_dict.get(categoria_nombre)
        
        # Obtener configuración
        config = load_config()
        enable_relevance = config.get('enable_relevance', True)
        
        # Obtener concepto por defecto desde config
        conceptos_default = config.get('conceptos_default', {})
        cat_key = categoria_nombre.lower().replace(" ", "_")
        concepto_default = conceptos_default.get(cat_key, "")
        
        # Concepto (justo después de categoría)
        concepto = st.text_input(
            f"📝 {t('sidebar.quick_add.concept_label')}", 
            value=concepto_default, 
            placeholder="Ej: Cena con amigos",
            key="concepto_input"
        )
        
        # Selector de relevancia (solo para GASTO)
        relevancia = None
        flag_liquidez = False
        
        if tipo_mov == TipoMovimiento.GASTO:
            if enable_relevance:
                st.markdown(f"**{t('sidebar.quick_add.relevance_label')}**")
                relevancia_code = st.radio(
                    "Relevancia",
                    options=["NE", "LI", "SUP", "TON"],
                    format_func=lambda x: f"{x} - {RELEVANCIA_DESCRIPTIONS[RelevanciaCode(x)]}",
                    horizontal=True,
                    label_visibility="collapsed",
                    key="relevancia_sel"
                )
                relevancia = RelevanciaCode(relevancia_code)
            else:
                # Si está desactivado, asignar valor neutro o None (depende del modelo, aquí usaremos None y manejaremos en insert)
                # O forzar un valor por defecto como NEcesario si la DB lo requiere. 
                # El modelo LedgerEntry permite relevancia_code opcional (Optional[RelevanciaCode])
                relevancia = None
            
            
        elif tipo_mov == TipoMovimiento.INGRESO:
            flag_liquidez = st.checkbox(
                f"⚡ {t('sidebar.quick_add.liquidity_flag')}",
                help="Marca si necesitas adelantar este ingreso al mes actual",
                key="flag_liquidez_sel"
            )
        
        
        # FORMULARIO para los datos de la transacción
        # Se elimina st.form para quitar el texto "Press enter to submit"
        
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
        
        # Fecha
        # Usamos key para poder reiniciar si es necesario
        if "quick_date" not in st.session_state:
            st.session_state["quick_date"] = fecha_default

        fecha = st.date_input(
            f"📅 {t('sidebar.quick_add.date_label')}", 
            value=st.session_state["quick_date"],
            key="quick_date_widget"
        )
        
        # Importe
        # Usamos key para resetear
        if "quick_amount" not in st.session_state:
            st.session_state["quick_amount"] = 0.00
            
        importe = st.number_input(
            f"💵 {t('sidebar.quick_add.amount_label')}", 
            min_value=0.00, # Permitir 0 para reset visual, validamos luego
            step=0.01, 
            format="%.2f",
            key="quick_amount_widget"
        )
        
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
                st.error("El concepto es obligatorio")
            elif importe <= 0:
                st.error("El importe debe ser mayor a 0")
            elif tipo_mov == TipoMovimiento.GASTO and enable_relevance and relevancia is None:
                st.error("Selecciona la relevancia del gasto")
            else:
                # Calcular fechas
                fecha_contable = calcular_fecha_contable(fecha, tipo_mov, flag_liquidez, concepto=concepto)
                mes_fiscal = calcular_mes_fiscal(fecha_contable)
                
                # Verificar si el mes está cerrado
                if is_mes_cerrado(mes_fiscal):
                    st.error(f"🔒 No puedes añadir entradas al mes **{mes_fiscal}** porque ya está cerrado.")
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
                        
                        # Limpiar campos manualmentes
                        # Concepto (key: concepto_input)
                        st.session_state["concepto_input"] = "" # Usa el valor por defecto del widget si no
                        # Importe
                        st.session_state["quick_amount"] = 0.00 # Reset value
                        # Fecha no la reseteamos a hoy necesariamente, o sí? 
                        # Mejor mantenerla o resetear a default? Mantenemos fecha suele ser cómodo.
                        
                        # Hack para limpiar widgets en el siguiente rerun
                        # Debemos actualizar las keys de los widgets si usamos st.session_state
                        # Para concepto_input ya funciona si el text_input lee de session_state (lo hace si key existe)
                        # Para number_input igual.
                        
                        # Para forzar update visual del number_input, actualizamos su key
                        st.session_state["quick_amount_widget"] = 0.00
                        st.session_state["concepto_input"] = concepto_default # Reset al default de categoría o vacío
                        
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error: {e}")
