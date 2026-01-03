"""
Lógica de negocio para el sistema de finanzas personales.
Implementa: Calculadora de KPIs, Algoritmo de Cierre, Análisis de Gastos.
"""
from datetime import date, datetime
from typing import Dict, Optional
from pathlib import Path
import calendar

from .models import TipoMovimiento, LedgerEntry, SnapshotMensual, CierreMensual
from .database import (
    get_ledger_by_month, insert_snapshot, get_latest_snapshot,
    insert_ledger_entry, get_all_categorias,
    get_cierre_mes, upsert_cierre_mes, is_mes_cerrado, abrir_mes,
    DEFAULT_DB_PATH
)
from .constants import (
    NOMINA_KEYWORDS,
    CATEGORIA_SALARIO, CATEGORIA_INVERSION_SALARIO, CATEGORIA_INVERSION_REMANENTE,
    CATEGORIA_INVERSION_EXTRA, STOPWORDS_ES, MIN_WORD_LENGTH, DEFAULT_WORD_LIMIT
)





# ============================================================================
# UTILIDADES DE FECHA
# ============================================================================

def calcular_fecha_contable(
    fecha_real: date,
    tipo: TipoMovimiento,
    flag_liquidez: bool = False,
    concepto: str = ""
) -> date:
    """
    Calcula la fecha contable de una transacción.
    
    Simplificado: La fecha contable siempre es igual a la fecha real.
    
    Args:
        fecha_real: Fecha real de la transacción
        tipo: Tipo de movimiento
        flag_liquidez: Flag de liquidez (mantenido para compatibilidad)
        concepto: Concepto de la transacción (mantenido para compatibilidad)
    
    Returns:
        Fecha contable (igual a fecha_real)
    """
    return fecha_real


def calcular_mes_fiscal(fecha_contable: date) -> str:
    """
    Genera el identificador de mes fiscal en formato 'YYYY-MM'.
    
    Args:
        fecha_contable: Fecha contable de la transacción
    
    Returns:
        String con formato 'YYYY-MM'
    """
    return fecha_contable.strftime("%Y-%m")


# ============================================================================
# CALCULADORA DE KPIs (Sanitizada)
# ============================================================================

def calcular_kpis(mes_fiscal: str, db_path: Path = DEFAULT_DB_PATH) -> Dict:
    """
    Calcula los KPIs de un mes fiscal específico.
    
    Args:
        mes_fiscal: Mes en formato 'YYYY-MM'
        db_path: Ruta a la base de datos
    
    Returns:
        Diccionario con totales de Ingresos, Gastos, Inversiones, etc.
    """
    entries = get_ledger_by_month(mes_fiscal, db_path)
    
    total_ingresos = sum(
        e.importe for e in entries 
        if e.tipo_movimiento == TipoMovimiento.INGRESO
    )
    
    total_gastos = sum(
        e.importe for e in entries 
        if e.tipo_movimiento == TipoMovimiento.GASTO
    )
    
    total_traspasos_entrada = sum(
        e.importe for e in entries 
        if e.tipo_movimiento == TipoMovimiento.TRASPASO_ENTRADA
    )
    
    total_traspasos_salida = sum(
        e.importe for e in entries 
        if e.tipo_movimiento == TipoMovimiento.TRASPASO_SALIDA
    )

    total_inversion = sum(
        e.importe for e in entries 
        if e.tipo_movimiento == TipoMovimiento.INVERSION
    )
    
    # Calcular % de retención sobre salario (ahorro líquido + inversión)
    # Definición: Capacidad de ahorro (Cashflow) = Ingresos + Entradas - Gastos - Salidas
    # Nota: Inversión no se resta aquí si lo consideramos parte del "Ahorro generado", 
    # pero para "Saldo" sí se restaría. 
    # La variable se llama 'ahorro_total' pero se mapea a 'balance_mes'.
    # Si el usuario pide "saldo actual", debería ser lo que queda en cuenta.
    
    # Ajuste solicitado: Detraer TRASPASO_SALIDA
    ahorro_total = (total_ingresos + total_traspasos_entrada) - (total_gastos + total_traspasos_salida)
    
    pct_salary_retention = 0.0
    if total_ingresos > 0:
        pct_salary_retention = ahorro_total / total_ingresos
    
    return {
        "mes_fiscal": mes_fiscal,
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "total_traspasos_entrada": total_traspasos_entrada,
        "total_traspasos_salida": sum(e.importe for e in entries if e.tipo_movimiento == TipoMovimiento.TRASPASO_SALIDA),
        "total_inversion": total_inversion,
        "pct_salary_retention": pct_salary_retention,
        "balance_mes": ahorro_total,
    }


