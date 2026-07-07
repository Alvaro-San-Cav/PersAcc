import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Check, StickyNote } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useNotes, useSaveNotes } from '@/api/queries'

/**
 * Notas por periodo (mes o año). Textarea colapsable con guardado por botón o
 * Ctrl-Enter. Readonly si el periodo está cerrado (paridad con el histórico legacy).
 */
export function NotesCard({
  periodType,
  periodId,
  readOnly = false,
  title = 'Notas',
}: {
  periodType: 'month' | 'year'
  periodId: string
  readOnly?: boolean
  title?: string
}) {
  const { data: saved } = useNotes(periodType, periodId)
  const save = useSaveNotes(periodType, periodId)
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const dirty = useRef(false)

  useEffect(() => {
    if (saved != null && !dirty.current) {
      setText(saved)
      if (saved.trim()) setOpen(true)
    }
  }, [saved])

  function persist() {
    save.mutate(text, {
      onSuccess: () => {
        dirty.current = false
        toast.success('Notas guardadas')
      },
      onError: () => toast.error('Error al guardar notas'),
    })
  }

  const isSaved = !dirty.current && saved === text

  return (
    <Card className="p-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 text-sm font-semibold text-txt"
      >
        <StickyNote className="size-4 text-accent2" />
        {title}
        {saved?.trim() && !open && <span className="ml-1 text-xs text-txt3">· con contenido</span>}
        <span className="ml-auto text-xs text-txt3">{open ? 'ocultar' : 'mostrar'}</span>
      </button>

      {open && (
        <div className="mt-3 flex flex-col gap-2">
          <textarea
            value={text}
            readOnly={readOnly}
            onChange={(e) => {
              dirty.current = true
              setText(e.target.value)
            }}
            onKeyDown={(e) => {
              if (!readOnly && (e.ctrlKey || e.metaKey) && e.key === 'Enter') persist()
            }}
            rows={4}
            placeholder={readOnly ? 'Sin notas' : 'Escribe una nota para este periodo…'}
            className="w-full resize-y rounded-[var(--radius-card)] border border-border-subtle bg-bg2 px-3 py-2 text-sm text-txt outline-none focus:border-accent disabled:opacity-60"
          />
          {!readOnly && (
            <div className="flex items-center gap-2">
              <Button onClick={persist} disabled={save.isPending || isSaved} size="sm">
                {save.isPending ? 'Guardando…' : 'Guardar'}
              </Button>
              {isSaved && saved?.trim() && (
                <span className="flex items-center gap-1 text-xs text-green">
                  <Check className="size-3" /> Guardado
                </span>
              )}
              <span className="ml-auto text-xs text-txt3">Ctrl+Enter</span>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
