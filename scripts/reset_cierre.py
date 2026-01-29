"""
Script para resetear un cierre de mes y permitir relanzarlo.
Elimina los registros relacionados con el cierre de un mes específico.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "finanzas.db"

def reset_cierre(mes_fiscal: str):
    """
    Elimina todos los datos relacionados con un cierre específico:
    - SNAPSHOTS_MENSUALES
    - CIERRES_MENSUALES (cambia estado a ABIERTO)
    - Entradas auto-generadas en LEDGER (salario, retenciones)
    """
    print(f"Reseteando cierre del mes: {mes_fiscal}")
    
    # Calcular mes siguiente
    year, month = map(int, mes_fiscal.split('-'))
    if month == 12:
        mes_siguiente = f"{year+1}-01"
    else:
        mes_siguiente = f"{year}-{month+1:02d}"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. Eliminar snapshot del mes
        conn.execute("DELETE FROM SNAPSHOTS_MENSUALES WHERE mes_cierre = ?", (mes_fiscal,))
        print(f"  [OK] Eliminado snapshot de {mes_fiscal}")
        
        # 2. Reabrir el mes (cambiar estado a ABIERTO)
        conn.execute("""
            UPDATE CIERRES_MENSUALES 
            SET estado = 'ABIERTO', fecha_cierre = NULL 
            WHERE mes_fiscal = ?
        """, (mes_fiscal,))
        print(f"  [OK] Reabierto mes {mes_fiscal}")
        
        # 3. Eliminar entradas auto-generadas del mes cerrado
        deleted = conn.execute("""
            DELETE FROM LEDGER 
            WHERE mes_fiscal = ? AND concepto LIKE '%(auto-generada)%'
        """, (mes_fiscal,)).rowcount
        print(f"  [OK] Eliminadas {deleted} entradas auto-generadas de {mes_fiscal}")
        
        # 4. Eliminar entradas auto-generadas del mes siguiente (salario + retenciones)
        deleted2 = conn.execute("""
            DELETE FROM LEDGER 
            WHERE mes_fiscal = ? AND concepto LIKE '%(auto-generada)%'
        """, (mes_siguiente,)).rowcount
        print(f"  [OK] Eliminadas {deleted2} entradas auto-generadas de {mes_siguiente}")
        
        # 5. Eliminar el mes siguiente si estaba abierto y vacío (opcional)
        conn.execute("""
            DELETE FROM CIERRES_MENSUALES 
            WHERE mes_fiscal = ? AND estado = 'ABIERTO'
        """, (mes_siguiente,))
        
        conn.commit()
        print(f"\n[SUCCESS] Cierre de {mes_fiscal} reseteado correctamente.")
        print("Ahora puedes volver a ejecutar el cierre desde la aplicación.")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        # Por defecto, resetear 2026-01
        mes = "2026-01"
    else:
        mes = sys.argv[1]
    
    reset_cierre(mes)
