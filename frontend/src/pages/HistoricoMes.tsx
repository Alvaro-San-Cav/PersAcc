import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
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
import { QualityDonut } from '@/components/charts/QualityDonut'
import { CategoryDonut } from '@/components/charts/CategoryDonut'
import { LedgerTable } from '@/components/dashboard/LedgerTable'
import { NotesCard } from '@/components/dashboard/NotesCard'
import { AnalysisPanel } from '@/components/ai/AnalysisPanel'
import { useMonthDetail } from '@/api/queries'
import { fmtMoney, fmtMonth } from '@/lib/format'

export function HistoricoMes() {
  const { anio, mes } = useParams()
  const anioNum = Number(anio)
  const mesNum = Number(mes)
  const { data, isLoading } = useMonthDetail(anioNum, mesNum)
  const [catFilter, setCatFilter] = useState<string>('')

  const mesFiscal = `${anio}-${String(mesNum).padStart(2, '0')}`

  const catEntries = useMemo(() => {
    if (!data || !catFilter) return []
    return data.entries.filter((e) => e.categoria_nombre === catFilter && e.tipo_movimiento === 'GASTO')
  }, [data, catFilter])

  const balance = data ? data.kpis.total_ingresos - data.kpis.total_gastos : 0

  return (
    <>
      <PageHeader
        title={fmtMonth(mesFiscal)}
        subtitle="Detalle mensual"
        actions={
          <Button variant="outline" asChild>
            <Link to="/historico">
              <ArrowLeft className="size-4" /> Volver al año {anio}
            </Link>
          </Button>
        }
      />

      {isLoading || !data ? (
        <Skeleton className="h-72" />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Ingresos" value={fmtMoney(data.kpis.total_ingresos)} tone="text-green" />
            <Stat label="Gastos" value={fmtMoney(data.kpis.total_gastos)} tone="text-red" />
            <Stat label="Balance" value={fmtMoney(balance)} tone={balance >= 0 ? 'text-green' : 'text-red'} />
            <Stat label="Inversión" value={fmtMoney(data.kpis.total_inversion)} tone="text-accent2" />
          </div>

          {data.retenciones.total > 0 && (
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-txt">Retenciones del cierre</h2>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Ret label="Salario" value={data.retenciones.salario} color="var(--li)" />
                <Ret label="Remanente" value={data.retenciones.remanente} color="var(--ne)" />
                <Ret label="Consecuencias" value={data.retenciones.consecuencias} color="var(--sup)" />
                <Ret label="Manual" value={data.retenciones.manual} color="var(--txt2)" />
              </div>
            </Card>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-txt">Gastos por categoría</h2>
              <CategoryDonut data={data.gastos_por_categoria} />
              {data.gastos_por_categoria.length > 0 && (
                <div className="mt-4 flex flex-col gap-2">
                  <Select value={catFilter} onValueChange={setCatFilter}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Explorar movimientos por categoría…" />
                    </SelectTrigger>
                    <SelectContent>
                      {data.gastos_por_categoria.map((c) => (
                        <SelectItem key={c.categoria} value={c.categoria}>
                          {c.categoria} · {fmtMoney(c.importe)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {catFilter && (
                    <ul className="flex flex-col gap-1 rounded-[var(--radius-card)] border border-border-subtle p-2 text-sm">
                      {catEntries.map((e) => (
                        <li key={e.id} className="flex items-center justify-between gap-2">
                          <span className="truncate text-txt2">{e.concepto || '—'}</span>
                          <span className="tabular-nums text-txt">{fmtMoney(e.importe)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </Card>

            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-txt">Calidad del gasto</h2>
              <QualityDonut data={data.relevancia} />
            </Card>
          </div>

          <NotesCard periodType="month" periodId={mesFiscal} readOnly title={`Notas de ${fmtMonth(mesFiscal)}`} />
          <AnalysisPanel periodType="month" periodId={mesFiscal} />

          <Card className="overflow-hidden p-0">
            <div className="border-b border-border-subtle px-4 py-3">
              <h2 className="text-sm font-semibold text-txt">Movimientos del mes</h2>
            </div>
            <LedgerTable entries={data.entries} locked={data.is_cerrado} />
          </Card>
        </div>
      )}
    </>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <Card className="gap-1 p-4">
      <span className="text-[11px] font-medium uppercase tracking-wide text-txt2">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${tone ?? 'text-txt'}`}>{value}</span>
    </Card>
  )
}

function Ret({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border-l-4 bg-card2 px-3 py-2" style={{ borderColor: color }}>
      <div className="text-[11px] uppercase tracking-wide text-txt2">{label}</div>
      <div className="text-base font-semibold tabular-nums" style={{ color }}>
        {fmtMoney(value)}
      </div>
    </div>
  )
}
