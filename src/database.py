"""
Módulo de base de datos para el sistema de finanzas personales.
Proporciona conexión SQLite y operaciones CRUD para todas las tablas.
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional, List, Callable
from functools import wraps

from src.models import (
    TipoMovimiento, RelevanciaCode, RELEVANCIA_DESCRIPTIONS,
    Categoria, LedgerEntry, SnapshotMensual, CierreMensual
)

# Ruta por defecto de la base de datos
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "finanzas.db"

# =============================================================================
# CACHE WRAPPER - Agnóstico de Streamlit
# =============================================================================

# Intentar usar el cache de Streamlit si está disponible, sino usar functools.lru_cache
_streamlit_available = False
_st_cache_data = None

try:
    import streamlit as st
    _streamlit_available = True
    _st_cache_data = st.cache_data
except ImportError:
    pass


def cache_data(show_spinner: bool = False) -> Callable:
    """
    Decorador de caché compatible con y sin Streamlit.
    Si Streamlit está disponible, usa st.cache_data.
    Si no, usa functools.lru_cache como fallback.
    """
    def decorator(func: Callable) -> Callable:
        if _streamlit_available and _st_cache_data:
            return _st_cache_data(show_spinner=show_spinner)(func)
        else:
            from functools import lru_cache
            return lru_cache(maxsize=128)(func)
    return decorator


def _clear_cache():
    """Invalidar toda la cache de datos."""
    if _streamlit_available:
        import streamlit as st
        st.cache_data.clear()
    # Para lru_cache se necesitaría mantener referencias a las funciones cacheadas
    # pero en contexto de Streamlit esto es suficiente


@contextmanager
def get_connection(db_path: Path = DEFAULT_DB_PATH):
    """Context manager para conexión SQLite con foreign keys habilitadas."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================================
# OPERACIONES CAT_MAESTROS
# ============================================================================

def insert_categoria(categoria: Categoria, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Inserta una nueva categoría y retorna su ID."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO CAT_MAESTROS (nombre, tipo_movimiento, es_activo)
               VALUES (?, ?, ?)""",
            (categoria.nombre, categoria.tipo_movimiento.value, categoria.es_activo)
        )
        _clear_cache()
        return cursor.lastrowid


@cache_data(show_spinner=False)
def get_all_categorias(db_path: Path = DEFAULT_DB_PATH) -> List[Categoria]:
    """Obtiene todas las categorías activas."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM CAT_MAESTROS WHERE es_activo = 1 ORDER BY nombre"
        ).fetchall()
        return [
            Categoria(
                id=row["id"],
                nombre=row["nombre"],
                tipo_movimiento=TipoMovimiento(row["tipo_movimiento"]),
                es_activo=bool(row["es_activo"])
            )
            for row in rows
        ]


@cache_data(show_spinner=False)
def get_categorias_by_tipo(tipo: TipoMovimiento, db_path: Path = DEFAULT_DB_PATH) -> List[Categoria]:
    """Obtiene categorías filtradas por tipo de movimiento."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM CAT_MAESTROS 
               WHERE tipo_movimiento = ? AND es_activo = 1 
               ORDER BY nombre""",
            (tipo.value,)
        ).fetchall()
        return [
            Categoria(
                id=row["id"],
                nombre=row["nombre"],
                tipo_movimiento=TipoMovimiento(row["tipo_movimiento"]),
                es_activo=bool(row["es_activo"])
            )
            for row in rows
        ]


def update_categoria(id: int, nuevo_nombre: str, nuevo_tipo: Optional[TipoMovimiento] = None, db_path: Path = DEFAULT_DB_PATH):
    """
    Actualiza el nombre y/o tipo de una categoría.
    Si cambia el tipo, actualiza también todas las entradas del LEDGER asociadas.
    """
    with get_connection(db_path) as conn:
        # 1. Actualizar nombre de la categoría
        conn.execute(
            "UPDATE CAT_MAESTROS SET nombre = ? WHERE id = ?",
            (nuevo_nombre, id)
        )
        
        # 2. Si hay cambio de tipo, actualizar categoría y ledger
        if nuevo_tipo:
            conn.execute(
                "UPDATE CAT_MAESTROS SET tipo_movimiento = ? WHERE id = ?",
                (nuevo_tipo.value, id)
            )
            # Actualizar entradas históricas
            conn.execute(
                "UPDATE LEDGER SET tipo_movimiento = ? WHERE categoria_id = ?",
                (nuevo_tipo.value, id)
            )
        _clear_cache()


