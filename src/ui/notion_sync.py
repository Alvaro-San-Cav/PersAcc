"""
Componente UI para sincronización con Notion.
Muestra un popup al inicio para revisar e importar entradas pendientes.
"""
import streamlit as st
from typing import List, Dict, Any, Optional
from datetime import date

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry
from src.database import get_all_categorias, get_categorias_by_tipo, insert_ledger_entry
from src.business_logic import calcular_fecha_contable, calcular_mes_fiscal
from src.config import load_config, get_config_value
from src.i18n import t


def check_notion_enabled() -> bool:
    """Verifica si la integración con Notion está habilitada y configurada."""
    config = load_config()
    notion_config = config.get('notion', {})
    return (
        notion_config.get('enabled', False) and
        notion_config.get('check_on_startup', True) and
        bool(notion_config.get('api_token')) and
        bool(notion_config.get('database_id'))
    )


def _load_notion_entries():
    """Carga las entradas de Notion."""
    from src.integrations.notion import get_notion_client, NotionIntegrationError
    from src.integrations.notion_parser import create_proposed_entry
    
    try:
        client = get_notion_client()
        
        if not client.is_available():
            return None, t('notion.error_library_not_installed')
        elif not client.is_configured():
            return None, t('notion.error_not_configured')
        else:
            raw_entries = client.get_all_entries()
            
            if not raw_entries:
                return [], None
            
            # Procesar y proponer entradas
            proposed = []
            for entry in raw_entries:
                proposed.append(create_proposed_entry(entry))
            return proposed, None
                
    except NotionIntegrationError as e:
        return None, str(e)
    except Exception as e:
        return None, t('notion.error_unexpected').format(error=str(e))


def _delete_from_notion(notion_id: str) -> tuple[bool, str]:
    """Elimina una entrada de Notion. Retorna (éxito, mensaje)."""
    from src.integrations.notion import get_notion_client
    try:
        client = get_notion_client()
        client.delete_entry(notion_id)
        return True, "Entrada eliminada"
    except Exception as e:
        return False, str(e)


def _update_in_notion(notion_id: str, entry: Dict[str, Any], original: Dict[str, Any]) -> tuple[bool, str]:
    """
    Actualiza una entrada en Notion si hay cambios.
    Retorna (hubo_cambios, mensaje).
    """
    from src.integrations.notion import get_notion_client
    
    # Mapear tipo_movimiento a string de Notion (simplificado sin emojis)
    tipo_map = {
        TipoMovimiento.GASTO: 'Gasto',
        TipoMovimiento.INGRESO: 'Ingreso',
        TipoMovimiento.TRASPASO_ENTRADA: 'Traspaso Entrada',
        TipoMovimiento.TRASPASO_SALIDA: 'Traspaso Salida',
        TipoMovimiento.INVERSION: 'Inversión'
    }
    
    # Mapear relevancia a código
    relevancia_code = None
    if entry.get('relevancia_code'):
        relevancia_code = entry['relevancia_code'].value if hasattr(entry['relevancia_code'], 'value') else str(entry['relevancia_code'])
    
    # Obtener nombre de categoría
    categoria_nombre = ""
    if entry.get('categoria_id'):
        from src.database import get_all_categorias
        for cat in get_all_categorias():
            if cat.id == entry['categoria_id']:
                categoria_nombre = cat.nombre
                break
    
    # Construir datos para actualizar
    new_data = {
        'concepto': entry.get('concepto', ''),
        'importe': float(entry.get('importe', 0)),
        'tipo': tipo_map.get(entry.get('tipo_movimiento'), 'Gasto'),
        'categoria': categoria_nombre,
        'relevancia': relevancia_code,
        'fecha': entry.get('fecha')
    }
    
    # Comparar con original (normalizar los tipos de Notion antes de comparar)
    import re
    original_tipo = original.get('tipo', 'Gasto')
    # Limpiar el tipo original de emojis y espacios
    original_tipo_clean = re.sub(r'[^\w\s]', '', original_tipo).strip()
    new_tipo_clean = re.sub(r'[^\w\s]', '', new_data['tipo']).strip()
    
    # Normalizar categorías también
    original_cat = re.sub(r'[^\w\s]', '', original.get('categoria', '')).strip().lower()
    new_cat = re.sub(r'[^\w\s]', '', new_data['categoria']).strip().lower()
    
    changes = (
        new_data['concepto'] != original.get('concepto', '') or
        abs(new_data['importe'] - original.get('importe', 0)) > 0.001 or
        new_tipo_clean.lower() != original_tipo_clean.lower() or
        new_cat != original_cat or
        new_data['fecha'] != original.get('fecha')
    )
    
    # También comparar relevancia si aplica
    if entry.get('tipo_movimiento') == TipoMovimiento.GASTO:
        original_rel = original.get('relevancia', '')
        if new_data['relevancia'] != original_rel:
            changes = True
    
    if not changes:
        return False, "Sin cambios"
    
    try:
        client = get_notion_client()
        success = client.update_entry(notion_id, new_data)
        if success:
            return True, "Actualizado"
        return False, "Error al actualizar"
    except Exception as e:
        return False, str(e)


