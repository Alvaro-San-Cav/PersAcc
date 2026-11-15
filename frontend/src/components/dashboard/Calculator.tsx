import { useCallback, useEffect, useReducer, type ReactNode } from 'react'
import { ArrowDownToLine, Delete } from 'lucide-react'
import { cn } from '@/lib/utils'

type Op = 'add' | 'sub' | 'mul' | 'div'

const OP_SYMBOL: Record<Op, string> = { add: '+', sub: '−', mul: '×', div: '÷' }

const MAX_DIGITS = 12

/** Representación interna: string con '.' como separador decimal ('Error' si NaN/∞). */
function toRaw(n: number): string {
  if (!Number.isFinite(n)) return 'Error'
  const r = Math.round((n + Number.EPSILON) * 1e10) / 1e10
  if (!Number.isFinite(r) || Math.abs(r) >= 1e15) return 'Error'
  return String(r)
}

function toNum(raw: string): number {
  const n = Number.parseFloat(raw)
  return Number.isFinite(n) ? n : 0
}

/** Formato es-ES para el visor: miles con '.', decimales con ','. */
function formatDisplay(raw: string): string {
  if (raw === 'Error') return 'Error'
  const neg = raw.startsWith('-')
  const body = neg ? raw.slice(1) : raw
  const [int, dec] = body.split('.')
  // es-ES no agrupa números de 4 dígitos (1210, no 1.210).
  const intFmt = int.length > 4 ? int.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : int
  const sep = body.includes('.') ? ',' : ''
  return `${neg ? '-' : ''}${intFmt}${sep}${dec ?? ''}`
}

function compute(prev: number, cur: number, op: Op): number {
  switch (op) {
    case 'add':
      return prev + cur
    case 'sub':
      return prev - cur
    case 'mul':
      return prev * cur
    case 'div':
      return cur === 0 ? NaN : prev / cur
  }
}

type State = { raw: string; acc: number | null; op: Op | null; fresh: boolean }

type Action =
  | { t: 'digit'; d: string }
  | { t: 'dot' }
  | { t: 'op'; op: Op }
  | { t: 'eq' }
  | { t: 'clear' }
  | { t: 'back' }
  | { t: 'neg' }
  | { t: 'pct' }

const INITIAL: State = { raw: '0', acc: null, op: null, fresh: true }

/**
 * Toda la máquina de estados vive en el reducer: cada tecla ve el estado real,
 * también cuando llegan varias pulsaciones antes de un re-render.
 */
function reduce(s: State, a: Action): State {
  const error = s.raw === 'Error'
  const value = toNum(s.raw)

  switch (a.t) {
    case 'clear':
      return INITIAL

    case 'digit': {
      if (error || s.fresh) return { ...s, raw: a.d, fresh: false }
      const digits = s.raw.replace(/[-.]/g, '').length
      if (digits >= MAX_DIGITS) return s
      const raw = s.raw === '0' ? a.d : s.raw === '-0' ? `-${a.d}` : s.raw + a.d
      return { ...s, raw, fresh: false }
    }

    case 'dot':
      if (error || s.fresh) return { ...s, raw: '0.', fresh: false }
      return s.raw.includes('.') ? s : { ...s, raw: `${s.raw}.`, fresh: false }

    case 'back':
      if (error) return INITIAL
      if (s.fresh) return { ...s, raw: '0' }
      return { ...s, raw: ((r) => (r === '' || r === '-' ? '0' : r))(s.raw.slice(0, -1)) }

    case 'neg':
      if (error || s.raw === '0') return s
      return { ...s, raw: s.raw.startsWith('-') ? s.raw.slice(1) : `-${s.raw}` }

    /** % relativo al acumulado en +/− (1000 + 21% = 1210), absoluto en ×/÷. */
    case 'pct': {
      if (error) return s
      const base =
        s.acc !== null && (s.op === 'add' || s.op === 'sub') ? (s.acc * value) / 100 : value / 100
      return { ...s, raw: toRaw(base), fresh: false }
    }

    case 'op': {
      if (error) return s
      if (s.acc !== null && s.op && !s.fresh) {
        const result = compute(s.acc, value, s.op)
        const raw = toRaw(result)
        return { raw, acc: raw === 'Error' ? null : result, op: raw === 'Error' ? null : a.op, fresh: true }
      }
      return { ...s, acc: value, op: a.op, fresh: true }
    }

    case 'eq': {
      if (error || s.acc === null || !s.op) return s
      return { raw: toRaw(compute(s.acc, value, s.op)), acc: null, op: null, fresh: true }
    }
  }
}

const EUR = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/**
 * Calculadora rápida del alta de movimientos (evoluciona legacy/ui/sidebar.py:248-478).
 * Entrada por string (decimales exactos, sin aritmética de dígitos en float),
 * teclado físico, %, signo, borrado y encadenado de operaciones.
 */
