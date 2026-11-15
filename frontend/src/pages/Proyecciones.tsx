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
import { Badge } from '@/components/ui/badge'
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

function nextMonth(key: string): string {
  const [y, m] = key.split('-').map(Number)
  return m >= 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`
}

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

    const histKeys = series.historical
      ? Object.keys(series.historical).sort((a, b) => a.localeCompare(b))
      : []

    // La banda de confianza de SARIMAX puede dispararse (miles de millones) y
    // reventar la escala del eje, dejando invisibles las líneas reales. La
    // acotamos a un múltiplo del mayor valor real (histórico + proyectado).
    const histVals = series.historical ? Object.values(series.historical) : []
    const projVals = Object.values(series.projected).flatMap((y) => y.monthly_values)
    const refMax = Math.max(1, ...histVals, ...projVals)
    const CAP = refMax * 3

    if (showHist && series.historical) {
      for (const mes of histKeys) rows.push({ label: mes, hist: series.historical[mes] })
    }

    // El mes inicial de la proyección es el siguiente al último histórico.
    // Los valores proyectados vienen agrupados por año natural, así que el
    // índice dentro de cada año NO es el mes: hay que asignar meses de forma
    // secuencial a partir del arranque real.
    const lastHist = histKeys.length ? histKeys[histKeys.length - 1] : null
    let cursor = lastHist ? nextMonth(lastHist) : null

    const years = Object.keys(series.projected).sort((a, b) => Number(a) - Number(b))
    for (const year of years) {
      const y = series.projected[year]
      y.monthly_values.forEach((v, i) => {
        const lower = Math.min(y.interval_80.lower[i] ?? 0, CAP)
        const upper = Math.min(y.interval_80.upper[i] ?? 0, CAP)
        const label = cursor ?? `${year}-${String(i + 1).padStart(2, '0')}`
        rows.push({
          label,
          value: v,
          lower,
          band: Math.max(0, upper - lower),
        })
        cursor = cursor ? nextMonth(cursor) : null
      })
    }
    return rows
  }, [series, showHist])

  const yearRows = useMemo(() => {
    if (!series.success) return []

    // El total por año se calcula sumando SIEMPRE los meses reales (historical) +
    // los meses proyectados (monthly_values). El backend no es consistente al doblar
    // el histórico del año en curso entre series, así que lo hacemos aquí: en el año
    // en curso el total es el AÑO COMPLETO (reales + proyectados), no solo el tramo
    // futuro. Media mensual = total / meses reales del año (11, 12…).
    const histByYear: Record<string, number[]> = {}
    if (series.historical) {
      for (const [mes, val] of Object.entries(series.historical)) {
        ;(histByYear[mes.slice(0, 4)] ??= []).push(val)
      }
    }
    const projected = series.projected ?? {}

    const years = Array.from(new Set([...Object.keys(histByYear), ...Object.keys(projected)])).sort(
      (a, b) => Number(a) - Number(b),
    )

    const rows: { year: string; kind: 'hist' | 'proj' | 'current'; annual_total: number; monthly_avg: number; months: number }[] = []
    for (const year of years) {
      const histVals = histByYear[year] ?? []
      const projVals = projected[year]?.monthly_values ?? []
      const months = histVals.length + projVals.length
      if (months === 0) continue
      const total = [...histVals, ...projVals].reduce((s, v) => s + v, 0)
      const kind = projVals.length === 0 ? 'hist' : histVals.length > 0 ? 'current' : 'proj'
      rows.push({ year, kind, annual_total: total, monthly_avg: total / months, months })
    }
    return rows
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
          <YAxis
            tick={{ fill: 'var(--txt2)', fontSize: 11 }}
            width={52}
            tickFormatter={(v) =>
              Math.abs(v) >= 1000 ? `${Math.round(Number(v) / 1000)}k` : String(Math.round(Number(v)))
            }
          />
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
                <th className="py-1 font-medium">Tipo</th>
                <th className="py-1 text-right font-medium">Total</th>
                <th className="py-1 text-right font-medium">Media mensual</th>
                <th className="py-1 text-right font-medium">Meses</th>
              </tr>
            </thead>
            <tbody>
              {yearRows.map((r) => (
                <tr key={`${r.kind}-${r.year}`} className="border-t border-border-subtle">
                  <td className="py-1.5 text-txt">{r.year}</td>
                  <td className="py-1.5">
                    <Badge variant={r.kind === 'hist' ? 'outline' : r.kind === 'current' ? 'amber' : 'accent'}>
                      {r.kind === 'hist' ? 'Histórico' : r.kind === 'current' ? 'En curso' : 'Proyección'}
                    </Badge>
                  </td>
                  <td className="py-1.5 text-right tabular-nums text-txt">{fmtMoney(r.annual_total)}</td>
                  <td className="py-1.5 text-right tabular-nums text-txt2">{fmtMoney(r.monthly_avg)}</td>
                  <td className="py-1.5 text-right tabular-nums text-txt3">{r.months}</td>
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
    <Card className="flex flex-col gap-1 p-4">
      <span className="text-[11px] font-medium uppercase tracking-wide text-txt2">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${tone ?? 'text-txt'}`}>{value}</span>
    </Card>
  )
}
