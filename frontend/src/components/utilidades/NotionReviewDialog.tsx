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
import { useCategories } from '@/api/queries'
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
  const { data: cats } = useCategories()
  const qc = useQueryClient()

  useEffect(() => {
    if (!open) return
    setLoading(true)
    apiPost<ImportPreviewResponse>('/api/notion/preview', {})
      .then((res) => setRows(res.entries.map((e, i) => ({ ...e, _sel: !e.is_duplicate, _idx: i }))))
      .catch((e) => toast.error(e instanceof ApiError ? e.message : 'Error consultando Notion'))
      .finally(() => setLoading(false))
  }, [open])

  function update(idx: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r) => (r._idx === idx ? { ...r, ...patch } : r)))
  }

  const selected = rows.filter((r) => r._sel)

  async function importSelected() {
    const entries = selected.map(({ _sel, _idx, ...e }) => e)
    if (!entries.length) return toast.error('Nada seleccionado')
    setBusy(true)
    try {
      const res = await apiPost<ImportCommitResponse>('/api/import/commit', { entries })
      toast.success(`${res.inserted} importados desde Notion · ${res.skipped} omitidos`)
      qc.invalidateQueries()
      onOpenChange(false)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Error al importar')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Revisar entradas de Notion</DialogTitle>
          <DialogDescription>
            Edita tipo, categoría o relevancia y elige qué importar. Los duplicados llegan sin marcar.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <Skeleton className="h-56" />
        ) : rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-txt2">No hay entradas pendientes en Notion.</p>
        ) : (
          <div className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
            {rows.map((r) => {
              const catsForTipo = (cats ?? []).filter((c) => c.tipo_movimiento === r.tipo_movimiento)
              return (
                <div key={r._idx} className="flex flex-wrap items-center gap-2 rounded-[var(--radius-card)] border border-border-subtle p-2 text-sm">
                  <input type="checkbox" checked={r._sel} onChange={(e) => update(r._idx, { _sel: e.target.checked })} />
                  <span className="w-24 text-txt2">{r.fecha}</span>
                  <Select value={r.tipo_movimiento} onValueChange={(v) => update(r._idx, { tipo_movimiento: v as TipoMovimiento })}>
                    <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TIPOS.map((t) => (
                        <SelectItem key={t} value={t}>{TIPO_LABEL[t]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={r.categoria_sugerida ?? ''} onValueChange={(v) => update(r._idx, { categoria_sugerida: v })}>
                    <SelectTrigger className="h-8 w-36"><SelectValue placeholder="Categoría" /></SelectTrigger>
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
                  {r.is_duplicate && <Badge variant="amber">dup</Badge>}
                </div>
              )
            })}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cerrar
          </Button>
          <Button onClick={importSelected} disabled={busy || selected.length === 0}>
            {busy ? 'Importando…' : `Importar ${selected.length}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
