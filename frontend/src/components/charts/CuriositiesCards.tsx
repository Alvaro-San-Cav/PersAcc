import { Card } from '@/components/ui/card'
import { fmtDate, fmtMoney } from '@/lib/format'
import type { Curiosities } from '@/api/types'

export function CuriositiesCards({ data }: { data: Curiosities }) {
  if (!data.total_registros) {
    return <div className="grid h-24 place-items-center text-sm text-txt2">Sin datos para curiosidades</div>
  }
  const items = [
    { label: 'Día top', value: data.dia_top_fecha ? fmtDate(data.dia_top_fecha) : '—' },
    { label: 'Gastado ese día', value: fmtMoney(data.dia_top_importe) },
    { label: 'Media días activos', value: fmtMoney(data.promedio_dias_activos) },
    { label: 'Días activos', value: String(data.dias_activos) },
    { label: 'Nº movimientos', value: String(data.total_registros) },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {items.map((it) => (
        <Card key={it.label} className="flex flex-col gap-1 p-4">
          <span className="text-[11px] font-medium uppercase tracking-wide text-txt2">{it.label}</span>
          <span className="text-lg font-semibold tabular-nums text-txt">{it.value}</span>
        </Card>
      ))}
    </div>
  )
}
