import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import {
  Area,
  ComposedChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useProjections, useTrainProjections } from '@/api/queries'
import { fmtMoney, fmtPct } from '@/lib/format'
import type { ProjectionSeries, ProjectionsResponse } from '@/api/types'

const SERIES_META = [
  { key: 'ingreso', label: 'Ingresos', color: 'var(--green)' },
  { key: 'gasto', label: 'Gastos', color: 'var(--red)' },
  { key: 'ahorro', label: 'Inversión / Ahorro', color: 'var(--accent2)' },
] as const

const HORIZONS = [6, 12, 24, 36] as const

function seriesTotal(s: ProjectionSeries): number {
  if (!s.success || !s.projected) return 0
  return Object.values(s.projected).reduce((sum, y) => sum + y.annual_total, 0)
}

export function Proyecciones() {
  const [months, setMonths] = useState(12)
  const [showHist, setShowHist] = useState(true)
  const { data, isLoading } = useProjections(months)
  const train = useTrainProjections()

  const untrained = data ? Object.values(data.series).every((s) => !s.success) : false

  const summary = useMemo(() => {
    if (!data) return null
    const ing = seriesTotal(data.series.ingreso)
    const gas = seriesTotal(data.series.gasto)
    const aho = seriesTotal(data.series.ahorro)
    const tasa = ing > 0 ? (aho / ing) * 100 : 0
    return { ing, gas, aho, tasa }
  }, [data])

  return (
    <>
      <PageHeader
        title="Proyecciones"
        subtitle="Previsión SARIMAX · banda de confianza 80 %"
        actions={
          <div className="flex items-center gap-2">
            <Select value={String(months)} onValueChange={(v) => setMonths(Number(v))}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                {HORIZONS.map((h) => (
                  <SelectItem key={h} value={String(h)}>{h} meses</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              disabled={train.isPending}
              onClick={() =>
                train.mutate(months, {
                  onSuccess: () => toast.success('Modelos reentrenados'),
                  onError: () => toast.error('Error al entrenar'),
                })
              }
            >
              {train.isPending ? 'Entrenando…' : 'Reentrenar modelos'}
            </Button>
          </div>
        }
      />

      {isLoading ? (
        <Skeleton className="h-72" />
      ) : untrained ? (
        <Card className="p-6 text-sm text-txt2">
          Los modelos aún no están entrenados. Pulsa «Reentrenar modelos» para generar las
          previsiones a partir de tu histórico.
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {summary && (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Metric label="Ingresos proyectados" value={fmtMoney(summary.ing)} tone="text-green" />
              <Metric label="Gastos proyectados" value={fmtMoney(summary.gas)} tone="text-red" />
              <Metric label="Ahorro proyectado" value={fmtMoney(summary.aho)} tone="text-accent2" />
              <Metric label="Tasa de ahorro" value={fmtPct(summary.tasa)} />
            </div>
          )}

          <label className="flex items-center gap-2 self-start text-sm text-txt2">
            <input type="checkbox" checked={showHist} onChange={(e) => setShowHist(e.target.checked)} />
            Mostrar histórico junto a la proyección
          </label>

          {SERIES_META.map(({ key, label, color }) => (
            <ProjectionCard
              key={key}
              label={label}
              color={color}
              series={(data as ProjectionsResponse).series[key]}
              showHist={showHist}
            />
          ))}
        </div>
      )}
    </>
  )
}

function ProjectionCard({
  label,
  color,
  series,
  showHist,
}: {
  label: string
  color: string
  series: ProjectionSeries
  showHist: boolean
}) {
  const chartData = useMemo(() => {
    if (!series.success || !series.projected) return []
    const rows: { label: string; value?: number; hist?: number; lower?: number; band?: number }[] = []

    if (showHist && series.historical) {
      const hist = Object.entries(series.historical).sort((a, b) => a[0].localeCompare(b[0]))
      for (const [mes, v] of hist) rows.push({ label: mes, hist: v })
    }

    for (const [year, y] of Object.entries(series.projected)) {
      y.monthly_values.forEach((v, i) => {
        const lower = y.interval_80.lower[i] ?? 0
        const upper = y.interval_80.upper[i] ?? 0
        rows.push({
          label: `${year}-${String(i + 1).padStart(2, '0')}`,
          value: v,
          lower,
          band: Math.max(0, upper - lower),
        })
      })
    }
    return rows
  }, [series, showHist])

  const yearRows = useMemo(() => {
    if (!series.success || !series.projected) return []
    return Object.entries(series.projected).map(([year, y]) => ({
      year,
      annual_total: y.annual_total,
      monthly_avg: y.monthly_avg,
    }))
  }, [series])

  if (!series.success) {
    return (
      <Card className="p-4 text-sm text-txt2">
        <span className="font-semibold text-txt">{label}: </span>
        {series.error ?? 'sin datos'}
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <h2 className="mb-3 text-sm font-semibold text-txt">{label}</h2>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="label" tick={{ fill: 'var(--txt2)', fontSize: 11 }} />
          <YAxis tick={{ fill: 'var(--txt2)', fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              background: 'var(--card2)',
              border: '1px solid var(--border2)',
              borderRadius: 8,
              color: 'var(--txt)',
            }}
            formatter={(v) => fmtMoney(Number(v))}
          />
          <Area dataKey="lower" stackId="band" stroke="none" fill="transparent" />
          <Area dataKey="band" stackId="band" stroke="none" fill={color} fillOpacity={0.12} />
          {showHist && <Line dataKey="hist" stroke="var(--txt3)" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />}
          <Line dataKey="value" stroke={color} strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>

      {yearRows.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-txt2">
                <th className="py-1 font-medium">Año</th>
                <th className="py-1 text-right font-medium">Total proyectado</th>
                <th className="py-1 text-right font-medium">Media mensual</th>
              </tr>
            </thead>
            <tbody>
              {yearRows.map((r) => (
                <tr key={r.year} className="border-t border-border-subtle">
                  <td className="py-1.5 text-txt">{r.year}</td>
                  <td className="py-1.5 text-right tabular-nums text-txt">{fmtMoney(r.annual_total)}</td>
                  <td className="py-1.5 text-right tabular-nums text-txt2">{fmtMoney(r.monthly_avg)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <Card className="gap-1 p-4">
      <span className="text-[11px] font-medium uppercase tracking-wide text-txt2">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${tone ?? 'text-txt'}`}>{value}</span>
    </Card>
  )
}
