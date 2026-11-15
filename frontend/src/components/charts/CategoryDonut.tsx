import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { fmtMoney } from '@/lib/format'
import type { CategoriaImporte } from '@/api/types'

// Paleta cualitativa (marca + acentos) para categorías arbitrarias.
const PALETTE = [
  'var(--accent)',
  'var(--li)',
  'var(--sup)',
  'var(--green)',
  'var(--ne)',
  'var(--amber)',
  'var(--accent2)',
  '#a78bfa',
  '#22d3ee',
  '#f472b6',
  '#94a3b8',
]

export function CategoryDonut({
  data,
  height = 200,
  emptyLabel = 'Sin gastos este periodo',
}: {
  data: CategoriaImporte[]
  height?: number
  emptyLabel?: string
}) {
  const rows = data.filter((r) => r.importe > 0)
  const total = rows.reduce((s, r) => s + r.importe, 0)

  if (total === 0) {
    return (
      <div className="grid place-items-center text-sm text-txt2" style={{ height }}>
        {emptyLabel}
      </div>
    )
  }

  // Agrupar la cola larga en "Otras" para no saturar el donut.
  const MAX = 9
  const shown = rows.slice(0, MAX)
  const rest = rows.slice(MAX)
  if (rest.length) {
    shown.push({ categoria: `Otras (${rest.length})`, importe: rest.reduce((s, r) => s + r.importe, 0) })
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <ResponsiveContainer width={180} height={height}>
        <PieChart>
          <Pie data={shown} dataKey="importe" nameKey="categoria" innerRadius={52} outerRadius={80} paddingAngle={2}>
            {shown.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} stroke="var(--card)" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: 'var(--card2)',
              border: '1px solid var(--border2)',
              borderRadius: 8,
              color: 'var(--txt)',
            }}
            formatter={(v) => fmtMoney(Number(v))}
          />
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex w-full flex-col gap-1.5 text-sm">
        {shown.map((r, i) => (
          <li key={r.categoria} className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />
            <span className="truncate text-txt2">{r.categoria}</span>
            <span className="ml-auto tabular-nums text-txt">{fmtMoney(r.importe)}</span>
            <span className="w-12 text-right tabular-nums text-txt3">
              {((r.importe / total) * 100).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