def _import_entries_to_db(entries: List[Dict[str, Any]]) -> tuple[int, List[str]]:
    """
    Importa las entradas al Ledger y las elimina de Notion.
    Retorna (cantidad importada, lista de errores).
    """
    from src.integrations.notion import get_notion_client
    
    client = get_notion_client()
    imported = 0
    errors = []
    
    for entry in entries:
        try:
            # Validar datos mínimos
            if not entry.get('categoria_id'):
                errors.append(f"'{entry['concepto']}': {t('notion.error_no_category')}")
                continue
            
            # Crear LedgerEntry
            fecha_contable = calcular_fecha_contable(
                entry['fecha'],
                entry['tipo_movimiento']
            )
            mes_fiscal = calcular_mes_fiscal(fecha_contable)
            
            ledger_entry = LedgerEntry(
                id=None,
                fecha_real=entry['fecha'],
                fecha_contable=fecha_contable,
                mes_fiscal=mes_fiscal,
                tipo_movimiento=entry['tipo_movimiento'],
                categoria_id=entry['categoria_id'],
                concepto=entry['concepto'],
                importe=entry['importe'],
                relevancia_code=entry['relevancia_code'],
                flag_liquidez=False
            )
            
            # Insertar en DB
            insert_ledger_entry(ledger_entry)
            
            # Eliminar de Notion
            if entry.get('notion_id'):
                client.delete_entry(entry['notion_id'])
            
            imported += 1
            
        except Exception as e:
            errors.append(f"'{entry['concepto']}': {str(e)}")
    
    return imported, errors


