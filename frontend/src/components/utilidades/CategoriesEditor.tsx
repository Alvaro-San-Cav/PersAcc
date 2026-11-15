import { useState } from 'react'
import { toast } from 'sonner'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from '@/api/queries'
import { TIPO_LABEL } from '@/lib/format'
import type { Categoria, TipoMovimiento } from '@/api/types'
import { ApiError } from '@/api/client'

const TIPOS: TipoMovimiento[] = [
  'GASTO',
  'INGRESO',
  'INVERSION_AHORRO',
  'TRASPASO_ENTRADA',
  'TRASPASO_SALIDA',
]

export function CategoriesEditor() {
  const { data: cats, isLoading } = useCategories()
  const create = useCreateCategory()
  const update = useUpdateCategory()
  const del = useDeleteCategory()

  const [editId, setEditId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [toDelete, setToDelete] = useState<Categoria | null>(null)
  const [newName, setNewName] = useState('')
  const [newTipo, setNewTipo] = useState<TipoMovimiento>('GASTO')

  if (isLoading) return <Skeleton className="h-64" />

  function startEdit(c: Categoria) {
    setEditId(c.id)
    setEditName(c.nombre)
  }

  function saveEdit(c: Categoria) {
    if (!editName.trim()) return
    update.mutate(
      { id: c.id, body: { nombre: editName.trim(), tipo_movimiento: c.tipo_movimiento } },
      {
        onSuccess: () => {
          toast.success('Categoría renombrada')
          setEditId(null)
        },
        onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Error al renombrar'),
      },
    )
  }

  function addCategory() {
    if (!newName.trim()) return toast.error('Escribe un nombre')
    create.mutate(
      { nombre: newName.trim(), tipo_movimiento: newTipo },
      {
        onSuccess: () => {
          toast.success('Categoría creada')
          setNewName('')
        },
        onError: (e) => toast.error(e instanceof ApiError ? e.message : 'Error al crear'),
      },
    )
  }

  const groups = TIPOS.map((tipo) => ({
    tipo,
    items: (cats ?? [])
      .filter((c) => c.tipo_movimiento === tipo)
      .sort((a, b) => a.nombre.localeCompare(b.nombre)),
  })).filter((g) => g.items.length > 0)

  const total = (cats ?? []).length

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4">
        <h3 className="text-sm font-semibold text-txt">Nueva categoría</h3>
        <div className="flex flex-wrap items-end gap-2">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Nombre"
            className="w-52"
            onKeyDown={(e) => e.key === 'Enter' && addCategory()}
          />
          <Select value={newTipo} onValueChange={(v) => setNewTipo(v as TipoMovimiento)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIPOS.map((t) => (
                <SelectItem key={t} value={t}>
                  {TIPO_LABEL[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={addCategory} disabled={create.isPending}>
            <Plus className="size-4" /> Añadir
          </Button>
        </div>
      </Card>

      {total === 0 ? (
        <Card className="p-8 text-center text-sm text-txt2">
          Aún no hay categorías. Crea la primera arriba.
        </Card>
      ) : (
        groups.map((g) => (
          <Card key={g.tipo} className="flex flex-col gap-2 p-4">
            <div className="flex items-center justify-between px-1">
              <h4 className="text-sm font-semibold text-txt">{TIPO_LABEL[g.tipo]}</h4>
              <span className="text-xs text-txt3">{g.items.length} categoría(s)</span>
            </div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {g.items.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center gap-2 rounded-[var(--radius-card)] border border-border-subtle px-3 py-2 text-sm"
                >
                  {editId === c.id ? (
                    <>
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="h-7 flex-1"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit(c)
                          if (e.key === 'Escape') setEditId(null)
                        }}
                      />
                      <Button variant="ghost" size="icon" className="size-7 text-green" onClick={() => saveEdit(c)}>
                        <Check className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-7 text-txt3" onClick={() => setEditId(null)}>
                        <X className="size-4" />
                      </Button>
                    </>
                  ) : (
                    <>
                      <span className="flex-1 truncate text-txt">{c.nombre}</span>
                      <Badge variant="outline" className="text-txt3" title="Movimientos usando esta categoría">
                        {c.count}
                      </Badge>
                      <Button variant="ghost" size="icon" className="size-7 text-txt3 hover:text-accent2" onClick={() => startEdit(c)}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-7 text-txt3 hover:text-red" onClick={() => setToDelete(c)}>
                        <Trash2 className="size-4" />
                      </Button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </Card>
        ))
      )}

      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Eliminar categoría"
        description={
          toDelete
            ? toDelete.count > 0
              ? `"${toDelete.nombre}" tiene ${toDelete.count} movimientos. Si no se puede borrar, se desactivará.`
              : `"${toDelete.nombre}" se eliminará.`
            : undefined
        }
        confirmLabel="Eliminar"
        destructive
        loading={del.isPending}
        onConfirm={() => {
          if (!toDelete) return
          del.mutate(toDelete.id, {
            onSuccess: (r) => {
              toast.success(r.detail === 'deactivated' ? 'Categoría desactivada' : 'Categoría eliminada')
              setToDelete(null)
            },
            onError: (e) => {
              toast.error(e instanceof ApiError ? e.message : 'Error al eliminar')
              setToDelete(null)
            },
          })
        }}
      />
    </div>
  )
}