def calcular_kpis_relevancia(mes_fiscal: str, db_path: Path = DEFAULT_DB_PATH) -> Dict:
    """
    Calcula el desglose de gastos por categoría de relevancia.
    
    Args:
        mes_fiscal: Mes en formato 'YYYY-MM'
        db_path: Ruta a la base de datos
    
    Returns:
        Diccionario con totales por cada código de relevancia (NE, LI, SUP, TON)
    """
    from .models import RelevanciaCode
    
    entries = get_ledger_by_month(mes_fiscal, db_path)
    gastos = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    
    resultado = {code.value: 0.0 for code in RelevanciaCode}
    for gasto in gastos:
        if gasto.relevancia_code:
            resultado[gasto.relevancia_code.value] += gasto.importe
    
    return resultado


# ============================================================================
# ALGORITMO DE CIERRE DE MES (El Wizard)
# ============================================================================

def calcular_inversion_cierre(
    retenciones_manuales: float,
    saldo_banco_real: float,
    nomina_nueva: float,
    pct_retencion_remanente: float = 0.0,
    pct_retencion_salario: float = 0.0
) -> float:
    """
    Calcula el total a transferir a inversión al cerrar el mes.
    
    Fórmula:
    Inversión = (Σ Retenciones Manuales) + (SaldoBancoReal × %Ret.Remanente) + (NuevaNómina × %Ret.Salario)
    
    Nota: Las retenciones manuales ya salieron del banco, así que el cálculo 
    de transferencia final solo ejecuta la parte del Remanente y Salario.
    
    Args:
        retenciones_manuales: Suma de TRANS_INVERSION_OUT del mes
        saldo_banco_real: Dinero real en el banco antes de cobrar
        nomina_nueva: Importe de la nueva nómina
        pct_retencion_remanente: % a retener del saldo remanente (0-1)
        pct_retencion_salario: % a retener de la nómina nueva (0-1)
    
    Returns:
        Total a transferir a inversión
    """
    retencion_remanente = saldo_banco_real * pct_retencion_remanente
    retencion_salario = nomina_nueva * pct_retencion_salario
    
    # Total contabilizado (ya transferido + a transferir ahora)
    total_inversion = retenciones_manuales + retencion_remanente + retencion_salario
    
    return total_inversion


