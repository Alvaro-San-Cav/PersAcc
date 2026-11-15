"""
Modelos Pydantic para la API de PersAcc.

Contratos request/response que envuelven la capa de dominio (src/). Los enums
reflejan exactamente los valores persistidos en SQLite (ver src/models.py).
"""
from __future__ import annotations

from datetime import date
from typing import Optional, List, Dict, Any, Literal

from pydantic import BaseModel, Field


# ── Enums (mismos valores que src/models.py) ────────────────────────────────
TipoMovimientoLiteral = Literal[
    "GASTO", "INGRESO", "TRASPASO_ENTRADA", "TRASPASO_SALIDA", "INVERSION_AHORRO"
]
RelevanciaLiteral = Literal["NE", "LI", "SUP", "TON"]
EstadoLiteral = Literal["ABIERTO", "CERRADO"]


# ── Categorías ──────────────────────────────────────────────────────────────
class CategoriaOut(BaseModel):
    id: int
    nombre: str
    tipo_movimiento: TipoMovimientoLiteral
    es_activo: bool = True
    descripcion_ia: Optional[str] = None
    count: int = 0  # nº de entradas del ledger que la usan


class CategoriaCreate(BaseModel):
    nombre: str
    tipo_movimiento: TipoMovimientoLiteral
    descripcion_ia: Optional[str] = None


class CategoriaUpdate(BaseModel):
    nombre: str
    tipo_movimiento: Optional[TipoMovimientoLiteral] = None
    descripcion_ia: Optional[str] = None


# ── Ledger ──────────────────────────────────────────────────────────────────
class LedgerEntryOut(BaseModel):
    id: int
    fecha_real: date
    fecha_contable: date
    mes_fiscal: str
    tipo_movimiento: TipoMovimientoLiteral
    categoria_id: int
    categoria_nombre: Optional[str] = None
    concepto: Optional[str] = None
    importe: float
    relevancia_code: Optional[RelevanciaLiteral] = None
    flag_liquidez: bool = False


class LedgerEntryCreate(BaseModel):
    fecha_real: date
    tipo_movimiento: TipoMovimientoLiteral
    categoria_id: int
    concepto: Optional[str] = None
    importe: float = Field(gt=0)
    relevancia_code: Optional[RelevanciaLiteral] = None
    flag_liquidez: bool = False


class LedgerEntryUpdate(BaseModel):
    categoria_id: int
    concepto: Optional[str] = None
    importe: float = Field(gt=0)
    relevancia_code: Optional[RelevanciaLiteral] = None


# ── KPIs / Dashboard ────────────────────────────────────────────────────────
class Kpis(BaseModel):
    mes_fiscal: str
    total_ingresos: float
    total_gastos: float
    total_traspasos_entrada: float
    total_traspasos_salida: float
    total_inversion: float
    inversion_manual: float
    pct_salary_retention: float
    balance_mes: float


class DashboardResponse(BaseModel):
    mes_fiscal: str
    is_cerrado: bool
    saldo_inicio: float       # Saldo con el que arrancó el mes (último cierre)
    saldo_cuenta: float       # Estimación del dinero en cuenta hoy
    kpis: Kpis
    relevancia: Dict[str, float]  # {NE, LI, SUP, TON}: importe
    entries: List[LedgerEntryOut]
    available_months: List[str]


class SaldoInicioRequest(BaseModel):
    saldo_inicio: float


# ── Cierre ──────────────────────────────────────────────────────────────────
class ClosingStatus(BaseModel):
    mes_a_cerrar: Optional[str]
    is_cerrado: bool
    saldo_inicio: float


class ClosingPreviewRequest(BaseModel):
    mes_fiscal: str
    saldo_banco_real: float
    nomina_nueva: float = 0.0
    pct_retencion_remanente: float = 0.0  # 0-1
    pct_retencion_salario: float = 0.0    # 0-1
    salario_ya_incluido: bool = False
    aplicar_consecuencias: bool = False


class ConsequenceBreakdown(BaseModel):
    rule_name: str
    amount: float
    count: int


class ClosingPreview(BaseModel):
    mes_fiscal: str
    mes_siguiente: str
    kpis: Kpis
    retencion_remanente: float
    retencion_salario: float
    consequences_total: float
    consequences_breakdown: List[ConsequenceBreakdown]
    retencion_total: float
    saldo_fin: float
    desviacion: Optional[float]


class ClosingExecuteResponse(BaseModel):
    mes_cerrado: str
    mes_siguiente: str
    saldo_inicial_nuevo: float
    retencion_ejecutada: float
    desviacion: Optional[float]


# ── Histórico ───────────────────────────────────────────────────────────────
class MesBalance(BaseModel):
    mes_fiscal: str
    ingresos: float
    gastos: float
    balance: float


