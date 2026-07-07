import { Toaster as SonnerToaster } from 'sonner'

export function Toaster() {
  return (
    <SonnerToaster
      theme="dark"
      position="bottom-right"
      toastOptions={{
        style: {
          background: 'var(--card2)',
          border: '1px solid var(--border2)',
          color: 'var(--txt)',
        },
      }}
    />
  )
}
