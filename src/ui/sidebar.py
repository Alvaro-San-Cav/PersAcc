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
        
        st.markdown("---")
        
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
        
        # Obtener concepto por defecto desde config
        config = load_config()
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
            
        elif tipo_mov == TipoMovimiento.INGRESO:
            flag_liquidez = st.checkbox(
                f"⚡ {t('sidebar.quick_add.liquidity_flag')}",
                help="Marca si necesitas adelantar este ingreso al mes actual",
                key="flag_liquidez_sel"
            )
        
        st.markdown("---")
        
        # FORMULARIO para los datos de la transacción
        with st.form("quick_add_form", clear_on_submit=True):
            # Fecha
            fecha = st.date_input(f"📅 {t('sidebar.quick_add.date_label')}", value=date.today())
            

            # Importe
            importe = st.number_input(
                f"💵 {t('sidebar.quick_add.amount_label')}", 
                min_value=0.01, 
                step=0.01, 
                format="%.2f"
            )
            
            # Botón submit
            submitted = st.form_submit_button(
                t('sidebar.quick_add.submit_button'), 
                use_container_width=True
            )
            
            if submitted:
                if not concepto.strip():
                    st.error("El concepto es obligatorio")
                elif importe <= 0:
                    st.error("El importe debe ser mayor a 0")
                elif tipo_mov == TipoMovimiento.GASTO and relevancia is None:
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

                        except Exception as e:
                            st.error(f"Error: {e}")
