import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
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
  Plus,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useConfig, useNotionPendingCount, useSaveConfig } from '@/api/queries'
import { apiPost } from '@/api/client'
import { setCurrencySymbol } from '@/lib/format'
import { applyTheme } from '@/lib/theme'
import { useT } from '@/lib/i18n'
import { NotionReviewDialog } from '@/components/utilidades/NotionReviewDialog'
import { QuickAddForm } from '@/components/dashboard/QuickAddForm'

interface NavItem {
  to: string
  key: string
  icon: LucideIcon
}

const NAV: NavItem[] = [
  { to: '/', key: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/historico', key: 'nav.historico', icon: History },
  { to: '/proyecciones', key: 'nav.proyecciones', icon: TrendingUp },
  { to: '/asistente', key: 'nav.asistente', icon: MessageSquare },
  { to: '/importar', key: 'nav.importar', icon: Upload },
  { to: '/utilidades', key: 'nav.utilidades', icon: Settings },
  { to: '/manual', key: 'nav.manual', icon: BookOpen },
]

export function AppShell() {
  const t = useT()
  const location = useLocation()
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
  const lifedeck = (config?.config?.lifedeck as { enabled?: boolean; check_on_startup?: boolean }) ?? {}
  // Bandeja activa: LifeDeck si está activado; si no, Notion.
  const notionWatch = lifedeck.enabled
    ? lifedeck.check_on_startup !== false
    : notion.enabled !== false && !!notion.check_on_startup
  const { data: pending } = useNotionPendingCount(notionWatch)
  const [notionOpen, setNotionOpen] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  const [quickOpen, setQuickOpen] = useState(false)
  // Panel izquierdo de alta rápida: colapsa fuera del dashboard, se puede reabrir a mano.
  const [asideCollapsed, setAsideCollapsed] = useState(false)

  useEffect(() => {
    setAsideCollapsed(location.pathname !== '/')
  }, [location.pathname])

  // Al entrar en PersAcc (o volver a su pestaña) se sube el resumen del mes a LifeDeck en segundo plano.
  // El backend no repite si ya subió hace menos de 2 min.
  useEffect(() => {
    if (!lifedeck.enabled) return
    const ping = () => {
      if (document.visibilityState === 'visible') apiPost('/api/lifedeck/autosync', {}).catch(() => {})
    }
    ping()
    document.addEventListener('visibilitychange', ping)
    return () => document.removeEventListener('visibilitychange', ping)
  }, [lifedeck.enabled])

  // Al arrancar, si Notion tiene entradas pendientes se abre la revisión sola
  // (una vez por sesión; el banner sigue disponible para reabrirla).
  const notionAutoOpened = useRef(false)
  useEffect(() => {
    if (!notionWatch || notionAutoOpened.current) return
    if (pending && pending.count > 0) {
      notionAutoOpened.current = true
      setNotionOpen(true)
    }
  }, [notionWatch, pending])

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
        setQuickOpen(true)
        // Esperar a que el panel móvil (si aplica) monte antes de enfocar.
        requestAnimationFrame(() => {
          const q = document.querySelector<HTMLInputElement>('[data-quickadd-importe]')
          if (q) q.focus()
        })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ── Navbar superior horizontal ─────────────────────────────── */}
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border-subtle bg-bg2 px-4">
        <div className="flex items-center gap-2">
          <img src="/logo.ico" alt="PersAcc" className="size-7 shrink-0 rounded-[var(--radius-card)]" />
          <span className="text-sm font-semibold text-txt">PersAcc</span>
        </div>

        {/* Burger de navegación en móvil */}
        <button className="ml-1 text-txt2 md:hidden" onClick={() => setNavOpen((o) => !o)}>
          <Menu className="size-5" />
        </button>

        {/* Enlaces horizontales (desktop) */}
        <nav className="ml-2 hidden items-center gap-0.5 md:flex">
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-[var(--radius-card)] px-3 py-1.5 text-sm font-medium transition-colors',
                  isActive ? 'bg-accent/15 text-accent2' : 'text-txt2 hover:bg-card2 hover:text-txt',
                )
              }
            >
              <Icon className="size-4" />
              {t(key)}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1">
          {bankUrl && (
            <a
              href={bankUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-[var(--radius-card)] px-3 py-1.5 text-sm font-medium text-txt2 transition-colors hover:bg-card2 hover:text-txt"
            >
              <ExternalLink className="size-4" />
              <span className="hidden lg:inline">{t('shell.bank')}</span>
            </a>
          )}
          <button
            onClick={toggleTheme}
            className="flex items-center gap-2 rounded-[var(--radius-card)] px-3 py-1.5 text-sm font-medium text-txt2 transition-colors hover:bg-card2 hover:text-txt"
          >
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            <span className="hidden lg:inline">{dark ? t('shell.theme_light') : t('shell.theme_dark')}</span>
          </button>
          {/* Toggle del panel de alta rápida en móvil/tablet */}
          <button
            onClick={() => setQuickOpen((o) => !o)}
            className="flex items-center gap-1 rounded-[var(--radius-card)] bg-accent/15 px-3 py-1.5 text-sm font-medium text-accent2 transition-colors hover:bg-accent/25 lg:hidden"
          >
            <Plus className="size-4" />
            <span className="hidden sm:inline">Añadir</span>
          </button>
        </div>
      </header>

      {/* Nav desplegable en móvil */}
      {navOpen && (
        <nav className="flex flex-col gap-0.5 border-b border-border-subtle bg-bg2 px-3 py-2 md:hidden">
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-[var(--radius-card)] px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-accent/15 text-accent2' : 'text-txt2 hover:bg-card2 hover:text-txt',
                )
              }
            >
              <Icon className="size-4" />
              {t(key)}
            </NavLink>
          ))}
        </nav>
      )}

      {/* ── Cuerpo: panel izquierdo de alta rápida + contenido ─────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Panel izquierdo persistente (desktop ancho). Colapsa fuera del dashboard. */}
        <aside
          className={cn(
            'hidden flex-shrink-0 overflow-hidden border-r border-border-subtle bg-bg2 transition-[width] duration-200 lg:flex lg:flex-col',
            asideCollapsed ? 'w-12 opacity-60 hover:opacity-100' : 'w-[340px]',
          )}
        >
          {asideCollapsed ? (
            <button
              onClick={() => setAsideCollapsed(false)}
              title="Añadir movimiento"
              className="flex flex-1 flex-col items-center gap-2 py-6 text-txt2 transition-colors hover:text-accent2"
            >
              <PanelLeftOpen className="size-5" />
              <span className="[writing-mode:vertical-rl] text-xs font-medium">Añadir</span>
            </button>
          ) : (
            <div className="flex flex-1 flex-col overflow-y-auto px-4 py-6">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-txt">Alta rápida</span>
                <button
                  onClick={() => setAsideCollapsed(true)}
                  title="Colapsar panel"
                  className="rounded-[var(--radius-card)] p-1.5 text-txt3 transition-colors hover:bg-card2 hover:text-txt"
                >
                  <PanelLeftClose className="size-4" />
                </button>
              </div>
              <QuickAddForm />
            </div>
          )}
        </aside>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-6">
            {location.pathname === '/' && pending && pending.count > 0 && (
              <button
                onClick={() => setNotionOpen(true)}
                className="mb-4 flex w-full items-center gap-2 rounded-[var(--radius-card)] border border-accent/40 bg-accent/10 px-4 py-2.5 text-left text-sm text-accent2 transition-colors hover:bg-accent/15"
              >
                📥 {pending.count} {pending.count === 1 ? 'entrada pendiente' : 'entradas pendientes'} en {pending.source ?? 'la bandeja'} — Revisar
              </button>
            )}
            <Outlet />
          </div>
        </main>
      </div>

      {/* Panel derecho como slide-over en móvil/tablet */}
      {quickOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setQuickOpen(false)} />
          <div className="absolute inset-y-0 right-0 w-[340px] max-w-[90vw] overflow-y-auto border-l border-border-subtle bg-bg2 px-4 py-4 shadow-xl">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-txt">Alta rápida</span>
              <button className="text-txt3" onClick={() => setQuickOpen(false)}>
                <X className="size-5" />
              </button>
            </div>
            <QuickAddForm />
          </div>
        </div>
      )}

      <NotionReviewDialog open={notionOpen} onOpenChange={setNotionOpen} />
    </div>
  )
}