class AnnualKpis(BaseModel):
    anio: int
    total_ingresos: float
    total_gastos: float
    total_ahorrado: float
    total_inversion: float
    pct_ahorro: float
    gastos_NE: float
    gastos_LI: float
    gastos_SUP: float
    gastos_TON: float
    mejor_mes: Optional[str]
    peor_mes: Optional[str]
    categoria_mas_gasto: Optional[str]
    meses: List[MesBalance]


# ── Histórico: detalle mensual y análisis anual ─────────────────────────────
class CategoriaImporte(BaseModel):
    categoria: str
    importe: float


class RetencionesBreakdown(BaseModel):
    salario: float = 0.0
    remanente: float = 0.0
    consecuencias: float = 0.0
    manual: float = 0.0
    total: float = 0.0


class MonthDetailResponse(BaseModel):
    mes_fiscal: str
    is_cerrado: bool
    kpis: Kpis
    relevancia: Dict[str, float]
    gastos_por_categoria: List[CategoriaImporte]
    retenciones: RetencionesBreakdown
    entries: List[LedgerEntryOut]


class WordCount(BaseModel):
    word: str
    count: int


class TopEntry(BaseModel):
    fecha: str
    categoria: str
    concepto: str
    importe: float


class Curiosities(BaseModel):
    dia_top_fecha: Optional[str] = None
    dia_top_importe: float = 0.0
    promedio_dias_activos: float = 0.0
    dias_activos: int = 0
    total_registros: int = 0


class YearAnalysisResponse(BaseModel):
    tipo: str
    word_counts: List[WordCount]
    top_entries: List[TopEntry]
    curiosities: Curiosities


# ── Config / Notas / Genéricos ──────────────────────────────────────────────
class NotesUpdate(BaseModel):
    note_text: str


class OkResponse(BaseModel):
    ok: bool = True
    detail: Optional[str] = None


class IdResponse(BaseModel):
    id: int


class ConfigResponse(BaseModel):
    config: Dict[str, Any]
    currency_symbol: str


# ── IA (Ollama) ─────────────────────────────────────────────────────────────
class AiStatus(BaseModel):
    enabled: bool
    ollama_running: bool
    models: List[str]


class TextResponse(BaseModel):
    text: str
    cached: bool = False


class AnalysisRequest(BaseModel):
    period_type: Literal["month", "year"]
    period_id: str  # "2026-07" o "2026"
    regenerate: bool = False


# ── Proyecciones ────────────────────────────────────────────────────────────
class ProjectionsResponse(BaseModel):
    months: int
    series: Dict[str, Any]  # {gasto, ingreso, ahorro}: resultado predict()
    status: Dict[str, Any]


# ── Importación ─────────────────────────────────────────────────────────────
class ImportEntry(BaseModel):
    fecha: str
    concepto: str
    concepto_original: Optional[str] = None
    importe: float
    tipo_movimiento: str
    categoria_sugerida: Optional[str] = None
    relevancia: Optional[str] = None
    confianza: float = 0.5
    is_duplicate: bool = False
    notion_id: Optional[str] = None  # page_id de Notion; se archiva al importar


class ImportPreviewResponse(BaseModel):
    file_type: str
    entries: List[ImportEntry]


class ImportCommitRequest(BaseModel):
    entries: List[ImportEntry]


class ImportCommitResponse(BaseModel):
    inserted: int
    skipped: int
    duplicates: int = 0  # ya existían en el ledger (mismo importe y fecha)
    notion_archived: int = 0  # entradas de la bandeja (Notion/LifeDeck) marcadas tras importar
    source: Optional[str] = None  # origen de la bandeja si el lote venía de ella


# ── Chat / búsqueda NL ──────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str


class ChatResultEntry(BaseModel):
    id: int
    fecha_real: str
    tipo_movimiento: str
    categoria_nombre: str
    concepto: str
    importe: float
    relevancia_code: Optional[str] = None


class ChatRunRequest(BaseModel):
    tool: str
    params: Dict[str, Any]


class ChatResponse(BaseModel):
    tool: str
    params: Dict[str, Any]
    summary: str
    count: int
    total: float
    entries: List[ChatResultEntry]


# ── Admin (backup / cleanup) ────────────────────────────────────────────────
class BackupImportResponse(BaseModel):
    inserted: int
    errors: List[str] = []


class CleanupRequest(BaseModel):
    scope: Literal["ledger", "full"]
    confirm: str  # debe coincidir con la frase de confirmación exacta


class CleanupResponse(BaseModel):
    ok: bool
    detail: str
    reseeded: int = 0


# ── Notion ──────────────────────────────────────────────────────────────────
class NotionStatus(BaseModel):
    configured: bool
    ok: bool
    detail: str
    source: str = "Notion"  # origen de la bandeja: "LifeDeck" o "Notion"


class NotionArchiveRequest(BaseModel):
    page_ids: List[str]


class NotionArchiveResponse(BaseModel):
    archived: int


class LifeDeckSyncResponse(BaseModel):
    ok: bool
    detail: str
    categories: int = 0
    month: Optional[str] = None
