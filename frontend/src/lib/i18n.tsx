import { createContext, useContext, type ReactNode } from 'react'

/**
 * i18n ligero sin dependencias. Diccionarios planos es/en y un hook useT().
 * El idioma se toma de config.language (AppShell lo provee). Ampliar los
 * diccionarios conforme se extraigan más textos de las páginas (Fase F).
 */
export type Lang = 'es' | 'en'

type Dict = Record<string, string>

const ES: Dict = {
  'nav.dashboard': 'Panel',
  'nav.cierre': 'Cierre de mes',
  'nav.historico': 'Histórico',
  'nav.proyecciones': 'Proyecciones',
  'nav.asistente': 'Asistente',
  'nav.importar': 'Importar',
  'nav.utilidades': 'Utilidades',
  'nav.manual': 'Manual',
  'shell.tagline': 'Finanzas personales',
  'shell.bank': 'Banco',
  'shell.theme_light': 'Tema claro',
  'shell.theme_dark': 'Tema oscuro',
}

const EN: Dict = {
  'nav.dashboard': 'Panel',
  'nav.cierre': 'Month close',
  'nav.historico': 'History',
  'nav.proyecciones': 'Projections',
  'nav.asistente': 'Assistant',
  'nav.importar': 'Import',
  'nav.utilidades': 'Settings',
  'nav.manual': 'Manual',
  'shell.tagline': 'Personal finance',
  'shell.bank': 'Bank',
  'shell.theme_light': 'Light theme',
  'shell.theme_dark': 'Dark theme',
}

const DICTS: Record<Lang, Dict> = { es: ES, en: EN }

const I18nContext = createContext<Lang>('es')

export function I18nProvider({ lang, children }: { lang: Lang; children: ReactNode }) {
  return <I18nContext.Provider value={lang}>{children}</I18nContext.Provider>
}

export function useT() {
  const lang = useContext(I18nContext)
  return (key: string): string => DICTS[lang]?.[key] ?? DICTS.es[key] ?? key
}
