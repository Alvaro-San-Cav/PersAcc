import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Check, Lock, Pencil, X, CalendarSync, ChevronLeft, ChevronRight } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CierreModal } from '@/components/dashboard/CierreModal'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Sparkles } from 'lucide-react'
import { KpiGrid } from '@/components/dashboard/KpiGrid'
import { QualityDonut } from '@/components/charts/QualityDonut'
import { CategoryDonut } from '@/components/charts/CategoryDonut'
import { LedgerTable } from '@/components/dashboard/LedgerTable'
import { NotesCard } from '@/components/dashboard/NotesCard'
import { useAiStatus, useCommentary, useDashboard, useSetSaldoInicio } from '@/api/queries'
import { fmtMoney, fmtMonth, signColor } from '@/lib/format'
import { parseAmount } from '@/lib/utils'
import type { DashboardResponse } from '@/api/types'

// Mes en curso = el más reciente de los disponibles (formato "YYYY-MM", orden lexicográfico).
function maxMonth(months: string[]): string | undefined {
  return months.length ? [...months].sort().at(-1) : undefined
}

export function Dashboard() {
  const [month, setMonth] = useState<string | undefined>(undefined)
  const [cierreOpen, setCierreOpen] = useState(false)
  const { data, isLoading, isError, error } = useDashboard(month)

  const gastosPorCategoria = useMemo(() => {
    if (!data) return []
    const acc = new Map<string, number>()
    for (const e of data.entries) {
      if (e.tipo_movimiento !== 'GASTO') continue
      const key = e.categoria_nombre ?? 'Sin categoría'
      acc.set(key, (acc.get(key) ?? 0) + e.importe)
    }
    return [...acc.entries()]
      .map(([categoria, importe]) => ({ categoria, importe }))
      .sort((a, b) => b.importe - a.importe)
  }, [data])

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <Card className="p-6 text-sm text-red">
        Error al cargar el dashboard: {(error as Error)?.message ?? 'desconocido'}
        <p className="mt-2 text-txt2">¿Está el backend arrancado en el puerto 8001?</p>
      </Card>
    )
  }

  return (
    <>
      <PageHeader
        title="Panel"
        subtitle={fmtMonth(data.mes_fiscal)}
        actions={
          <div className="flex items-center gap-2">
            {data.is_cerrado && (
              <Badge variant="outline" className="gap-1 text-amber" style={{ borderColor: 'var(--amber)' }}>
                <Lock className="size-3" /> Mes cerrado
              </Badge>
            )}
            <MonthPicker
              value={data.mes_fiscal}
              months={data.available_months}
              onChange={setMonth}
            />
            {data.mes_fiscal === maxMonth(data.available_months) && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => setCierreOpen(true)}
                title="Cambio de mes"
              >
                <CalendarSync className="size-4" />
                Cambio de mes
              </Button>
            )}
          </div>
        }
      />

      <CierreModal
        open={cierreOpen}
        onOpenChange={setCierreOpen}
        onClosed={(mesSiguiente) => setMonth(mesSiguiente)}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px] lg:items-start">
        {/* Columna izquierda: saldo, KPIs, comentario y tabla */}
        <div className="flex flex-col gap-2.5">
          <SaldoCard data={data} />

          <KpiGrid kpis={data.kpis} />

          <Commentary month={data.mes_fiscal} />

          <Card className="overflow-hidden p-0">
            <div className="border-b border-border-subtle px-4 py-3">
              <h2 className="text-sm font-semibold text-txt">Movimientos</h2>
            </div>
            <LedgerTable entries={data.entries} locked={data.is_cerrado} />
          </Card>
        </div>

        {/* Columna derecha: donuts y notas */}
        <div className="flex flex-col gap-4">
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-txt">Gastos por categoría</h2>
            <CategoryDonut data={gastosPorCategoria} />
          </Card>
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-txt">Calidad del gasto</h2>
            <QualityDonut data={data.relevancia} />
          </Card>
          <NotesCard
            periodType="month"
            periodId={data.mes_fiscal}
            readOnly={data.is_cerrado}
            title={`Notas de ${fmtMonth(data.mes_fiscal)}`}
          />
        </div>
      </div>
    </>
  )
}

/**
 * Navegador de mes: flechas ‹ › para saltar al mes contiguo y un menú
 * desplegable para saltar a cualquier mes. `months` llega descendente
 * (más reciente primero) desde el backend.
 */
