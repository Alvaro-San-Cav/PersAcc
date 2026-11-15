import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiPost, ApiError } from '@/api/client'
import { useCategories, useNotionPendingCount } from '@/api/queries'
import { fmtMoney, RELEVANCIA_LABEL, TIPO_LABEL } from '@/lib/format'
import type {
  ImportEntry,
  ImportPreviewResponse,
  ImportCommitResponse,
  Relevancia,
  TipoMovimiento,
} from '@/api/types'

const TIPOS: TipoMovimiento[] = ['GASTO', 'INGRESO', 'INVERSION_AHORRO', 'TRASPASO_ENTRADA', 'TRASPASO_SALIDA']
const NO_REL = '__none__'

type Row = ImportEntry & { _sel: boolean; _idx: number }

export function NotionReviewDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  // Origen de la bandeja ("LifeDeck" o "Notion"), según lo que devuelve la vista previa.
  const [source, setSource] = useState<string | null>(null)
  const label = source ?? 'la bandeja'
  const isLifeDeck = source === 'LifeDeck'
  const { data: cats } = useCategories()
  const qc = useQueryClient()
  // Antes de la vista previa (que puede tardar si hay que preguntar a la IA): cuántos llegan y cuántos van a la IA.
  const { data: pending } = useNotionPendingCount(open)
  const [stats, setStats] = useState<{ ai: number; ms: number } | null>(null)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!loading) return
    const t0 = Date.now()
    setElapsed(0)
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 500)
    return () => clearInterval(id)
  }, [loading])

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setStats(null)
    apiPost<ImportPreviewResponse>('/api/inbox/preview', {})
      .then((res) => {
        setSource(res.file_type || null)
        setStats({ ai: res.ai_count ?? 0, ms: res.elapsed_ms ?? 0 })
        setRows(res.entries.map((e, i) => ({ ...e, _sel: !e.is_duplicate, _idx: i })))
      })
      .catch((e) => toast.error(e instanceof ApiError ? e.message : 'Error consultando la bandeja'))
      .finally(() => setLoading(false))
  }, [open])

  function update(idx: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r) => (r._idx === idx ? { ...r, ...patch } : r)))
  }

  // Al cambiar el tipo, la categoría anterior pertenece a otro tipo: se limpia
  // para forzar una válida (si no, el backend descarta la fila en silencio).
  function changeTipo(idx: number, tipo: TipoMovimiento) {
    setRows((rs) =>
      rs.map((r) =>
        r._idx === idx
          ? {
              ...r,
              tipo_movimiento: tipo,
              categoria_sugerida: r.tipo_movimiento === tipo ? r.categoria_sugerida : null,
              relevancia: tipo === 'GASTO' ? r.relevancia : null,
            }
          : r,
      ),
    )
  }

  const selected = rows.filter((r) => r._sel)

  async function importSelected() {
    const entries = selected.map(({ _sel, _idx, ...e }) => e)
    if (!entries.length) return toast.error('Nada seleccionado')
    const sinCat = selected.filter((r) => !r.categoria_sugerida).length
    if (sinCat) return toast.error(`${sinCat} fila(s) sin categoría. Elige una para cada tipo.`)
    setBusy(true)
    try {
      const res = await apiPost<ImportCommitResponse>('/api/import/commit', { entries })
      const archived = res.notion_archived ?? 0
      const dups = res.duplicates ?? 0
      const src = res.source || source || 'la bandeja'
      toast.success(
        `${res.inserted} importados desde ${src} · ${res.skipped} omitidos` +
          (dups ? ` · ${dups} duplicados saltados` : '') +
          (archived ? ` · ${archived} ${src === 'LifeDeck' ? 'marcados como importados en' : 'archivados en'} ${src}` : ''),
      )
      qc.invalidateQueries()
      onOpenChange(false)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Error al importar')
    } finally {
      setBusy(false)
    }
  }

  const deletableCount = selected.filter((r) => r.notion_id).length

  async function deleteSelected() {
    const page_ids = selected.map((r) => r.notion_id).filter((id): id is string => !!id)
    if (!page_ids.length) return toast.error('Nada seleccionado')
    setBusy(true)
    try {
      const res = await apiPost<{ archived: number }>('/api/inbox/archive', { page_ids })
      toast.success(isLifeDeck ? `${res.archived} descartadas en LifeDeck` : `${res.archived} borradas de ${label}`)
      // Quitar de la lista las que se han borrado.
      setRows((rs) => rs.filter((r) => !(r._sel && r.notion_id)))
      qc.invalidateQueries({ queryKey: ['notion'] })
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : `Error al borrar en ${label}`)
    } finally {
      setBusy(false)
      setConfirmDelete(false)
    }
  }

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{source ? `Revisar entradas de ${source}` : 'Revisar bandeja'}</DialogTitle>
          <DialogDescription>
            Edita tipo, categoría o relevancia y elige qué importar. Los duplicados llegan sin marcar.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1 rounded-[var(--radius-card)] border border-border-subtle bg-card2 px-3 py-2.5 text-sm">
              <span className="flex items-center gap-2 text-txt">
                <span className="size-2 animate-pulse rounded-full bg-accent" aria-hidden />
                {pending?.total != null
                  ? `Cargando ${pending.total} ${pending.total === 1 ? 'apunte' : 'apuntes'} de ${pending.source ?? 'la bandeja'}…`
                  : 'Consultando la bandeja…'}
                <span className="ml-auto tabular-nums text-txt3">{elapsed} s</span>
              </span>
              {!!pending?.needs_ai && (
                <span className="text-xs text-amber">
                  {pending.needs_ai} sin categoría o relevancia → clasificando con IA (Ollama) en paralelo. Puede tardar unos segundos por apunte.
                </span>
              )}
            </div>
            <Skeleton className="h-44" />
          </div>
        ) : rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-txt2">No hay entradas pendientes en {label}.</p>
        ) : (
          <>
          {stats && (
            <p className={`text-xs ${stats.ai ? 'text-amber' : 'text-txt3'}`}>
              {stats.ai
                ? `${stats.ai} ${stats.ai === 1 ? 'apunte clasificado' : 'apuntes clasificados'} con IA en ${(stats.ms / 1000).toFixed(1)} s (marcados «IA»): revisa categoría y relevancia. Si eliges la categoría al apuntar en ${label}, carga al instante.`
                : `Listo en ${(stats.ms / 1000).toFixed(1)} s · todo llegó ya clasificado, sin IA.`}
            </p>
          )}
          <div className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
            {rows.map((r) => {
              const catsForTipo = (cats ?? []).filter((c) => c.tipo_movimiento === r.tipo_movimiento)
              return (
                <div key={r._idx} className="flex flex-wrap items-center gap-2 rounded-[var(--radius-card)] border border-border-subtle p-2 text-sm">
                  <input type="checkbox" checked={r._sel} onChange={(e) => update(r._idx, { _sel: e.target.checked })} />
                  <span className="w-24 text-txt2">{r.fecha}</span>
                  <Select value={r.tipo_movimiento} onValueChange={(v) => changeTipo(r._idx, v as TipoMovimiento)}>
                    <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TIPOS.map((t) => (
                        <SelectItem key={t} value={t}>{TIPO_LABEL[t]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={r.categoria_sugerida ?? ''} onValueChange={(v) => update(r._idx, { categoria_sugerida: v })}>
                    <SelectTrigger className={`h-8 w-36${r.categoria_sugerida ? '' : ' border-red'}`}>
                      <SelectValue placeholder="Categoría" />
                    </SelectTrigger>
                    <SelectContent>
                      {catsForTipo.map((c) => (
                        <SelectItem key={c.id} value={c.nombre}>{c.nombre}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="flex-1 truncate text-txt2">{r.concepto}</span>
                  {r.tipo_movimiento === 'GASTO' && (
                    <Select value={r.relevancia || NO_REL} onValueChange={(v) => update(r._idx, { relevancia: v === NO_REL ? null : (v as Relevancia) })}>
                      <SelectTrigger className="h-8 w-20"><SelectValue placeholder="—" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NO_REL}>—</SelectItem>
                        {(Object.keys(RELEVANCIA_LABEL) as Relevancia[]).map((rel) => (
                          <SelectItem key={rel} value={rel}>{rel}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  <span className="w-20 text-right tabular-nums text-txt">{fmtMoney(r.importe)}</span>
                  {r.ai_classified && <Badge variant="amber" title="Categoría/relevancia sugeridas por la IA">IA</Badge>}
                  {r.is_duplicate && <Badge variant="amber">dup</Badge>}
                </div>
              )
            })}
          </div>
          </>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cerrar
          </Button>
          <Button
            variant="danger"
            onClick={() => setConfirmDelete(true)}
            disabled={busy || deletableCount === 0}
          >
            {isLifeDeck ? 'Descartar' : 'Borrar'} {deletableCount}
          </Button>
          <Button onClick={importSelected} disabled={busy || selected.length === 0}>
            {busy ? 'Importando…' : `Importar ${selected.length}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`${isLifeDeck ? 'Descartar' : 'Borrar'} ${deletableCount} entrada${deletableCount === 1 ? '' : 's'} de ${label}`}
        description={
          isLifeDeck
            ? 'Se marcarán como descartadas en LifeDeck sin importarlas a la app.'
            : `Se archivarán en ${label} sin importarlas a la app. Esta acción no se puede deshacer.`
        }
        confirmLabel={isLifeDeck ? 'Descartar' : 'Borrar'}
        cancelLabel="Cancelar"
        destructive
        loading={busy}
        onConfirm={deleteSelected}
      />
    </>
  )
}
