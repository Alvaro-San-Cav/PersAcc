/**
 * Tipos del API PersAcc (escritos a mano, espejo de backend/api_models.py).
 * Se pueden regenerar desde OpenAPI con `pnpm gen:api` cuando se prefiera.
 */

export type TipoMovimiento =
  | 'GASTO'
  | 'INGRESO'
  | 'TRASPASO_ENTRADA'
  | 'TRASPASO_SALIDA'
  | 'INVERSION_AHORRO'

export type Relevancia = 'NE' | 'LI' | 'SUP' | 'TON'

export interface Categoria {
  id: number
  nombre: string
  tipo_movimiento: TipoMovimiento
  es_activo: boolean
  descripcion_ia: string | null
  count: number
}

export interface LedgerEntry {
  id: number
  fecha_real: string
  fecha_contable: string
  mes_fiscal: string
  tipo_movimiento: TipoMovimiento
  categoria_id: number
  categoria_nombre: string | null
  concepto: string | null
  importe: number
  relevancia_code: Relevancia | null
  flag_liquidez: boolean
}

export interface Kpis {
  mes_fiscal: string
  total_ingresos: number
  total_gastos: number
  total_traspasos_entrada: number
  total_traspasos_salida: number
  total_inversion: number
  inversion_manual: number
  pct_salary_retention: number
  balance_mes: number
}

export interface DashboardResponse {
  mes_fiscal: string
  is_cerrado: boolean
  saldo_inicio: number
  saldo_cuenta: number
  kpis: Kpis
  relevancia: Record<Relevancia, number>
  entries: LedgerEntry[]
  available_months: string[]
}

export interface ClosingStatus {
  mes_a_cerrar: string | null
  is_cerrado: boolean
  saldo_inicio: number
}

export interface ClosingPreviewRequest {
  mes_fiscal: string
  saldo_banco_real: number
  nomina_nueva: number
  pct_retencion_remanente: number
  pct_retencion_salario: number
  salario_ya_incluido: boolean
  aplicar_consecuencias: boolean
}

export interface ConsequenceBreakdown {
  rule_name: string
  amount: number
  count: number
}

export interface ClosingPreview {
  mes_fiscal: string
  mes_siguiente: string
  kpis: Kpis
  retencion_remanente: number
  retencion_salario: number
  consequences_total: number
  consequences_breakdown: ConsequenceBreakdown[]
  retencion_total: number
  saldo_fin: number
  desviacion: number | null
}

export interface ClosingExecuteResponse {
  mes_cerrado: string
  mes_siguiente: string
  saldo_inicial_nuevo: number
  retencion_ejecutada: number
  desviacion: number | null
}

export interface MesBalance {
  mes_fiscal: string
  ingresos: number
  gastos: number
  balance: number
}

export interface AnnualKpis {
  anio: number
  total_ingresos: number
  total_gastos: number
  total_ahorrado: number
  total_inversion: number
  pct_ahorro: number
  gastos_NE: number
  gastos_LI: number
  gastos_SUP: number
  gastos_TON: number
  mejor_mes: string | null
  peor_mes: string | null
  categoria_mas_gasto: string | null
  meses: MesBalance[]
}

export interface ConfigResponse {
  config: Record<string, unknown>
  currency_symbol: string
}

// ── Histórico: detalle mensual y análisis anual ────────────────────────────
export interface CategoriaImporte {
  categoria: string
  importe: number
}

export interface RetencionesBreakdown {
  salario: number
  remanente: number
  consecuencias: number
  manual: number
  total: number
}

export interface MonthDetail {
  mes_fiscal: string
  is_cerrado: boolean
  kpis: Kpis
  relevancia: Record<Relevancia, number>
  gastos_por_categoria: CategoriaImporte[]
  retenciones: RetencionesBreakdown
  entries: LedgerEntry[]
}

export interface WordCount {
  word: string
  count: number
}

export interface TopEntry {
  fecha: string
  categoria: string
  concepto: string
  importe: number
}

export interface Curiosities {
  dia_top_fecha: string | null
  dia_top_importe: number
  promedio_dias_activos: number
  dias_activos: number
  total_registros: number
}

export interface YearAnalysis {
  tipo: TipoMovimiento
  word_counts: WordCount[]
  top_entries: TopEntry[]
  curiosities: Curiosities
}

export interface LedgerEntryCreate {
  fecha_real: string
  tipo_movimiento: TipoMovimiento
  categoria_id: number
  concepto?: string | null
  importe: number
  relevancia_code?: Relevancia | null
  flag_liquidez?: boolean
}

export interface LedgerEntryUpdate {
  categoria_id: number
  concepto?: string | null
  importe: number
  relevancia_code?: Relevancia | null
}

// ── IA ───────────────────────────────────────────────────────────────────
export interface AiStatus {
  enabled: boolean
  ollama_running: boolean
  models: string[]
}

export interface TextResponse {
  text: string
  cached: boolean
}

// ── Proyecciones ─────────────────────────────────────────────────────────
export interface ProjectionYear {
  monthly_values: number[]
  monthly_avg: number
  annual_total: number
  annualized_total: number
  interval_80: { lower: number[]; upper: number[] }
  /** Meses del año ya reales (histórico) incluidos en annual_total; presente en el año en curso. */
  historical_months?: number
}

export interface ProjectionSeries {
  success: boolean
  error?: string
  projected?: Record<string, ProjectionYear>
  historical?: Record<string, number>
  train_date?: string | null
}

export interface ProjectionsResponse {
  months: number
  series: { gasto: ProjectionSeries; ingreso: ProjectionSeries; ahorro: ProjectionSeries }
  status: Record<string, { is_trained: boolean; train_date: string | null; model_exists: boolean }>
}

// ── Importación ──────────────────────────────────────────────────────────
export interface ImportEntry {
  fecha: string
  concepto: string
  concepto_original?: string | null
  importe: number
  tipo_movimiento: TipoMovimiento
  categoria_sugerida?: string | null
  relevancia?: Relevancia | null
  confianza: number
  is_duplicate: boolean
  notion_id?: string | null
}

export interface ImportPreviewResponse {
  file_type: string
  entries: ImportEntry[]
}

export interface ImportCommitResponse {
  inserted: number
  skipped: number
  duplicates?: number
  notion_archived?: number
  source?: string | null
}

// ── Chat ─────────────────────────────────────────────────────────────────
export interface ChatResultEntry {
  id: number
  fecha_real: string
  tipo_movimiento: TipoMovimiento
  categoria_nombre: string
  concepto: string
  importe: number
  relevancia_code: Relevancia | null
}

export interface ChatResponse {
  tool: string
  params: Record<string, unknown>
  summary: string
  count: number
  total: number
  entries: ChatResultEntry[]
}

// ── Notion ───────────────────────────────────────────────────────────────
export interface NotionStatus {
  configured: boolean
  ok: boolean
  detail: string
  /** Origen de la bandeja: "LifeDeck" o "Notion". */
  source?: string
}

export interface LifeDeckSyncResponse {
  ok: boolean
  detail: string
  categories: number
  month?: string | null
}
