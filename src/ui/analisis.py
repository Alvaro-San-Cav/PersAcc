"""
Página de Análisis - PersAcc
Renderiza la vista principal del ledger con KPIs y movimientos del mes.
"""
import streamlit as st
from datetime import date, timedelta
import pandas as pd
import plotly.graph_objects as go

from src.models import TipoMovimiento, CierreMensual
from src.database import (
    get_ledger_by_month, get_all_categorias, is_mes_cerrado,
    get_snapshot_by_month, get_cierre_mes, upsert_cierre_mes,
    delete_ledger_entry, update_ledger_entry
)
from src.business_logic import calcular_kpis, calcular_kpis_relevancia, calcular_mes_fiscal
from src.i18n import t


def render_analisis():
    """Renderiza la página de análisis."""
    st.markdown(f'<div class="main-header"><h1>{t("analisis.title")}</h1></div>', unsafe_allow_html=True)
    
    # Selector de mes
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Determinar qué año fiscal mostrar (12 meses)
        # Lógica: empezar desde el año actual y avanzar mientras diciembre esté cerrado
        today = date.today()
        year_to_show = today.year
        
        # Avanzar años mientras diciembre esté cerrado (funciona ad infinitum)
        while is_mes_cerrado(f"{year_to_show}-12"):
            year_to_show += 1
        
        # Generar solo los 12 meses del año a mostrar
        meses = [f"{year_to_show}-{str(m).zfill(2)}" for m in range(1, 13)]
        
        mes_actual = calcular_mes_fiscal(today)
        
        # Encontrar el índice del mes seleccionado
        mes_default = st.session_state.get('mes_global', mes_actual)
        if mes_default in meses:
            default_index = meses.index(mes_default)
        elif mes_actual in meses:
            default_index = meses.index(mes_actual)
        else:
            default_index = 0  # Enero del año a mostrar
        
        mes_seleccionado = st.selectbox(
            t('analisis.month_selector', year=year_to_show),
            options=meses,
            index=default_index,
            key="mes_selector_analisis"
        )
        # Guardar en session_state global
        st.session_state['mes_global'] = mes_seleccionado
    
    st.markdown("---")
    
    # Obtener KPIs
    kpis = calcular_kpis(mes_seleccionado)
    kpis_rel = calcular_kpis_relevancia(mes_seleccionado)
    
    # Obtener saldo inicial del mes
    # Primero intentar desde CIERRES_MENSUALES (si el mes tiene entrada)
    cierre_actual = get_cierre_mes(mes_seleccionado)
    
    # Luego intentar desde snapshot del mes anterior
    try:
        y, m = map(int, mes_seleccionado.split('-'))
        dt_prev = date(y, m, 1).replace(day=1) - timedelta(days=1)
        prev_month = dt_prev.strftime("%Y-%m")
        snapshot_prev = get_snapshot_by_month(prev_month)
    except Exception:
        snapshot_prev = None
    
    # Determinar saldo inicial según prioridad
    if cierre_actual and cierre_actual.saldo_inicio > 0:
        saldo_inicial = cierre_actual.saldo_inicio
        tiene_saldo_guardado = True
    elif snapshot_prev:
        saldo_inicial = snapshot_prev.saldo_inicial_nuevo
        tiene_saldo_guardado = True
    else:
        saldo_inicial = 0.0
        tiene_saldo_guardado = False
    
    # Si no hay saldo guardado, mostrar input para configurarlo
    if not tiene_saldo_guardado:
        with st.expander(t('analisis.initial_balance_config.title'), expanded=True):
            st.info(t('analisis.initial_balance_config.info'))
            nuevo_saldo = st.number_input(
                t('analisis.initial_balance_config.input_label'),
                min_value=0.0,
                value=0.0,
                step=100.0,
                key="saldo_inicial_manual"
            )
            if st.button(t('analisis.initial_balance_config.save_button')):
                # Crear o actualizar entrada en CIERRES_MENSUALES
                cierre_nuevo = CierreMensual(
                    mes_fiscal=mes_seleccionado,
                    estado='ABIERTO',
                    fecha_cierre=None,
                    saldo_inicio=nuevo_saldo,
                    salario_mes=None,
                    total_ingresos=None,
                    total_gastos=None,
                    total_inversion=None,
                    saldo_fin=None,
                    nomina_siguiente=None,
                    notas=None
                )
                upsert_cierre_mes(cierre_nuevo)
                st.success(t('analisis.initial_balance_config.success_message', month=mes_seleccionado, amount=nuevo_saldo))
                st.rerun()
        st.markdown("---")
    
    # Mostrar KPIs en tarjetas (6 columnas)
    col_bal, col1, col2, col3, col4, col5 = st.columns(6)
    
    with col_bal:
         st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.initial_balance')}</div>
            <div class="kpi-value">{saldo_inicial:,.2f} €</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.income')}</div>
            <div class="kpi-value">{kpis['total_ingresos']:,.2f} €</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.expenses')}</div>
            <div class="kpi-value" style="color: #ff6b6b;">{kpis['total_gastos']:,.2f} €</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        balance_color = "#00ff88" if kpis['balance_mes'] >= 0 else "#ff6b6b"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.balance')}</div>
            <div class="kpi-value" style="color: {balance_color};">{kpis['balance_mes']:,.2f} €</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.investment')}</div>
            <div class="kpi-value">{kpis['total_inversion']:,.2f} €</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # Saldo actual = saldo inicial + balance del mes - inversiones (que salen de la cuenta)
        saldo_actual = saldo_inicial + kpis['balance_mes'] - kpis['total_inversion']
        saldo_color = "#00ff88" if saldo_actual >= 0 else "#ff6b6b"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.current_balance')}</div>
            <div class="kpi-value" style="color: {saldo_color};">{saldo_actual:,.2f} €</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Dos columnas: Tabla y Gráfico
    col_tabla, col_grafico = st.columns([2, 1])
    
    with col_tabla:
        st.markdown(f"### {t('analisis.movements.title')}")
        entries = get_ledger_by_month(mes_seleccionado)
        
        if entries:
            # Verificar si el mes está cerrado
            mes_cerrado = is_mes_cerrado(mes_seleccionado)
            
            if mes_cerrado:
                st.warning(t('analisis.movements.month_closed_warning'))
            
            # Mapeo de categorías
            cats = get_all_categorias()
            cats_map = {c.id: c.nombre for c in cats}
            cats_inv_map = {c.nombre: c.id for c in cats}
            
            # Crear lista de diccionarios
            data = []
            for e in entries:
                es_positivo = e.tipo_movimiento in [TipoMovimiento.INGRESO, TipoMovimiento.TRASPASO_ENTRADA]
                data.append({
                    "id": e.id,
                    "Borrar": False,
                    "Fecha": e.fecha_real,
                    "Categoría": cats_map.get(e.categoria_id, "Desconocida"),
                    "Concepto": e.concepto,
                    "Importe": float(e.importe),  # Asegurar float
                    "Tipo": "+" if es_positivo else "-",
                    "Relevancia": e.relevancia_code.value if e.relevancia_code else ""
                })
            
            df = pd.DataFrame(data)
            
            # Configuración de columnas
            column_config = {
                "id": None,  # Ocultar ID
                "Borrar": st.column_config.CheckboxColumn(
                    t('analisis.movements.columns.delete'),
                    help="Selecciona para borrar",
                    default=False,
                    disabled=mes_cerrado
                ),
                "Fecha": st.column_config.DateColumn(
                    t('analisis.movements.columns.date'),
                    format="DD/MM/YYYY",
                    disabled=True # Por ahora solo lectura fecha
                ),
                "Categoría": st.column_config.SelectboxColumn(
                    t('analisis.movements.columns.category'),
                    options=list(cats_inv_map.keys()),
                    required=True,
                    disabled=mes_cerrado
                ),
                "Concepto": st.column_config.TextColumn(
                    t('analisis.movements.columns.concept'),
                    disabled=mes_cerrado
                ),
                "Importe": st.column_config.NumberColumn(
                    t('analisis.movements.columns.amount'),
                    format="%.2f €",
                    min_value=0.0,
                    disabled=mes_cerrado
                ),
                "Tipo": st.column_config.TextColumn(t('analisis.movements.columns.type'), disabled=True),
                "Relevancia": st.column_config.SelectboxColumn(
                    t('analisis.movements.columns.relevance'),
                    options=["NE", "LI", "SUP", "TON"],
                    required=False,
                    disabled=mes_cerrado
                )
            }
            
            # Mostrar tabla editable
            edited_df = st.data_editor(
                df,
                key=f"editor_movs_{mes_seleccionado}",
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed", # No permitir agregar filas aquí, usar formulario
                disabled=["id", "Tipo"] if not mes_cerrado else ["id", "Borrar", "Fecha", "Categoría", "Concepto", "Importe", "Tipo", "Relevancia"]
            )
            
            # Procesar cambios (solo si no está cerrado)
            if not mes_cerrado:
                col_btn_del, col_btn_save = st.columns([1, 1])
                
                # 1. Eliminación
                filas_a_borrar = edited_df[edited_df["Borrar"] == True]
                if not filas_a_borrar.empty:
                    if st.button(t('analisis.movements.delete_selected', count=len(filas_a_borrar)), type="secondary"):
                        for _, row in filas_a_borrar.iterrows():
                            delete_ledger_entry(int(row["id"]))
                        st.success(t('analisis.movements.delete_success', count=len(filas_a_borrar)))
                        st.rerun()
                
                # 2. Edición (detectar cambios en DF vs DB)
                # Detectar si hubo cambios en los datos (excluyendo Borrar)
                cols_check = ["Categoría", "Concepto", "Importe", "Relevancia"]
                hay_cambios = not edited_df[cols_check].equals(df[cols_check])
                
                if hay_cambios:
                    if st.button(t('analisis.movements.save_changes')):
                        count_updates = 0
                        for index, row in edited_df.iterrows():
                            original_row = df.loc[index]
                            
                            # Verificar si esta fila cambió
                            if not row[cols_check].equals(original_row[cols_check]):
                                # Obtener ID categoría nuevo
                                nuevo_cat_id = cats_inv_map.get(row["Categoría"])
                                prueba_rel = row["Relevancia"] if row["Relevancia"] else None
                                
                                # Actualizar en BD usando la función importada
                                update_ledger_entry(
                                    entry_id=int(row['id']),
                                    categoria_id=nuevo_cat_id,
                                    concepto=row['Concepto'],
                                    importe=float(row['Importe']),
                                    relevencia_code=prueba_rel
                                )
                                count_updates += 1
                        
                        st.success(t('analisis.movements.update_success', count=count_updates))
                        st.rerun()
        else:
            st.info(t('analisis.movements.no_movements'))
    
    with col_grafico:
        st.markdown(f"### {t('analisis.spending_quality.title')}")
        
        # Datos para donut chart
        total_gastos = sum(kpis_rel.values())
        if total_gastos > 0:
            labels = [
                t('analisis.spending_quality.labels.necessary'),
                t('analisis.spending_quality.labels.like'),
                t('analisis.spending_quality.labels.superfluous'),
                t('analisis.spending_quality.labels.nonsense')
            ]
            values = [kpis_rel['NE'], kpis_rel['LI'], kpis_rel['SUP'], kpis_rel['TON']]
            colors = ['#00c853', '#448aff', '#ffab00', '#ff5252']
            
            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.6,
                marker_colors=colors,
                textinfo='percent',
                textfont_size=14
            )])
            
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                margin=dict(t=20, b=20, l=20, r=20),
                height=300
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(t('analisis.spending_quality.no_data'))
