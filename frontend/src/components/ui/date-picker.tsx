import { useEffect, useMemo, useRef, useState } from 'react'
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const MONTHS = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

/** 'YYYY-MM-DD' → [y, m (0-based), d]. Vacío → hoy. */
function parse(value: string): [number, number, number] {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (m) return [Number(m[1]), Number(m[2]) - 1, Number(m[3])]
  const now = new Date()
  return [now.getFullYear(), now.getMonth(), now.getDate()]
}

function toValue(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function fmtDisplay(value: string): string {
  const [y, m, d] = parse(value)
  return `${String(d).padStart(2, '0')}/${String(m + 1).padStart(2, '0')}/${y}`
}

/** Lunes = 0. getDay() da domingo=0 → normalizamos. */
function mondayIndex(jsDay: number): number {
  return (jsDay + 6) % 7
}

export function DatePicker({
  value,
  onChange,
  className,
}: {
  value: string
  onChange: (value: string) => void
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const [selY, selM, selD] = parse(value)
  const [viewY, setViewY] = useState(selY)
  const [viewM, setViewM] = useState(selM)

  // Al abrir, situar la vista en el mes del valor seleccionado.
  useEffect(() => {
    if (open) {
      setViewY(selY)
      setViewM(selM)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Cerrar al clicar fuera o pulsar Escape.
  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const today = useMemo(() => {
    const n = new Date()
    return { y: n.getFullYear(), m: n.getMonth(), d: n.getDate() }
  }, [])

  const cells = useMemo(() => {
    const firstDow = mondayIndex(new Date(viewY, viewM, 1).getDay())
    const daysInMonth = new Date(viewY, viewM + 1, 0).getDate()
    const out: (number | null)[] = []
    for (let i = 0; i < firstDow; i++) out.push(null)
    for (let d = 1; d <= daysInMonth; d++) out.push(d)
    return out
  }, [viewY, viewM])

  function prevMonth() {
    setViewM((m) => {
      if (m === 0) {
        setViewY((y) => y - 1)
        return 11
      }
      return m - 1
    })
  }
  function nextMonth() {
    setViewM((m) => {
      if (m === 11) {
        setViewY((y) => y + 1)
        return 0
      }
      return m + 1
    })
  }

  function pick(d: number) {
    onChange(toValue(viewY, viewM, d))
    setOpen(false)
  }

  function pickToday() {
    onChange(toValue(today.y, today.m, today.d))
    setOpen(false)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex h-9 w-full items-center gap-2 rounded-[var(--radius-card)] border border-border-strong bg-bg2 px-3 text-left text-sm text-txt transition-colors hover:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/50',
          className,
        )}
      >
        <CalendarIcon className="size-3.5 shrink-0 text-txt3" />
        <span className="tabular-nums">{fmtDisplay(value)}</span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-[268px] rounded-[var(--radius-card-lg)] border border-border-strong bg-card p-3 shadow-[var(--shadow-md,0_10px_30px_rgba(0,0,0,0.3))]">
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={prevMonth}
              className="flex size-7 items-center justify-center rounded-[var(--radius-card)] text-txt2 transition-colors hover:bg-card2 hover:text-txt"
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="text-sm font-semibold text-txt">
              {MONTHS[viewM]} {viewY}
            </span>
            <button
              type="button"
              onClick={nextMonth}
              className="flex size-7 items-center justify-center rounded-[var(--radius-card)] text-txt2 transition-colors hover:bg-card2 hover:text-txt"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>

          <div className="mb-1 grid grid-cols-7 gap-0.5">
            {WEEKDAYS.map((w) => (
              <span key={w} className="grid h-7 place-items-center text-[10px] font-medium uppercase text-txt3">
                {w}
              </span>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-0.5">
            {cells.map((d, i) => {
              if (d === null) return <span key={`e${i}`} />
              const isSel = d === selD && viewM === selM && viewY === selY
              const isToday = d === today.d && viewM === today.m && viewY === today.y
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => pick(d)}
                  className={cn(
                    'grid h-8 place-items-center rounded-[var(--radius-card)] text-sm tabular-nums transition-colors',
                    isSel
                      ? 'bg-accent font-semibold text-white'
                      : 'text-txt hover:bg-card2',
                    !isSel && isToday && 'font-semibold text-accent ring-1 ring-inset ring-accent/50',
                  )}
                >
                  {d}
                </button>
              )
            })}
          </div>

          <div className="mt-2 flex justify-end border-t border-border-subtle pt-2">
            <button
              type="button"
              onClick={pickToday}
              className="rounded-[var(--radius-card)] px-2.5 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
            >
              Hoy
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
