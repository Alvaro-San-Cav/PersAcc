import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, Pencil, StickyNote } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useNotes, useSaveNotes } from '@/api/queries'
import { normalizeNote } from '@/lib/notesMarkdown'

/**
 * Notas por periodo (mes o año). Se guardan como Markdown y se muestran
 * renderizadas; el editor es un textarea con la fuente Markdown. Datos legacy en
 * HTML se convierten a Markdown al cargar. Readonly si el periodo está cerrado.
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
  const savedMd = normalizeNote(saved)
  const save = useSaveNotes(periodType, periodId)
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const dirty = useRef(false)

  useEffect(() => {
    if (saved != null && !dirty.current) {
      const md = normalizeNote(saved)
      setText(md)
      if (md.trim()) setOpen(true)
    }
  }, [saved])

  function persist() {
    save.mutate(text, {
      onSuccess: () => {
        dirty.current = false
        setEditing(false)
        toast.success('Notas guardadas')
      },
      onError: () => toast.error('Error al guardar notas'),
    })
  }

  const isSaved = !dirty.current && savedMd === text
  const showEditor = !readOnly && (editing || !savedMd.trim())

  return (
    <Card className="p-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 text-sm font-semibold text-txt"
      >
        <StickyNote className="size-4 text-accent2" />
        {title}
        {savedMd.trim() && !open && <span className="ml-1 text-xs text-txt3">· con contenido</span>}
        <span className="ml-auto text-xs text-txt3">{open ? 'ocultar' : 'mostrar'}</span>
      </button>

      {open && (
        <div className="mt-3 flex flex-col gap-2">
          {showEditor ? (
            <>
              <textarea
                value={text}
                onChange={(e) => {
                  dirty.current = true
                  setText(e.target.value)
                }}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') persist()
                }}
                rows={4}
                placeholder="Escribe una nota (Markdown) para este periodo…"
                className="w-full resize-y rounded-[var(--radius-card)] border border-border-subtle bg-bg2 px-3 py-2 font-mono text-sm text-txt outline-none focus:border-accent disabled:opacity-60"
              />
              <div className="flex items-center gap-2">
                <Button onClick={persist} disabled={save.isPending || isSaved} size="sm">
                  {save.isPending ? 'Guardando…' : 'Guardar'}
                </Button>
                {savedMd.trim() && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setText(savedMd)
                      dirty.current = false
                      setEditing(false)
                    }}
                  >
                    Cancelar
                  </Button>
                )}
                {isSaved && savedMd.trim() && (
                  <span className="flex items-center gap-1 text-xs text-green">
                    <Check className="size-3" /> Guardado
                  </span>
                )}
                <span className="ml-auto text-xs text-txt3">Ctrl+Enter</span>
              </div>
            </>
          ) : savedMd.trim() ? (
            <>
              <div className="prose-notes text-sm text-txt">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{savedMd}</ReactMarkdown>
              </div>
              {!readOnly && (
                <div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setText(savedMd)
                      setEditing(true)
                    }}
                  >
                    <Pencil className="size-3" /> Editar
                  </Button>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-txt3">Sin notas</p>
          )}
        </div>
      )}
    </Card>
  )
}
