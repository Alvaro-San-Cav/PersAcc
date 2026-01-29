"""
Página de Cierre de Mes - PersAcc
Renderiza la interfaz de cierre usando @st.fragment para aislamiento completo.
"""
import streamlit as st
from datetime import date, timedelta

from src.database import (
    get_all_meses_fiscales_cerrados, get_latest_snapshot,
    is_mes_cerrado, get_cierre_mes
)
from src.business_logic import (
    calcular_mes_fiscal, calcular_kpis, ejecutar_cierre_mes,
    calculate_consequences
)
from src.config import format_currency, get_currency_symbol, load_config
from src.i18n import t


def render_cierre():
    """Renderiza el asistente de cierre de mes."""
    st.markdown(f'<div class="main-header"><h1>{t("cierre.title")}</h1></div>', unsafe_allow_html=True)
    
    # --- LÓGICA DE MES ---
    today = date.today()
    year = today.year
    mes_default = calcular_mes_fiscal(today)
    
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        cerrados = get_all_meses_fiscales_cerrados()
        
        if cerrados:
            ultimo_cerrado = sorted([c.mes_fiscal for c in cerrados])[-1]
            y, m = map(int, ultimo_cerrado.split('-'))
            dt_ultimo = date(y, m, 1)
            next_month_date = (dt_ultimo + timedelta(days=32)).replace(day=1)
            mes_cierre_target = next_month_date.strftime("%Y-%m")
            
            st.info(t('cierre.last_closed', month=ultimo_cerrado))
            bloqueado = True
        else:
            mes_cierre_target = st.session_state.get('mes_global', mes_default)
            bloqueado = False
        
        if bloqueado:
             st.markdown(f"### {t('cierre.month_to_close', month=mes_cierre_target)}")
             st.session_state['mes_global'] = mes_cierre_target
             mes_actual = mes_cierre_target
        else:
            meses_arranque = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
            mes_seleccionado = st.selectbox(
                t('cierre.select_first_month'),
                options=meses_arranque,
                index=meses_arranque.index(mes_cierre_target) if mes_cierre_target in meses_arranque else 0,
                key="mes_selector_cierre"
            )
            st.session_state['mes_global'] = mes_seleccionado
            mes_actual = mes_seleccionado
    
    st.markdown(f"### {t('cierre.header_close_month', month=mes_actual)}")
    st.markdown("---")
    
    if is_mes_cerrado(mes_actual):
        st.error(t('cierre.already_closed', month=mes_actual))
        st.info(t('cierre.already_closed_info'))
        return
    
    # Renderizar wizard como fragment aislado
    _render_wizard_fragment(mes_actual)


@st.fragment
def _render_wizard_fragment(mes_actual: str):
    """Fragment aislado para el wizard - se limpia completamente en cada rerun."""
    
    step = st.session_state.get('cierre_step', 1)
    config = load_config()
    metodo_saldo = config.get('cierre', {}).get('metodo_saldo', 'antes_salario')
    st.session_state['metodo_saldo'] = metodo_saldo
    
    # STEP 1
    if step == 1:
        _render_step1(metodo_saldo)
    elif step == 2:
        _render_step2()
    elif step == 3:
        _render_step3(config)
    elif step == 4:
        _render_step4(mes_actual, config, metodo_saldo)
    elif step == 5:
        _render_step5()


def _render_step1(metodo_saldo: str):
    suffix = 'antes' if metodo_saldo == 'antes_salario' else 'despues'
    st.markdown(f"#### {t(f'cierre.wizard.step1.title_{suffix}')}")
    st.markdown(t(f'cierre.wizard.step1.description_{suffix}'))
    
    default_saldo = 0.0
    last_snapshot = get_latest_snapshot()
    if last_snapshot:
         default_saldo = last_snapshot.saldo_inicial_nuevo
         st.info(t('cierre.wizard.step1.expected_balance_info', amount=default_saldo))
    
    saldo = st.number_input(
        t(f'cierre.wizard.step1.input_label_{suffix}'),
        min_value=0.0,
        step=100.0,
        value=default_saldo,
        format="%.2f",
        key="saldo_banco_input"
    )
    
    if st.button(t('cierre.wizard.step1.next_button'), use_container_width=True, key="btn_s1_next"):
        st.session_state['saldo_banco_real'] = saldo
        st.session_state['cierre_step'] = 2
        st.rerun(scope="fragment")


