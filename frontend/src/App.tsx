import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Toaster } from '@/components/ui/sonner'
import { useConfig } from '@/api/queries'
import { I18nProvider, type Lang } from '@/lib/i18n'
import { Dashboard } from '@/pages/Dashboard'
import { Historico } from '@/pages/Historico'
import { HistoricoMes } from '@/pages/HistoricoMes'
import { Utilidades } from '@/pages/Utilidades'
import { Proyecciones } from '@/pages/Proyecciones'
import { Importar } from '@/pages/Importar'
import { Chat } from '@/pages/Chat'
import { Manual } from '@/pages/Manual'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'historico', element: <Historico /> },
      { path: 'historico/:anio/:mes', element: <HistoricoMes /> },
      { path: 'proyecciones', element: <Proyecciones /> },
      { path: 'asistente', element: <Chat /> },
      { path: 'importar', element: <Importar /> },
      { path: 'utilidades', element: <Utilidades /> },
      { path: 'manual', element: <Manual /> },
    ],
  },
])

function I18nGate({ children }: { children: ReactNode }) {
  const { data: config } = useConfig()
  const lang = ((config?.config?.language as string) === 'en' ? 'en' : 'es') as Lang
  return <I18nProvider lang={lang}>{children}</I18nProvider>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nGate>
        <RouterProvider router={router} />
      </I18nGate>
      <Toaster />
    </QueryClientProvider>
  )
}