def ejecutar_cierre_mes(
    mes_fiscal: str,
    saldo_banco_real: float,
    nomina_nueva: float,
    pct_retencion_remanente: float = 0.0,
    pct_retencion_salario: float = 0.0,
    consequences_amount: float = 0.0,
    db_path: Path = DEFAULT_DB_PATH,
    salario_ya_incluido: bool = False
) -> SnapshotMensual:
    """
    Ejecuta el cierre de mes completo:
    1. Verifica que el mes no esté ya cerrado.
    2. Calcula KPIs y retenciones.
    3. Crea entrada de Salario para el MES SIGUIENTE (fecha 01/MM+1).
    4. Guarda el cierre en CIERRES_MENSUALES.
    5. Abre el mes siguiente con el saldo final como saldo inicial.
    
    Args:
        mes_fiscal: Mes a cerrar en formato 'YYYY-MM'
        saldo_banco_real: Dinero real en el banco (puede incluir o no la nómina según salario_ya_incluido)
        nomina_nueva: Importe de la nueva nómina (para el MES SIGUIENTE)
        pct_retencion_remanente: % a retener del saldo remanente
        pct_retencion_salario: % a retener de la nómina nueva
        db_path: Ruta a la base de datos
        salario_ya_incluido: Si True, el saldo_banco_real YA incluye la nómina nueva
    
    Returns:
        Snapshot del cierre guardado
        
    Raises:
        ValueError: Si el mes ya está cerrado.
    """
    # 1. Verificar que el mes no esté cerrado
    if is_mes_cerrado(mes_fiscal, db_path):
        raise ValueError(f"El mes {mes_fiscal} ya está cerrado.")
    
    # 2. Obtener KPIs del mes actual
    kpis = calcular_kpis(mes_fiscal, db_path)
    
    # 3. Obtener saldo inicial del mes (desde CIERRES_MENSUALES o 0)
    cierre_actual = get_cierre_mes(mes_fiscal, db_path)
    saldo_inicio = cierre_actual.saldo_inicio if cierre_actual else 0.0
    
    # 4. Calcular retención total
    retencion_ejecutada = calcular_inversion_cierre(
        retenciones_manuales=kpis["total_inversion"],
        saldo_banco_real=saldo_banco_real,
        nomina_nueva=nomina_nueva,
        pct_retencion_remanente=pct_retencion_remanente,
        pct_retencion_salario=pct_retencion_salario
    )
    
    # Solo la parte nueva a transferir (excluyendo retenciones manuales ya hechas)
    transferencia_nueva = retencion_ejecutada - kpis["total_inversion"]
    
    # Calcular saldo base para retención de remanente
    # Si salario_ya_incluido=True, el saldo real del mes (sin la nómina nueva) es saldo - nómina
    if salario_ya_incluido:
        saldo_base_remanente = saldo_banco_real - nomina_nueva
    else:
        saldo_base_remanente = saldo_banco_real
    
    # Retenciones separadas
    retencion_remanente = saldo_base_remanente * pct_retencion_remanente
    retencion_salario = nomina_nueva * pct_retencion_salario
    
    # 4b. Crear entrada en LEDGER para la retención del remanente (en el mes actual)
    if retencion_remanente > 0:
        # Calcular último día del mes actual

        year_cierre, month_cierre = map(int, mes_fiscal.split('-'))
        last_day = calendar.monthrange(year_cierre, month_cierre)[1]
        fecha_retencion = date(year_cierre, month_cierre, last_day)
        
        # Buscar categoría específica "Inversion retención de remanente"
        categorias_all = get_all_categorias(db_path)
        cat_remanente = next((c for c in categorias_all if c.nombre.lower() == CATEGORIA_INVERSION_REMANENTE.lower()), None)
        
        # Fallback
        if not cat_remanente:
            cat_remanente = next((c for c in categorias_all if c.nombre.lower() == CATEGORIA_INVERSION_EXTRA.lower()), None)
        if not cat_remanente:
             cat_remanente = next((c for c in categorias_all if c.tipo_movimiento == TipoMovimiento.INVERSION), None)
             
        if cat_remanente:
            entry_remanente = LedgerEntry(
                id=None,
                fecha_real=fecha_retencion,
                fecha_contable=fecha_retencion,
                mes_fiscal=mes_fiscal,
                tipo_movimiento=TipoMovimiento.INVERSION,
                categoria_id=cat_remanente.id,
                concepto=f"Retención remanente {mes_fiscal} (auto-generada)",
                importe=retencion_remanente,
                relevancia_code=None,
                flag_liquidez=False
            )
            insert_ledger_entry(entry_remanente, db_path)
    
    # 5. Calcular saldo final del mes actual (después de retención del remanente, ANTES del salario)
    # Si el saldo ya incluye la nómina, usamos saldo_base_remanente como punto de partida
    if salario_ya_incluido:
        saldo_fin = saldo_base_remanente - retencion_remanente
    else:
        saldo_fin = saldo_banco_real - retencion_remanente
    
    # 6. Calcular saldo inicial del mes siguiente (saldo_fin + salario - retención salario)
    saldo_inicio_siguiente = saldo_fin + nomina_nueva - retencion_salario
    
    # 6. Calcular mes siguiente
    year, month = map(int, mes_fiscal.split('-'))
    if month == 12:
        mes_siguiente = f"{year+1}-01"
        dia_salario = date(year+1, 1, 1)
    else:
        mes_siguiente = f"{year}-{month+1:02d}"
        dia_salario = date(year, month+1, 1)
    
    # 7. Buscar categoría "Salario"
    categorias = get_all_categorias(db_path)
    cat_salario = next((c for c in categorias if c.nombre.lower() == CATEGORIA_SALARIO.lower() and c.tipo_movimiento == TipoMovimiento.INGRESO), None)
    
    if cat_salario and nomina_nueva > 0:
        # 8. Crear entrada de Salario para el mes siguiente
        entrada_salario = LedgerEntry(
            id=None,
            fecha_real=dia_salario,
            fecha_contable=dia_salario,
            mes_fiscal=mes_siguiente,
            tipo_movimiento=TipoMovimiento.INGRESO,
            categoria_id=cat_salario.id,
            concepto=f"Nómina {mes_siguiente} (auto-generada)",
            importe=nomina_nueva,
            relevancia_code=None,
            flag_liquidez=True
        )
        insert_ledger_entry(entrada_salario, db_path)
        
        # 8b. Crear entrada de Inversión por retención de salario (si > 0)
        if retencion_salario > 0:
            # Buscar categoría específica "Inversion retención de salario"
            cat_inversion = next((c for c in categorias if c.nombre.lower() == CATEGORIA_INVERSION_SALARIO.lower() and c.tipo_movimiento == TipoMovimiento.INVERSION), None)
            
            # Si no existe, fallback a "Inversion extra" o cualquiera de INVERSION
            if not cat_inversion:
                cat_inversion = next((c for c in categorias if c.tipo_movimiento == TipoMovimiento.INVERSION), None)
            
            if cat_inversion:
                entrada_retencion_salario = LedgerEntry(
                    id=None,
                    fecha_real=dia_salario,
                    fecha_contable=dia_salario,
                    mes_fiscal=mes_siguiente,
                    tipo_movimiento=TipoMovimiento.INVERSION,
                    categoria_id=cat_inversion.id,
                    concepto=f"Retención salario {mes_siguiente} (auto-generada)",
                    importe=retencion_salario,
                    relevancia_code=None,
                    flag_liquidez=False
                )
                insert_ledger_entry(entrada_retencion_salario, db_path)
                insert_ledger_entry(entrada_retencion_salario, db_path)

        # 8c. Crear entrada de Inversión por CONSECUENCIAS (si > 0)
        if consequences_amount > 0:
             # Buscar o crear categoría "Inversión consecuencias"
             cat_cons = next((c for c in categorias if c.nombre.lower() == "inversión consecuencias"), None)
             
             if not cat_cons:
                 cat_cons = next((c for c in categorias if c.tipo_movimiento == TipoMovimiento.INVERSION), None)
                 
             if cat_cons:
                 entrada_consecuencias = LedgerEntry(
                     id=None,
                     fecha_real=dia_salario,
                     fecha_contable=dia_salario,
                     mes_fiscal=mes_siguiente,
                     tipo_movimiento=TipoMovimiento.INVERSION,
                     categoria_id=cat_cons.id,
                     concepto=f"Retención Consecuencias {mes_fiscal} (auto-generada)",
                     importe=consequences_amount,
                     relevancia_code=None,
                     flag_liquidez=False
                 )
                 insert_ledger_entry(entrada_consecuencias, db_path)
    cierre = CierreMensual(
        mes_fiscal=mes_fiscal,
        estado='CERRADO',
        fecha_cierre=datetime.now(),
        saldo_inicio=saldo_inicio,
        salario_mes=kpis["total_ingresos"],  # Ingresos del mes que cierra
        total_ingresos=kpis["total_ingresos"],
        total_gastos=kpis["total_gastos"],
        total_inversion=kpis["total_inversion"],
        saldo_fin=saldo_fin,
        nomina_siguiente=nomina_nueva,
        notas=None
    )
    upsert_cierre_mes(cierre, db_path)
    
    # 11. Abrir mes siguiente con saldo_fin (balance cierre, SIN incluir salario del nuevo mes)
    # El salario se contabiliza como ingreso en balance_mes del nuevo mes vía LEDGER entry
    try:
        abrir_mes(mes_siguiente, saldo_inicio=saldo_fin, db_path=db_path)
    except ValueError:
        pass  # El mes siguiente ya existe (puede haber sido abierto antes)
    
    # 12. Calcular desviación (diferencia entre lo registrado y la realidad)
    balance_esperado = kpis["balance_mes"] + kpis["total_traspasos_entrada"] - kpis["total_inversion"]
    desviacion = balance_esperado - saldo_banco_real if saldo_banco_real else None
    
    # 13. Crear y guardar snapshot (legacy, para compatibilidad)
    snapshot = SnapshotMensual(
        mes_cierre=mes_fiscal,
        fecha_ejecucion=datetime.now(),
        saldo_banco_real=saldo_banco_real,
        nomina_nuevo_mes=nomina_nueva,
        desviacion_registrada=desviacion,
        retencion_ejecutada=retencion_ejecutada,
        saldo_inicial_nuevo=saldo_fin  # Balance al cierre del mes (sin salario siguiente)
    )
    insert_snapshot(snapshot, db_path)
    
    return snapshot