@st.fragment
def _notion_sync_content():
    """Contenido del popup de sincronización con Notion (como fragment aislado)."""
    
    # Inicializar estado
    if 'nsync_entries' not in st.session_state:
        entries, error = _load_notion_entries()
        st.session_state.nsync_entries = entries
        st.session_state.nsync_error = error
    
    # Error
    if st.session_state.nsync_error:
        st.error(t('notion.error_title').format(error=st.session_state.nsync_error))
        if st.button(t('notion.button_close_simple'), key="nsync_close_error", use_container_width=True):
            st.session_state.notion_dialog_open = False
            st.session_state.pop('nsync_entries', None)
            st.session_state.pop('nsync_error', None)
            st.rerun()
        return
    
    # Sin entradas
    entries = st.session_state.nsync_entries or []
    if len(entries) == 0:
        st.info(t('notion.no_entries'))
        if st.button(t('notion.button_close_simple'), key="nsync_close_empty", use_container_width=True):
            st.session_state.notion_dialog_open = False
            st.session_state.pop('nsync_entries', None)
            st.session_state.pop('nsync_error', None)
            st.rerun()
        return
    
    st.markdown(f"### {t('notion.entries_pending').format(count=len(entries))}")
    st.caption(t('notion.caption'))
    
    # Obtener categorías
    cat_by_tipo = {
        TipoMovimiento.GASTO: get_categorias_by_tipo(TipoMovimiento.GASTO),
        TipoMovimiento.INGRESO: get_categorias_by_tipo(TipoMovimiento.INGRESO),
        TipoMovimiento.INVERSION: get_categorias_by_tipo(TipoMovimiento.INVERSION),
    }
    
    # Opciones de acción
    ACCION_IMPORTAR = t('notion.action_import')
    ACCION_ELIMINAR = t('notion.action_delete')
    ACCION_OMITIR = t('notion.action_skip')
    acciones = [ACCION_IMPORTAR, ACCION_ELIMINAR, ACCION_OMITIR]
    
    st.divider()
    
    # Renderizar entradas
    edited_entries = []
    for i, entry in enumerate(entries):
        with st.container(border=True):
            # Fila 1: Acción, Fecha, Tipo
            col_accion, col_fecha, col_tipo = st.columns([1.2, 1.3, 1.8])
            
            with col_accion:
                if f"nsync_accion_{i}" not in st.session_state:
                    st.session_state[f"nsync_accion_{i}"] = ACCION_IMPORTAR
                accion = st.selectbox(
                    t('notion.label_action'),
                    options=acciones,
                    index=acciones.index(st.session_state[f"nsync_accion_{i}"]),
                    key=f"nsync_accion_{i}"
                )
            
            es_eliminar = (accion == ACCION_ELIMINAR)
            # Solo deshabilitar campos si es Eliminar (Omitir permite editar para guardar en Notion)
            disabled = es_eliminar
            
            with col_fecha:
                fecha = st.date_input(t('notion.label_date'), value=entry.get('fecha', date.today()), 
                                      key=f"nsync_fecha_{i}", format="DD/MM/YYYY",
                                      disabled=disabled)
            
            with col_tipo:
                tipo_options = list(TipoMovimiento)
                tipo_names = [
                    t('notion.type_expense'),
                    t('notion.type_income'),
                    t('notion.type_transfer_in'),
                    t('notion.type_transfer_out'),
                    t('notion.type_investment')
                ]
                current_tipo = entry.get('tipo_movimiento', TipoMovimiento.GASTO)
                tipo_idx = tipo_options.index(current_tipo) if current_tipo in tipo_options else 0
                tipo = st.selectbox(t('notion.label_type'), options=tipo_options,
                                   format_func=lambda x: tipo_names[tipo_options.index(x)],
                                   index=tipo_idx, key=f"nsync_tipo_{i}",
                                   disabled=disabled)
            
            # Fila 2: Categoría, Importe, Concepto
            cats = cat_by_tipo.get(tipo, [])
            cat_names = [c.nombre for c in cats]
            cat_ids = [c.id for c in cats]
            
            if cats:
                col_cat, col_importe, col_concepto = st.columns([1.5, 1, 2])
                
                with col_cat:
                    current_cat_id = entry.get('categoria_id')
                    cat_idx = cat_ids.index(current_cat_id) if current_cat_id and current_cat_id in cat_ids else 0
                    cat_selected = st.selectbox(t('notion.label_category'), options=cat_names, index=cat_idx, 
                                               key=f"nsync_cat_{i}", disabled=disabled)
                    categoria_id = cat_ids[cat_names.index(cat_selected)]
                
                with col_importe:
                    importe = st.number_input(t('notion.label_amount'), value=float(entry.get('importe', 0)),
                                             min_value=0.01, step=0.01, format="%.2f", 
                                             key=f"nsync_imp_{i}", disabled=disabled)
                
                with col_concepto:
                    concepto = st.text_input(t('notion.label_concept'), value=entry.get('concepto', ''), 
                                            key=f"nsync_conc_{i}", placeholder=t('notion.placeholder_concept'),
                                            disabled=disabled)
            else:
                categoria_id = None
                col_importe, col_concepto = st.columns([1, 2])
                
                with col_importe:
                    importe = st.number_input(t('notion.label_amount'), value=float(entry.get('importe', 0)),
                                             min_value=0.01, step=0.01, format="%.2f", 
                                             key=f"nsync_imp_{i}", disabled=disabled)
                
                with col_concepto:
                    concepto = st.text_input(t('notion.label_concept'), value=entry.get('concepto', ''), 
                                            key=f"nsync_conc_{i}", placeholder=t('notion.placeholder_concept'),
                                            disabled=disabled)
            
            # Fila 3: Relevancia (solo gastos)
            if tipo == TipoMovimiento.GASTO:
                rel_options = list(RelevanciaCode)
                rel_names = [
                    t('notion.relevance_ne'),
                    t('notion.relevance_li'),
                    t('notion.relevance_sup'),
                    t('notion.relevance_ton')
                ]
                current_rel = entry.get('relevancia_code', RelevanciaCode.LI)
                rel_idx = rel_options.index(current_rel) if current_rel in rel_options else 1
                relevancia = st.selectbox(t('notion.label_relevance'), options=rel_options,
                                         format_func=lambda x: rel_names[rel_options.index(x)],
                                         index=rel_idx, key=f"nsync_rel_{i}",
                                         disabled=disabled)
            else:
                relevancia = None
            
            edited_entries.append({
                'accion': accion,
                'notion_id': entry.get('notion_id'),
                'fecha': fecha,
                'tipo_movimiento': tipo,
                'categoria_id': categoria_id,
                'concepto': concepto,
                'importe': importe,
                'relevancia_code': relevancia,
                'original': entry  # Guardar original para comparar cambios
            })
    
    st.divider()
    
    # Resumen y botones
    import_count = sum(1 for e in edited_entries if e['accion'] == ACCION_IMPORTAR)
    delete_count = sum(1 for e in edited_entries if e['accion'] == ACCION_ELIMINAR)
    skip_count = sum(1 for e in edited_entries if e['accion'] == ACCION_OMITIR)
    
    st.caption(t('notion.summary').format(
        import_count=import_count,
        delete_count=delete_count,
        skip_count=skip_count
    ))
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button(t('notion.button_save'), use_container_width=True,
                    type="primary", key="nsync_save"):
            # Procesar importaciones
            to_import = [e for e in edited_entries if e['accion'] == ACCION_IMPORTAR]
            imported, errors = _import_entries_to_db(to_import)
            
            # Procesar eliminaciones
            deleted = 0
            for entry in edited_entries:
                if entry['accion'] == ACCION_ELIMINAR and entry.get('notion_id'):
                    success, _ = _delete_from_notion(entry['notion_id'])
                    if success:
                        deleted += 1
            
            # Procesar actualizaciones en Notion (para las omitidas con cambios)
            updated = 0
            for entry in edited_entries:
                if entry['accion'] == ACCION_OMITIR and entry.get('notion_id'):
                    had_changes, _ = _update_in_notion(
                        entry['notion_id'], 
                        entry, 
                        entry.get('original', {})
                    )
                    if had_changes:
                        updated += 1
            
            # Mostrar resultado
            msgs = []
            if imported > 0:
                msgs.append(t('notion.success_imported').format(count=imported))
            if deleted > 0:
                msgs.append(t('notion.success_deleted').format(count=deleted))
            if updated > 0:
                msgs.append(t('notion.success_updated').format(count=updated))
            if skip_count > 0 and updated == 0:
                msgs.append(t('notion.success_skipped').format(count=skip_count))
            elif skip_count > updated:
                msgs.append(t('notion.success_skipped_no_changes').format(count=skip_count - updated))
            if errors:
                st.error(t('notion.errors_title') + "\n" + "\n".join(errors))
            if msgs:
                st.success(" | ".join(msgs))
            
            # Cerrar diálogo
            st.session_state.notion_dialog_open = False
            st.session_state.pop('nsync_entries', None)
            st.session_state.pop('nsync_error', None)
            st.rerun()
    
    with col_btn2:
        if st.button(t('notion.button_close'), use_container_width=True, key="nsync_close"):
            st.session_state.notion_dialog_open = False
            st.session_state.pop('nsync_entries', None)
            st.session_state.pop('nsync_error', None)
            st.rerun()


