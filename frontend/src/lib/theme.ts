/**
 * Aplica el tema claro/oscuro fijando `data-theme` en <html>.
 * El dark es el default (sin atributo); el claro se activa con data-theme="light".
 * Los charts y componentes usan CSS vars → cambian solos.
 */
export type Theme = 'dark' | 'light'

export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'light') root.setAttribute('data-theme', 'light')
  else root.removeAttribute('data-theme')
}