def get_category_counts(db_path: Path = DEFAULT_DB_PATH) -> dict[int, int]:
    """Retorna un diccionario {id_categoria: num_entradas}."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT categoria_id, COUNT(*) as count FROM LEDGER GROUP BY categoria_id"
        ).fetchall()
        return {row["categoria_id"]: row["count"] for row in rows}


def delete_categoria(id: int, db_path: Path = DEFAULT_DB_PATH):
    """
    Intenta eliminar físicamente una categoría.
    Fallará si hay FK constraints (i.e. si tiene entradas).
    """
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM CAT_MAESTROS WHERE id = ?", (id,))
        _clear_cache()


def deactivate_categoria(id: int, db_path: Path = DEFAULT_DB_PATH):
    """
    Desactiva una categoría (soft delete).
    Se usa cuando no se puede borrar porque tiene historial.
    """
    with get_connection(db_path) as conn:
        conn.execute("UPDATE CAT_MAESTROS SET es_activo = 0 WHERE id = ?", (id,))
        _clear_cache()


def get_category_usage_stats(tipo_movimiento: TipoMovimiento, target_month: int, current_year: int, db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Retorna estadisticas de uso de categorias para ordenamiento inteligente.
    Retorna dict: {cat_id: {'history': count, 'curr_year': count}}
    
    Criterios:
    1. Uso en el MISMO mes de años ANTERIORES.
    2. Uso acumulado en el año ACTUAL.
    """
    stats = {}
    with get_connection(db_path) as conn:
        # 1. Histórico (mismo mes, años anteriores)
        rows_hist = conn.execute(
            """SELECT categoria_id, COUNT(*) as count 
               FROM LEDGER 
               WHERE tipo_movimiento = ? 
                 AND CAST(strftime('%m', fecha_real) AS INT) = ?
                 AND CAST(strftime('%Y', fecha_real) AS INT) < ?
               GROUP BY categoria_id""",
            (tipo_movimiento.value, target_month, current_year)
        ).fetchall()
        
        # 2. Año actual
        rows_curr = conn.execute(
            """SELECT categoria_id, COUNT(*) as count 
               FROM LEDGER 
               WHERE tipo_movimiento = ? 
                 AND CAST(strftime('%Y', fecha_real) AS INT) = ?
               GROUP BY categoria_id""",
            (tipo_movimiento.value, current_year)
        ).fetchall()

        # Procesar resultados
        for row in rows_hist:
            cid = row["categoria_id"]
            if cid not in stats: stats[cid] = {'history': 0, 'curr_year': 0}
            stats[cid]['history'] = row["count"]
            
        for row in rows_curr:
            cid = row["categoria_id"]
            if cid not in stats: stats[cid] = {'history': 0, 'curr_year': 0}
            stats[cid]['curr_year'] = row["count"]
            
    return stats


# ============================================================================
# OPERACIONES LEDGER
# ============================================================================

def insert_ledger_entry(entry: LedgerEntry, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Inserta una entrada en el libro diario y retorna su ID."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO LEDGER 
               (fecha_real, fecha_contable, mes_fiscal, tipo_movimiento,
                categoria_id, relevancia_code, concepto, importe, flag_liquidez)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.fecha_real.isoformat(),
                entry.fecha_contable.isoformat(),
                entry.mes_fiscal,
                entry.tipo_movimiento.value,
                entry.categoria_id,
                entry.relevancia_code.value if entry.relevancia_code else None,
                entry.concepto,
                entry.importe,
                entry.flag_liquidez
            )
        )
        _clear_cache()
        return cursor.lastrowid


def delete_ledger_entry(entry_id: int, db_path: Path = DEFAULT_DB_PATH):
    """Elimina una entrada del libro diario por su ID."""
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM LEDGER WHERE id = ?", (entry_id,))
        _clear_cache()


