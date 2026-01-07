"""
Initial Database Setup Script (English Version)
Creates all tables and loads static data with English category names.

Usage:
    python setup_db_en.py
"""
import sqlite3
from pathlib import Path

# Database path (same consistent path)
DB_PATH = Path(__file__).parent / "data" / "finanzas.db"

# Add src to path to import config
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import load_config



def create_tables(conn: sqlite3.Connection):
    """Creates the schema tables."""
    
    # Table CAT_MAESTROS (Categories)
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
    
    # Table CAT_RELEVANCIA (Spending psychology - static data)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS CAT_RELEVANCIA (
            code TEXT PRIMARY KEY,
            descripcion TEXT NOT NULL
        )
    """)
    
    # Table LEDGER (General Ledger)
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
    
    # Table SNAPSHOTS_MENSUALES (Closures)
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
    

    # Table CIERRES_MENSUALES (Month Status)
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
    
    # Table for AI analysis
    conn.execute("""
        CREATE TABLE IF NOT EXISTS AI_ANALYSIS (
            period_type TEXT NOT NULL CHECK(period_type IN ('year', 'month')),
            period_identifier TEXT NOT NULL,
            analysis_text TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            model_used TEXT,
            lang TEXT,
            PRIMARY KEY (period_type, period_identifier)
        )
    """)
    
    # Indexes for optimization
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_mes ON LEDGER(mes_fiscal)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_fecha ON LEDGER(fecha_real)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_tipo ON LEDGER(tipo_movimiento)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_anio ON LEDGER(substr(mes_fiscal, 1, 4))")
    
    print("✓ Tables created successfully")


def insert_relevancia_codes(conn: sqlite3.Connection):
    """Inserts static relevance codes with English descriptions."""
    codes = [
        ("NE", "Necessary / Inevitable"),
        ("LI", "I like it / Conscious enjoyment"),
        ("SUP", "Superfluous / Optimizable"),
        ("TON", "Nonsense / Spending error"),
    ]
    
    for code, descripcion in codes:
        conn.execute(
            "INSERT OR IGNORE INTO CAT_RELEVANCIA (code, descripcion) VALUES (?, ?)",
            (code, descripcion)
        )
    
    print("✓ Relevance codes inserted")


def insert_default_categories(conn: sqlite3.Connection):
    """Inserts default categories in English."""
    categorias = [
        # EXPENSES
        ("Supermarket", "GASTO"),
        ("Restaurants", "GASTO"),
        ("Party", "GASTO"),
        ("Alcohol", "GASTO"),
        ("Transport", "GASTO"),
        ("Self Gifts", "GASTO"),
        ("Mobile Plan", "GASTO"),
        ("Clothing", "GASTO"),
        ("Shopping", "GASTO"),
        ("Education", "GASTO"),
        ("Vacations", "GASTO"),
        ("Subscriptions", "GASTO"),
        ("Leisure", "GASTO"),
        ("Loan Repayment", "GASTO"),
        ("Money Owed to You", "GASTO"),
        ("Taxes", "GASTO"),
        ("Health", "GASTO"),
        ("Home", "GASTO"),
        
        # INVESTMENT
        ("Extra Investment", "INVERSION"),
        ("Salary Retention Investment", "INVERSION"),
        ("Surplus Retention Investment", "INVERSION"),
        
        # OUTGOING TRANSFER
        ("Transfer to another account", "TRASPASO_SALIDA"),
        
        # INCOMING TRANSFER
        ("Deposit from another account", "TRASPASO_ENTRADA"),
        ("Initial Balance", "TRASPASO_ENTRADA"),
        
        # INCOME
        ("Salary", "INGRESO"),
        ("Gift", "INGRESO"),
        ("Refund", "INGRESO"),
        ("Sodexo Refund", "INGRESO"),
        ("Loan", "INGRESO"),
        ("Sale", "INGRESO"),
    ]
    
    for nombre, tipo in categorias:
        conn.execute(
            "INSERT OR IGNORE INTO CAT_MAESTROS (nombre, tipo_movimiento) VALUES (?, ?)",
            (nombre, tipo)
        )
    
    print(f"✓ {len(categorias)} default categories inserted")


def setup_database():
    """Main setup function."""
    # Create data directory if it doesn't exist
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Setting up database at: {DB_PATH}")
    print("-" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    
    try:
        create_tables(conn)
        insert_relevancia_codes(conn)
        insert_default_categories(conn)
        
        # Generate default config.json if not exists
        print("Setting up default configuration file...")
        load_config()
        
        conn.commit()
        
        print("-" * 50)
        print("✅ Database successfully configured!")
        
        # Verify created tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        print(f"\nTables created: {[t[0] for t in tables]}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
