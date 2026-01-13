"""
Script de migración para importar datos históricos desde CSVs.
Soporta múltiples formatos de entrada.

Uso:
    python migration.py <ruta_csv>
    
Formatos soportados:
    1. Formato Simple: fecha, concepto, importe, categoria, relevancia
    2. Formato Banco: fecha, descripcion, cargo, abono
    3. Formato Fondo M: fecha, concepto, importe, tipo (donde tipo puede ser "Fondo M")
"""
import csv
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict, List

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.models import TipoMovimiento, RelevanciaCode, LedgerEntry, Categoria
from src.database import (
    insert_ledger_entry, insert_categoria, get_all_categorias,
    DEFAULT_DB_PATH
)
from src.business_logic import calcular_fecha_contable, calcular_mes_fiscal


# ============================================================================
# MAPEADORES DE CATEGORÍAS
# ============================================================================

# Mapeo de palabras clave a tipos de movimiento
# Mapeo de palabras clave a tipos de movimiento
KEYWORD_TO_TYPE: Dict[str, TipoMovimiento] = {
    # Ingresos
    "nomina": TipoMovimiento.INGRESO,
    "nómina": TipoMovimiento.INGRESO,
    "salario": TipoMovimiento.INGRESO,
    "sueldo": TipoMovimiento.INGRESO,
    "devolucion": TipoMovimiento.INGRESO,
    "devolución": TipoMovimiento.INGRESO,
    "reembolso": TipoMovimiento.INGRESO,
    "ingreso": TipoMovimiento.INGRESO,
    
    # Traspaso de otras cuentas (Entrada)
    "fondo m": TipoMovimiento.TRASPASO_ENTRADA,
    "fondo monetario": TipoMovimiento.TRASPASO_ENTRADA,
    "rescate": TipoMovimiento.TRASPASO_ENTRADA,
    "liquidez": TipoMovimiento.TRASPASO_ENTRADA,
    "traspaso desde": TipoMovimiento.TRASPASO_ENTRADA,
    
    # Ingreso a otras cuentas (Salida)
    "traspaso a": TipoMovimiento.TRASPASO_SALIDA,
    "envio a": TipoMovimiento.TRASPASO_SALIDA,
    "ingreso en": TipoMovimiento.TRASPASO_SALIDA,
    
    # Inversiones
    "inversion": TipoMovimiento.INVERSION,
    "inversión": TipoMovimiento.INVERSION,
    "ahorro": TipoMovimiento.INVERSION,
    "retencion": TipoMovimiento.INVERSION,
    "retención": TipoMovimiento.INVERSION,
    "acciones": TipoMovimiento.INVERSION,
}




def detectar_tipo_movimiento(concepto: str, importe: float, categoria: str = "", mode: str = "GASTO") -> TipoMovimiento:
    """
    Detecta el tipo de movimiento basándose en el concepto y la categoría.
    
    Args:
        concepto: Descripción del movimiento
        importe: Cantidad del movimiento
        categoria: Nombre de la categoría
        mode: Modo de importación ("GASTO", "INGRESO", "INVERSION")
    """
    texto = (concepto + " " + categoria).lower()
    
    # Priority 1: Strict Mode Enforcement (User requested: "si viene de gastos es gasto")
    if mode == "GASTO":
        # Exception: Explicit transfers
        if any(k in texto for k in ["traspaso a", "envio a", "envío a", "transferencia a"]):
            return TipoMovimiento.TRASPASO_SALIDA
        return TipoMovimiento.GASTO
    if mode == "INGRESO":
        return TipoMovimiento.INGRESO
    if mode == "INVERSION":
        return TipoMovimiento.INVERSION
    
    # Legacy logic (only if mode is not specified or mixed)
    for keyword, tipo in KEYWORD_TO_TYPE.items():
        if keyword in texto:
             # Logic overrides
             if mode == "GASTO" and tipo == TipoMovimiento.INVERSION:
                 continue # Ignore guessed investment if we are in GASTO mode (unless forced differently later)
             if mode == "GASTO" and tipo == TipoMovimiento.INGRESO:
                 continue # Ignore guessed income in GASTO mode
             
             # Specific logic for Fondo M / Liquidez
             if tipo == TipoMovimiento.TRASPASO_ENTRADA and mode == "GASTO":
                  return TipoMovimiento.TRASPASO_SALIDA
             
             return tipo
    
    if mode == "INGRESO":
        return TipoMovimiento.INGRESO
        
    return TipoMovimiento.GASTO