def update_ledger_entry(entry_id: int, categoria_id: int, concepto: str, importe: float, relevancia_code: str = None, db_path: Path = DEFAULT_DB_PATH):
    """Actualiza una entrada del libro diario."""
    with get_connection(db_path) as conn:
        conn.execute(
            """UPDATE LEDGER 
               SET categoria_id = ?, concepto = ?, importe = ?, relevancia_code = ?
               WHERE id = ?""",
            (categoria_id, concepto, importe, relevancia_code, entry_id)
        )
        _clear_cache()


@cache_data(show_spinner=False)
def get_ledger_by_month(mes_fiscal: str, db_path: Path = DEFAULT_DB_PATH) -> List[LedgerEntry]:
    """Obtiene todas las entradas de un mes fiscal específico."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM LEDGER 
               WHERE mes_fiscal = ? 
               ORDER BY fecha_real DESC, id DESC""",
            (mes_fiscal,)
        ).fetchall()
        return [_row_to_ledger_entry(row) for row in rows]


@cache_data(show_spinner=False)
def get_ledger_by_year(anio: int, db_path: Path = DEFAULT_DB_PATH) -> List[LedgerEntry]:
    """Obtiene todas las entradas de un año específico."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM LEDGER 
               WHERE substr(mes_fiscal, 1, 4) = ? 
               ORDER BY fecha_real DESC""",
            (str(anio),)
        ).fetchall()
        return [_row_to_ledger_entry(row) for row in rows]


@cache_data(show_spinner=False)
def get_all_ledger_entries(db_path: Path = DEFAULT_DB_PATH) -> List[LedgerEntry]:
    """Obtiene todas las entradas del libro diario."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM LEDGER ORDER BY fecha_real DESC"
        ).fetchall()
        return [_row_to_ledger_entry(row) for row in rows]


@cache_data(show_spinner=False)
def get_available_years(db_path: Path = DEFAULT_DB_PATH) -> List[int]:
    """Obtiene lista de años con datos en el LEDGER."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT substr(mes_fiscal, 1, 4) as anio 
               FROM LEDGER ORDER BY anio DESC"""
        ).fetchall()
        return [int(row["anio"]) for row in rows]


def _row_to_ledger_entry(row: sqlite3.Row) -> LedgerEntry:
    """Convierte una fila de base de datos a LedgerEntry."""
    return LedgerEntry(
        id=row["id"],
        fecha_real=date.fromisoformat(row["fecha_real"]),
        fecha_contable=date.fromisoformat(row["fecha_contable"]),
        mes_fiscal=row["mes_fiscal"],
        tipo_movimiento=TipoMovimiento(row["tipo_movimiento"]),
        categoria_id=row["categoria_id"],
        relevancia_code=RelevanciaCode(row["relevancia_code"]) if row["relevancia_code"] else None,
        concepto=row["concepto"],
        importe=row["importe"],
        flag_liquidez=bool(row["flag_liquidez"])
    )


# ============================================================================
# OPERACIONES SNAPSHOTS_MENSUALES
# ============================================================================

def insert_snapshot(snapshot: SnapshotMensual, db_path: Path = DEFAULT_DB_PATH) -> str:
    """Inserta un snapshot de cierre de mes."""
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO SNAPSHOTS_MENSUALES 
               (mes_cierre, fecha_ejecucion, saldo_banco_real, nomina_nuevo_mes,
                desviacion_registrada, retencion_ejecutada, saldo_inicial_nuevo)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot.mes_cierre,
                snapshot.fecha_ejecucion.isoformat(),
                snapshot.saldo_banco_real,
                snapshot.nomina_nuevo_mes,
                snapshot.desviacion_registrada,
                snapshot.retencion_ejecutada,
                snapshot.saldo_inicial_nuevo
            )
        )
        return snapshot.mes_cierre


def get_latest_snapshot(db_path: Path = DEFAULT_DB_PATH) -> Optional[SnapshotMensual]:
    """Obtiene el snapshot más reciente."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM SNAPSHOTS_MENSUALES 
               ORDER BY mes_cierre DESC LIMIT 1"""
        ).fetchone()
        if row:
            return SnapshotMensual(
                mes_cierre=row["mes_cierre"],
                fecha_ejecucion=datetime.fromisoformat(row["fecha_ejecucion"]),
                saldo_banco_real=row["saldo_banco_real"],
                nomina_nuevo_mes=row["nomina_nuevo_mes"],
                desviacion_registrada=row["desviacion_registrada"],
                retencion_ejecutada=row["retencion_ejecutada"],
                saldo_inicial_nuevo=row["saldo_inicial_nuevo"]
            )
        return None


def get_snapshot_by_month(mes_cierre: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[SnapshotMensual]:
    """Obtiene un snapshot específico por mes."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM SNAPSHOTS_MENSUALES WHERE mes_cierre = ?",
            (mes_cierre,)
        ).fetchone()
        if row:
            return SnapshotMensual(
                mes_cierre=row["mes_cierre"],
                fecha_ejecucion=datetime.fromisoformat(row["fecha_ejecucion"]),
                saldo_banco_real=row["saldo_banco_real"],
                nomina_nuevo_mes=row["nomina_nuevo_mes"],
                desviacion_registrada=row["desviacion_registrada"],
                retencion_ejecutada=row["retencion_ejecutada"],
                saldo_inicial_nuevo=row["saldo_inicial_nuevo"]
            )
        return None


