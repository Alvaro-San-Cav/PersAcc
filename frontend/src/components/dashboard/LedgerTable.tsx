import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ArrowDown, ArrowUp, Pencil, Search, Trash2 } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { EntryEditDialog } from '@/components/dashboard/EntryEditDialog'
import { useCreateEntry, useDeleteEntry } from '@/api/queries'
import {
  fmtDate,
  fmtMoney,
  RELEVANCIA_COLOR,
  RELEVANCIA_LABEL,
  TIPO_LABEL,
} from '@/lib/format'
import { cn } from '@/lib/utils'
import type { LedgerEntry, TipoMovimiento } from '@/api/types'
import { ApiError } from '@/api/client'

const SIGN: Record<string, number> = {
  GASTO: -1,
  TRASPASO_SALIDA: -1,
  INVERSION_AHORRO: -1,
  INGRESO: 1,
  TRASPASO_ENTRADA: 1,
}

// Color del importe por tipo de movimiento (fallback por signo si desconocido).
const AMOUNT_COLOR: Record<string, string> = {
  GASTO: 'text-red',
  INGRESO: 'text-green',
  INVERSION_AHORRO: 'text-purple',
  TRASPASO_ENTRADA: 'text-cyan',
  TRASPASO_SALIDA: 'text-indigo',
}

const TIPO_FILTERS: { value: TipoMovimiento | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'Todos' },
  { value: 'GASTO', label: 'Gastos' },
  { value: 'INGRESO', label: 'Ingresos' },
  { value: 'INVERSION_AHORRO', label: 'Inv./Ahorro' },
  { value: 'TRASPASO_ENTRADA', label: 'Trasp. +' },
  { value: 'TRASPASO_SALIDA', label: 'Trasp. −' },
]

type SortKey = 'fecha' | 'categoria' | 'importe'
type SortDir = 'asc' | 'desc'