def _render_step2():
    st.markdown(f"#### {t('cierre.wizard.step2.title')}")
    st.markdown(t('cierre.wizard.step2.description'))
    
    nomina = st.number_input(
        t('cierre.wizard.step2.input_label'),
        min_value=0.0,
        step=100.0,
        format="%.2f",
        key="nomina_nueva_input"
    )
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button(t('cierre.wizard.step2.back_button'), key="btn_s2_back", use_container_width=True):
            st.session_state['cierre_step'] = 1
            st.rerun(scope="fragment")
    with c2:
        if st.button(t('cierre.wizard.step2.next_button'), key="btn_s2_next", use_container_width=True):
            st.session_state['nomina_nuevo_mes'] = nomina
            st.session_state['cierre_step'] = 4  # Skip step 3, go directly to step 4
            st.rerun(scope="fragment")


def _render_step3(config: dict):
    st.markdown(f"#### {t('cierre.wizard.step3.title')}")
    
    sc1, sc2 = st.columns(2)
    
    retenciones = config.get('retenciones', {})
    enable_retentions = config.get('enable_retentions', True)
    
    default_pct_rem = retenciones.get('pct_remanente_default', 0)
    default_pct_sal = retenciones.get('pct_salario_default', 20)

    if enable_retentions:
        with sc1:
            pct_remanente = st.slider(
                t('cierre.wizard.step3.surplus_label'),
                min_value=0, max_value=100,
                value=default_pct_rem,
                help=t('cierre.wizard.step3.surplus_help'),
                key="slider_rem"
            ) / 100
        with sc2:
            pct_salario = st.slider(
                t('cierre.wizard.step3.salary_label'),
                min_value=0, max_value=100,
                value=default_pct_sal,
                help=t('cierre.wizard.step3.salary_help'),
                key="slider_sal"
            ) / 100
    else:
        pct_remanente = 0.0
        pct_salario = 0.0
        st.info(t('utilidades.config.enable_retentions_help'))
    
    st.markdown("---")
    
    nc1, nc2 = st.columns(2)
    with nc1:
        if st.button(t('cierre.wizard.step3.back_button'), key="btn_s3_back", use_container_width=True):
            st.session_state['cierre_step'] = 2
            st.rerun(scope="fragment")
    with nc2:
        if st.button(t('cierre.wizard.step3.next_button'), key="btn_s3_next", use_container_width=True):
            st.session_state['pct_remanente'] = pct_remanente
            st.session_state['pct_salario'] = pct_salario
            st.session_state['cierre_step'] = 4
            st.rerun(scope="fragment")