def obtener_o_crear_categoria(nombre: str, tipo: TipoMovimiento) -> int:
    """
    Obtiene una categoría existente o crea una nueva.
    Maneja conflictos de nombre (UNIQUE constraint) añadiendo sufijo si es necesario.
    """
    categorias = get_all_categorias()
    
    # Si el usuario menciona explícitamente "Fondo M" y es TRASPASO_SALIDA, 
    # podemos intentar mapearlo a "Envío a otra cuenta" si lo prefiere, 
    # o dejarlo como "Fondo M (TRASPASO_SALIDA)". 
    # Por ahora mantenemos el nombre original + tipo para trazabilidad, 
    # salvo que sea muy genérico.
    
    # 1. Buscar coincidencia exacta (nombre + tipo)
    for cat in categorias:
        if cat.nombre.lower() == nombre.lower() and cat.tipo_movimiento == tipo:
            return cat.id
            
    # 2. Verificar si el nombre ya existe con OTRO tipo (para evitar UNIQUE error)
    nombre_final = nombre
    for cat in categorias:
        if cat.nombre.lower() == nombre.lower():
            # Existe con otro tipo, necesario renombrar
            nombre_final = f"{nombre} ({tipo.value})"
            # Verificar si este nuevo nombre ya existe también
            for sub_cat in categorias:
                 if sub_cat.nombre.lower() == nombre_final.lower() and sub_cat.tipo_movimiento == tipo:
                     return sub_cat.id
            break
    
    # 3. Crear nueva categoría
    try:
        nueva = Categoria(
            id=None,
            nombre=nombre_final,
            tipo_movimiento=tipo,
            es_activo=True
        )
        return insert_categoria(nueva)
    except Exception as e:
        # Fallback de último recurso si falla la inserción
        print(f" [WARN] Error creando categoria '{nombre_final}': {e}. Usando 'Sin categoria'")
        # Intentar buscar o crear 'Sin categoria'
        for cat in categorias:
             if cat.nombre == "Sin categoría" and cat.tipo_movimiento == tipo:
                 return cat.id
        return insert_categoria(Categoria(None, f"Sin categoría ({tipo.value})", tipo, True))


def parse_fecha(fecha_str: str) -> date:
    """
    Parsea una fecha en múltiples formatos.
    """
    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]
    
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_str.strip(), fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"No se pudo parsear la fecha: {fecha_str}")




def parse_importe(importe_str: str) -> float:
    """
    Parsea un importe, manejando diferentes formatos.
    """
    # Limpiar string
    s = importe_str.strip()
    
    # Remover símbolo de moneda
    s = s.replace("€", "").replace("$", "").replace("EUR", "").strip()
    
    # Manejar formato europeo (1.234,56) vs americano (1,234.56)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Formato europeo
            s = s.replace(".", "").replace(",", ".")
        else:
            # Formato americano
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    
    return abs(float(s))


# ============================================================================
# IMPORTADOR PRINCIPAL
# ============================================================================

