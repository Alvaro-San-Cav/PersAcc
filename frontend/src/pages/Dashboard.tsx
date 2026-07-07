import { useState } from 'react'
import { Lock } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
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
import { QuickAddForm } from '@/components/dashboard/QuickAddForm'
import { LedgerTable } from '@/components/dashboard/LedgerTable'
import { NotesCard } from '@/components/dashboard/NotesCard'
import { useAiStatus, useCommentary, useDashboard } from '@/api/queries'
import { fmtMonth } from '@/lib/format'

export function Dashboard() {
  const [month, setMonth] = useState<string | undefined>(undefined)
  const { data, isLoading, isError, error } = useDashboard(month)

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
        title="Dashboard"
        subtitle={fmtMonth(data.mes_fiscal)}
        actions={
          <div className="flex items-center gap-2">
            {data.is_cerrado && (
              <Badge variant="outline" className="gap-1 text-amber" style={{ borderColor: 'var(--amber)' }}>
                <Lock className="size-3" /> Mes cerrado
              </Badge>
            )}
            <Select value={data.mes_fiscal} onValueChange={setMonth}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {data.available_months.map((m) => (
                  <SelectItem key={m} value={m}>
                    {fmtMonth(m)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
      />

      <div className="flex flex-col gap-4">
        <KpiGrid kpis={data.kpis} />

        <Commentary month={data.mes_fiscal} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
          <div className="flex flex-col gap-4">
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-txt">Calidad del gasto</h2>
              <QualityDonut data={data.relevancia} />
            </Card>
            <Card className="overflow-hidden p-0">
              <div className="border-b border-border-subtle px-4 py-3">
                <h2 className="text-sm font-semibold text-txt">Movimientos</h2>
              </div>
              <LedgerTable entries={data.entries} locked={data.is_cerrado} />
            </Card>
          </div>

          <div className="flex flex-col gap-4">
            {!data.is_cerrado && <QuickAddForm mesFiscal={data.mes_fiscal} />}
            <NotesCard
              periodType="month"
              periodId={data.mes_fiscal}
              readOnly={data.is_cerrado}
              title={`Notas de ${fmtMonth(data.mes_fiscal)}`}
            />
          </div>
        </div>
      </div>
    </>
  )
}

function Commentary({ month }: { month: string }) {
  const { data: status } = useAiStatus()
  const enabled = !!status?.enabled && !!status?.ollama_running
  const { data, isLoading } = useCommentary(month, enabled)

  if (!enabled || (!isLoading && !data?.text)) return null

  return (
    <Card className="flex items-center gap-3 p-4">
      <Sparkles className="size-4 shrink-0 text-accent2" />
      <p className="text-sm text-txt2">{isLoading ? 'Generando comentario…' : data?.text}</p>
    </Card>
  )
}
