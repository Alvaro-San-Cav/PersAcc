import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Upload } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiPost, apiUpload, ApiError } from '@/api/client'
import { useCategories } from '@/api/queries'
import { RELEVANCIA_LABEL, TIPO_LABEL } from '@/lib/format'
import type { ImportEntry, ImportPreviewResponse, ImportCommitResponse, Relevancia, TipoMovimiento } from '@/api/types'

const TIPOS: TipoMovimiento[] = ['GASTO', 'INGRESO', 'INVERSION_AHORRO', 'TRASPASO_ENTRADA', 'TRASPASO_SALIDA']
const THRESHOLD = 0.6
const NO_REL = '__none__'

type Row = ImportEntry & { _sel: boolean; _idx: number }

export function Importar() {
  const [fileType, setFileType] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [busy, setBusy] = useState(false)
  const { data: cats } = useCategories()

  async function onFile(file: File) {
    setBusy(true)
    setRows([])
    try {
      const res = await apiUpload<ImportPreviewResponse>('/api/import/preview', [file])
      setFileType(res.file_type)
      setRows(res.entries.map((e, i) => ({ ...e, _sel: !e.is_duplicate, _idx: i })))
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Error al procesar el fichero')
    } finally {
      setBusy(false)
    }
  }

  function update(idx: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r) => (r._idx === idx ? { ...r, ...patch } : r)))
  }

  const buckets = useMemo(() => {
    const good: Row[] = []
    const review: Row[] = []
    const ignored: Row[] = []
    for (const r of rows) {
      if (r.is_duplicate) ignored.push(r)
      else if (r.confianza >= THRESHOLD && r.categoria_sugerida) good.push(r)
      else review.push(r)
    }
    return { good, review, ignored }
  }, [rows])

  const selectedCount = rows.filter((r) => r._sel && !r.is_duplicate).length

  async function commit() {
    const entries = rows
      .filter((r) => r._sel && !r.is_duplicate)
      .map(({ _sel, _idx, ...e }) => e)
    if (!entries.length) return toast.error('No hay movimientos seleccionados')
    setBusy(true)
    try {
      const res = await apiPost<ImportCommitResponse>('/api/import/commit', { entries })
      toast.success(
        `${res.inserted} añadidos · ${res.skipped} omitidos` +
          (res.duplicates ? ` · ${res.duplicates} duplicados saltados` : ''),
      )
      setRows([])
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Error al guardar')
    } finally {
      setBusy(false)
    }
  }

  const hasPreview = rows.length > 0

  return (
    <>
      <PageHeader title="Importar" subtitle="Ficheros bancarios (AEB N43, SEPA, Excel)" />

      {!hasPreview && (
        <Card className="flex flex-col items-start gap-3 p-6">
          <p className="text-sm text-txt2">
            Sube un extracto bancario. La IA (Ollama) clasificará los movimientos y marcará los
            duplicados. Podrás revisar y editar antes de confirmar.
          </p>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-[var(--radius-card)] bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90">
            <Upload className="size-4" />
            {busy ? 'Procesando…' : 'Seleccionar fichero'}
            <input
              type="file"
              className="hidden"
              disabled={busy}
              accept=".csv,.txt,.aeb,.csb,.xlsx,.xls"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) onFile(f)
                e.target.value = ''
              }}
            />
          </label>
        </Card>
      )}

      {hasPreview && (
        <Card className="overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-4 py-3">
            <div className="text-sm text-txt2">
              {fileType} · {rows.length} movimientos · {selectedCount} seleccionados
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setRows([])} disabled={busy}>
                Cancelar
              </Button>
              <Button onClick={commit} disabled={busy || selectedCount === 0}>
                {busy ? 'Guardando…' : `Importar ${selectedCount}`}
              </Button>
            </div>
          </div>

          <Tabs defaultValue="good" className="p-3">
            <TabsList>
              <TabsTrigger value="good">Buenas ({buckets.good.length})</TabsTrigger>
              <TabsTrigger value="review">A revisar ({buckets.review.length})</TabsTrigger>
              <TabsTrigger value="ignored">Ignoradas ({buckets.ignored.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="good">
              <EditableTable rows={buckets.good} cats={cats ?? []} update={update} />
            </TabsContent>
            <TabsContent value="review">
              <EditableTable rows={buckets.review} cats={cats ?? []} update={update} />
            </TabsContent>
            <TabsContent value="ignored">
              <EditableTable rows={buckets.ignored} cats={cats ?? []} update={update} ignored />
            </TabsContent>
          </Tabs>
        </Card>
      )}
    </>
  )
}