def _render_step4(mes_actual: str, config: dict, metodo_saldo: str):
    st.markdown(f"#### {t('cierre.wizard.step4.title')}")
    
    if 'cierre_error' in st.session_state:
        st.error(t('cierre.wizard.step4.error', error=st.session_state['cierre_error']))
    
    saldo = st.session_state.get('saldo_banco_real', 0)
    nomina = st.session_state.get('nomina_nuevo_mes', 0)
    
    # Retention sliders integrated in step 4 for dynamic adjustment
    retenciones = config.get('retenciones', {})
    enable_retentions = config.get('enable_retentions', True)
    
    default_pct_rem = retenciones.get('pct_remanente_default', 0)
    default_pct_sal = retenciones.get('pct_salario_default', 20)
    
    if enable_retentions:
        st.markdown(f"##### {t('cierre.wizard.step3.title')}")
        sc1, sc2 = st.columns(2)
        with sc1:
            pct_rem = st.slider(
                t('cierre.wizard.step3.surplus_label'),
                min_value=0, max_value=100,
                value=st.session_state.get('pct_remanente_value', default_pct_rem),
                help=t('cierre.wizard.step3.surplus_help'),
                key="slider_rem_step4"
            ) / 100
        with sc2:
            pct_sal = st.slider(
                t('cierre.wizard.step3.salary_label'),
                min_value=0, max_value=100,
                value=st.session_state.get('pct_salario_value', default_pct_sal),
                help=t('cierre.wizard.step3.salary_help'),
                key="slider_sal_step4"
            ) / 100
        st.markdown("---")
    else:
        pct_rem = 0.0
        pct_sal = 0.0
    
    enable_consequences = config.get('enable_consequences', False)
    consequences_data = {'total': 0.0, 'breakdown': []}
    if enable_consequences:
        rules = config.get('consequences_rules', [])
        consequences_data = calculate_consequences(mes_actual, rules)
    consequences_amount = consequences_data['total']
    
    kpis = calcular_kpis(mes_actual)
    
    salario_ya_incluido = (metodo_saldo == 'despues_salario')
    saldo_base_remanente = saldo - nomina if salario_ya_incluido else saldo
    
    retencion_remanente = saldo_base_remanente * pct_rem
    retencion_salario = nomina * pct_sal
    
    # Usar inversion_manual (excluye auto-generadas) para el cálculo total
    total_inversion = kpis['inversion_manual'] + retencion_remanente + retencion_salario + consequences_amount
    transferencia_nueva = retencion_remanente + retencion_salario + consequences_amount
    saldo_fin_mes = saldo_base_remanente - retencion_remanente
    
    st.markdown(f"##### {t('cierre.wizard.step4.summary_title')}")
    
    rc1, rc2 = st.columns(2)
    with rc1:
        st.metric(t('cierre.wizard.step4.metric_bank_balance'), format_currency(saldo))
        st.metric(t('cierre.wizard.step4.metric_new_salary'), format_currency(nomina))
        st.metric(t('cierre.wizard.step4.metric_manual_retentions'), format_currency(kpis['inversion_manual']))
    
    with rc2:
        st.metric(t('cierre.wizard.step4.metric_surplus_retention'), format_currency(retencion_remanente))
        st.metric(t('cierre.wizard.step4.metric_salary_retention'), format_currency(retencion_salario))
        if consequences_amount > 0:
            st.metric(t('cierre.wizard.step4.metric_consequences'), format_currency(consequences_amount))
            # Show breakdown if available
            if consequences_data.get('breakdown'):
                with st.expander(t('consequences.closing_breakdown')):
                    for item in consequences_data['breakdown']:
                        rule_name = item.get('rule_name', 'Unknown')
                        amount = item.get('amount', 0.0)
                        count = item.get('count', 0)
                        st.write(f"**{rule_name}**: {format_currency(amount)} ({count} gasto{'s' if count != 1 else ''})")
        
        st.metric(t('cierre.wizard.step4.metric_total_investment'), format_currency(total_inversion), 
                 delta=f"+{format_currency(transferencia_nueva)} {t('cierre.wizard.step4.metric_new_transfer')}")
    
    st.markdown("---")
    
    # Calculate balances
    saldo_con_salario = saldo_fin_mes + nomina - retencion_salario - consequences_amount
    
    cierre_mes = get_cierre_mes(mes_actual)
    saldo_inicial_mes = cierre_mes.saldo_inicio if (cierre_mes and cierre_mes.saldo_inicio > 0) else 0.0
    
    balance_esperado = saldo_inicial_mes + kpis['balance_mes'] - kpis['total_inversion']
    saldo_comparar = saldo - nomina if salario_ya_incluido else saldo
    desviacion = balance_esperado - saldo_comparar if saldo > 0 else 0
    sym = get_currency_symbol()
    
    # VALIDATION SECTION: Real vs Calculated balance
    st.markdown(f"##### 🔍 Validación de Saldos")
    val_col1, val_col2, val_col3 = st.columns(3)
    with val_col1:
        st.metric(
            t('cierre.wizard.step4.metric_bank_balance'), 
            format_currency(saldo_comparar),
            help="Saldo real actual en tu cuenta bancaria"
        )
    with val_col2:
        st.metric(
            t('cierre.wizard.step4.metric_calculated_balance'), 
            format_currency(balance_esperado),
            help=t('cierre.wizard.step4.metric_calculated_balance_help')
        )
    with val_col3:
        dev_label = t('cierre.wizard.step4.metric_deviation_ok') if abs(desviacion) <= 10 else t('cierre.wizard.step4.metric_deviation_warn')
        st.metric(
            dev_label, 
            f"{desviacion:+,.2f} {sym}",
            delta=t('cierre.wizard.step4.metric_review') if abs(desviacion) > 10 else None,
            delta_color="inverse" if abs(desviacion) > 10 else "off",
            help=t('cierre.wizard.step4.metric_deviation_help')
        )
    
    st.markdown("---")
    
    # MAIN BALANCE: What user will have available next month
    main_col, info_col = st.columns([4, 1])
    with main_col:
        st.markdown(f"### {t('cierre.wizard.step4.metric_balance_with_salary')}: **{format_currency(saldo_con_salario)}**")
    with info_col:
        st.caption(f"ℹ️ {t('cierre.wizard.step4.metric_balance_with_salary_help')}")
    
    ac1, ac2 = st.columns(2)
    with ac1:
        if st.button(t('cierre.wizard.step4.back_button'), key="btn_s4_back", use_container_width=True):
            st.session_state['cierre_step'] = 2  # Go back to step 2 (skip step 3)
            st.rerun(scope="fragment")
    with ac2:
        if st.button(t('cierre.wizard.step4.execute_button'), key="btn_s4_exec", type="primary", use_container_width=True):
            try:
                metodo = st.session_state.get('metodo_saldo', 'antes_salario')
                snapshot = ejecutar_cierre_mes(
                    mes_fiscal=mes_actual,
                    saldo_banco_real=saldo,
                    nomina_nueva=nomina,
                    pct_retencion_remanente=pct_rem,
                    pct_retencion_salario=pct_sal,
                    consequences_amount=consequences_amount,
                    salario_ya_incluido=(metodo == 'despues_salario')
                )
                st.session_state['cierre_step'] = 5
                st.session_state['snapshot'] = snapshot
                st.session_state['transferencia_nueva'] = transferencia_nueva
                st.rerun(scope="fragment")
            except Exception as e:
                st.session_state['cierre_error'] = str(e)
                st.rerun(scope="fragment")