# ============================================================================
# CÁLCULOS ANUALES
# ============================================================================

def calcular_kpis_anuales(anio: int, db_path: Path = DEFAULT_DB_PATH) -> Dict:
    """
    Calcula los KPIs agregados de un año completo.
    
    Args:
        anio: Año a calcular (ej: 2025)
        db_path: Ruta a la base de datos
    
    Returns:
        Diccionario con estadísticas anuales
    """
    from .database import get_ledger_by_year, get_all_categorias
    
    entries = get_ledger_by_year(anio, db_path)
    
    if not entries:
        return {
            "anio": anio,
            "total_ingresos": 0,
            "total_gastos": 0,
            "total_ahorrado": 0,
            "pct_ahorro": 0,
            "gastos_NE": 0,
            "gastos_LI": 0,
            "gastos_SUP": 0,
            "gastos_TON": 0,
            "mejor_mes": None,
            "peor_mes": None,
            "categoria_mas_gasto": None,
            "meses_data": {}
        }
    
    # Totales por tipo
    total_ingresos = sum(e.importe for e in entries if e.tipo_movimiento == TipoMovimiento.INGRESO)
    total_gastos = sum(e.importe for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO)
    total_ahorrado = total_ingresos - total_gastos
    
    # Calcular Inversiones (separado del ahorro líquido)
    total_inversion = sum(e.importe for e in entries if e.tipo_movimiento == TipoMovimiento.INVERSION)
    
    # KPIs de Gastos por Relevancia (Solo GASTO)
    gastos_entries = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    gastos_NE = sum(e.importe for e in gastos_entries if e.relevancia_code and e.relevancia_code.value == "NE")
    gastos_LI = sum(e.importe for e in gastos_entries if e.relevancia_code and e.relevancia_code.value == "LI")
    gastos_SUP = sum(e.importe for e in gastos_entries if e.relevancia_code and e.relevancia_code.value == "SUP")
    gastos_TON = sum(e.importe for e in gastos_entries if e.relevancia_code and e.relevancia_code.value == "TON")
    
    # Calcular porcentaje de ahorro (incluyendo inversiones como "destino" del ahorro?)
    # Definición: Ahorro Total = (Ingresos - Gastos). 
    # De ese ahorro, una parte es liquidez (banco) y otra inversión.
    pct_ahorro = (total_ahorrado / total_ingresos * 100) if total_ingresos > 0 else 0.0
    
    # Calcular balance por mes para encontrar mejor/peor
    meses_balance = {}
    for e in entries:
        mes = e.mes_fiscal
        if mes not in meses_balance:
            meses_balance[mes] = {"ingresos": 0, "gastos": 0}
        if e.tipo_movimiento == TipoMovimiento.INGRESO:
            meses_balance[mes]["ingresos"] += e.importe
        elif e.tipo_movimiento == TipoMovimiento.GASTO:
            meses_balance[mes]["gastos"] += e.importe
    
    # Calcular balance neto por mes
    for mes in meses_balance:
        meses_balance[mes]["balance"] = meses_balance[mes]["ingresos"] - meses_balance[mes]["gastos"]
    
    # Mejor y peor mes (por balance)
    if meses_balance:
        mejor_mes = max(meses_balance.keys(), key=lambda m: meses_balance[m]["balance"])
        peor_mes = min(meses_balance.keys(), key=lambda m: meses_balance[m]["balance"])
    else:
        mejor_mes = peor_mes = None
    
    # Categoría con más gasto
    gastos_por_categoria = {}
    categorias = {c.id: c.nombre for c in get_all_categorias(db_path)}
    for e in entries:
        if e.tipo_movimiento == TipoMovimiento.GASTO:
            cat_nombre = categorias.get(e.categoria_id, "Desconocida")
            gastos_por_categoria[cat_nombre] = gastos_por_categoria.get(cat_nombre, 0) + e.importe
    
    categoria_mas_gasto = max(gastos_por_categoria.keys(), key=lambda c: gastos_por_categoria[c]) if gastos_por_categoria else None
    
    return {
        "anio": anio,
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "total_ahorrado": total_ahorrado,
        "total_inversion": total_inversion,
        "pct_ahorro": pct_ahorro,
        "gastos_NE": gastos_NE,
        "gastos_LI": gastos_LI,
        "gastos_SUP": gastos_SUP,
        "gastos_TON": gastos_TON,
        "mejor_mes": mejor_mes,
        "peor_mes": peor_mes,
        "categoria_mas_gasto": categoria_mas_gasto,
        "meses_data": meses_balance
    }