function EditableTable({
  rows,
  cats,
  update,
  ignored = false,
}: {
  rows: Row[]
  cats: { id: number; nombre: string; tipo_movimiento: string }[]
  update: (idx: number, patch: Partial<Row>) => void
  ignored?: boolean
}) {
  if (!rows.length) {
    return <div className="grid h-24 place-items-center text-sm text-txt2">Sin movimientos aquí</div>
  }
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8" />
            <TableHead>Fecha</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Categoría</TableHead>
            <TableHead>Concepto</TableHead>
            <TableHead>Relev.</TableHead>
            <TableHead className="text-right">Importe</TableHead>
            <TableHead>Conf.</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const catsForTipo = cats.filter((c) => c.tipo_movimiento === r.tipo_movimiento)
            return (
              <TableRow key={r._idx} className={ignored ? 'opacity-60' : ''}>
                <TableCell>
                  <input
                    type="checkbox"
                    checked={r._sel}
                    disabled={ignored}
                    onChange={(e) => update(r._idx, { _sel: e.target.checked })}
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="date"
                    value={r.fecha}
                    onChange={(e) => update(r._idx, { fecha: e.target.value })}
                    className="h-8 w-36"
                  />
                </TableCell>
                <TableCell>
                  <Select value={r.tipo_movimiento} onValueChange={(v) => update(r._idx, { tipo_movimiento: v as TipoMovimiento })}>
                    <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TIPOS.map((t) => (
                        <SelectItem key={t} value={t}>{TIPO_LABEL[t]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <Select
                    value={r.categoria_sugerida ?? ''}
                    onValueChange={(v) => update(r._idx, { categoria_sugerida: v })}
                  >
                    <SelectTrigger className="h-8 w-40"><SelectValue placeholder="Sin categoría" /></SelectTrigger>
                    <SelectContent>
                      {catsForTipo.map((c) => (
                        <SelectItem key={c.id} value={c.nombre}>{c.nombre}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <Input
                    value={r.concepto}
                    onChange={(e) => update(r._idx, { concepto: e.target.value })}
                    className="h-8 w-48"
                  />
                </TableCell>
                <TableCell>
                  {r.tipo_movimiento === 'GASTO' ? (
                    <Select
                      value={r.relevancia || NO_REL}
                      onValueChange={(v) => update(r._idx, { relevancia: v === NO_REL ? null : (v as Relevancia) })}
                    >
                      <SelectTrigger className="h-8 w-24"><SelectValue placeholder="—" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NO_REL}>—</SelectItem>
                        {(Object.keys(RELEVANCIA_LABEL) as Relevancia[]).map((rel) => (
                          <SelectItem key={rel} value={rel}>{rel}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="text-txt3">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Input
                    value={String(r.importe)}
                    onChange={(e) => update(r._idx, { importe: Number(e.target.value) || 0 })}
                    inputMode="decimal"
                    className="h-8 w-24 text-right"
                  />
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {r.is_duplicate ? (
                    <Badge variant="amber">dup</Badge>
                  ) : (
                    <span className="tabular-nums text-txt3">{(r.confianza * 100).toFixed(0)}%</span>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      {ignored && (
        <p className="px-3 py-2 text-xs text-txt3">
          Duplicados detectados contra movimientos ya guardados (mismo importe y fecha). No se importan.
        </p>
      )}
    </div>
  )
}
