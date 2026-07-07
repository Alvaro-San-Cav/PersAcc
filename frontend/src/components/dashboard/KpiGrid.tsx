import { Card } from '@/components/ui/card'
import { fmtMoney, fmtPct, signColor } from '@/lib/format'
import type { Kpis } from '@/api/types'

function KpiCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <Card className="gap-1 p-4">
      <span className="text-[11px] font-medium uppercase tracking-wide text-txt2">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${tone ?? 'text-txt'}`}>{value}</span>
    </Card>
  )
}

export function KpiGrid({ kpis }: { kpis: Kpis }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <KpiCard label="Ingresos" value={fmtMoney(kpis.total_ingresos)} tone="text-green" />
      <KpiCard label="Gastos" value={fmtMoney(kpis.total_gastos)} tone="text-red" />
      <KpiCard label="Inversión / Ahorro" value={fmtMoney(kpis.total_inversion)} tone="text-accent2" />
      <KpiCard
        label="Balance del mes"
        value={fmtMoney(kpis.balance_mes)}
        tone={signColor(kpis.balance_mes)}
      />
      <KpiCard label="Tasa de ahorro" value={fmtPct(kpis.pct_salary_retention * 100)} />
      <KpiCard label="Traspasos entrada" value={fmtMoney(kpis.total_traspasos_entrada)} />
      <KpiCard label="Traspasos salida" value={fmtMoney(kpis.total_traspasos_salida)} />
      <KpiCard label="Inversión manual" value={fmtMoney(kpis.inversion_manual)} />
    </div>
  )
}