# ============================================================================
# ANÁLISIS AVANZADO
# ============================================================================

def get_word_counts(entries: list[LedgerEntry], filter_type: TipoMovimiento = TipoMovimiento.GASTO, min_length: int = MIN_WORD_LENGTH, limit: int = DEFAULT_WORD_LIMIT) -> dict[str, int]:
    """
    Cuenta la frecuencia de palabras en los conceptos.
    Ignora stop words comunes en español.
    """
    stopwords = STOPWORDS_ES
    
    word_counts = {}
    
    for e in entries:
        if e.tipo_movimiento != filter_type or not e.concepto:
            continue
            
        words = e.concepto.lower().replace(".", " ").replace(",", " ").split()
        for w in words:
            w_clean = w.strip()
            if len(w_clean) >= min_length and w_clean not in stopwords:
                word_counts[w_clean] = word_counts.get(w_clean, 0) + 1
                
    # Retornar los top N
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_words[:limit])

def get_top_entries(entries: list[LedgerEntry], filter_type: TipoMovimiento = TipoMovimiento.GASTO, limit: int = 10) -> list[LedgerEntry]:
    """Retorna las N entradas más elevadas del tipo especificado."""
    filtered = [e for e in entries if e.tipo_movimiento == filter_type]
    return sorted(filtered, key=lambda x: x.importe, reverse=True)[:limit]

