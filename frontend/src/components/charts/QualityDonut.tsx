import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { fmtMoney, RELEVANCIA_COLOR, RELEVANCIA_LABEL } from '@/lib/format'
import type { Relevancia } from '@/api/types'

export function QualityDonut({ data }: { data: Record<Relevancia, number> }) {
  const rows = (Object.keys(RELEVANCIA_LABEL) as Relevancia[])
    .map((code) => ({ code, label: RELEVANCIA_LABEL[code], value: data[code] ?? 0 }))
    .filter((r) => r.value > 0)

  const total = rows.reduce((s, r) => s + r.value, 0)

  if (total === 0) {
    return (
      <div className="grid h-[220px] place-items-center text-sm text-txt2">
        Sin gastos clasificados este mes
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <ResponsiveContainer width={180} height={180}>
        <PieChart>
          <Pie data={rows} dataKey="value" nameKey="label" innerRadius={52} outerRadius={80} paddingAngle={2}>
            {rows.map((r) => (
              <Cell key={r.code} fill={RELEVANCIA_COLOR[r.code]} stroke="var(--card)" />
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
        {rows.map((r) => (
          <li key={r.code} className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ background: RELEVANCIA_COLOR[r.code] }} />
            <span className="text-txt2">{r.label}</span>
            <span className="ml-auto tabular-nums text-txt">{fmtMoney(r.value)}</span>
            <span className="w-12 text-right tabular-nums text-txt3">
              {((r.value / total) * 100).toFixed(0)}%
            </span>
          </li>
        ))}
        <li className="mt-1 flex items-center gap-2 border-t border-border-subtle pt-1.5 font-semibold">
          <span className="size-2.5" />
          <span className="text-txt2">Total</span>
          <span className="ml-auto tabular-nums text-txt">{fmtMoney(total)}</span>
          <span className="w-12" />
        </li>
      </ul>
    </div>
  )
}
