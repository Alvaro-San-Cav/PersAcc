import TurndownService from 'turndown'

/**
 * Las notas se guardan como Markdown. Datos legacy (Streamlit Quill) llegan como
 * HTML (`<p>…</p>`, `<strong>`, `<ul><li>`…); se convierten a Markdown al cargar
 * para que el editor muestre fuente limpia y el guardado quede normalizado.
 */

let turndown: TurndownService | null = null
function service() {
  if (!turndown) {
    turndown = new TurndownService({
      headingStyle: 'atx',
      bulletListMarker: '-',
      codeBlockStyle: 'fenced',
      emDelimiter: '_',
    })
  }
  return turndown
}

// Heurística: contiene una etiqueta HTML de bloque/inline propia de Quill.
const HTML_RE = /<\/?(p|br|strong|em|b|i|u|ul|ol|li|h[1-6]|a|blockquote|pre|code|span|div)\b[^>]*>/i

export function normalizeNote(raw: string | null | undefined): string {
  if (!raw) return ''
  if (!HTML_RE.test(raw)) return raw // ya es Markdown/texto plano
  return service().turndown(raw).trim()
}
