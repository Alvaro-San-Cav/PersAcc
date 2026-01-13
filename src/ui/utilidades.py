"""
Página de Utilidades - PersAcc
Renderiza la interfaz de utilidades.
"""
import streamlit as st
import subprocess
import csv
import sys
from datetime import date
from pathlib import Path
from io import StringIO
import pandas as pd

from src.config import get_currency_symbol, load_config, save_config
from src.database import get_all_categorias, get_category_counts, get_all_ledger_entries, DEFAULT_DB_PATH
from src.models import TipoMovimiento
from src.ui.manual import render_manual
from src.ui.manual_en import render_manual_en
from src.i18n import t, get_language, set_language, get_language_flag, get_language_name


def render_utilidades():
    """Renderiza la página de utilidades del sistema."""

    
    st.markdown(f'<div class="main-header"><h1>{t("utilidades.title")}</h1></div>', unsafe_allow_html=True)
    
    # Mostrar notificación de éxito si existe (antes de las tabs)
    if st.session_state.get('notify_success'):
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #00c853 0%, #00e676 100%); 
                    color: white; padding: 1rem; border-radius: 10px; 
                    margin-bottom: 1rem; text-align: center; font-weight: bold;
                    box-shadow: 0 4px 15px rgba(0,200,83,0.3);
                    animation: fadeIn 0.5s ease-out;">
            {st.session_state['notify_success']}
        </div>
        <style>
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(-10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
        </style>
        """, unsafe_allow_html=True)
        del st.session_state['notify_success']
    
    # Navegación persistente con Radio Buttons en lugar de Tabs
    tabs_map = {
        t('utilidades.tabs.config'): 'config',
        t('utilidades.tabs.defaults'): 'defaults',  # Nueva tab de valores por defecto
        t('utilidades.tabs.categories'): 'categories',
        t('consequences.title'): 'consequences',
        t('utilidades.tabs.manual'): 'manual',
        t('utilidades.tabs.export'): 'export',
        t('utilidades.tabs.import'): 'import',
        t('utilidades.tabs.cleanup'): 'cleanup'
    }
    
    # Asegurar que la selección persiste si cambia el idioma
    # Si el valor actual no está en las opciones (por cambio de idioma), resetear
    current_selection = st.session_state.get("utilidades_tab_selected")
    if current_selection and current_selection not in tabs_map.keys():
        # Intentar recuperar por índice si es posible, o default a manual
        st.session_state["utilidades_tab_selected"] = list(tabs_map.keys())[0]

    selected_tab_label = st.radio(
        label="Navegación Utilidades",
        options=list(tabs_map.keys()),
        horizontal=True,
        label_visibility="collapsed",
        key="utilidades_tab_selected"
    )
    
    if selected_tab_label == t('utilidades.tabs.manual'):
        # Load correct manual based on language
        current_lang = get_language()
        if current_lang == 'en':
            render_manual_en()
        else:
            render_manual()
    
    
    # ========================
    # TAB 1: EXPORTAR CSV
    # ========================
    if selected_tab_label == t('utilidades.tabs.export'):
        st.markdown(f"### {t('utilidades.export.title')}")
        st.markdown(t('utilidades.export.description'))
        
        entries = get_all_ledger_entries()
        
        if entries:
            st.info(t('utilidades.export.total_entries', count=len(entries)))
            
            # Generar CSV en memoria
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "fecha_real", "fecha_contable", "mes_fiscal", "tipo_movimiento",
                "categoria_id", "concepto", "importe", "relevancia", "flag_liquidez"
            ])
            
            for e in entries:
                writer.writerow([
                    e.fecha_real.isoformat(),
                    e.fecha_contable.isoformat(),
                    e.mes_fiscal,
                    e.tipo_movimiento.value,
                    e.categoria_id,
                    e.concepto,
                    e.importe,
                    e.relevancia_code.value if e.relevancia_code else "",
                    e.flag_liquidez
                ])
            
            csv_content = output.getvalue()
            
            st.download_button(
                label=t('utilidades.export.button'),
                data=csv_content,
                file_name=f"persacc_export_{date.today().isoformat()}.csv",
                mime="text/csv"
            )
        else:
            st.warning(t('utilidades.export.no_entries'))
    
    # ========================
    # TAB 2: IMPORTAR LEGACY
    # ========================
    if selected_tab_label == t('utilidades.tabs.import'):
        st.markdown(f"### {t('utilidades.import.title')}")
        st.markdown(t('utilidades.import.description'))
        
        # Selector de tipo de importación
        tipo_import = st.radio(
            t('utilidades.import.type_label'),
            [t('utilidades.import.types.expenses'), t('utilidades.import.types.income'), t('utilidades.import.types.investments')],
            horizontal=True
        )
        
        is_ingreso = "Ingresos" in tipo_import or "Income" in tipo_import
        is_inversion = "Inversiones" in tipo_import or "Investments" in tipo_import
        
        if is_ingreso:
            st.markdown(f"""
            {t('utilidades.import.format_income')}
            ```
            DATE,CONCEPT,AMOUNT
            01/01/2023,Nomina Enero,2500.00
            ```
            """)
        elif is_inversion:
             st.markdown(f"""
            {t('utilidades.import.format_investments')}
            ```
            DATE,CONCEPT,AMOUNT,CATEGORY
            01/05/2023,Aportacion Fondo,500.00,Inversion
            ```
            """)
        else:
            st.markdown(f"""
            {t('utilidades.import.format_expenses')}
            ```
            DATE,CONCEPT,CATEGORY,RELEVANCE,AMOUNT
            01/01/2025,Supermercado,Comida,NE,45.30
            ```
            """)
        
        uploaded_file = st.file_uploader(t('utilidades.import.uploader_label'), type=['csv'])
        
        if uploaded_file is not None:
            try:
                content = uploaded_file.read().decode('utf-8-sig')
                lines = content.strip().split('\n')
                st.info(t('utilidades.import.file_info', count=len(lines)-1))
                
                # Preview
                st.markdown(t('utilidades.import.preview'))
                preview_lines = lines[:6]
                st.code('\n'.join(preview_lines))
                
                if st.button(t('utilidades.import.button'), type="primary"):
                    # Guardar temporalmente y ejecutar migration
                    temp_path = DEFAULT_DB_PATH.parent / "temp_import.csv"
                    temp_path.write_text(content, encoding='utf-8')
                    
                    try:
                        # Construir comando base use sys.executable for safety
                        cmd = [sys.executable, "migration.py", str(temp_path)]
                        if is_ingreso:
                            cmd.append("--ingresos")
                        elif is_inversion:
                            cmd.append("--inversion")
                        
                        with st.spinner(t('utilidades.import.processing')):
                            result = subprocess.run(
                                cmd,
                                capture_output=True,
                                text=True,
                                cwd=str(DEFAULT_DB_PATH.parent.parent)
                            )
                        st.success(t('utilidades.import.success'))
                        st.code(result.stdout)
                        if result.stderr:
                            st.warning(result.stderr)
                    finally:
                        if temp_path.exists():
                            temp_path.unlink()
                    
            except Exception as e:
                st.error(t('utilidades.import.error', error=str(e)))
    
    # ========================
    # TAB 3: LIMPIAR BD
    # ========================
    if selected_tab_label == t('utilidades.tabs.cleanup'):
        st.markdown(f"### {t('utilidades.cleanup.title')}")
        st.markdown(t('utilidades.cleanup.warning_irreversible'))
        
        # Mostrar mensaje de éxito si existe
        if st.session_state.get('delete_success'):
            st.success(st.session_state['delete_success'])
            del st.session_state['delete_success']
        
        st.markdown("---")
        
        # Opción 1: Limpiar LEDGER y CIERRES
        st.markdown(t('utilidades.cleanup.option1_title'))
        entries_count = len(get_all_ledger_entries())
        st.warning(t('utilidades.cleanup.option1_warning', count=entries_count))
        st.info(t('utilidades.cleanup.option1_info'))
        
        confirm_text_1 = t('utilidades.cleanup.option1_confirm_text')
        confirm1 = st.text_input(
            t('utilidades.cleanup.option1_confirm_label'),
            key="confirm_ledger"
        )
        
        if st.button(t('utilidades.cleanup.option1_button'), type="secondary"):
            if confirm1 == confirm_text_1:
                with get_connection() as conn:
                    conn.execute("DELETE FROM LEDGER")
                    conn.execute("DELETE FROM CIERRES_MENSUALES")
                    # Also clear deprecated tables if exist
                    try:
                        conn.execute("DELETE FROM SNAPSHOTS_MENSUALES")

                    except Exception:
                        pass
                st.session_state['delete_success'] = t('utilidades.cleanup.option1_success', count=entries_count)
                st.rerun()
            else:
                st.error(t('utilidades.cleanup.option1_error'))
        
        st.markdown("---")
        
        # Opción 2: Reset completo
        st.markdown(t('utilidades.cleanup.option2_title'))
        st.error(t('utilidades.cleanup.option2_error'))
        
        confirm_text_2 = t('utilidades.cleanup.option2_confirm_text')
        confirm2 = st.text_input(
            t('utilidades.cleanup.option2_confirm_label'),
            key="confirm_reset"
        )
        
        if st.button(t('utilidades.cleanup.option2_button'), type="primary"):
            if confirm2 == confirm_text_2:
                with get_connection() as conn:
                    conn.execute("DELETE FROM LEDGER")
                    conn.execute("DELETE FROM CIERRES_MENSUALES")
                    conn.execute("DELETE FROM CAT_MAESTROS")
                    try:
                        conn.execute("DELETE FROM SNAPSHOTS_MENSUALES")

                    except Exception:
                        pass
                
                # Regenerar categorías por defecto
                subprocess.run([sys.executable, "setup_db.py"], cwd=str(DEFAULT_DB_PATH.parent.parent), capture_output=True)
                
                st.session_state['delete_success'] = t('utilidades.cleanup.option2_success')
                st.rerun()
            else:
                st.error(t('utilidades.cleanup.option2_error_msg'))

    # ========================
    # TAB 4: GESTIÓN CATEGORÍAS
    # ========================
    if selected_tab_label == t('utilidades.tabs.categories'):
        st.markdown(f"### {t('utilidades.categories.title')}")
        st.info(t('utilidades.categories.info'))
        
        cats = get_all_categorias()
        counts = get_category_counts()
        
        # Ordenar por Tipo y luego Nombre
        cats.sort(key=lambda x: (x.tipo_movimiento.value, x.nombre))
        
        # Preparar datos para el editor
        data = [
            {
                "id": c.id, 
                "nombre": c.nombre, 
                "tipo": c.tipo_movimiento.value, 
                "activo": c.es_activo,
                "conteo": counts.get(c.id, 0)
            } 
            for c in cats
        ]
        
        tipos_validos = [t.value for t in TipoMovimiento]
        
        edited_data = st.data_editor(
            data,
            column_config={
                "id": st.column_config.NumberColumn(t('utilidades.categories.columns.id'), disabled=True),
                "tipo": st.column_config.SelectboxColumn(
                    t('utilidades.categories.columns.type'), 
                    options=tipos_validos,
                    width="medium",
                    required=True
                ),
                "activo": st.column_config.CheckboxColumn(t('utilidades.categories.columns.active'), disabled=True), 
                "nombre": st.column_config.TextColumn(t('utilidades.categories.columns.name'), width="large", required=True),
                "conteo": st.column_config.NumberColumn(t('utilidades.categories.columns.count'), disabled=True, width="small")
            },
            column_order=("tipo", "nombre", "conteo", "activo"), # Ocultar ID, ordenar columnas
            hide_index=True,
            key="editor_categorias",
            use_container_width=True,
            num_rows="dynamic"  # Permitir añadir y borrar filas
        )
        
        if st.button(t('utilidades.categories.button'), type="primary"):
            count_updated = 0
            count_created = 0
            count_deleted = 0
            count_archived = 0
            
            # 1. Detectar CREACIONES (filas nuevas sin ID)
            # st.data_editor no retorna directamente las nuevas vs editadas fácilmente en esta versión,
            # pero las nuevas tienen id=None si lo configuramos, o si vienen del UI suelen venir al final.
            # Estrategia: Iterar edited_data. Si id es None o no existe en originales -> CREAR.
            # Si existe -> ACTUALIZAR.
            # Para BORRADOS: Comparar lista original vs edited_data ids.
            
            # Obtener IDs actuales en el editor
            current_ids = {row["id"] for row in edited_data if row.get("id") is not None}
            original_ids = {c.id for c in cats}
            
            # A. BORRADOS (Smart Delete)
            deleted_ids = original_ids - current_ids
            for did in deleted_ids:
                try:
                    delete_categoria(did)
                    count_deleted += 1
                except Exception:
                    # Fallback: Archivar si tiene integridad referencial (historial)
                    deactivate_categoria(did)
                    count_archived += 1
            
            # B. CREACIONES Y ACTUALIZACIONES

            
            with st.spinner(t('utilidades.categories.processing')):
                for row in edited_data:
                     cid = row.get("id")
                     nombre = row["nombre"]
                     tipo_str = row["tipo"]
                     
                     # Validar inputs básicos
                     if not nombre or not tipo_str:
                         continue
                     
                     if cid is None:
                         # NUEVA CATEGORÍA
                         try:
                             new_cat = Categoria(None, nombre, TipoMovimiento(tipo_str), True)
                             insert_categoria(new_cat)
                             count_created += 1
                         except Exception as e:
                             st.error(f"Error: {e}")
                     else:
                         # EDICIÓN EXISTENTE
                         original = next((c for c in cats if c.id == cid), None)
                         if original:
                             cambio_nombre = original.nombre != nombre
                             cambio_tipo = original.tipo_movimiento.value != tipo_str
                             
                             if cambio_nombre or cambio_tipo:
                                 try:
                                     tipo_enum = TipoMovimiento(tipo_str) if cambio_tipo else None
                                     update_categoria(cid, nombre, tipo_enum)
                                     count_updated += 1
                                 except Exception as e:
                                     st.error(f"Error ({cid}): {e}")

            # Mensajes de feedback
            if count_created + count_updated + count_deleted + count_archived > 0:
                msg = []
                if count_created: msg.append(t('utilidades.categories.created', count=count_created))
                if count_updated: msg.append(t('utilidades.categories.updated', count=count_updated))
                if count_deleted: msg.append(t('utilidades.categories.deleted', count=count_deleted))
                if count_archived: msg.append(t('utilidades.categories.archived', count=count_archived))
                
                # Guardar mensaje en session_state para mostrar después del rerun
                st.session_state['notify_success'] = t('utilidades.categories.success', details=', '.join(msg))
                st.rerun()
            else:
                st.info(t('utilidades.categories.no_changes'))

    # ========================
    # TAB: CONSECUENCIAS
    # ========================
    if selected_tab_label == t('consequences.title'):
        st.markdown(f"### {t('consequences.title')}")
        st.info(t('consequences.info'))
        
        # Cargar configuración y reglas
        config_data = load_config()
        
        if not config_data.get('enable_consequences', False):
             st.warning(f"⚠️ {t('utilidades.config.enable_consequences_help')}")
             st.info("Ve a Configuración para activar esta funcionalidad.")
        else:
            rules = config_data.get('consequences_rules', [])
            
            # Convertir a DataFrame para mejor manejo de tipos en editor
            if rules:
                df_rules = pd.DataFrame(rules)
            else:
                # Definir esquema vacío explícito
                df_rules = pd.DataFrame(columns=[
                    "id", "active", "name", "filter_relevance", 
                    "filter_category", "filter_concept", "action_type", "action_value"
                ])
            
            # Asegurar tipos
            df_rules = df_rules.astype({
                "active": bool,
                "name": str,
                "filter_relevance": str,
                "filter_category": str,
                "filter_concept": str,
                "action_type": str,
                "action_value": float
            })
            
            # Proteger ID si no existe (nuevas filas)
            if "id" not in df_rules.columns:
                df_rules["id"] = None
            
            # Crear columna formateada para mostrar valor con símbolo correcto
            def format_value(row):
                if pd.isna(row.get('action_value')):
                    return ""
                val = float(row.get('action_value', 0))
                action_type = row.get('action_type', 'percent')
                if action_type == 'percent':
                    return f"{val:.1f}%"
                else:
                    return f"{get_currency_symbol()} {val:.2f}"
            
            df_rules['value_display'] = df_rules.apply(format_value, axis=1)

            # Obtener si relevancia está habilitada
            enable_relevance = config_data.get('enable_relevance', True)
            
            column_config = {
                "id": None, # Oculto
                "active": st.column_config.CheckboxColumn(t('consequences.table_columns.active'), width="small", default=True),
                "name": st.column_config.TextColumn(t('consequences.table_columns.name'), required=True, width="medium"),
                "filter_category": st.column_config.SelectboxColumn(
                    t('consequences.table_columns.filter_cat'),
                    options=[""] + [c.nombre for c in get_all_categorias()],
                    required=False, width="medium"
                ),
                "filter_concept": st.column_config.TextColumn(t('consequences.table_columns.filter_concept'), required=False),
                "action_type": st.column_config.SelectboxColumn(
                    t('consequences.table_columns.action_type'),
                    options=["percent", "fixed"],
                    required=True, width="small", default="percent"
                ),
                "action_value": st.column_config.NumberColumn(
                    "Valor (número)", 
                    min_value=0.0, step=0.1, required=True, width="small",
                    help="Ingrese el número. El formato se muestra en la siguiente columna."
                ),
                "value_display": st.column_config.TextColumn(
                    t('consequences.table_columns.action_value'),
                    disabled=True,
                    width="small",
                    help="Formato automático: % para porcentajes, moneda para valores fijos"
                )
            }
            
            # Solo mostrar columna de relevancia si está habilitada
            if enable_relevance:
                column_config["filter_relevance"] = st.column_config.SelectboxColumn(
                    t('consequences.table_columns.filter_rel'), 
                    options=["", "NE", "LI", "SUP", "TON"],
                    required=False, width="small"
                )
                column_order = ["active", "name", "filter_relevance", "filter_category", "filter_concept", "action_type", "action_value", "value_display"]
            else:
                # Ocultar columna de relevancia
                column_config["filter_relevance"] = None
                column_order = ["active", "name", "filter_category", "filter_concept", "action_type", "action_value", "value_display"]
            
            # Actualizar value_display antes de mostrar
            df_rules['value_display'] = df_rules.apply(format_value, axis=1)
            
            edited_df = st.data_editor(
                df_rules,
                column_config=column_config,
                column_order=column_order,
                num_rows="dynamic",
                use_container_width=True,
                key="rules_editor",
                hide_index=True
            )
            
            if st.button(t('consequences.save_button'), type="primary"):
                try:
                    new_rules_list = []
                    
                    # Iterar sobre DataFrame editado (convertir a records)
                    # replace nan with None/empty string for clean json
                    records = edited_df.replace({pd.NA: None, float('nan'): None}).to_dict('records')
                    
                    for row in records:
                        # Validar nombre obligatorio
                        if not row.get("name") or str(row.get("name")).strip() == "":
                            continue
                            
                        r_id = row.get("id")
                        # Si es None o NaN o vacio
                        if not r_id or pd.isna(r_id):
                            r_id = str(uuid.uuid4())
                        
                        new_rules_list.append({
                            "id": r_id,
                            "active": bool(row.get("active", True)),
                            "name": str(row.get("name")),
                            "filter_relevance": str(row.get("filter_relevance", "") or ""),
                            "filter_category": str(row.get("filter_category", "") or ""),
                            "filter_concept": str(row.get("filter_concept", "") or ""),
                            "action_type": str(row.get("action_type", "percent")),
                            "action_value": float(row.get("action_value", 0.0))
                        })
                    
                    config_data['consequences_rules'] = new_rules_list
                    save_config(config_data)
                    st.success(t('consequences.success'))
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving rules: {e}")

    # ========================
    # TAB 5: CONFIGURACIÓN
    # ========================
    if selected_tab_label == t('utilidades.tabs.config'):
        st.markdown(f"### {t('utilidades.config.title')}")
        
        # Cargar configuración desde archivo
        config = load_config()
        
        
        # Botón de guardar configuración (al principio)
        if st.button(t('utilidades.config.button'), type="primary", key="save_config_btn", use_container_width=True):
            # Recopilar valores de los widgets
            default_rem = st.session_state.get('config_pct_remanente', 0)
            default_sal = st.session_state.get('config_pct_salario', 20)
            metodo_saldo = st.session_state.get('config_metodo_saldo', 'antes_salario')
            enable_relevance = st.session_state.get('config_enable_relevance', True)
            enable_retentions = st.session_state.get('config_enable_retentions', True)
            enable_consequences = st.session_state.get('config_enable_consequences', False)
            enable_llm = st.session_state.get('config_enable_llm', False)
            
            # Actualizar configuración
            current_lang = get_language()
            idioma_seleccionado = st.session_state.get('config_language', current_lang)
            divisa_seleccionada = st.session_state.get('config_currency', 'EUR')
            config['language'] = idioma_seleccionado
            config['currency'] = divisa_seleccionada
            config['enable_relevance'] = enable_relevance
            config['enable_retentions'] = enable_retentions
            config['enable_consequences'] = enable_consequences
            
            # Actualizar configuración de LLM
            if 'llm' not in config:
                config['llm'] = {}
            config['llm']['enabled'] = enable_llm
            
            # Guardar modelo seleccionado si LLM está habilitado
            if enable_llm:
                selected_model = st.session_state.get('config_llm_model')
                if selected_model:
                    config['llm']['model_tier'] = selected_model
            
            config['retenciones'] = {
                'pct_remanente_default': default_rem,
                'pct_salario_default': default_sal
            }
            config['cierre'] = {
                'metodo_saldo': metodo_saldo
            }
            
            # Guardar a archivo
            save_config(config)
            
            # Si cambió el idioma, actualizarlo en session
            if idioma_seleccionado != current_lang:
                set_language(idioma_seleccionado)
            
            # También actualizar session_state para uso inmediato
            st.session_state['default_pct_remanente'] = default_rem
            st.session_state['default_pct_salario'] = default_sal
            
            # Guardar mensaje en session_state para mostrar después del rerun
            st.session_state['notify_success'] = t('utilidades.config.success')
            st.rerun()
        
        st.markdown("---")
        

        # SECCIÓN 0: Idioma
        st.markdown("#### 🌐 Language / Idioma")
        current_lang = get_language()
        
        idioma_seleccionado = st.selectbox(
            "Select Language / Seleccionar Idioma",
            options=['es', 'en'],
            format_func=lambda x: f"{get_language_flag(x)} {get_language_name(x)}",
            index=0 if current_lang == 'es' else 1,
            key="config_language"
        )
        
        st.markdown("---")
        
        # SECCIÓN: Divisa / Currency
        st.markdown("#### 💱 Currency / Divisa")
        
        # Lista de divisas comunes
        CURRENCIES = {
            "EUR": "€ Euro (EUR)",
            "USD": "$ US Dollar (USD)",
            "GBP": "£ British Pound (GBP)",
            "CHF": "₣ Swiss Franc (CHF)",
            "JPY": "¥ Japanese Yen (JPY)",
            "CNY": "¥ Chinese Yuan (CNY)",
            "MXN": "$ Mexican Peso (MXN)",
            "ARS": "$ Argentine Peso (ARS)",
            "COP": "$ Colombian Peso (COP)",
            "BRL": "R$ Brazilian Real (BRL)"
        }
        
        current_currency = config.get('currency', 'EUR')
        currency_list = list(CURRENCIES.keys())
        current_index = currency_list.index(current_currency) if current_currency in currency_list else 0
        
        divisa_seleccionada = st.selectbox(
            t('utilidades.config.currency_label'),
            options=currency_list,
            format_func=lambda x: CURRENCIES.get(x, x),
            index=current_index,
            key="config_currency"
        )

        st.markdown("---")

        # SECCIÓN: Características / Features
        st.markdown(t('utilidades.config.section_features_title'))
        
        enable_relevance = st.toggle(
            t('utilidades.config.enable_relevance_label'),
            value=config.get('enable_relevance', True),
            help=t('utilidades.config.enable_relevance_help'),
            key="config_enable_relevance"
        )
        
        enable_retentions = st.toggle(
            t('utilidades.config.enable_retentions_label'),
            value=config.get('enable_retentions', True),
            help=t('utilidades.config.enable_retentions_help'),
            key="config_enable_retentions"
        )
        
        enable_consequences = st.toggle(
            t('utilidades.config.enable_consequences_label'),
            value=config.get('enable_consequences', False),
            help=t('utilidades.config.enable_consequences_help'),
            key="config_enable_consequences"
        )
        
        enable_llm = st.toggle(
            t('utilidades.config.enable_llm_label'),
            value=config.get('llm', {}).get('enabled', False),
            help=t('utilidades.config.enable_llm_help'),
            key="config_enable_llm"
        )
        
        # Selector de modelo de Ollama (solo si LLM está habilitado)
        if enable_llm:
            from src.llm_service import check_ollama_running, get_available_models
            
            st.markdown(t('utilidades.config.ai_config_title'))
            
            # Verificar si Ollama está corriendo
            if check_ollama_running():
                available_models = get_available_models()
                
                if available_models:
                    st.success(t('utilidades.config.ollama_detected', count=len(available_models)))
                    
                    current_model = config.get('llm', {}).get('model_tier', 'light')
                    
                    # Si el modelo actual no está en la lista, usar el primero disponible
                    if current_model not in available_models:
                        default_index = 0
                    else:
                        default_index = available_models.index(current_model)
                    
                    selected_model = st.selectbox(
                        t('utilidades.config.llm_model_label'),
                        options=available_models,
                        index=default_index,
                        help=t('utilidades.config.llm_model_help'),
                        key="config_llm_model"
                    )
                else:
                    st.warning(t('utilidades.config.ollama_no_models_warn'))
                    st.info(t('utilidades.config.llm_no_models'))
                    selected_model = config.get('llm', {}).get('model_tier', 'light')
            else:
                st.error(t('utilidades.config.ollama_not_running_err'))
                st.info(t('utilidades.config.llm_not_running'))
                selected_model = config.get('llm', {}).get('model_tier', 'light')

        st.markdown("---")


        # SECCIÓN 1: Retenciones
        st.markdown(t('utilidades.config.section1_title'))
        st.info(t('utilidades.config.section1_info'))
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_rem = st.slider(
                t('utilidades.config.slider_rem_label'),
                min_value=0,
                max_value=100,
                value=config.get('retenciones', {}).get('pct_remanente_default', 0),
                help=t('utilidades.config.slider_rem_help'),
                key="config_pct_remanente"
            )
        
        with col2:
            default_sal = st.slider(
                t('utilidades.config.slider_sal_label'),
                min_value=0,
                max_value=100,
                value=config.get('retenciones', {}).get('pct_salario_default', 20),
                help=t('utilidades.config.slider_sal_help'),
                key="config_pct_salario"
            )
        
        
        # SECCIÓN: Método de Cierre
        st.markdown(t('utilidades.config.section_closing_title'))
        
        metodo_actual = config.get('cierre', {}).get('metodo_saldo', 'antes_salario')
        metodo_saldo = st.radio(
            t('utilidades.config.closing_method_label'),
            options=['antes_salario', 'despues_salario'],
            format_func=lambda x: t(f'utilidades.config.method_{x.split("_")[0]}'),
            index=0 if metodo_actual == 'antes_salario' else 1,
            help=t('utilidades.config.closing_method_help'),
            key="config_metodo_saldo",
            horizontal=True
        )
        
    # ========================
    # TAB: VALORES POR DEFECTO
    # ========================
    if selected_tab_label == t('utilidades.tabs.defaults'):
        st.markdown(f"### {t('utilidades.defaults.title')}")
        st.info(t('utilidades.defaults.info'))
        
        # Cargar configuración y categorías
        config = load_config()
        enable_relevance = config.get('enable_relevance', True)
        
        conceptos = config.get('conceptos_default', {})
        importes = config.get('importes_default', {})
        relevancias = config.get('relevancias_default', {})
        
        cats = get_all_categorias()
        cats.sort(key=lambda x: (x.tipo_movimiento.value, x.nombre))
        
        # Preparar datos para el editor
        table_data = []
        for cat in cats:
            cat_key = cat.nombre.lower().replace(" ", "_")
            is_gasto = cat.tipo_movimiento == TipoMovimiento.GASTO
            
            row_data = {
                "cat_key": cat_key,
                "tipo": cat.tipo_movimiento.value,
                "categoria": cat.nombre,
                "concepto": conceptos.get(cat_key, ""),
                "importe": importes.get(cat_key, 0.0),
            }
            
            # Solo incluir relevancia si está habilitada
            if enable_relevance:
                row_data["relevancia"] = relevancias.get(cat_key, "") if is_gasto else "-"
            
            table_data.append(row_data)
        
        # Crear DataFrame
        df = pd.DataFrame(table_data)
        
        # Configurar editor con columnas apropiadas
        column_config = {
            "cat_key": None,  # Oculto
            "tipo": st.column_config.TextColumn(
                t('utilidades.defaults.columns.type'), 
                disabled=True,
                width="small"
            ),
            "categoria": st.column_config.TextColumn(
                t('utilidades.defaults.columns.category'), 
                disabled=True,
                width="medium"
            ),
            "concepto": st.column_config.TextColumn(
                t('utilidades.defaults.columns.concept'),
                width="large"
            ),
            "importe": st.column_config.NumberColumn(
                t('utilidades.defaults.columns.amount'),
                min_value=0.0,
                step=0.01,
                format="%.2f",
                width="small"
            )
        }
        
        # Solo mostrar columna de relevancia si está habilitada
        if enable_relevance:
            column_config["relevancia"] = st.column_config.SelectboxColumn(
                t('utilidades.defaults.columns.relevance'),
                options=["", "NE", "LI", "SUP", "TON", "-"],
                width="small",
                help="Solo aplica para categorías de tipo GASTO"
            )
        
        edited_df = st.data_editor(
            df,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            key="defaults_editor",
            num_rows="fixed"  # No permitir añadir/borrar filas
        )
        
        if st.button(t('utilidades.defaults.button'), type="primary", use_container_width=True):
            try:
                nuevos_conceptos = {}
                nuevos_importes = {}
                nuevas_relevancias = {}
                
                for _, row in edited_df.iterrows():
                    cat_key = row['cat_key']
                    
                    # Guardar concepto si no está vacío
                    if row['concepto'] and str(row['concepto']).strip():
                        nuevos_conceptos[cat_key] = str(row['concepto']).strip()
                    
                    # Guardar importe si es > 0
                    if row['importe'] and float(row['importe']) > 0:
                        nuevos_importes[cat_key] = float(row['importe'])
                    
                    # Guardar relevancia solo si está habilitada y es válida
                    if enable_relevance and 'relevancia' in row and row['relevancia'] and row['relevancia'] not in ["", "-"]:
                        nuevas_relevancias[cat_key] = str(row['relevancia'])
                
                config['conceptos_default'] = nuevos_conceptos
                config['importes_default'] = nuevos_importes
                config['relevancias_default'] = nuevas_relevancias
                
                save_config(config)
                
                st.session_state['notify_success'] = t('utilidades.defaults.success')
                st.rerun()
                
            except Exception as e:
                st.error(f"Error: {e}")
