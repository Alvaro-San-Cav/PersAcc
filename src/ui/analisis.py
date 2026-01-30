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
from src.config import get_currency_symbol, format_currency
from src.i18n import t


def render_analisis():
    """Renderiza la página de análisis."""
    st.markdown(f'<div class="main-header"><h1>{t("analisis.title")}</h1></div>', unsafe_allow_html=True)
    
    # Cargar configuración
    from src.config import load_config
    config = load_config()
    enable_relevance = config.get('enable_relevance', True)

    # Selector de mes
    _, col2, _ = st.columns([1, 2, 1])
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
        
        def on_mes_change():
            """Callback al cambiar de mes para forzar actualización."""
            st.session_state['mes_global'] = st.session_state['mes_selector_analisis']
        
        mes_seleccionado = st.selectbox(
            t('analisis.month_selector', year=year_to_show),
            options=meses,
            index=default_index,
            key="mes_selector_analisis",
            on_change=on_mes_change
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
    
    # Verificar si el sistema ya fue inicializado (existe algún snapshot)
    from src.database import get_latest_snapshot
    sistema_inicializado = get_latest_snapshot() is not None
    
    # Solo mostrar config de saldo inicial si:
    # 1. No hay saldo guardado para este mes Y
    # 2. El sistema NUNCA fue inicializado (primera vez)
    if not tiene_saldo_guardado and not sistema_inicializado:
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
            <div class="kpi-value">{format_currency(saldo_inicial)}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.income')}</div>
            <div class="kpi-value">{format_currency(kpis['total_ingresos'])}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.expenses')}</div>
            <div class="kpi-value" style="color: #ff6b6b;">{format_currency(kpis['total_gastos'])}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        balance_color = "#00ff88" if kpis['balance_mes'] >= 0 else "#ff6b6b"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.balance')}</div>
            <div class="kpi-value" style="color: {balance_color};">{format_currency(kpis['balance_mes'])}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.investment')}</div>
            <div class="kpi-value">{format_currency(kpis['total_inversion'])}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # Saldo actual = saldo inicial + balance del mes - inversiones (que salen de la cuenta)
        saldo_actual = saldo_inicial + kpis['balance_mes'] - kpis['total_inversion']
        saldo_color = "#00ff88" if saldo_actual >= 0 else "#ff6b6b"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{t('analisis.kpis.current_balance')}</div>
            <div class="kpi-value" style="color: {saldo_color};">{format_currency(saldo_actual)}</div>
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
            
            
            if not enable_relevance:
                # Si está deshabilitado, eliminamos la columna de relevancia de los datos (aunque aquí no afecta a data_editor tanto como la config)
                pass 
            
            df = pd.DataFrame(data)
            
            # Configuración de columnas
            
            # Base config
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
                    format=f"%.2f {get_currency_symbol()}",
                    min_value=0.0,
                    disabled=mes_cerrado
                ),
                "Tipo": st.column_config.TextColumn(t('analisis.movements.columns.type'), disabled=True),
            }
            
            # Add Relevance column only if enabled
            if enable_relevance:
                column_config["Relevance"] = st.column_config.SelectboxColumn(
                    t('analisis.movements.columns.relevance'),
                    options=["NE", "LI", "SUP", "TON"],
                    required=False,
                    disabled=mes_cerrado
                )
            
            # Definir columnas visibles
            col_order = ["Borrar", "Fecha", "Categoría", "Concepto", "Importe", "Tipo"]
            if enable_relevance:
                col_order.append("Relevancia")
            
            # Mostrar tabla editable - altura dinámica para mostrar todas las entradas
            # Calcular altura: ~35px por fila + 38px header
            table_height = min(max(len(df) * 35 + 38, 150), 800)
            
            edited_df = st.data_editor(
                df,
                key=f"editor_movs_{mes_seleccionado}",
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                column_order=col_order,
                num_rows="fixed", # No permitir agregar filas aquí, usar formulario
                height=table_height,
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
                # 2. Edición (detectar cambios en DF vs DB)
                # Detectar si hubo cambios en los datos (excluyendo Borrar)
                cols_check = ["Categoría", "Concepto", "Importe"]
                if enable_relevance:
                    cols_check.append("Relevancia")
                
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
                                prueba_rel = row["Relevancia"] if (enable_relevance and row["Relevancia"]) else None
                                
                                # Actualizar en BD usando la función importada
                                update_ledger_entry(
                                    entry_id=int(row['id']),
                                    categoria_id=nuevo_cat_id,
                                    concepto=row['Concepto'],
                                    importe=float(row['Importe']),
                                    relevancia_code=prueba_rel
                                )
                                count_updates += 1
                        
                        st.success(t('analisis.movements.update_success', count=count_updates))
                        st.rerun()
        else:
            st.info(t('analisis.movements.no_movements'))
        
        # Espacio para el resumen de IA (marcador de posición)
        ai_summary_placeholder = st.empty()

        # Separador y Sección de Notas (Ahora se renderiza INMEDIATAMENTE)
        st.markdown("---")
        _render_user_notes_section("month", mes_seleccionado)
        
        # Lógica lenta de IA al final para no bloquear el renderizado de las notas
        # Generar resumen de IA para cualquier mes que tenga entradas
        if entries:
            from src.ai.llm_service import is_llm_enabled, generate_quick_summary
            from src.i18n import get_language
            
            if is_llm_enabled():
                # Cache key includes month AND language
                current_lang = get_language()
                cache_key = f"ai_summary_{mes_seleccionado}_{current_lang}"
                cached_summary = st.session_state.get('ai_summary_cache', {})
                
                if cached_summary.get('key') == cache_key and cached_summary.get('text'):
                    summary = cached_summary['text']
                else:
                    expense_items = []
                    for e in entries:
                        if e.tipo_movimiento == TipoMovimiento.GASTO:
                            expense_items.append({
                                'categoria': cats_map.get(e.categoria_id, 'Sin categoría'),
                                'concepto': e.concepto,
                                'importe': float(e.importe)
                            })
                    
                    with ai_summary_placeholder.container():
                        with st.spinner(t('analisis.ai_generating')):
                            summary = generate_quick_summary(
                                income=kpis['total_ingresos'],
                                expenses=kpis['total_gastos'],
                                balance=kpis['balance_mes'],
                                lang=get_language(),
                                expense_items=expense_items
                            )
                    
                    if summary:
                        st.session_state['ai_summary_cache'] = {'key': cache_key, 'text': summary}
                
                if summary:
                    ai_summary_placeholder.markdown(f"*{summary}*")
        
    with col_grafico:
        # 1. Gráfico de Gastos por Categoría
        st.markdown(f"### {t('analisis.expenses_by_category.title')}")
        
        # Placeholder para spinner + gráfico
        chart1_ph = st.empty()
        
        with chart1_ph.container():
            with st.spinner("📉 Cargando gráfico..."):
                from collections import defaultdict
                
                gastos_por_cat = defaultdict(float)
                for e in entries:
                    if e.tipo_movimiento == TipoMovimiento.GASTO:
                        cat_nombre = cats_map.get(e.categoria_id, "Desconocida")
                        gastos_por_cat[cat_nombre] += e.importe
                
                if gastos_por_cat:
                    sorted_cats = sorted(gastos_por_cat.items(), key=lambda x: x[1], reverse=True)
                    cats_labels = [x[0] for x in sorted_cats]
                    cats_values = [x[1] for x in sorted_cats]
                    
                    fig_cat = go.Figure(data=[go.Pie(
                        labels=cats_labels,
                        values=cats_values,
                        hole=0.4,
                        textinfo='label+percent',
                        textposition='inside',
                        insidetextorientation='radial',
                        textfont_size=20
                    )])
                    
                    fig_cat.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='white',
                        font_size=10,
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=400,
                        showlegend=False
                    )
        
        if gastos_por_cat:
            chart1_ph.plotly_chart(fig_cat, use_container_width=True)
        else:
            chart1_ph.info(t('analisis.movements.no_movements'))

        if enable_relevance:
            st.markdown(f"### {t('analisis.spending_quality.title')}")
            
            # Placeholder para spinner + gráfico
            chart2_ph = st.empty()
            
            with chart2_ph.container():
                with st.spinner("🎯 Cargando análisis..."):
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
                            hole=0.4,
                            marker_colors=colors,
                            textinfo='label+percent',
                            textposition='inside',
                            insidetextorientation='radial',
                            textfont_size=16
                        )])
                        
                        fig.update_layout(
                            showlegend=False,
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font_color='white',
                            font_size=10,
                            margin=dict(t=10, b=10, l=10, r=10),
                            height=400
                        )
            
            if total_gastos > 0:
                chart2_ph.plotly_chart(fig, use_container_width=True)
            else:
                chart2_ph.info(t('analisis.spending_quality.no_data'))