def get_snapshots_by_year(anio: int, db_path: Path = DEFAULT_DB_PATH) -> List[SnapshotMensual]:
    """Obtiene todos los snapshots mensuales de un año."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM SNAPSHOTS_MENSUALES 
               WHERE substr(mes_cierre, 1, 4) = ? 
               ORDER BY mes_cierre""",
            (str(anio),)
        ).fetchall()
        return [
            SnapshotMensual(
                mes_cierre=row["mes_cierre"],
                fecha_ejecucion=datetime.fromisoformat(row["fecha_ejecucion"]),
                saldo_banco_real=row["saldo_banco_real"],
                nomina_nuevo_mes=row["nomina_nuevo_mes"],
                desviacion_registrada=row["desviacion_registrada"],
                retencion_ejecutada=row["retencion_ejecutada"],
                saldo_inicial_nuevo=row["saldo_inicial_nuevo"]
            )
            for row in rows
        ]





# ============================================================================
# OPERACIONES CIERRES_MENSUALES
# ============================================================================

def get_cierre_mes(mes_fiscal: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[CierreMensual]:
    """Obtiene el cierre de un mes específico."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM CIERRES_MENSUALES WHERE mes_fiscal = ?",
            (mes_fiscal,)
        ).fetchone()
        if row:
            return _row_to_cierre_mensual(row)
        return None


def upsert_cierre_mes(cierre: CierreMensual, db_path: Path = DEFAULT_DB_PATH) -> str:
    """Inserta o actualiza el cierre de un mes."""
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO CIERRES_MENSUALES 
               (mes_fiscal, estado, fecha_cierre, saldo_inicio, salario_mes,
                total_ingresos, total_gastos, total_inversion, saldo_fin,
                nomina_siguiente, notas)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cierre.mes_fiscal,
                cierre.estado,
                cierre.fecha_cierre.isoformat() if cierre.fecha_cierre else None,
                cierre.saldo_inicio,
                cierre.salario_mes,
                cierre.total_ingresos,
                cierre.total_gastos,
                cierre.total_inversion,
                cierre.saldo_fin,
                cierre.nomina_siguiente,
                cierre.notas
            )
        )
        return cierre.mes_fiscal


def is_mes_cerrado(mes_fiscal: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Verifica si un mes ya está cerrado."""
    cierre = get_cierre_mes(mes_fiscal, db_path)
    return cierre is not None and cierre.estado == 'CERRADO'


def abrir_mes(mes_fiscal: str, saldo_inicio: float = 0.0, db_path: Path = DEFAULT_DB_PATH) -> str:
    """Crea o actualiza un registro de mes como ABIERTO con el saldo inicial dado."""
    cierre_existente = get_cierre_mes(mes_fiscal, db_path)
    if cierre_existente and cierre_existente.estado == 'CERRADO':
        raise ValueError(f"El mes {mes_fiscal} ya está cerrado.")
    
    nuevo_cierre = CierreMensual(
        mes_fiscal=mes_fiscal,
        estado='ABIERTO',
        fecha_cierre=None,
        saldo_inicio=saldo_inicio,
        salario_mes=None,
        total_ingresos=None,
        total_gastos=None,
        total_inversion=None,
        saldo_fin=None,
        nomina_siguiente=None,
        notas=None
    )
    return upsert_cierre_mes(nuevo_cierre, db_path)


def _row_to_cierre_mensual(row: sqlite3.Row) -> CierreMensual:
    """Convierte una fila de base de datos a CierreMensual."""
    return CierreMensual(
        mes_fiscal=row["mes_fiscal"],
        estado=row["estado"],
        fecha_cierre=datetime.fromisoformat(row["fecha_cierre"]) if row["fecha_cierre"] else None,
        saldo_inicio=row["saldo_inicio"],
        salario_mes=row["salario_mes"],
        total_ingresos=row["total_ingresos"],
        total_gastos=row["total_gastos"],
        total_inversion=row["total_inversion"],
        saldo_fin=row["saldo_fin"],
        nomina_siguiente=row["nomina_siguiente"],
        notas=row["notas"]
    )


def get_all_meses_fiscales_cerrados(db_path: Path = DEFAULT_DB_PATH) -> List[CierreMensual]:
    """Obtiene todos los registros de cierres mensuales con estado CERRADO, ordenados por mes."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM CIERRES_MENSUALES WHERE estado = 'CERRADO' ORDER BY mes_fiscal ASC"
        ).fetchall()
        return [_row_to_cierre_mensual(row) for row in rows]


# ============================================================================
# OPERACIONES AI_ANALYSIS
# ============================================================================

def get_ai_analysis(period_type: str, period_identifier: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[str]:
    """
    Obtiene el análisis guardado para un período específico.
    
    Args:
        period_type: "year" o "month"
        period_identifier: Identificador del período (ej: "2024" o "2024-01")
        
    Returns:
        El texto del análisis si existe, None si no hay análisis guardado
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT analysis_text FROM AI_ANALYSIS WHERE period_type = ? AND period_identifier = ?",
            (period_type, period_identifier)
        ).fetchone()
        return row["analysis_text"] if row else None


