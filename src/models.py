"""
Modelos de datos para el sistema de finanzas personales.
Define enumeraciones y dataclasses para los tipos de movimiento y relevancia.
"""
from enum import Enum
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


class TipoMovimiento(Enum):
    """
    Los 5 tipos de movimiento que existen en el sistema.
    """
    GASTO = "GASTO"                         # Dinero que sale y se consume (Resta patrimonio)
    INGRESO = "INGRESO"                     # Dinero nuevo generado (Suma patrimonio)
    TRASPASO_ENTRADA = "TRASPASO_ENTRADA"   # Dinero que entra desde otra cuenta propia (Neutro)
    TRASPASO_SALIDA = "TRASPASO_SALIDA"     # Dinero que sale a otra cuenta propia (Neutro)
    INVERSION = "INVERSION_AHORRO"          # Dinero que sale a inversión/ahorro (Suma Ahorro/Patrimonio)
    
    @classmethod
    def _missing_(cls, value):
        """Compatibilidad con bases de datos antiguas que usan 'INVERSION'."""
        if value == "INVERSION":
            return cls.INVERSION
        return None


class RelevanciaCode(Enum):
    """
    Categorías psicológicas de gasto.
    Solo aplicable cuando tipo_movimiento == GASTO.
    """
    NE = "NE"    # Necesario / Inevitable
    LI = "LI"    # Me gusta / Disfrute consciente
    SUP = "SUP"  # Superfluo / Optimizable
    TON = "TON"  # Tontería / Error de gasto


# Descripciones para CAT_RELEVANCIA
RELEVANCIA_DESCRIPTIONS = {
    RelevanciaCode.NE: "Necesario / Inevitable",
    RelevanciaCode.LI: "Me gusta / Disfrute consciente",
    RelevanciaCode.SUP: "Superfluo / Optimizable",
    RelevanciaCode.TON: "Tontería / Error de gasto",
}


@dataclass
class Categoria:
    """Representa una categoría maestra (CAT_MAESTROS)."""
    id: Optional[int]
    nombre: str
    tipo_movimiento: TipoMovimiento
    es_activo: bool = True


@dataclass
class LedgerEntry:
    """Representa una entrada del libro diario (LEDGER)."""
    id: Optional[int]
    fecha_real: date
    fecha_contable: date
    mes_fiscal: str  # Formato: "YYYY-MM"
    tipo_movimiento: TipoMovimiento
    categoria_id: int
    concepto: str
    importe: float  # Siempre positivo, el tipo define el signo
    relevancia_code: Optional[RelevanciaCode] = None  # Obligatorio solo si GASTO
    flag_liquidez: bool = False  # Si True, ignora regla fecha salario


@dataclass
class SnapshotMensual:
    """Representa un cierre de mes (SNAPSHOTS_MENSUALES)."""
    mes_cierre: str  # Formato: "YYYY-MM"
    fecha_ejecucion: datetime
    saldo_banco_real: float
    nomina_nuevo_mes: float
    desviacion_registrada: Optional[float]
    retencion_ejecutada: Optional[float]
    saldo_inicial_nuevo: float



@dataclass
class CierreMensual:
    """Representa el estado de un mes en el sistema (CIERRES_MENSUALES)."""
    mes_fiscal: str  # Formato: "YYYY-MM"
    estado: str  # 'ABIERTO' o 'CERRADO'
    fecha_cierre: Optional[datetime]
    saldo_inicio: float
    salario_mes: Optional[float]
    total_ingresos: Optional[float]
    total_gastos: Optional[float]
    total_inversion: Optional[float]
    saldo_fin: Optional[float]
    nomina_siguiente: Optional[float]
    notas: Optional[str] = None


