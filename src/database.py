"""
Módulo de base de datos para el sistema de finanzas personales.
Proporciona conexión SQLite y operaciones CRUD para todas las tablas.
"""
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional, List, Callable

from src.models import (
    TipoMovimiento, RelevanciaCode,
    Categoria, LedgerEntry, SnapshotMensual, CierreMensual, EstadoCierre
)
from src.disk_cache import disk_cache

logger = logging.getLogger(__name__)

# Ruta por defecto de la base de datos
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "finanzas.db"

# =============================================================================
# CACHE WRAPPER - Agnóstico de Streamlit
# =============================================================================

# Intentar usar el cache de Streamlit si está disponible, sino usar functools.lru_cache
_streamlit_available = False
_st_cache_data = None
_migrated_db_paths: set[str] = set()
_fallback_cached_functions: list[Callable] = []

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
            cached_func = lru_cache(maxsize=128)(func)
            _fallback_cached_functions.append(cached_func)
            return cached_func
    return decorator


def _clear_cache():
    """Invalidar toda la cache de datos."""
    if _streamlit_available:
        import streamlit as st
        st.cache_data.clear()
    else:
        # En ejecuciones sin Streamlit (tests/scripts), limpiar también lru_cache.
        for func in _fallback_cached_functions:
            cache_clear = getattr(func, "cache_clear", None)
            if callable(cache_clear):
                cache_clear()


def _clear_ledger_cache():
    """Invalida solo las cachés de consultas del LEDGER (más eficiente que _clear_cache)."""
    for func in (get_ledger_by_month, get_ledger_by_year, get_all_ledger_entries, get_available_years):
        clear = getattr(func, "clear", None)
        if callable(clear):
            clear()
    if not _streamlit_available:
        for func in _fallback_cached_functions:
            cache_clear = getattr(func, "cache_clear", None)
            if callable(cache_clear):
                cache_clear()


def _clear_category_cache():
    """Invalida solo las cachés de categorías (más eficiente que _clear_cache)."""
    for func in (get_all_categorias, get_categorias_by_tipo):
        clear = getattr(func, "clear", None)
        if callable(clear):
            clear()
    if not _streamlit_available:
        for func in _fallback_cached_functions:
            cache_clear = getattr(func, "cache_clear", None)
            if callable(cache_clear):
                cache_clear()


@contextmanager
def get_connection(db_path: Path = DEFAULT_DB_PATH):
    """Context manager para conexión SQLite con foreign keys habilitadas."""
    resolved_db_path = str(Path(db_path).resolve())
    conn = sqlite3.connect(resolved_db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        # MIGRATION CHECK (una vez por DB en el proceso):
        # asegurar que existe la columna descripcion_ia en CAT_MAESTROS.
        if resolved_db_path not in _migrated_db_paths:
            try:
                conn.execute("ALTER TABLE CAT_MAESTROS ADD COLUMN descripcion_ia TEXT")
            except sqlite3.OperationalError:
                pass  # La columna ya existe o la tabla no aplica en ese contexto
            _migrated_db_paths.add(resolved_db_path)
            
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
            """INSERT INTO CAT_MAESTROS (nombre, tipo_movimiento, es_activo, descripcion_ia)
               VALUES (?, ?, ?, ?)""",
            (categoria.nombre, categoria.tipo_movimiento.value, categoria.es_activo, categoria.descripcion_ia)
        )
        _clear_category_cache()
        return cursor.lastrowid


@cache_data(show_spinner=False)
@disk_cache()
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
                es_activo=bool(row["es_activo"]),
                descripcion_ia=dict(row).get("descripcion_ia")
            )
            for row in rows
        ]


@cache_data(show_spinner=False)
@disk_cache()
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
                es_activo=bool(row["es_activo"]),
                descripcion_ia=dict(row).get("descripcion_ia")
            )
            for row in rows
        ]