def importar_csv_simple(csv_path: Path, delimiter: str = ",", mode: str = "GASTO") -> int:
    """
    Importa un CSV con formato simple.
    
    Columnas esperadas (flexibles):
        - fecha / date
        - concepto / descripcion / description
        - importe / amount / cargo / abono
        - categoria / category (opcional)
        - relevancia / relevance (opcional: NE/LI/SUP/TON)
    
    Returns:
        Número de registros importados
    """
    importados = 0
    errores = []
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        
        # Normalizar nombres de columnas
        if reader.fieldnames:
            fieldnames_lower = {col.lower().strip(): col for col in reader.fieldnames}
        else:
            raise ValueError("CSV vacío o sin cabeceras")
        
        # Mapear columnas conocidas
        def get_col(nombres: List[str]) -> Optional[str]:
            for n in nombres:
                if n in fieldnames_lower:
                    return fieldnames_lower[n]
            return None
        
        col_fecha = get_col(["fecha", "date", "fecha_real"])
        col_concepto = get_col(["concepto", "concept", "descripcion", "description", "desc"])
        col_importe = get_col(["importe", "amount", "valor", "value"])
        col_cargo = get_col(["cargo", "gasto", "expense"])
        col_abono = get_col(["abono", "ingreso", "income"])
        col_categoria = get_col(["categoria", "category", "tipo", "type"])
        col_relevancia = get_col(["relevancia", "relevance", "rel"])
        
        if not col_fecha:
            raise ValueError("No se encontró columna de fecha")
        if not col_concepto:
            raise ValueError("No se encontró columna de concepto")
        if not col_importe and not (col_cargo or col_abono):
            raise ValueError("No se encontró columna de importe")
            
        for i, row in enumerate(reader, start=2):
            try:
                # Parsear fecha
                fecha = parse_fecha(row[col_fecha])
                
                # Parsear concepto
                concepto = row[col_concepto].strip()
                if not concepto:
                    continue
                
                # Parsear importe
                if col_importe and row.get(col_importe):
                    importe = parse_importe(row[col_importe])
                elif col_cargo and row.get(col_cargo):
                    importe = parse_importe(row[col_cargo])
                elif col_abono and row.get(col_abono):
                    importe = parse_importe(row[col_abono])
                else:
                    continue  # Skip si no hay importe
                
                if importe <= 0:
                    continue
                
                # Obtener categoría
                categoria_nombre = row.get(col_categoria, "").strip() if col_categoria else ""
                
                # Detectar tipo
                if mode == "INVERSION":
                    tipo = TipoMovimiento.INVERSION
                else:
                    tipo = detectar_tipo_movimiento(concepto, importe, categoria_nombre, mode=mode)
                    
                    # Forzar tipo INGRESO si estamos en modo ingreso y no se detectó nada específico
                    if mode == "INGRESO" and tipo == TipoMovimiento.GASTO:
                        tipo = TipoMovimiento.INGRESO
                
                if not categoria_nombre:
                     if mode == "INGRESO":
                         categoria_nombre = "Ingresos Varios"
                     elif mode == "INVERSION":
                         categoria_nombre = "Inversion Historical"
                     else:
                         categoria_nombre = "Sin categoría"
                
                # Obtener relevancia (solo para gastos)
                relevancia = None
                if tipo == TipoMovimiento.GASTO:
                    if col_relevancia and row.get(col_relevancia):
                        rel_str = row[col_relevancia].upper().strip()
                        if rel_str in ["NE", "LI", "SUP", "TON"]:
                            relevancia = RelevanciaCode(rel_str)
                    if not relevancia:
                        relevancia = RelevanciaCode.LI  # Default: Me gusta
                
                # Obtener o crear categoría
                cat_id = obtener_o_crear_categoria(categoria_nombre, tipo)
                
                # Calcular fechas
                fecha_contable = calcular_fecha_contable(fecha, tipo, flag_liquidez=False, concepto=concepto)
                mes_fiscal = calcular_mes_fiscal(fecha_contable)
                
                # Crear entrada
                entry = LedgerEntry(
                    id=None,
                    fecha_real=fecha,
                    fecha_contable=fecha_contable,
                    mes_fiscal=mes_fiscal,
                    tipo_movimiento=tipo,
                    categoria_id=cat_id,
                    concepto=concepto,
                    importe=importe,
                    relevancia_code=relevancia,
                    flag_liquidez=False
                )
                
                insert_ledger_entry(entry)
                importados += 1
                
            except Exception as e:
                errores.append(f"Fila {i}: {e}")
    
    if errores:
        print(f"\n[WARN] Errores durante la importacion:")
        for err in errores[:10]:  # Mostrar máximo 10 errores
            print(f"  - {err}")
        if len(errores) > 10:
            print(f"  ... y {len(errores) - 10} errores mas")
    
    return importados





# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 60)
    print("  PersAcc - Migracion de Datos")
    print("=" * 60)
    
    mode = "GASTO"
    if "--ingresos" in sys.argv:
        mode = "INGRESO"
        # Remove flag from args to not confuse path detection
        if "--ingresos" in sys.argv: sys.argv.remove("--ingresos")
    elif "--inversion" in sys.argv:
        mode = "INVERSION"
        if "--inversion" in sys.argv: sys.argv.remove("--inversion")

    # Path retrieval after removing flags (basic robustness)
    # Re-reading argv after removal
    if len(sys.argv) < 2:
        print("\nUso: python migration.py <ruta_csv> [--ingresos | --inversion]")
        print("\nFormato esperado del CSV:")
        print("  fecha,concepto,importe,categoria,relevancia")
        print("\nEjemplo:")
        print("  2026-01-02,Supermercado,45.30,Comida,NE")
        return
    
    path_arg = sys.argv[1]
    csv_path = Path(path_arg)
    
    if not csv_path.exists():
        print(f"X El archivo no existe: {csv_path}")
        return
    
    print(f"\n Importando: {csv_path}")
    print("-" * 60)
    
    # Detectar delimitador (tab, punto y coma, o coma)
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        primera_linea = f.readline()
        if "\t" in primera_linea:
            delimiter = "\t"
        elif ";" in primera_linea:
            delimiter = ";"
        else:
            delimiter = ","
    
    try:
        count = importar_csv_simple(csv_path, delimiter, mode)
        print("-" * 60)
        print(f" OK  Importacion completada: {count} registros")
    except Exception as e:
        print(f" ERROR Error durante la importacion: {e}")


if __name__ == "__main__":
    main()
