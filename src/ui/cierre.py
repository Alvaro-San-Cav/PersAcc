"""
Página de Cierre de Mes - PersAcc
Renderiza la interfaz de cierre.
"""
import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import csv
from io import StringIO

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry, CierreMensual, Categoria
from src.database import (
    get_all_categorias, get_categorias_by_tipo, get_ledger_by_month,
    get_all_ledger_entries, get_latest_snapshot, update_categoria,
    get_category_counts, delete_categoria, deactivate_categoria,
    insert_categoria, DEFAULT_DB_PATH, delete_ledger_entry,
    update_ledger_entry, get_all_meses_fiscales_cerrados,
    is_mes_cerrado, get_connection
)
from src.business_logic import (
    calcular_fecha_contable, calcular_mes_fiscal, calcular_kpis,
    calcular_kpis_relevancia, ejecutar_cierre_mes,
    calcular_kpis_anuales, get_word_counts, get_top_entries,
    calculate_curious_metrics
)
from src.i18n import t


def render_cierre():
    """Renderiza el asistente de cierre de mes."""
    st.markdown(f'<div class="main-header"><h1>{t("cierre.title")}</h1></div>', unsafe_allow_html=True)
    
    # Obtener mes actual (default)
    today = date.today()
    year = today.year
    mes_default = calcular_mes_fiscal(today)
    
    # Determinar el SIGUIENTE mes a cerrar (estrictamente lineal)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        from src.database import get_all_meses_fiscales_cerrados
        
        # Obtener historial de cierres ordenado
        cerrados = get_all_meses_fiscales_cerrados()
        
        if cerrados:
            # Si hay historial, el único mes cerrable es el siguiente al último cerrado
            ultimo_cerrado = sorted([c.mes_fiscal for c in cerrados])[-1]
            y, m = map(int, ultimo_cerrado.split('-'))
            
            # Calcular siguiente mes
            dt_ultimo = date(y, m, 1)
            # Sumar 32 días y ajustar al día 1 para obtener mes siguiente seguro
            next_month_date = (dt_ultimo + timedelta(days=32)).replace(day=1)
            mes_cierre_target = next_month_date.strftime("%Y-%m")
            
            st.info(t('cierre.last_closed', month=ultimo_cerrado))
            bloqueado = True
        else:
            # Si no hay historial, permitir seleccionar (arranque del sistema)
            mes_cierre_target = st.session_state.get('mes_global', mes_default)
            bloqueado = False
        
        # Visualización
        if bloqueado:
             st.markdown(f"### {t('cierre.month_to_close', month=mes_cierre_target)}")
             mes_seleccionado = mes_cierre_target
             # Actualizar global
             st.session_state['mes_global'] = mes_seleccionado
        else:
            # Selector limitado para el primer inicio (solo año actual/siguiente)
            # Reutilizamos la lógica simple para el arranque
            meses_arranque = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
            mes_seleccionado = st.selectbox(
                t('cierre.select_first_month'),
                options=meses_arranque,
                index=meses_arranque.index(mes_cierre_target) if mes_cierre_target in meses_arranque else 0,
                key="mes_selector_cierre"
            )
            st.session_state['mes_global'] = mes_seleccionado
    
    mes_actual = mes_seleccionado  # Usar el mes seleccionado, no el calculado
    
    st.markdown(f"### {t('cierre.header_close_month', month=mes_actual)}")
    st.markdown("---")
    
    # Verificar si el mes ya está cerrado ANTES de iniciar el wizard
    from src.database import is_mes_cerrado
    if is_mes_cerrado(mes_actual):
        st.error(t('cierre.already_closed', month=mes_actual))
        st.info(t('cierre.already_closed_info'))
        return  # Salir de la función, no mostrar wizard
    
    # Wizard paso a paso
    step = st.session_state.get('cierre_step', 1)
    
    if step == 1:
        st.markdown(f"#### {t('cierre.wizard.step1.title')}")
        st.markdown(t('cierre.wizard.step1.description'))
        
        # Intentar obtener saldo estimado desde el cierre anterior
        default_saldo = 0.0
        last_snapshot = get_latest_snapshot()
        if last_snapshot:
             # Si el último snapshot es del mes anterior (o reciente), sugerimos ese saldo
             default_saldo = last_snapshot.saldo_inicial_nuevo
             st.info(t('cierre.wizard.step1.expected_balance_info', amount=default_saldo))

        saldo_banco = st.number_input(
            t('cierre.wizard.step1.input_label'),
            min_value=0.0,
            step=100.0,
            value=default_saldo,
            format="%.2f",
            key="saldo_banco"
        )
        
        if st.button(t('cierre.wizard.step1.next_button'), use_container_width=True):
            st.session_state['saldo_banco_real'] = saldo_banco
            st.session_state['cierre_step'] = 2
            st.rerun()
    
    elif step == 2:
        st.markdown(f"#### {t('cierre.wizard.step2.title')}")
        st.markdown(t('cierre.wizard.step2.description'))
        
        nomina = st.number_input(
            t('cierre.wizard.step2.input_label'),
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key="nomina_nueva"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t('cierre.wizard.step2.back_button'), use_container_width=True):
                st.session_state['cierre_step'] = 1
                st.rerun()
        with col2:
            if st.button(t('cierre.wizard.step2.next_button'), use_container_width=True):
                st.session_state['nomina_nuevo_mes'] = nomina
                st.session_state['cierre_step'] = 3
                st.rerun()
    
    elif step == 3:
        st.markdown(f"#### {t('cierre.wizard.step3.title')}")
        
        col1, col2 = st.columns(2)
        
        # Obtener defaults desde archivo de configuración (con fallback a session_state)
        from src.config import load_config
        config = load_config()
        retenciones = config.get('retenciones', {})
        default_pct_remanente = st.session_state.get('default_pct_remanente', retenciones.get('pct_remanente_default', 0))
        default_pct_salario = st.session_state.get('default_pct_salario', retenciones.get('pct_salario_default', 20))
        
        with col1:
            pct_remanente = st.slider(
                t('cierre.wizard.step3.surplus_label'),
                min_value=0,
                max_value=100,
                value=default_pct_remanente,
                help="Porcentaje del saldo sobrante a enviar a inversión"
            ) / 100
        
        with col2:
            pct_salario = st.slider(
                t('cierre.wizard.step3.salary_label'),
                min_value=0,
                max_value=100,
                value=default_pct_salario,
                help="Porcentaje de la nueva nómina a enviar a inversión"
            ) / 100
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t('cierre.wizard.step3.back_button'), use_container_width=True):
                st.session_state['cierre_step'] = 2
                st.rerun()
        with col2:
            if st.button(t('cierre.wizard.step3.next_button'), use_container_width=True):
                st.session_state['pct_remanente'] = pct_remanente
                st.session_state['pct_salario'] = pct_salario
                st.session_state['cierre_step'] = 4
                st.rerun()
    
    elif step == 4:
        st.markdown(f"#### {t('cierre.wizard.step4.title')}")
        
        saldo = st.session_state.get('saldo_banco_real', 0)
        nomina = st.session_state.get('nomina_nuevo_mes', 0)
        pct_rem = st.session_state.get('pct_remanente', 0)
        pct_sal = st.session_state.get('pct_salario', 0.2)
        
        # Calcular KPIs del mes
        kpis = calcular_kpis(mes_actual)
        
        # Calcular transferencia
        retencion_remanente = saldo * pct_rem
        retencion_salario = nomina * pct_sal
        total_inversion = kpis['total_inversion'] + retencion_remanente + retencion_salario
        transferencia_nueva = retencion_remanente + retencion_salario
        
        # Saldo final del mes actual (después de retención remanente, antes del salario)
        saldo_fin_mes = saldo - retencion_remanente
        
        # Saldo inicial del mes siguiente (saldo fin + salario - retención salario)
        saldo_inicio_siguiente = saldo_fin_mes + nomina - retencion_salario
        
        # Mostrar resumen
        st.markdown(f"##### {t('cierre.wizard.step4.summary_title')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Saldo Banco Actual", f"{saldo:,.2f} €")
            st.metric("Nueva Nómina", f"{nomina:,.2f} €")
            st.metric("Retenciones Manuales (ya hechas)", f"{kpis['total_inversion']:,.2f} €")
        
        with col2:
            st.metric("Retención Remanente", f"{retencion_remanente:,.2f} €")
            st.metric("Retención Nómina", f"{retencion_salario:,.2f} €")
            st.metric("💎 Total a Inversión", f"{total_inversion:,.2f} €", 
                     delta=f"+{transferencia_nueva:,.2f} € nueva transferencia")
        
        st.markdown("---")
        st.markdown(f"### 🏦 Saldo Inicio Nuevo Mes: **{saldo_fin_mes:,.2f} €**")
        st.caption("(El salario se sumará como ingreso en el nuevo mes)")
        
        # Detectar desviación (diferencia entre saldo calculado y saldo real)
        # Obtener saldo inicial del mes
        from src.database import get_cierre_mes, get_snapshot_by_month
        cierre_mes = get_cierre_mes(mes_actual)
        
        # Obtener saldo inicial
        if cierre_mes and cierre_mes.saldo_inicio > 0:
            saldo_inicial_mes = cierre_mes.saldo_inicio
        else:
            # Intentar desde snapshot del mes anterior
            try:
                y, m = map(int, mes_actual.split('-'))
                dt_prev = date(y, m, 1).replace(day=1) - timedelta(days=1)
                prev_month = dt_prev.strftime("%Y-%m")
                snapshot_prev = get_snapshot_by_month(prev_month)
                saldo_inicial_mes = snapshot_prev.saldo_inicial_nuevo if snapshot_prev else 0.0
            except Exception:
                saldo_inicial_mes = 0.0
        
        # Saldo calculado = saldo inicial + balance del mes - inversiones ya hechas
        balance_esperado = saldo_inicial_mes + kpis['balance_mes'] - kpis['total_inversion']
        desviacion = balance_esperado - saldo if saldo > 0 else 0
        
        # Mostrar siempre la desviación
        col_dev1, col_dev2 = st.columns(2)
        with col_dev1:
            st.metric("📊 Saldo Calculado (según registros)", f"{balance_esperado:,.2f} €")
        with col_dev2:
            # Color según magnitud de desviación
            if abs(desviacion) <= 10:
                st.metric("✅ Desviación", f"{desviacion:+,.2f} €", help="Diferencia mínima, todo correcto")
            elif desviacion > 0:
                st.metric("⚠️ Desviación", f"{desviacion:+,.2f} €", delta="Tienes menos de lo registrado", delta_color="inverse")
            else:
                st.metric("⚠️ Desviación", f"{desviacion:+,.2f} €", delta="Tienes más de lo registrado", delta_color="normal")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t('cierre.wizard.step4.back_button'), use_container_width=True):
                st.session_state['cierre_step'] = 3
                st.rerun()
        with col2:
            if st.button(t('cierre.wizard.step4.execute_button'), type="primary", use_container_width=True):
                try:
                    snapshot = ejecutar_cierre_mes(
                        mes_fiscal=mes_actual,
                        saldo_banco_real=saldo,
                        nomina_nueva=nomina,
                        pct_retencion_remanente=pct_rem,
                        pct_retencion_salario=pct_sal
                    )
                    st.session_state['cierre_step'] = 5
                    st.session_state['snapshot'] = snapshot
                    st.rerun()
                except Exception as e:
                    st.error(t('cierre.wizard.step4.error', error=str(e)))
    
    elif step == 5:
        st.markdown(f'<div class="success-message"><h2>{t("cierre.wizard.step4.success")}</h2></div>', 
                   unsafe_allow_html=True)
        
        snapshot = st.session_state.get('snapshot')
        if snapshot:
            # Calcular mes siguiente para mostrar en mensaje
            year, month = map(int, snapshot.mes_cierre.split('-'))
            mes_sig = f"{year}-{month+1:02d}" if month < 12 else f"{year+1}-01"
            
            st.markdown(f"""
            - **Mes cerrado:** {snapshot.mes_cierre}
            - **Retención ejecutada:** {snapshot.retencion_ejecutada:,.2f} €
            - **Saldo inicial nuevo mes:** {snapshot.saldo_inicial_nuevo:,.2f} €
            """)
            
            if snapshot.nomina_nuevo_mes > 0:
                st.success(f"💰 Al cerrar **{snapshot.mes_cierre}** se ha registrado el salario de **{mes_sig}**: **{snapshot.nomina_nuevo_mes:,.2f} €**")
        
        if st.button("🆕 Nuevo Cierre", use_container_width=True):
            st.session_state['cierre_step'] = 1
            st.rerun()
