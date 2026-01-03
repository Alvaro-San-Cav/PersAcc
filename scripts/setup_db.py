"""
Script de configuración inicial de la base de datos SQLite.
Crea todas las tablas y carga los datos estáticos.

Uso:
    python setup_db.py
"""
import sqlite3
from pathlib import Path

# Ruta de la base de datos
DB_PATH = Path(__file__).parent / "data" / "finanzas.db"


def create_tables(conn: sqlite3.Connection):
    """Crea las tablas del esquema."""
    
    # Tabla CAT_MAESTROS (Categorías)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS CAT_MAESTROS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            tipo_movimiento TEXT NOT NULL CHECK(
                tipo_movimiento IN ('GASTO', 'INGRESO', 'TRASPASO_ENTRADA', 'TRASPASO_SALIDA', 'INVERSION')
            ),
            es_activo BOOLEAN DEFAULT 1
        )
    """)
    
    # Tabla CAT_RELEVANCIA (Psicología del gasto - datos estáticos)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS CAT_RELEVANCIA (
            code TEXT PRIMARY KEY,
            descripcion TEXT NOT NULL
        )
    """)
    
    # Tabla LEDGER (Libro Diario)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS LEDGER (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_real DATE NOT NULL,
            fecha_contable DATE NOT NULL,
            mes_fiscal TEXT NOT NULL,
            tipo_movimiento TEXT NOT NULL CHECK(
                tipo_movimiento IN ('GASTO', 'INGRESO', 'TRASPASO_ENTRADA', 'TRASPASO_SALIDA', 'INVERSION')
            ),
            categoria_id INTEGER REFERENCES CAT_MAESTROS(id),
            relevancia_code TEXT REFERENCES CAT_RELEVANCIA(code),
            concepto TEXT,
            importe REAL NOT NULL CHECK(importe > 0),
            flag_liquidez BOOLEAN DEFAULT 0
        )
    """)
    
    # Tabla SNAPSHOTS_MENSUALES (Cierres)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS SNAPSHOTS_MENSUALES (
            mes_cierre TEXT PRIMARY KEY,
            fecha_ejecucion DATETIME NOT NULL,
            saldo_banco_real REAL NOT NULL,
            nomina_nuevo_mes REAL NOT NULL,
            desviacion_registrada REAL,
            retencion_ejecutada REAL,
            saldo_inicial_nuevo REAL NOT NULL
        )
    """)
    
    # Tabla SNAPSHOTS_ANUALES (Cierres de Fin de Año)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS SNAPSHOTS_ANUALES (
            anio INTEGER PRIMARY KEY,
            fecha_ejecucion DATETIME NOT NULL,
            total_ingresos REAL NOT NULL,
            total_gastos REAL NOT NULL,
            total_ahorrado REAL NOT NULL,
            pct_ahorro REAL,
            gastos_NE REAL,
            gastos_LI REAL,
            gastos_SUP REAL,
            gastos_TON REAL,
            mejor_mes TEXT,
            peor_mes TEXT,
            categoria_mas_gasto TEXT,
            notas TEXT
        )
    """)
    
    # Tabla CIERRES_MENSUALES (Estado de cada mes)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS CIERRES_MENSUALES (
            mes_fiscal TEXT PRIMARY KEY,
            estado TEXT NOT NULL DEFAULT 'ABIERTO' CHECK(estado IN ('ABIERTO', 'CERRADO')),
            fecha_cierre DATETIME,
            saldo_inicio REAL NOT NULL DEFAULT 0,
            salario_mes REAL,
            total_ingresos REAL,
            total_gastos REAL,
            total_inversion REAL,
            saldo_fin REAL,
            nomina_siguiente REAL,
            notas TEXT
        )
    """)
    
    # Índices para optimizar consultas
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_mes ON LEDGER(mes_fiscal)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_fecha ON LEDGER(fecha_real)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_tipo ON LEDGER(tipo_movimiento)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_anio ON LEDGER(substr(mes_fiscal, 1, 4))")
    
    print("✓ Tablas creadas correctamente")


def insert_relevancia_codes(conn: sqlite3.Connection):
    """Inserta los códigos de relevancia estáticos."""
    codes = [
        ("NE", "Necesario / Inevitable"),
        ("LI", "Me gusta / Disfrute consciente"),
        ("SUP", "Superfluo / Optimizable"),
        ("TON", "Tontería / Error de gasto"),
    ]
    
    for code, descripcion in codes:
        conn.execute(
            "INSERT OR IGNORE INTO CAT_RELEVANCIA (code, descripcion) VALUES (?, ?)",
            (code, descripcion)
        )
    
    print("✓ Códigos de relevancia insertados")


def insert_default_categories(conn: sqlite3.Connection):
    """Inserta categorías por defecto para empezar."""
    categorias = [
        # GASTOS
        ("Supermercado", "GASTO"),
        ("Restaurantes", "GASTO"),
        ("Fiesta", "GASTO"),
        ("Alcohol", "GASTO"),
        ("Transporte", "GASTO"),
        ("Regalos yo", "GASTO"),
        ("tarifa movil", "GASTO"),
        ("Ropa", "GASTO"),
        ("Compras", "GASTO"),
        ("Educacion", "GASTO"),
        ("Vacaciones", "GASTO"),
        ("Suscripciones", "GASTO"),
        ("Ocio", "GASTO"),
        ("Liquidar prestamo", "GASTO"),
        ("Dinero que te deben", "GASTO"),
        ("Impuestos", "GASTO"),
        ("Salud", "GASTO"),
        ("Hogar", "GASTO"),
        
        # INVERSION
        ("Inversion extra", "INVERSION"),
        ("Inversion retención de salario", "INVERSION"),
        ("Inversion retención de remanente", "INVERSION"),
        
        # TRASPASO SALIDA
        ("Traspaso a otra cuenta", "TRASPASO_SALIDA"),
        
        # TRASPASO ENTRADA
        ("Ingreso desde otra cuenta", "TRASPASO_ENTRADA"),
        ("Saldo Inicial", "TRASPASO_ENTRADA"),
        
        # INGRESOS
        ("Salario", "INGRESO"),
        ("Regalo", "INGRESO"),
        ("Devolucion", "INGRESO"),
        ("Sodexo devolucion bizum", "INGRESO"),
        ("Prestamo", "INGRESO"),
        ("Venta", "INGRESO"),
    ]
    
    for nombre, tipo in categorias:
        conn.execute(
            "INSERT OR IGNORE INTO CAT_MAESTROS (nombre, tipo_movimiento) VALUES (?, ?)",
            (nombre, tipo)
        )
    
    print(f"✓ {len(categorias)} categorías por defecto insertadas")


def setup_database():
    """Función principal de configuración."""
    # Crear directorio data si no existe
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Configurando base de datos en: {DB_PATH}")
    print("-" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    
    try:
        create_tables(conn)
        insert_relevancia_codes(conn)
        insert_default_categories(conn)
        conn.commit()
        
        print("-" * 50)
        print("✅ Base de datos configurada exitosamente!")
        
        # Verificar tablas creadas
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        print(f"\nTablas creadas: {[t[0] for t in tables]}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
