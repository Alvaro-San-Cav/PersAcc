import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Parsea un importe tecleado, tolerante a formato ES/EU y EN.
 * "7.248,83" → 7248.83 · "7,248.83" → 7248.83 · "1.000" → 1000 · "12,5" → 12.5
 * Regla: si aparecen ambos separadores, el ÚLTIMO es el decimal.
 */
export function parseAmount(raw: string | number | null | undefined): number {
  if (raw == null) return NaN
  if (typeof raw === 'number') return raw
  let s = raw.trim().replace(/[^\d.,-]/g, '')
  if (!s) return NaN

  const lastComma = s.lastIndexOf(',')
  const lastDot = s.lastIndexOf('.')
  let decimalSep: ',' | '.' | '' = ''

  if (lastComma >= 0 && lastDot >= 0) {
    decimalSep = lastComma > lastDot ? ',' : '.'
  } else if (lastComma >= 0) {
    decimalSep = s.indexOf(',') === lastComma ? ',' : ''
  } else if (lastDot >= 0) {
    const after = s.length - lastDot - 1
    const onlyOne = s.indexOf('.') === lastDot
    decimalSep = onlyOne && after > 0 && after <= 2 ? '.' : ''
  }

  if (decimalSep === ',') {
    s = s.replace(/\./g, '').replace(',', '.')
  } else if (decimalSep === '.') {
    s = s.replace(/,/g, '')
    const parts = s.split('.')
    const dec = parts.pop()
    s = parts.join('') + '.' + dec
  } else {
    s = s.replace(/[.,]/g, '')
  }

  return parseFloat(s)
}
