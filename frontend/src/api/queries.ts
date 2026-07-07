/**
 * Hooks de TanStack Query para el API PersAcc.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPost, apiPut } from './client'
import type {
  AiStatus,
  AnnualKpis,
  Categoria,
  ClosingExecuteResponse,
  ClosingPreview,
  ClosingPreviewRequest,
  ClosingStatus,
  ConfigResponse,
  DashboardResponse,
  LedgerEntry,
  LedgerEntryCreate,
  LedgerEntryUpdate,
  ProjectionsResponse,
  TextResponse,
} from './types'

/** {cat_id: {history, curr_year}} — uso histórico para orden inteligente en QuickAdd. */
export type CategoryUsageStats = Record<string, { history: number; curr_year: number }>

export const keys = {
  config: ['config'] as const,
  dashboard: (month?: string) => ['dashboard', month ?? 'current'] as const,
  categories: (tipo?: string) => ['categories', tipo ?? 'all'] as const,
  closingStatus: ['closing', 'status'] as const,
  years: ['history', 'years'] as const,
  year: (y: number) => ['history', y] as const,
}

export function useConfig() {
  return useQuery({ queryKey: keys.config, queryFn: () => apiGet<ConfigResponse>('/api/config') })
}

export function useDashboard(month?: string) {
  return useQuery({
    queryKey: keys.dashboard(month),
    queryFn: () =>
      apiGet<DashboardResponse>(`/api/dashboard${month ? `?month=${month}` : ''}`),
  })
}

export function useCategories(tipo?: string) {
  return useQuery({
    queryKey: keys.categories(tipo),
    queryFn: () => apiGet<Categoria[]>(`/api/categories${tipo ? `?tipo=${tipo}` : ''}`),
  })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { nombre: string; tipo_movimiento: string; descripcion_ia?: string | null }) =>
      apiPost<{ id: number }>('/api/categories', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useUpdateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: { nombre: string; tipo_movimiento?: string; descripcion_ia?: string | null } }) =>
      apiPut<{ ok: boolean }>(`/api/categories/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useDeleteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete<{ ok: boolean; detail?: string }>(`/api/categories/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useAiModels(enabled: boolean) {
  return useQuery({
    queryKey: ['ai', 'models'],
    queryFn: () => apiGet<string[]>('/api/ai/models'),
    enabled,
    retry: false,
  })
}

export function useCategoryUsageStats(tipo: string | undefined) {
  return useQuery({
    queryKey: ['categories', 'usage-stats', tipo],
    queryFn: () => apiGet<CategoryUsageStats>(`/api/categories/usage-stats?tipo=${tipo}`),
    enabled: !!tipo,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLedgerByYear(year: number | undefined) {
  return useQuery({
    queryKey: ['ledger', 'year', year],
    queryFn: () => apiGet<LedgerEntry[]>(`/api/ledger?year=${year}`),
    enabled: !!year,
    staleTime: 5 * 60 * 1000,
  })
}

export function useClosingStatus() {
  return useQuery({
    queryKey: keys.closingStatus,
    queryFn: () => apiGet<ClosingStatus>('/api/closing/status'),
  })
}

export function useYears() {
  return useQuery({ queryKey: keys.years, queryFn: () => apiGet<number[]>('/api/history/years') })
}

export function useYear(anio: number | undefined) {
  return useQuery({
    queryKey: keys.year(anio ?? 0),
    queryFn: () => apiGet<AnnualKpis>(`/api/history/${anio}`),
    enabled: !!anio,
  })
}

export function useMonthDetail(anio: number | undefined, mes: number | undefined) {
  return useQuery({
    queryKey: ['history', 'month', anio, mes],
    queryFn: () =>
      apiGet<import('./types').MonthDetail>(`/api/history/${anio}/${mes}`),
    enabled: !!anio && !!mes,
  })
}

export function useYearAnalysis(anio: number | undefined, tipo: string) {
  return useQuery({
    queryKey: ['history', 'analysis', anio, tipo],
    queryFn: () =>
      apiGet<import('./types').YearAnalysis>(`/api/history/${anio}/analysis?tipo=${tipo}`),
    enabled: !!anio,
  })
}

function useLedgerInvalidation() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['history'] })
    qc.invalidateQueries({ queryKey: ['categories'] })
  }
}

