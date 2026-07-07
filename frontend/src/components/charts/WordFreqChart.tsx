import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { WordCount } from '@/api/types'

export function WordFreqChart({ data }: { data: WordCount[] }) {
  if (!data.length) {
    return <div className="grid h-40 place-items-center text-sm text-txt2">Sin conceptos suficientes</div>
  }
  return (
    <ResponsiveContainer width="100%" height={Math.max(240, data.length * 26)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis type="number" tick={{ fill: 'var(--txt2)', fontSize: 11 }} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="word"
          width={110}
          tick={{ fill: 'var(--txt2)', fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: 'var(--card2)' }}
          contentStyle={{
            background: 'var(--card2)',
            border: '1px solid var(--border2)',
            borderRadius: 8,
            color: 'var(--txt)',
          }}
        />
        <Bar dataKey="count" fill="var(--accent)" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