def save_ai_analysis(
    period_type: str, 
    period_identifier: str, 
    analysis_text: str,
    model_used: str = None,
    lang: str = None,
    db_path: Path = DEFAULT_DB_PATH
):
    """
    Guarda o actualiza el análisis de IA para un período.
    
    Args:
        period_type: "year" o "month"
        period_identifier: Identificador del período
        analysis_text: Texto del análisis generado
        model_used: Nombre del modelo usado
        lang: Idioma del análisis
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO AI_ANALYSIS 
               (period_type, period_identifier, analysis_text, created_at, model_used, lang)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (period_type, period_identifier, analysis_text, datetime.now(), model_used, lang)
        )


def delete_ai_analysis(period_type: str, period_identifier: str, db_path: Path = DEFAULT_DB_PATH):
    """Elimina el análisis guardado para un período."""
    with get_connection(db_path) as conn:
        conn.execute(
            "DELETE FROM AI_ANALYSIS WHERE period_type = ? AND period_identifier = ?",
            (period_type, period_identifier)
        )




# ============================================================================
# OPERACIONES PERIOD_NOTES
# ============================================================================

def get_period_notes(period_type: str, period_identifier: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[str]:
    """
    Obtiene las notas del usuario para un período específico.
    """
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT note_text FROM PERIOD_NOTES WHERE period_type = ? AND period_identifier = ?",
            (period_type, period_identifier)
        ).fetchone()
        return row["note_text"] if row else None


def save_period_notes(period_type: str, period_identifier: str, note_text: str, db_path: Path = DEFAULT_DB_PATH):
    """
    Guarda o actualiza las notas del usuario para un período.
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO PERIOD_NOTES 
               (period_type, period_identifier, note_text, updated_at)
               VALUES (?, ?, ?, ?)""",
            (period_type, period_identifier, note_text, datetime.now())
        )
