"""
Página de Utilidades - PersAcc
Renderiza la interfaz de utilidades.
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
from src.ui.manual import render_manual
from src.ui.manual_en import render_manual_en
from src.i18n import t, get_language, set_language, get_language_flag, get_language_name


def render_utilidades():
    """Renderiza la página de utilidades del sistema."""
    from src.database import get_all_ledger_entries, get_connection, DEFAULT_DB_PATH
    import csv
    from io import StringIO
    
    st.markdown(f'<div class="main-header"><h1>{t("utilidades.title")}</h1></div>', unsafe_allow_html=True)
    
    # Sub-tabs para diferentes utilidades
    util_tab_manual, util_tab1, util_tab2, util_tab3, util_tab4, util_tab5 = st.tabs([
        t('utilidades.tabs.manual'),
        t('utilidades.tabs.export'),
        t('utilidades.tabs.import'),
        t('utilidades.tabs.cleanup'),
        t('utilidades.tabs.categories'),
        t('utilidades.tabs.config')
    ])
    
    with util_tab_manual:
        # Load correct manual based on language
        current_lang = get_language()
        if current_lang == 'en':
            render_manual_en()
        else:
            render_manual()
    
    
    # ========================
    # TAB 1: EXPORTAR CSV
    # ========================
    with util_tab1:
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
    with util_tab2:
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
                        import subprocess
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
    with util_tab3:
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

                    except:
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

                    except:
                        pass
                
                # Regenerar categorías por defecto
                import subprocess
                subprocess.run([sys.executable, "setup_db.py"], cwd=str(DEFAULT_DB_PATH.parent.parent), capture_output=True)
                
                st.session_state['delete_success'] = t('utilidades.cleanup.option2_success')
                st.rerun()
            else:
                st.error(t('utilidades.cleanup.option2_error_msg'))

    # ========================
    # TAB 4: GESTIÓN CATEGORÍAS
    # ========================
    with util_tab4:
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
            from src.models import Categoria  # Import local para evitar circular si fuera necesario
            
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
                
                st.success(t('utilidades.categories.success', details=', '.join(msg)))

                st.rerun()
            else:
                st.info(t('utilidades.categories.no_changes'))

    # ========================
    # TAB 5: CONFIGURACIÓN
    # ========================
    with util_tab5:
        st.markdown(f"### {t('utilidades.config.title')}")
        
        # Cargar configuración desde archivo
        from src.config import load_config, save_config
        config = load_config()
        
        
        # Botón de guardar configuración (al principio)
        if st.button(t('utilidades.config.button'), type="primary", key="save_config_btn", use_container_width=True):
            # Recopilar valores de los widgets
            default_rem = st.session_state.get('config_pct_remanente', 0)
            default_sal = st.session_state.get('config_pct_salario', 20)
            metodo_saldo = st.session_state.get('config_metodo_saldo', 'antes_salario')
            
            # Recopilar conceptos desde todos los inputs
            nuevos_conceptos = {}
            categorias = get_all_categorias()
            for cat in categorias:
                cat_key = cat.nombre.lower().replace(" ", "_")
                input_key = f"concepto_{cat.id}"
                if input_key in st.session_state:
                    nuevos_conceptos[cat_key] = st.session_state[input_key]
            
            # Actualizar configuración
            current_lang = get_language()
            idioma_seleccionado = st.session_state.get('config_language', current_lang)
            config['language'] = idioma_seleccionado
            config['retenciones'] = {
                'pct_remanente_default': default_rem,
                'pct_salario_default': default_sal
            }
            config['cierre'] = {
                'metodo_saldo': metodo_saldo
            }
            config['conceptos_default'] = nuevos_conceptos
            
            # Guardar a archivo
            save_config(config)
            
            # Si cambió el idioma, actualizarlo en session
            if idioma_seleccionado != current_lang:
                set_language(idioma_seleccionado)
            
            # También actualizar session_state para uso inmediato
            st.session_state['default_pct_remanente'] = default_rem
            st.session_state['default_pct_salario'] = default_sal
            
            st.success(t('utilidades.config.success'))
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
        
        st.markdown("---")
        
        # SECCIÓN 2: Conceptos por defecto
        st.markdown(t('utilidades.config.section2_title'))
        st.info(t('utilidades.config.section2_info'))
        
        conceptos = config.get('conceptos_default', {})
        
        # Cargar todas las categorías desde DB
        cats = get_all_categorias()
        cats.sort(key=lambda x: (x.tipo_movimiento.value, x.nombre))
        
        # Mostrar inputs para cada categoría
        nuevos_conceptos = {}
        
        # Agrupar por tipo para mejor organización
        current_tipo = None
        for cat in cats:
            if cat.tipo_movimiento != current_tipo:
                current_tipo = cat.tipo_movimiento
                st.markdown(f"**{current_tipo.value}**")
            
            # Usar nombre en minúsculas como clave
            key = cat.nombre.lower().replace(" ", "_")
            valor_actual = conceptos.get(key, "")
            
            nuevos_conceptos[key] = st.text_input(
                f"📝 {cat.nombre}",
                value=valor_actual,
                placeholder=t('utilidades.config.input_placeholder', cat=cat.nombre),
                key=f"config_concepto_{key}",
                label_visibility="visible"
            )
        