def calculate_curious_metrics(entries: list[LedgerEntry], filter_type: TipoMovimiento = TipoMovimiento.GASTO) -> dict:
    """Calcula métricas curiosas como día con más movimiento, promedio, etc."""
    filtered = [e for e in entries if e.tipo_movimiento == filter_type]
    if not filtered:
        return {}
        
    # Día con más movimiento
    movs_por_dia = {}
    for item in filtered:
        date_str = item.fecha_real.isoformat()
        movs_por_dia[date_str] = movs_por_dia.get(date_str, 0) + item.importe
        
    dia_top = max(movs_por_dia.items(), key=lambda x: x[1])
    
    # Promedio en días activos
    dias_activos = len(movs_por_dia)
    promedio_dias_activos = sum(movs_por_dia.values()) / dias_activos if dias_activos else 0
    
    return {
        "dia_top_fecha": dia_top[0],
        "dia_top_importe": dia_top[1],
        "promedio_dias_activos": promedio_dias_activos,
        "dias_activos": dias_activos,
        "total_registros": len(filtered)
    }

# ============================================================================
# CUENTA DE CONSECUENCIAS
# ============================================================================

def calculate_consequences(mes_fiscal: str, rules: list, db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Calcula el importe total de retenciones por 'consecuencias' y su desglose.
    
    Args:
        mes_fiscal: Mes a analizar
        rules: Lista de reglas configuradas (dicts)
        db_path: Ruta a la base de datos
    
    Returns:
        Dict con:
            'total': float (suma total)
            'breakdown': list of dicts [{'rule_name', 'amount', 'details'}]
    """
    if not rules:
        return {'total': 0.0, 'breakdown': []}
        
    entries = get_ledger_by_month(mes_fiscal, db_path)
    gastos = [e for e in entries if e.tipo_movimiento == TipoMovimiento.GASTO]
    categorias = {c.id: c.nombre for c in get_all_categorias(db_path)}
    
    total_consequences = 0.0
    breakdown = []
    
    # Procesar cada regla independientemente (efecto acumulativo)
    for rule in rules:
        if not rule.get('active', True):
            continue
            
        rule_amount = 0.0
        details_count = 0
        
        filter_rel = rule.get('filter_relevance')
        filter_cat = rule.get('filter_category')
        filter_concept = rule.get('filter_concept')
        action_type = rule.get('action_type', 'percent')
        action_value = float(rule.get('action_value', 0.0))
        
        for gasto in gastos:
            # 1. Comprobar Filtros
            
            # Relevancia
            if filter_rel:
                # Si el gasto no tiene relevancia, no matchea si hay filtro
                if not gasto.relevancia_code or gasto.relevancia_code.value != filter_rel:
                    continue
            
            # Categoría
            if filter_cat:
                cat_name = categorias.get(gasto.categoria_id, "")
                if cat_name != filter_cat:
                    continue
            
            # Concepto (contains, case insensitive)
            if filter_concept:
                if not gasto.concepto or filter_concept.lower() not in gasto.concepto.lower():
                    continue
            
            # 2. Aplicar Acción si pasa filtros
            amount_to_add = 0.0
            if action_type == 'percent':
                amount_to_add = gasto.importe * (action_value / 100.0)
            elif action_type == 'fixed':
                amount_to_add = action_value
                
            rule_amount += amount_to_add
            details_count += 1
        
        if rule_amount > 0:
            total_consequences += rule_amount
            breakdown.append({
                'rule_name': rule.get('name', 'Unnamed Rule'),
                'amount': rule_amount,
                'count': details_count
            })
            
    return {
        'total': total_consequences,
        'breakdown': breakdown
    }