def _render_step5():
    st.markdown(f'<div class="success-message"><h2>{t("cierre.wizard.step4.success")}</h2></div>', 
               unsafe_allow_html=True)
    
    snapshot = st.session_state.get('snapshot')
    transferencia_nueva = st.session_state.get('transferencia_nueva', 0)
    if snapshot:
        year_s, month_s = map(int, snapshot.mes_cierre.split('-'))
        mes_sig = f"{year_s}-{month_s+1:02d}" if month_s < 12 else f"{year_s+1}-01"
        
        st.markdown(f"""
        - **{t('cierre.wizard.step5.closed_month')}:** {snapshot.mes_cierre}
        - **{t('cierre.wizard.step5.retention_executed')}:** {format_currency(transferencia_nueva)}
        - **{t('cierre.wizard.step5.new_month_balance')}:** {format_currency(snapshot.saldo_inicial_nuevo)}
        """)
        
        if snapshot.nomina_nuevo_mes > 0:
            st.success(t('cierre.wizard.step5.salary_registered', 
                        closed_month=snapshot.mes_cierre, 
                        next_month=mes_sig, 
                        amount=format_currency(snapshot.nomina_nuevo_mes)))
    
    if st.button(t('cierre.wizard.step5.new_closure_button'), use_container_width=True, key="btn_new_closure"):
        st.session_state['cierre_step'] = 1
        st.session_state.pop('snapshot', None)
        st.session_state.pop('cierre_error', None)
        st.rerun(scope="fragment")
