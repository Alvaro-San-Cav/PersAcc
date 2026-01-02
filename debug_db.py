
import sqlite3
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path.cwd()))

from src.database import get_connection

def debug_ledger():
    db_path = Path("data/finanzas.db")
    print(f"Checking DB at: {db_path.absolute()}")
    
    with get_connection(db_path) as conn:
        # Check counts by type for 2022
        rows = conn.execute("""
            SELECT tipo_movimiento, COUNT(*) as count, SUM(importe) as total 
            FROM LEDGER 
            WHERE strftime('%Y', fecha_real) = '2022'
            GROUP BY tipo_movimiento
        """).fetchall()
        
        print("\nSummary for 2022:")
        for row in rows:
            print(f"Type: {row['tipo_movimiento']}, Count: {row['count']}, Total: {row['total']}")

        # Check specific sample
        print("\nAll Inversions 2024:")
        rows = conn.execute("""
            SELECT fecha_real, concepto, importe, tipo_movimiento, categoria_id 
            FROM LEDGER 
            WHERE strftime('%Y', fecha_real) = '2024' AND tipo_movimiento = 'INVERSION'
            ORDER BY fecha_real
        """).fetchall()
        total_2024 = 0
        for row in rows:
            d = dict(row)
            print(f"{d['fecha_real']} - {d['concepto']}: {d['importe']}")
            total_2024 += d['importe']
        print(f"\nTotal Calculated 2024: {total_2024}")

if __name__ == "__main__":
    debug_ledger()
