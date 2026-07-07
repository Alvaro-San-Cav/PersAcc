import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, Download, Upload } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiPost, apiPostForm, downloadFile } from '@/api/client'
import { ApiError } from '@/api/client'

const TIPOS = [
  { value: 'expenses', label: 'Gastos' },
  { value: 'income', label: 'Ingresos' },
  { value: 'investments', label: 'Inversiones/Ahorro' },
]

const CLEANUP_PHRASE = 'BORRAR TODO'

export function DataTab() {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <ExportCard />
      <RestoreCard />
      <DangerZone />
    </div>
  )
}

function ExportCard() {
  return (
    <Card className="flex flex-col items-start gap-3 p-6">
      <h3 className="text-sm font-semibold text-txt">Exportar</h3>
      <p className="text-sm text-txt2">Exporta todo el libro diario a CSV como copia de seguridad.</p>
      <Button
        variant="outline"
        onClick={() => downloadFile('/api/export/csv', 'persacc_ledger.csv').catch(() => toast.error('Error al exportar'))}
      >
        <Download className="size-4" /> Exportar CSV
      </Button>
    </Card>
  )
}

function RestoreCard() {
  const [tipo, setTipo] = useState('expenses')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)

  async function onPick(f: File | null) {
    setFile(f)
    setPreview([])
    if (f) {
      const text = await f.text()
      setPreview(text.split(/\r?\n/).slice(0, 5))
    }
  }

  async function upload() {
    if (!file) return toast.error('Elige un fichero CSV')
    setBusy(true)
    try {
      const res = await apiPostForm<{ inserted: number; errors: string[] }>('/api/import/backup', {
        file,
        tipo,
      })
      toast.success(`${res.inserted} movimientos importados`)
      qc.invalidateQueries()
      setFile(null)
      setPreview([])
      if (inputRef.current) inputRef.current.value = ''
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Error al importar')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-6">
      <h3 className="text-sm font-semibold text-txt">Restaurar backup CSV</h3>
      <p className="text-sm text-txt2">
        Importa un CSV con columnas fecha, concepto, importe (y opcionalmente categoría, relevancia).
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={tipo} onValueChange={setTipo}>
          <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
          <SelectContent>
            {TIPOS.map((t) => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
          className="text-sm text-txt2 file:mr-2 file:rounded-[var(--radius-card)] file:border-0 file:bg-card2 file:px-3 file:py-1.5 file:text-txt"
        />
      </div>
      {preview.length > 0 && (
        <pre className="max-h-32 overflow-auto rounded-[var(--radius-card)] border border-border-subtle bg-bg2 p-2 text-xs text-txt2">
          {preview.join('\n')}
        </pre>
      )}
      <Button onClick={upload} disabled={busy || !file} className="self-start">
        <Upload className="size-4" /> {busy ? 'Importando…' : 'Importar'}
      </Button>
    </Card>
  )
}

function DangerZone() {
  const [scope, setScope] = useState<'ledger' | 'full'>('ledger')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const qc = useQueryClient()

  async function run() {
    setBusy(true)
    try {
      const res = await apiPost<{ ok: boolean; detail: string }>('/api/admin/cleanup', { scope, confirm })
      toast.success(res.detail)
      setConfirm('')
      qc.invalidateQueries()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Error en la limpieza')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-6" style={{ borderColor: 'var(--red)' }}>
      <h3 className="flex items-center gap-2 text-sm font-semibold text-red">
        <AlertTriangle className="size-4" /> Zona de peligro
      </h3>
      <p className="text-sm text-txt2">
        Borra datos de forma irreversible. Exporta antes con «Exportar CSV». Escribe{' '}
        <code className="rounded bg-card2 px-1 text-txt">{CLEANUP_PHRASE}</code> para confirmar.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={scope} onValueChange={(v) => setScope(v as 'ledger' | 'full')}>
          <SelectTrigger className="w-64"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ledger">Solo movimientos, cierres y notas</SelectItem>
            <SelectItem value="full">Todo + resetear categorías</SelectItem>
          </SelectContent>
        </Select>
        <Input
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder={CLEANUP_PHRASE}
          className="w-40"
        />
        <Button
          variant="danger"
          onClick={run}
          disabled={busy || confirm.trim() !== CLEANUP_PHRASE}
        >
          {busy ? 'Borrando…' : 'Borrar'}
        </Button>
      </div>
    </Card>
  )
}