export function Calculator({ onUse }: { onUse: (value: number) => void }) {
  const [{ raw, acc, op, fresh }, dispatch] = useReducer(reduce, INITIAL)

  const error = raw === 'Error'
  const value = toNum(raw)
  const amount = Math.round(Math.abs(value) * 100) / 100

  const clearAll = useCallback(() => dispatch({ t: 'clear' }), [])
  const appendDigit = useCallback((d: string) => dispatch({ t: 'digit', d }), [])
  const appendDot = useCallback(() => dispatch({ t: 'dot' }), [])
  const backspace = useCallback(() => dispatch({ t: 'back' }), [])
  const negate = useCallback(() => dispatch({ t: 'neg' }), [])
  const percent = useCallback(() => dispatch({ t: 'pct' }), [])
  const applyOperation = useCallback((next: Op) => dispatch({ t: 'op', op: next }), [])
  const equals = useCallback(() => dispatch({ t: 'eq' }), [])

  const sendToForm = useCallback(() => {
    if (error) return
    onUse(amount)
  }, [amount, error, onUse])

  // Teclado físico: sólo cuando el foco no está en un campo de texto.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null
      if (el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))) return
      const k = e.key
      let handled = true
      if (k >= '0' && k <= '9') appendDigit(k)
      else if (k === '.' || k === ',') appendDot()
      else if (k === '+') applyOperation('add')
      else if (k === '-') applyOperation('sub')
      else if (k === '*' || k === 'x' || k === 'X') applyOperation('mul')
      else if (k === '/' || k === ':') applyOperation('div')
      else if (k === '%') percent()
      else if (k === 'Enter' || k === '=') {
        if (e.ctrlKey || e.metaKey || e.shiftKey) sendToForm()
        else equals()
      } else if (k === 'Backspace') backspace()
      else if (k === 'Escape' || k === 'Delete') clearAll()
      else handled = false
      if (handled) e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [appendDigit, appendDot, applyOperation, backspace, clearAll, equals, percent, sendToForm])

  const shown = formatDisplay(raw)
  const pending = op && acc !== null ? `${formatDisplay(toRaw(acc))} ${OP_SYMBOL[op]}` : ''

  const keyBase =
    'inline-flex h-11 select-none items-center justify-center rounded-[var(--radius-card)] text-base font-semibold tabular-nums transition-all duration-75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 active:scale-[0.96] disabled:pointer-events-none disabled:opacity-40'
  const digitKey = 'bg-card2 text-txt hover:bg-card3'
  const utilKey = 'bg-card2/60 text-txt2 hover:bg-card3 hover:text-txt text-sm'
  const opKey = 'bg-card2 text-accent hover:bg-card3'
  const opActive = 'bg-accent text-white hover:bg-accent2'
  const eqKey = 'bg-accent text-white hover:bg-accent2 text-lg'

  type Key = { label: ReactNode; cls: string; onClick: () => void; aria: string }
  const digit = (d: string): Key => ({ label: d, cls: digitKey, onClick: () => appendDigit(d), aria: d })
  const operator = (o: Op): Key => ({
    label: OP_SYMBOL[o],
    cls: cn(opKey, op === o && fresh && opActive),
    onClick: () => applyOperation(o),
    aria: OP_SYMBOL[o],
  })

  const KEYS: Key[] = [
    { label: 'AC', cls: utilKey, onClick: clearAll, aria: 'Borrar todo' },
    { label: <Delete className="size-4" />, cls: utilKey, onClick: backspace, aria: 'Borrar dígito' },
    { label: '%', cls: utilKey, onClick: percent, aria: 'Porcentaje' },
    operator('div'),
    digit('7'),
    digit('8'),
    digit('9'),
    operator('mul'),
    digit('4'),
    digit('5'),
    digit('6'),
    operator('sub'),
    digit('1'),
    digit('2'),
    digit('3'),
    operator('add'),
    { label: '±', cls: utilKey, onClick: negate, aria: 'Cambiar signo' },
    digit('0'),
    { label: ',', cls: digitKey, onClick: appendDot, aria: 'Decimal' },
    { label: '=', cls: eqKey, onClick: equals, aria: 'Igual' },
  ]

  return (
    <div className="flex flex-col gap-2 rounded-[var(--radius-card-lg)] border border-border-subtle bg-card p-2.5 shadow-[var(--shadow-sm)]">
      <div className="rounded-[var(--radius-card)] bg-bg2 px-3 py-2 text-right">
        <div className="min-h-[15px] font-mono text-[11px] tabular-nums text-txt3">{pending || ' '}</div>
        <div
          className={cn(
            'truncate font-mono font-semibold tabular-nums',
            error ? 'text-red' : 'text-txt',
            shown.length > 14 ? 'text-xl' : shown.length > 10 ? 'text-2xl' : 'text-3xl',
          )}
          title={shown}
        >
          {shown}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-1.5">
        {KEYS.map((k, i) => (
          <button key={i} type="button" aria-label={k.aria} className={cn(keyBase, k.cls)} onClick={k.onClick}>
            {k.label}
          </button>
        ))}
      </div>

      <button
        type="button"
        disabled={error}
        onClick={sendToForm}
        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-[var(--radius-card)] border border-accent/40 bg-accent/10 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:pointer-events-none disabled:opacity-40"
      >
        <ArrowDownToLine className="size-4" />
        Usar {error ? 'importe' : EUR.format(amount)}
      </button>

      <p className="text-center text-[10px] leading-tight text-txt3">
        Teclado: dígitos · + − × ÷ · Enter = · Esc borra · Ctrl+Enter usa importe
      </p>
    </div>
  )
}
