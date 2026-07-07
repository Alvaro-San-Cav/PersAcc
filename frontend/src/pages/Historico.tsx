import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useYear, useYears, useYearAnalysis, useLedgerByYear } from '@/api/queries'
import { AnalysisPanel } from '@/components/ai/AnalysisPanel'
import { NotesCard } from '@/components/dashboard/NotesCard'
import { WordFreqChart } from '@/components/charts/WordFreqChart'
import { TopEntriesTable } from '@/components/charts/TopEntriesTable'
import { CuriositiesCards } from '@/components/charts/CuriositiesCards'
import { LedgerTable } from '@/components/dashboard/LedgerTable'
import { fmtMoney, fmtPct, TIPO_LABEL } from '@/lib/format'
import type { TipoMovimiento } from '@/api/types'

const ANALYSIS_TIPOS: TipoMovimiento[] = ['GASTO', 'INGRESO', 'INVERSION_AHORRO']

export function Historico() {
  const { data: years } = useYears()
  const navigate = useNavigate()
  const [anio, setAnio] = useState<number | undefined>(undefined)

  useEffect(() => {
    if (years?.length && anio === undefined) setAnio(years[0])
  }, [years, anio])

  const { data, isLoading } = useYear(anio)

  // Medias mensuales derivadas de los meses con datos.
  const medias = useMemo(() => {
    if (!data || !data.meses.length) return { ingresos: 0, gastos: 0 }
    const n = data.meses.length
    const ing = data.meses.reduce((s, m) => s + m.ingresos, 0) / n
    const gas = data.meses.reduce((s, m) => s + m.gastos, 0) / n
    return { ingresos: ing, gastos: gas }
  }, [data])

  return (
    <>
      <PageHeader
        title="Histórico"
        subtitle="KPIs anuales, análisis y datos"
        actions={
          <Select value={anio ? String(anio) : ''} onValueChange={(v) => setAnio(Number(v))}>
            <SelectTrigger className="w-28">
              <SelectValue placeholder="Año" />
            </SelectTrigger>
            <SelectContent>
              {(years ?? []).map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      {years?.length === 0 ? (
        <Card className="p-6 text-sm text-txt2">
          Sin datos históricos todavía. Añade movimientos o importa un backup para ver tu evolución
          anual.
        </Card>
      ) : isLoading || !data ? (
        <Skeleton className="h-72" />
      ) : (
        <Tabs defaultValue="resumen">
          <TabsList>
            <TabsTrigger value="resumen">Resumen</TabsTrigger>
            <TabsTrigger value="analisis">Análisis</TabsTrigger>
            <TabsTrigger value="datos">Datos</TabsTrigger>
          </TabsList>

          <TabsContent value="resumen">
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Ingresos" value={fmtMoney(data.total_ingresos)} tone="text-green" />
                <Stat label="Gastos" value={fmtMoney(data.total_gastos)} tone="text-red" />
                <Stat label="Ahorrado" value={fmtMoney(data.total_ahorrado)} tone="text-accent2" />
                <Stat label="Tasa de ahorro" value={fmtPct(data.pct_ahorro)} />
              </div>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Media ingresos/mes" value={fmtMoney(medias.ingresos)} tone="text-green" />
                <Stat label="Media gastos/mes" value={fmtMoney(medias.gastos)} tone="text-red" />
                <Stat label="Mejor mes" value={data.mejor_mes ?? '—'} />
                <Stat label="Peor mes" value={data.peor_mes ?? '—'} />
              </div>

              <Card className="p-4">
                <h2 className="mb-1 text-sm font-semibold text-txt">Balance mensual</h2>
                <p className="mb-3 text-xs text-txt3">Haz clic en un mes para ver su detalle.</p>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={data.meses}
                    onClick={(st) => {
                      const label = st?.activeLabel as string | undefined
                      if (label) {
                        const [, m] = label.split('-')
                        navigate(`/historico/${anio}/${Number(m)}`)
                      }
                    }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="mes_fiscal" tick={{ fill: 'var(--txt2)', fontSize: 12 }} />
                    <YAxis tick={{ fill: 'var(--txt2)', fontSize: 12 }} />
                    <Tooltip
                      cursor={{ fill: 'var(--card2)' }}
                      contentStyle={{
                        background: 'var(--card2)',
                        border: '1px solid var(--border2)',
                        borderRadius: 8,
                        color: 'var(--txt)',
                      }}
                      formatter={(v) => fmtMoney(Number(v))}
                    />
                    <Bar dataKey="ingresos" fill="var(--green)" radius={[3, 3, 0, 0]} className="cursor-pointer" />
                    <Bar dataKey="gastos" fill="var(--red)" radius={[3, 3, 0, 0]} className="cursor-pointer" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Necesario" value={fmtMoney(data.gastos_NE)} tone="text-ne" />
                <Stat label="Me gusta" value={fmtMoney(data.gastos_LI)} tone="text-li" />
                <Stat label="Superfluo" value={fmtMoney(data.gastos_SUP)} tone="text-sup" />
                <Stat label="Tontería" value={fmtMoney(data.gastos_TON)} tone="text-ton" />
              </div>

              {anio && <NotesCard periodType="year" periodId={String(anio)} title={`Notas ${anio}`} />}
              {anio && <AnalysisPanel periodType="year" periodId={String(anio)} />}
            </div>
          </TabsContent>

          <TabsContent value="analisis">{anio && <AnalisisTab anio={anio} />}</TabsContent>

          <TabsContent value="datos">{anio && <DatosTab anio={anio} />}</TabsContent>
        </Tabs>
      )}
    </>
  )
}

function AnalisisTab({ anio }: { anio: number }) {
  const [tipo, setTipo] = useState<TipoMovimiento>('GASTO')
  const { data, isLoading } = useYearAnalysis(anio, tipo)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <span className="text-sm text-txt2">Tipo:</span>
        <Select value={tipo} onValueChange={(v) => setTipo(v as TipoMovimiento)}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ANALYSIS_TIPOS.map((t) => (
              <SelectItem key={t} value={t}>
                {TIPO_LABEL[t]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading || !data ? (
        <Skeleton className="h-72" />
      ) : (
        <>
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-txt">Curiosidades</h2>
            <CuriositiesCards data={data.curiosities} />
          </Card>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-txt">Frecuencia de palabras</h2>
              <WordFreqChart data={data.word_counts} />
            </Card>
            <Card className="overflow-hidden p-0">
              <div className="border-b border-border-subtle px-4 py-3">
                <h2 className="text-sm font-semibold text-txt">Top 10 movimientos</h2>
              </div>
              <TopEntriesTable data={data.top_entries} />
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function DatosTab({ anio }: { anio: number }) {
  const { data, isLoading } = useLedgerByYear(anio)
  if (isLoading || !data) return <Skeleton className="h-72" />
  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-border-subtle px-4 py-3">
        <h2 className="text-sm font-semibold text-txt">Movimientos de {anio}</h2>
      </div>
      <LedgerTable entries={data} locked />
    </Card>
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
