import { format, parseISO } from 'date-fns'

type Num = number | null | undefined

/** Símbolo de divisa activo. Lo fija AppShell al cargar /api/config. */
let CURRENCY_SYMBOL = '€'

export function setCurrencySymbol(sym: string): void {
  if (sym) CURRENCY_SYMBOL = sym
}

export function fmtMoney(v: Num, dec = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  const n = v.toLocaleString('es-ES', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  })
  return `${n} ${CURRENCY_SYMBOL}`
}

export function fmtPct(v: Num, dec = 1): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${v.toLocaleString('es-ES', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  })} %`
}

export function fmtNum(v: Num, dec = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: dec })
}

/** "2026-07-03" → "03/07/2026". */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return format(parseISO(iso.slice(0, 10)), 'dd/MM/yyyy')
  } catch {
    return iso
  }
}

/** "2026-07" → "julio 2026". */
export function fmtMonth(mes: string | null | undefined): string {
  if (!mes) return '—'
  try {
    return format(parseISO(`${mes}-01`), 'LLLL yyyy')
  } catch {
    return mes
  }
}

export function signColor(v: Num): string {
  if (v == null) return 'text-txt2'
  return v >= 0 ? 'text-green' : 'text-red'
}

export const TIPO_LABEL: Record<string, string> = {
  GASTO: 'Gasto',
  INGRESO: 'Ingreso',
  TRASPASO_ENTRADA: 'Traspaso entrada',
  TRASPASO_SALIDA: 'Traspaso salida',
  INVERSION_AHORRO: 'Inversión/Ahorro',
}

export const RELEVANCIA_LABEL: Record<string, string> = {
  NE: 'Necesario',
  LI: 'Me gusta',
  SUP: 'Superfluo',
  TON: 'Tontería',
}

export const RELEVANCIA_COLOR: Record<string, string> = {
  NE: 'var(--ne)',
  LI: 'var(--li)',
  SUP: 'var(--sup)',
  TON: 'var(--ton)',
}