@st.dialog(t('notion.dialog_title'), width="large")
def show_notion_sync_dialog():
    """Modal dialog que muestra las entradas pendientes de Notion."""
    _notion_sync_content()


def check_and_show_notion_sync() -> None:
    """
    Función principal llamada al inicio de la app.
    Verifica si hay entradas en Notion y muestra el diálogo.
    DEBE LLAMARSE AL PRINCIPIO DEL FLUJO DE LA APP.
    """
    if not check_notion_enabled():
        return
    
    # Si ya se mostró el diálogo en esta sesión, no volver a mostrarlo
    # Esta bandera se marca ANTES de mostrar y nunca se resetea
    if st.session_state.get('notion_dialog_was_shown', False):
        return
    
    # Solo verificar una vez por sesión
    if st.session_state.get('notion_entries_checked', False):
        return
    
    st.session_state.notion_entries_checked = True
    
    # Verificar si hay entradas
    try:
        from src.integrations.notion import get_notion_client
        
        client = get_notion_client()
        if client.is_configured():
            entries = client.get_all_entries()
            if entries:
                # Marcar que se mostró ANTES de mostrar el diálogo
                # Así cuando se cierre (con X o botón), no se vuelve a abrir
                st.session_state.notion_dialog_was_shown = True
                show_notion_sync_dialog()
    except Exception:
        pass