def update_categoria(id: int, nuevo_nombre: str, nuevo_tipo: Optional[TipoMovimiento] = None, nueva_descripcion: Optional[str] = None, db_path: Path = DEFAULT_DB_PATH):
    """
    Actualiza el nombre, tipo y descripción de IA de una categoría.
    Si cambia el tipo, actualiza también todas las entradas del LEDGER asociadas.
    """
    with get_connection(db_path) as conn:
        # 1. Actualizar nombre de la categoría
        conn.execute(
            "UPDATE CAT_MAESTROS SET nombre = ?, descripcion_ia = ? WHERE id = ?",
            (nuevo_nombre, nueva_descripcion, id)
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
        if nuevo_tipo:
            _clear_ledger_cache()
        _clear_category_cache()


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
        _clear_category_cache()


def deactivate_categoria(id: int, db_path: Path = DEFAULT_DB_PATH):
    """
    Desactiva una categoría (soft delete).
    Se usa cuando no se puede borrar porque tiene historial.
    """
    with get_connection(db_path) as conn:
        conn.execute("UPDATE CAT_MAESTROS SET es_activo = 0 WHERE id = ?", (id,))
        _clear_category_cache()


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
        _clear_ledger_cache()
        return cursor.lastrowid


def batch_insert_ledger_entries(entries: List[LedgerEntry], db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Inserta múltiples entradas en el ledger en una sola transacción.
    Limpia la caché una única vez al finalizar.
    Retorna el número de entradas insertadas correctamente.
    """
    inserted = 0
    with get_connection(db_path) as conn:
        for entry in entries:
            conn.execute(
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
            inserted += 1
    _clear_ledger_cache()
    return inserted


def delete_ledger_entry(entry_id: int, db_path: Path = DEFAULT_DB_PATH):
    """Elimina una entrada del libro diario por su ID."""
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM LEDGER WHERE id = ?", (entry_id,))
        _clear_ledger_cache()


def update_ledger_entry(entry_id: int, categoria_id: int, concepto: str, importe: float, relevancia_code: str = None, db_path: Path = DEFAULT_DB_PATH):
    """Actualiza una entrada del libro diario."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT tipo_movimiento FROM LEDGER WHERE id = ?",
            (entry_id,)
        ).fetchone()

        if row is None:
            raise ValueError(f"No existe entrada con id={entry_id}")

        tipo_mov = TipoMovimiento(row["tipo_movimiento"])

        # Regla de negocio: relevancia solo para gastos.
        if tipo_mov != TipoMovimiento.GASTO:
            relevancia_code = None
        elif relevancia_code:
            # Validar códigos permitidos para detectar errores antes de persistir.
            RelevanciaCode(relevancia_code)

        conn.execute(
            """UPDATE LEDGER 
               SET categoria_id = ?, concepto = ?, importe = ?, relevancia_code = ?
               WHERE id = ?""",
            (categoria_id, concepto, importe, relevancia_code, entry_id)
        )
        _clear_ledger_cache()


@cache_data(show_spinner=False)
@disk_cache()
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
@disk_cache()
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
@disk_cache()
def get_all_ledger_entries(db_path: Path = DEFAULT_DB_PATH) -> List[LedgerEntry]:
    """Obtiene todas las entradas del libro diario."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM LEDGER ORDER BY fecha_real DESC"
        ).fetchall()
        return [_row_to_ledger_entry(row) for row in rows]


@cache_data(show_spinner=False)
@disk_cache()
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
    tipo_mov = TipoMovimiento(row["tipo_movimiento"])

    rel_raw = row["relevancia_code"]
    relevancia = None

    if tipo_mov == TipoMovimiento.GASTO:
        if rel_raw:
            try:
                relevancia = RelevanciaCode(rel_raw)
            except ValueError:
                logger.warning(
                    "Invalid relevancia_code '%s' for LEDGER id=%s; setting to NULL in memory",
                    rel_raw,
                    row["id"],
                )
    elif rel_raw:
        # Datos legacy inconsistentes: no romper la UI por registros inválidos.
        logger.warning(
            "Ignoring relevancia_code '%s' for non-GASTO LEDGER id=%s",
            rel_raw,
            row["id"],
        )

    return LedgerEntry(
        id=row["id"],
        fecha_real=date.fromisoformat(row["fecha_real"]),
        fecha_contable=date.fromisoformat(row["fecha_contable"]),
        mes_fiscal=row["mes_fiscal"],
        tipo_movimiento=tipo_mov,
        categoria_id=row["categoria_id"],
        relevancia_code=relevancia,
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


def execute_month_closure_transaction(
    ledger_entries: List[LedgerEntry],
    cierre: CierreMensual,
    snapshot: SnapshotMensual,
    mes_siguiente: str,
    saldo_inicio_mes_siguiente: float,
    db_path: Path = DEFAULT_DB_PATH,
) -> SnapshotMensual:
    """
    Persiste el cierre de mes completo de forma atómica.

    Operaciones incluidas en UNA sola transacción:
    1. Inserción de entradas LEDGER auto-generadas del cierre.
    2. UPSERT del mes cerrado en CIERRES_MENSUALES.
    3. Apertura/actualización del mes siguiente como ABIERTO (si no está CERRADO).
    4. Inserción del snapshot de auditoría.
    """
    with get_connection(db_path) as conn:
        for entry in ledger_entries:
            conn.execute(
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
                    entry.flag_liquidez,
                ),
            )

        conn.execute(
            """INSERT OR REPLACE INTO CIERRES_MENSUALES
               (mes_fiscal, estado, fecha_cierre, saldo_inicio, salario_mes,
                total_ingresos, total_gastos, total_inversion, saldo_fin,
                nomina_siguiente, notas)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cierre.mes_fiscal,
                cierre.estado.value,
                cierre.fecha_cierre.isoformat() if cierre.fecha_cierre else None,
                cierre.saldo_inicio,
                cierre.salario_mes,
                cierre.total_ingresos,
                cierre.total_gastos,
                cierre.total_inversion,
                cierre.saldo_fin,
                cierre.nomina_siguiente,
                cierre.notas,
            ),
        )

        row = conn.execute(
            "SELECT estado FROM CIERRES_MENSUALES WHERE mes_fiscal = ?",
            (mes_siguiente,),
        ).fetchone()

        # Mantener compatibilidad con el flujo previo: si el mes siguiente ya está
        # cerrado, no se abre ni se modifica.
        if not row or row["estado"] != "CERRADO":
            conn.execute(
                """INSERT OR REPLACE INTO CIERRES_MENSUALES
                   (mes_fiscal, estado, fecha_cierre, saldo_inicio, salario_mes,
                    total_ingresos, total_gastos, total_inversion, saldo_fin,
                    nomina_siguiente, notas)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mes_siguiente,
                    "ABIERTO",
                    None,
                    saldo_inicio_mes_siguiente,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )

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
                snapshot.saldo_inicial_nuevo,
            ),
        )

    _clear_cache()
    return snapshot


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
                cierre.estado.value,
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
    return cierre is not None and cierre.estado == EstadoCierre.CERRADO


def abrir_mes(mes_fiscal: str, saldo_inicio: float = 0.0, db_path: Path = DEFAULT_DB_PATH) -> str:
    """Crea o actualiza un registro de mes como ABIERTO con el saldo inicial dado."""
    cierre_existente = get_cierre_mes(mes_fiscal, db_path)
    if cierre_existente and cierre_existente.estado == EstadoCierre.CERRADO:
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
