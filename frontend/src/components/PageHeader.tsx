import { useEffect, type ReactNode } from 'react'

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  // Title de la pestaña por página: "PersAcc — <sección>".
  useEffect(() => {
    document.title = `PersAcc — ${title}`
    return () => {
      document.title = 'PersAcc'
    }
  }, [title])

  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div className="flex items-baseline gap-2">
        <h1 className="text-lg font-semibold text-txt">{title}</h1>
        {subtitle && <p className="text-sm text-txt2">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
