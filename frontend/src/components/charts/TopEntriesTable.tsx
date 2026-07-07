import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { fmtDate, fmtMoney } from '@/lib/format'
import type { TopEntry } from '@/api/types'

export function TopEntriesTable({ data }: { data: TopEntry[] }) {
  if (!data.length) {
    return <div className="grid h-24 place-items-center text-sm text-txt2">Sin movimientos</div>
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10 text-txt3">#</TableHead>
          <TableHead>Fecha</TableHead>
          <TableHead>Categoría</TableHead>
          <TableHead>Concepto</TableHead>
          <TableHead className="text-right">Importe</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((e, i) => (
          <TableRow key={i}>
            <TableCell className="tabular-nums text-txt3">{i + 1}</TableCell>
            <TableCell className="whitespace-nowrap text-txt2">{fmtDate(e.fecha)}</TableCell>
            <TableCell className="text-txt">{e.categoria || '—'}</TableCell>
            <TableCell className="max-w-[280px] truncate text-txt2">{e.concepto || '—'}</TableCell>
            <TableCell className="text-right tabular-nums text-txt">{fmtMoney(e.importe)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
