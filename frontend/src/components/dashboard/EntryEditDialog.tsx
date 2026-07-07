import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCategories, useUpdateEntry } from '@/api/queries'
import { parseAmount } from '@/lib/utils'
import { fmtDate, RELEVANCIA_LABEL, TIPO_LABEL } from '@/lib/format'
import type { LedgerEntry, Relevancia } from '@/api/types'
import { ApiError } from '@/api/client'

const NO_REL = '__none__'

/**
 * Editor de un movimiento existente. El backend (PUT /api/ledger/{id}) permite
 * cambiar categoría, concepto, importe y relevancia. La fecha y el tipo son
 * inmutables aquí (cambiarlos movería el mes fiscal); se muestran como contexto.
 */
export function EntryEditDialog({
  entry,
  open,
  onOpenChange,
}: {
  entry: LedgerEntry | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { data: cats } = useCategories()
  const update = useUpdateEntry()

  const [catId, setCatId] = useState('')
  const [concepto, setConcepto] = useState('')
  const [importe, setImporte] = useState('')
  const [relevancia, setRelevancia] = useState<Relevancia | ''>('')

  useEffect(() => {
    if (entry) {
      setCatId(String(entry.categoria_id))
      setConcepto(entry.concepto ?? '')
      setImporte(String(entry.importe))
      setRelevancia(entry.relevancia_code ?? '')
    }
  }, [entry])

  const catsForTipo = useMemo(
    () =>
      (cats ?? [])
        .filter((c) => c.tipo_movimiento === entry?.tipo_movimiento)
        .sort((a, b) => b.count - a.count),
    [cats, entry?.tipo_movimiento],
  )

  if (!entry) return null
  const isGasto = entry.tipo_movimiento === 'GASTO'

  function submit() {
    if (!entry) return
    const amount = parseAmount(importe)
    if (!catId) return toast.error('Selecciona una categoría')
    if (!Number.isFinite(amount) || amount <= 0) return toast.error('Importe inválido')

    update.mutate(
      {
        id: entry.id,
        body: {
          categoria_id: Number(catId),
          concepto: concepto || null,
          importe: amount,
          relevancia_code: isGasto && relevancia ? relevancia : null,
        },
      },
      {
        onSuccess: () => {
          toast.success('Movimiento actualizado')
          onOpenChange(false)
        },
        onError: (err) =>
          toast.error(err instanceof ApiError ? err.message : 'Error al actualizar'),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar movimiento</DialogTitle>
          <DialogDescription>
            {TIPO_LABEL[entry.tipo_movimiento]} · {fmtDate(entry.fecha_real)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Categoría</Label>
            <Select value={catId} onValueChange={setCatId}>
              <SelectTrigger>
                <SelectValue placeholder="Selecciona…" />
              </SelectTrigger>
              <SelectContent>
                {catsForTipo.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Concepto</Label>
            <Input value={concepto} onChange={(e) => setConcepto(e.target.value)} placeholder="Opcional" />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Importe</Label>
            <Input
              value={importe}
              onChange={(e) => setImporte(e.target.value)}
              inputMode="decimal"
              placeholder="0,00"
            />
          </div>

          {isGasto && (
            <div className="flex flex-col gap-1.5">
              <Label>Relevancia</Label>
              <Select
                value={relevancia || NO_REL}
                onValueChange={(v) => setRelevancia(v === NO_REL ? '' : (v as Relevancia))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sin clasificar" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_REL}>Sin clasificar</SelectItem>
                  {(Object.keys(RELEVANCIA_LABEL) as Relevancia[]).map((r) => (
                    <SelectItem key={r} value={r}>
                      {RELEVANCIA_LABEL[r]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={update.isPending}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={update.isPending}>
            {update.isPending ? 'Guardando…' : 'Guardar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