export function useCreateEntry() {
  const invalidate = useLedgerInvalidation()
  return useMutation({
    mutationFn: (body: LedgerEntryCreate) => apiPost<{ id: number }>('/api/ledger', body),
    onSuccess: invalidate,
  })
}

export function useUpdateEntry() {
  const invalidate = useLedgerInvalidation()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: LedgerEntryUpdate }) =>
      apiPut<{ ok: boolean }>(`/api/ledger/${id}`, body),
    onSuccess: invalidate,
  })
}

export function useDeleteEntry() {
  const invalidate = useLedgerInvalidation()
  return useMutation({
    mutationFn: (id: number) => apiDelete<{ ok: boolean }>(`/api/ledger/${id}`),
    onSuccess: invalidate,
  })
}

export function useClosingPreview() {
  return useMutation({
    mutationFn: (body: ClosingPreviewRequest) =>
      apiPost<ClosingPreview>('/api/closing/preview', body),
  })
}

export function useClosingExecute() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ClosingPreviewRequest) =>
      apiPost<ClosingExecuteResponse>('/api/closing/execute', body),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useAiStatus() {
  return useQuery({ queryKey: ['ai', 'status'], queryFn: () => apiGet<AiStatus>('/api/ai/status') })
}

export function useCommentary(month: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['ai', 'commentary', month],
    queryFn: () => apiGet<TextResponse>(`/api/ai/commentary?month=${month}`),
    enabled: enabled && !!month,
    retry: false,
  })
}

export function useAnalysisCached(periodType: string, periodId: string | undefined) {
  return useQuery({
    queryKey: ['ai', 'analysis', periodType, periodId],
    queryFn: () => apiGet<TextResponse>(`/api/ai/analysis/${periodType}/${periodId}`),
    enabled: !!periodId,
  })
}

export function useGenerateAnalysis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { period_type: string; period_id: string; regenerate?: boolean }) =>
      apiPost<TextResponse>('/api/ai/analysis', body),
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ['ai', 'analysis', vars.period_type, vars.period_id] }),
  })
}

export function useProjections(months: number) {
  return useQuery({
    queryKey: ['projections', months],
    queryFn: () => apiGet<ProjectionsResponse>(`/api/projections?months=${months}`),
  })
}

export function useTrainProjections() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (months: number) =>
      apiPost<ProjectionsResponse>(`/api/projections/train?months=${months}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projections'] }),
  })
}

export function useChat() {
  return useMutation({
    mutationFn: (query: string) => apiPost<import('./types').ChatResponse>('/api/chat', { query }),
  })
}

export function useChatRun() {
  return useMutation({
    mutationFn: (body: { tool: string; params: Record<string, unknown> }) =>
      apiPost<import('./types').ChatResponse>('/api/chat/run', body),
  })
}

export function useNotionPendingCount(enabled: boolean) {
  return useQuery({
    queryKey: ['notion', 'pending-count'],
    queryFn: () => apiGet<{ count: number; configured: boolean }>('/api/notion/pending-count'),
    enabled,
    retry: false,
    staleTime: 60 * 1000,
  })
}

export function useNotionStatus() {
  return useQuery({
    queryKey: ['notion', 'status'],
    queryFn: () => apiGet<import('./types').NotionStatus>('/api/notion/status'),
    retry: false,
  })
}

export function useNotes(periodType: string, periodId: string | undefined) {
  return useQuery({
    queryKey: ['notes', periodType, periodId],
    queryFn: () => apiGet<string>(`/api/notes/${periodType}/${periodId}`),
    enabled: !!periodId,
  })
}

export function useSaveNotes(periodType: string, periodId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (note_text: string) =>
      apiPut<{ ok: boolean }>(`/api/notes/${periodType}/${periodId}`, { note_text }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes', periodType, periodId] }),
  })
}

export function useSaveConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (config: Record<string, unknown>) =>
      apiPut<ConfigResponse>('/api/config', config),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.config }),
  })
}
