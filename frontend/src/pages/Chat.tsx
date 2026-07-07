import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Download, Search, Sliders } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAiStatus, useChat, useChatRun } from '@/api/queries'
import { fmtDate, fmtMoney } from '@/lib/format'
import { ApiError } from '@/api/client'
import type { ChatResponse } from '@/api/types'

const EXAMPLES = [
  'gastos en comida el año pasado',
  'top 5 gastos de 2025',
  'cuánto gasté en transporte',
]

interface Turn {
  query: string
  result: ChatResponse
}

export function Chat() {
  const { data: status } = useAiStatus()
  const chat = useChat()
  const [query, setQuery] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [elapsed, setElapsed] = useState(0)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const available = status?.enabled && status?.ollama_running

  // Cronómetro de latencia (el modelo local puede tardar >60 s).
  useEffect(() => {
    if (chat.isPending) {
      setElapsed(0)
      timer.current = setInterval(() => setElapsed((e) => e + 1), 1000)
    } else if (timer.current) {
      clearInterval(timer.current)
      timer.current = null
    }
    return () => {
      if (timer.current) clearInterval(timer.current)
    }
  }, [chat.isPending])

  function submit(q: string) {
    if (!q.trim()) return
    chat.mutate(q, {
      onSuccess: (result) => setTurns((t) => [...t, { query: q, result }]),
      onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Error en la búsqueda'),
    })
  }

  return (
    <>
      <PageHeader title="Asistente" subtitle="Busca en tus finanzas en lenguaje natural" />

      {!available ? (
        <Card className="p-6 text-sm text-txt2">
          IA desactivada. Actívala en Utilidades y arranca Ollama para usar el asistente.
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              submit(query)
              setQuery('')
            }}
            className="flex gap-2"
          >
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="¿Cuánto gasté en…?" />
            <Button type="submit" disabled={chat.isPending}>
              <Search className="size-4" />
              {chat.isPending ? 'Buscando…' : 'Buscar'}
            </Button>
          </form>

          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => submit(ex)}
                className="rounded-full border border-border-subtle px-3 py-1 text-xs text-txt2 hover:bg-card2"
              >
                {ex}
              </button>
            ))}
          </div>

          {chat.isPending && (
            <Card className="flex items-center gap-3 p-4 text-sm text-txt2">
              <span className="size-2 animate-pulse rounded-full bg-accent2" />
              {elapsed < 3 ? 'Extrayendo parámetros…' : 'Ejecutando búsqueda…'} · {elapsed}s
            </Card>
          )}

          {/* Historial de la sesión (más reciente arriba). */}
          <div className="flex flex-col gap-4">
            {turns
              .slice()
              .reverse()
              .map((turn, i) => (
                <TurnCard key={turns.length - 1 - i} turn={turn} />
              ))}
          </div>
        </div>
      )}
    </>
  )
}

function TurnCard({ turn }: { turn: Turn }) {
  const run = useChatRun()
  const [data, setData] = useState<ChatResponse>(turn.result)
  const [params, setParams] = useState<Record<string, unknown>>(turn.result.params)
  const [open, setOpen] = useState(false)

  function rerun() {
    run.mutate(
      { tool: data.tool, params },
      {
        onSuccess: (r) => {
          setData(r)
          toast.success('Búsqueda actualizada')
        },
        onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Error al reejecutar'),
      },
    )
  }

  function exportCsv() {
    const header = ['fecha', 'concepto', 'categoria', 'importe']
    const lines = data.entries.map((e) =>
      [e.fecha_real, JSON.stringify(e.concepto ?? ''), e.categoria_nombre ?? '', e.importe].join(','),
    )
    const csv = [header.join(','), ...lines].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'busqueda.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const paramKeys = Object.keys(params)

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-4 py-3 text-sm">
        <div className="flex flex-col">
          <span className="text-xs text-txt3">«{turn.query}»</span>
          <span className="text-txt">{data.summary}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-semibold tabular-nums text-accent2">{fmtMoney(data.total)}</span>
          <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)}>
            <Sliders className="size-4" /> Parámetros
          </Button>
          {data.entries.length > 0 && (
            <Button variant="ghost" size="sm" onClick={exportCsv}>
              <Download className="size-4" /> CSV
            </Button>
          )}
        </div>
      </div>

      {open && (
        <div className="flex flex-wrap items-end gap-3 border-b border-border-subtle bg-card2/40 px-4 py-3">
          <span className="text-xs text-txt3">herramienta: {data.tool}</span>
          {paramKeys.map((k) => (
            <div key={k} className="flex flex-col gap-1">
              <label className="text-[11px] uppercase tracking-wide text-txt2">{k}</label>
              <Input
                value={String(params[k] ?? '')}
                onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                className="h-8 w-32"
              />
            </div>
          ))}
          <Button size="sm" onClick={rerun} disabled={run.isPending}>
            {run.isPending ? 'Ejecutando…' : 'Volver a ejecutar'}
          </Button>
        </div>
      )}

      {data.entries.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Concepto</TableHead>
              <TableHead>Categoría</TableHead>
              <TableHead className="text-right">Importe</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.entries.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="whitespace-nowrap text-txt2">{fmtDate(e.fecha_real)}</TableCell>
                <TableCell className="max-w-[280px] truncate text-txt">{e.concepto}</TableCell>
                <TableCell className="text-txt2">{e.categoria_nombre}</TableCell>
                <TableCell className="text-right tabular-nums text-txt">{fmtMoney(e.importe)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="grid h-24 place-items-center text-sm text-txt2">Sin resultados</div>
      )}
    </Card>
  )
}