function MonthPicker({
  value,
  months,
  onChange,
}: {
  value: string
  months: string[]
  onChange: (m: string) => void
}) {
  // Ordenar descendente por seguridad (más reciente → más antiguo).
  const sorted = [...months].sort().reverse()
  const idx = sorted.indexOf(value)
  const newer = idx > 0 ? sorted[idx - 1] : null // mes siguiente en el tiempo
  const older = idx >= 0 && idx < sorted.length - 1 ? sorted[idx + 1] : null // anterior

  return (
    <div className="flex h-9 items-center rounded-[var(--radius-card)] border border-border-strong bg-bg2">
      <button
        type="button"
        onClick={() => older && onChange(older)}
        disabled={!older}
        title="Mes anterior"
        className="flex h-full items-center rounded-l-[var(--radius-card)] px-1.5 text-txt3 transition-colors hover:bg-card2 hover:text-txt disabled:pointer-events-none disabled:opacity-30"
      >
        <ChevronLeft className="size-4" />
      </button>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="!h-full min-w-32 justify-center gap-1.5 !border-0 !bg-transparent px-2 font-medium capitalize focus:!ring-0">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {sorted.map((m) => (
            <SelectItem key={m} value={m} className="capitalize">
              {fmtMonth(m)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <button
        type="button"
        onClick={() => newer && onChange(newer)}
        disabled={!newer}
        title="Mes siguiente"
        className="flex h-full items-center rounded-r-[var(--radius-card)] px-1.5 text-txt3 transition-colors hover:bg-card2 hover:text-txt disabled:pointer-events-none disabled:opacity-30"
      >
        <ChevronRight className="size-4" />
      </button>
    </div>
  )
}

function SaldoCard({ data }: { data: DashboardResponse }) {
  const setSaldo = useSetSaldoInicio()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')

  function open() {
    setValue(String(data.saldo_inicio))
    setEditing(true)
  }

  function save() {
    const amount = parseAmount(value)
    if (!Number.isFinite(amount) || amount < 0) return toast.error('Saldo inválido')
    setSaldo.mutate(
      { month: data.mes_fiscal, saldo_inicio: amount },
      {
        onSuccess: () => {
          toast.success('Saldo inicial actualizado')
          setEditing(false)
        },
        onError: () => toast.error('No se pudo guardar (¿mes cerrado?)'),
      },
    )
  }

  return (
    <Card className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-accent/40 bg-accent/5 px-3 py-1.5">
      <div className="flex items-baseline gap-2.5">
        <span className="text-[9px] font-medium uppercase tracking-wide text-txt2">Dinero en cuenta</span>
        <span className={`text-xl font-bold tabular-nums ${signColor(data.saldo_cuenta)}`}>
          {fmtMoney(data.saldo_cuenta)}
        </span>
      </div>
      {editing ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-txt3">Saldo inicio</span>
          <Input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') save()
              if (e.key === 'Escape') setEditing(false)
            }}
            placeholder="0,00"
            inputMode="decimal"
            className="h-7 w-24 tabular-nums"
          />
          <button
            type="button"
            onClick={save}
            disabled={setSaldo.isPending}
            className="flex size-7 items-center justify-center rounded-[var(--radius-card)] text-green transition-colors hover:bg-green/10"
          >
            <Check className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="flex size-7 items-center justify-center rounded-[var(--radius-card)] text-txt3 transition-colors hover:bg-card2"
          >
            <X className="size-4" />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-txt3">
            Saldo inicio {fmtMoney(data.saldo_inicio)} + balance {fmtMoney(data.kpis.balance_mes)} − inversión {fmtMoney(data.kpis.total_inversion)}
          </span>
          {!data.is_cerrado && (
            <button
              type="button"
              onClick={open}
              title="Editar saldo inicial"
              className="flex size-6 items-center justify-center rounded-[var(--radius-card)] text-txt3 transition-colors hover:bg-card2 hover:text-accent2"
            >
              <Pencil className="size-3" />
            </button>
          )}
        </div>
      )}
    </Card>
  )
}

function Commentary({ month }: { month: string }) {
  const { data: status } = useAiStatus()
  const enabled = !!status?.enabled && !!status?.ollama_running
  const { data, isLoading } = useCommentary(month, enabled)

  if (!enabled || (!isLoading && !data?.text)) return null

  return (
    <Card className="flex items-center gap-2 px-3 py-2">
      <Sparkles className="size-4 shrink-0 text-accent2" />
      <p className="text-xs text-txt2">{isLoading ? 'Generando comentario…' : data?.text}</p>
    </Card>
  )
}
