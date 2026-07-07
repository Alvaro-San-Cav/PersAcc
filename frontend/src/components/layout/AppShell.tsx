import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  Lock,
  History,
  TrendingUp,
  Upload,
  Settings,
  MessageSquare,
  BookOpen,
  Moon,
  Sun,
  ExternalLink,
  Menu,
  X,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useConfig, useNotionPendingCount, useSaveConfig } from '@/api/queries'
import { setCurrencySymbol } from '@/lib/format'
import { applyTheme } from '@/lib/theme'
import { useT } from '@/lib/i18n'
import { NotionReviewDialog } from '@/components/utilidades/NotionReviewDialog'

interface NavItem {
  to: string
  key: string
  icon: LucideIcon
}

const NAV: NavItem[] = [
  { to: '/', key: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/cierre', key: 'nav.cierre', icon: Lock },
  { to: '/historico', key: 'nav.historico', icon: History },
  { to: '/proyecciones', key: 'nav.proyecciones', icon: TrendingUp },
  { to: '/asistente', key: 'nav.asistente', icon: MessageSquare },
  { to: '/importar', key: 'nav.importar', icon: Upload },
  { to: '/utilidades', key: 'nav.utilidades', icon: Settings },
  { to: '/manual', key: 'nav.manual', icon: BookOpen },
]

export function AppShell() {
  const t = useT()
  const { data: config } = useConfig()
  const saveConfig = useSaveConfig()
  const [dark, setDark] = useState(true)

  useEffect(() => {
    if (config?.currency_symbol) setCurrencySymbol(config.currency_symbol)
  }, [config?.currency_symbol])

  // Sincronizar tema con la config al cargar.
  useEffect(() => {
    if (!config?.config) return
    const isDark = config.config.dark_mode !== false
    setDark(isDark)
    applyTheme(isDark ? 'dark' : 'light')
  }, [config?.config])

  function toggleTheme() {
    const next = !dark
    setDark(next)
    applyTheme(next ? 'dark' : 'light')
    // Merge sobre la config fresca para no pisar otros campos.
    saveConfig.mutate({ ...(config?.config ?? {}), dark_mode: next })
  }

  const bankUrl = (config?.config?.bank_url as string) || ''

  const notion = (config?.config?.notion as { enabled?: boolean; check_on_startup?: boolean }) ?? {}
  const notionWatch = notion.enabled !== false && !!notion.check_on_startup
  const { data: pending } = useNotionPendingCount(notionWatch)
  const [notionOpen, setNotionOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  // Atajos globales: `/` enfoca la búsqueda de la tabla, `n` el formulario de alta.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable
      if (typing) return
      if (e.key === '/') {
        const s = document.querySelector<HTMLInputElement>('[data-table-search]')
        if (s) {
          e.preventDefault()
          s.focus()
        }
      } else if (e.key === 'n' || e.key === 'N') {
        const q = document.querySelector<HTMLInputElement>('[data-quickadd-importe]')
        if (q) {
          e.preventDefault()
          q.focus()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Backdrop del drawer en móvil */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={cn(
          'flex w-[220px] flex-shrink-0 flex-col border-r border-border-subtle bg-bg2',
          'max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-40 max-md:shadow',
          !mobileOpen && 'max-md:hidden',
        )}
      >
        <div className="flex h-14 items-center gap-2 px-5">
          <img src="/logo.ico" alt="PersAcc" className="size-7 shrink-0 rounded-[var(--radius-card)]" />
          <span className="text-sm font-semibold text-txt">PersAcc</span>
          <button className="ml-auto text-txt3 md:hidden" onClick={() => setMobileOpen(false)}>
            <X className="size-5" />
          </button>
        </div>
        <nav className="flex flex-col gap-0.5 px-3 py-2">
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-[var(--radius-card)] px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-accent/15 text-accent2'
                    : 'text-txt2 hover:bg-card2 hover:text-txt',
                )
              }
            >
              <Icon className="size-4" />
              {t(key)}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-1 px-3 py-3">
          {bankUrl && (
            <a
              href={bankUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 rounded-[var(--radius-card)] px-3 py-2 text-sm font-medium text-txt2 transition-colors hover:bg-card2 hover:text-txt"
            >
              <ExternalLink className="size-4" />
              {t('shell.bank')}
            </a>
          )}
          <button
            onClick={toggleTheme}
            className="flex items-center gap-3 rounded-[var(--radius-card)] px-3 py-2 text-sm font-medium text-txt2 transition-colors hover:bg-card2 hover:text-txt"
          >
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            {dark ? t('shell.theme_light') : t('shell.theme_dark')}
          </button>
          <div className="px-3 pt-2 text-[11px] text-txt3">
            {t('shell.tagline')} · {config?.currency_symbol ?? '€'}
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        {/* Barra superior con burger en móvil */}
        <div className="flex h-12 items-center gap-2 border-b border-border-subtle px-4 md:hidden">
          <button onClick={() => setMobileOpen(true)} className="text-txt2">
            <Menu className="size-5" />
          </button>
          <img src="/logo.ico" alt="PersAcc" className="size-6 rounded-[var(--radius-card)]" />
          <span className="text-sm font-semibold text-txt">PersAcc</span>
        </div>
        <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-6">
          {pending && pending.count > 0 && (
            <button
              onClick={() => setNotionOpen(true)}
              className="mb-4 flex w-full items-center gap-2 rounded-[var(--radius-card)] border border-accent/40 bg-accent/10 px-4 py-2.5 text-left text-sm text-accent2 transition-colors hover:bg-accent/15"
            >
              📥 {pending.count} {pending.count === 1 ? 'entrada pendiente' : 'entradas pendientes'} en Notion — Revisar
            </button>
          )}
          <Outlet />
        </div>
      </main>

      <NotionReviewDialog open={notionOpen} onOpenChange={setNotionOpen} />
    </div>
  )
}