def _render_user_notes_section(period_type: str, period_identifier: str):
    """Renderiza la sección de notas del usuario con editor de texto enriquecido."""
    from src.database import get_period_notes, save_period_notes
    
    try:
        from streamlit_quill import st_quill
        quill_available = True
    except ImportError:
        quill_available = False
        st.warning("⚠️ Para usar el editor de texto rico, instala: `pip install streamlit-quill`")
    
    # Intentar cargar notas existentes
    try:
        current_notes = get_period_notes(period_type, period_identifier) or ""
    except Exception:
        current_notes = ""
        
    # Mostrar notificación si viene de un guardado exitoso
    toast_key = f"toast_notes_{period_type}_{period_identifier}"
    if st.session_state.get(toast_key):
        st.success(t('analisis.notes_saved'))
        st.session_state[toast_key] = False

    st.markdown(f"### {t('analisis.notes_title')}")
    
    if quill_available:
        # Editor de texto enriquecido con streamlit-quill
        content = st_quill(
            value=current_notes,
            placeholder=t('analisis.notes_placeholder'),
            html=True,
            toolbar=[
                [{'header': [1, 2, 3, False]}],
                ['bold', 'italic', 'underline', 'strike'],
                [{'list': 'ordered'}, {'list': 'bullet'}],
                [{'color': []}, {'background': []}],
                ['clean']
            ],
            key=f"quill_editor_{period_type}_{period_identifier}"
        )
        
        # Botón de guardar fuera del editor
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(t('analisis.notes_save_button'), type="primary", use_container_width=True):
                save_period_notes(period_type, period_identifier, content if content else "")
                st.session_state[toast_key] = True
                st.rerun()
    else:
        # Fallback: editor simple de texto plano
        form_key = f"notes_form_{period_type}_{period_identifier}"
        
        with st.form(form_key):
            new_notes = st.text_area(
                t('analisis.notes_placeholder'),
                value=current_notes,
                height=150,
                key=f"txt_{period_type}_{period_identifier}"
            )
            
            if st.form_submit_button(t('analisis.notes_save_button')):
                save_period_notes(period_type, period_identifier, new_notes)
                st.session_state[toast_key] = True
                st.rerun()