export function LedgerTable({ entries, locked }: { entries: LedgerEntry[]; locked: boolean }) {
  const del = useDeleteEntry()
  const create = useCreateEntry()

  function undoDelete(e: LedgerEntry) {
    create.mutate(
      {
        fecha_real: e.fecha_real,
        tipo_movimiento: e.tipo_movimiento,
        categoria_id: e.categoria_id,
        concepto: e.concepto,
        importe: e.importe,
        relevancia_code: e.relevancia_code,
        flag_liquidez: e.flag_liquidez,
      },
      {
        onSuccess: () => toast.success('Movimiento restaurado'),
        onError: () => toast.error('No se pudo restaurar'),
      },
    )
  }

  const [tipo, setTipo] = useState<TipoMovimiento | 'ALL'>('ALL')
  const [text, setText] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('fecha')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [editing, setEditing] = useState<LedgerEntry | null>(null)
  const [toDelete, setToDelete] = useState<LedgerEntry | null>(null)

  const filtered = useMemo(() => {
    const q = text.trim().toLowerCase()
    let rows = entries.filter((e) => {
      if (tipo !== 'ALL' && e.tipo_movimiento !== tipo) return false
      if (q) {
        const hay = `${e.concepto ?? ''} ${e.categoria_nombre ?? ''}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
    rows = [...rows].sort((a, b) => {
      let cmp = 0
      if (sortKey === 'fecha') cmp = a.fecha_real.localeCompare(b.fecha_real)
      else if (sortKey === 'importe') cmp = a.importe - b.importe
      else cmp = (a.categoria_nombre ?? '').localeCompare(b.categoria_nombre ?? '')
      return sortDir === 'asc' ? cmp : -cmp
    })
    return rows
  }, [entries, tipo, text, sortKey, sortDir])

  const totals = useMemo(() => {
    let sum = 0
    for (const e of filtered) sum += (SIGN[e.tipo_movimiento] ?? 1) * e.importe
    return { count: filtered.length, sum }
  }, [filtered])

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir(key === 'categoria' ? 'asc' : 'desc')
    }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return null
    return sortDir === 'asc' ? (
      <ArrowUp className="ml-1 inline size-3" />
    ) : (
      <ArrowDown className="ml-1 inline size-3" />
    )
  }

  if (entries.length === 0) {
    return (
      <div className="grid h-32 place-items-center text-sm text-txt2">
        No hay movimientos este mes
      </div>
    )
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 border-b border-border-subtle px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {TIPO_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setTipo(f.value)}
              className={cn(
                'rounded-full border px-2.5 py-1 text-xs transition-colors',
                tipo === f.value
                  ? 'border-accent bg-accent/15 text-accent2'
                  : 'border-border-subtle text-txt2 hover:bg-card2',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative ml-auto w-full sm:w-56">
          <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-txt3" />
          <Input
            data-table-search
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Buscar concepto o categoría… (/)"
            className="pl-8"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="grid h-24 place-items-center text-sm text-txt2">
          Ningún movimiento coincide con el filtro
        </div>
      ) : (
        <Table className="table-fixed">
          <colgroup>
            <col className="w-[104px]" />
            <col className="w-[132px]" />
            <col className="w-[15%]" />
            <col />
            <col className="w-[120px]" />
            <col className="w-[120px]" />
            <col className="w-[76px]" />
          </colgroup>
          <TableHeader>
            <TableRow>
              <TableHead className="cursor-pointer select-none" onClick={() => toggleSort('fecha')}>
                Fecha <SortIcon col="fecha" />
              </TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead
                className="cursor-pointer select-none"
                onClick={() => toggleSort('categoria')}
              >
                Categoría <SortIcon col="categoria" />
              </TableHead>
              <TableHead>Concepto</TableHead>
              <TableHead>Relevancia</TableHead>
              <TableHead
                className="cursor-pointer select-none text-right"
                onClick={() => toggleSort('importe')}
              >
                Importe <SortIcon col="importe" />
              </TableHead>
              <TableHead className="w-16" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((e) => {
              const sign = SIGN[e.tipo_movimiento] ?? 1
              return (
                <TableRow key={e.id}>
                  <TableCell className="whitespace-nowrap text-txt2">{fmtDate(e.fecha_real)}</TableCell>
                  <TableCell className="whitespace-nowrap text-txt2">
                    {TIPO_LABEL[e.tipo_movimiento]}
                  </TableCell>
                  <TableCell className="truncate text-txt" title={e.categoria_nombre ?? undefined}>
                    {e.categoria_nombre ?? '—'}
                  </TableCell>
                  <TableCell className="truncate text-txt2" title={e.concepto ?? undefined}>
                    {e.concepto ?? '—'}
                  </TableCell>
                  <TableCell>
                    {e.relevancia_code ? (
                      <Badge
                        variant="outline"
                        style={{
                          color: RELEVANCIA_COLOR[e.relevancia_code],
                          borderColor: RELEVANCIA_COLOR[e.relevancia_code],
                        }}
                      >
                        {RELEVANCIA_LABEL[e.relevancia_code]}
                      </Badge>
                    ) : (
                      <span className="text-txt3">—</span>
                    )}
                  </TableCell>
                  <TableCell
                    className={`text-right tabular-nums ${AMOUNT_COLOR[e.tipo_movimiento] ?? (sign < 0 ? 'text-red' : 'text-green')}`}
                  >
                    {sign < 0 ? '−' : '+'}
                    {fmtMoney(e.importe)}
                  </TableCell>
                  <TableCell>
                    {!locked && (
                      <div className="flex items-center justify-end gap-0.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-txt3 hover:text-accent2"
                          onClick={() => setEditing(e)}
                        >
                          <Pencil className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 text-txt3 hover:text-red"
                          onClick={() => setToDelete(e)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}

      <div className="flex items-center justify-between border-t border-border-subtle px-4 py-2.5 text-xs text-txt2">
        <span>
          {totals.count} {totals.count === 1 ? 'movimiento' : 'movimientos'}
        </span>
        <span>
          Neto:{' '}
          <span className={cn('font-semibold tabular-nums', totals.sum < 0 ? 'text-red' : 'text-green')}>
            {totals.sum < 0 ? '−' : '+'}
            {fmtMoney(Math.abs(totals.sum))}
          </span>
        </span>
      </div>

      <EntryEditDialog
        entry={editing}
        open={!!editing}
        onOpenChange={(o) => !o && setEditing(null)}
      />

      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Eliminar movimiento"
        description={
          toDelete
            ? `${TIPO_LABEL[toDelete.tipo_movimiento]} · ${fmtMoney(toDelete.importe)} · ${toDelete.concepto ?? 'sin concepto'}`
            : undefined
        }
        confirmLabel="Eliminar"
        destructive
        loading={del.isPending}
        onConfirm={() => {
          if (!toDelete) return
          const removed = toDelete
          del.mutate(removed.id, {
            onSuccess: () => {
              toast.success('Movimiento eliminado', {
                action: { label: 'Deshacer', onClick: () => undoDelete(removed) },
              })
              setToDelete(null)
            },
            onError: (err) => {
              toast.error(err instanceof ApiError ? err.message : 'Error al eliminar')
              setToDelete(null)
            },
          })
        }}
      />
    </>
  )
}
