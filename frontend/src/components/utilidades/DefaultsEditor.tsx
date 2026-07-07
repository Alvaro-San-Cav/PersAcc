import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCategories, useConfig, useSaveConfig } from '@/api/queries'
import { RELEVANCIA_LABEL } from '@/lib/format'
import type { Relevancia } from '@/api/types'

/** Clave de defaults: nombre en minúsculas con espacios → guion bajo (paridad legacy). */
function defaultKey(nombre: string): string {
  return nombre.toLowerCase().replace(/\s+/g, '_')
}

const NO_REL = '__none__'

export function DefaultsEditor() {
  const { data: config, isLoading } = useConfig()
  const { data: cats } = useCategories()
  const save = useSaveConfig()

  const [conceptos, setConceptos] = useState<Record<string, string>>({})
  const [importes, setImportes] = useState<Record<string, string>>({})
  const [relevancias, setRelevancias] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!config?.config) return
    setConceptos((config.config.conceptos_default as Record<string, string>) ?? {})
    const imp = (config.config.importes_default as Record<string, number>) ?? {}
    setImportes(Object.fromEntries(Object.entries(imp).map(([k, v]) => [k, String(v)])))
    setRelevancias((config.config.relevancias_default as Record<string, string>) ?? {})
  }, [config?.config])

  if (isLoading) return <Skeleton className="h-64" />

  const gastoCats = (cats ?? []).filter((c) => c.tipo_movimiento === 'GASTO')

  function persist() {
    const importesNum: Record<string, number> = {}
    for (const [k, v] of Object.entries(importes)) {
      const n = Number(v)
      if (v.trim() !== '' && Number.isFinite(n)) importesNum[k] = n
    }
    const conceptosClean = Object.fromEntries(Object.entries(conceptos).filter(([, v]) => v.trim() !== ''))
    const relClean = Object.fromEntries(Object.entries(relevancias).filter(([, v]) => v))

    save.mutate(
      {
        ...(config?.config ?? {}),
        conceptos_default: conceptosClean,
        importes_default: importesNum,
        relevancias_default: relClean,
      },
      {
        onSuccess: () => toast.success('Defaults guardados'),
        onError: () => toast.error('Error al guardar'),
      },
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-txt">Valores por defecto por categoría (gasto)</h3>
        <Button onClick={persist} disabled={save.isPending} size="sm">
          {save.isPending ? 'Guardando…' : 'Guardar'}
        </Button>
      </div>
      <p className="text-xs text-txt3">
        Al elegir una categoría en «Añadir movimiento», estos valores se precargan automáticamente.
      </p>

      <div className="flex flex-col gap-2">
        <div className="hidden grid-cols-[1fr_1.5fr_100px_140px] gap-2 px-1 text-xs font-medium text-txt2 md:grid">
          <span>Categoría</span>
          <span>Concepto</span>
          <span>Importe</span>
          <span>Relevancia</span>
        </div>
        {gastoCats.map((c) => {
          const key = defaultKey(c.nombre)
          return (
            <div key={c.id} className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1.5fr_100px_140px] md:items-center">
              <span className="truncate text-sm text-txt">{c.nombre}</span>
              <Input
                value={conceptos[key] ?? ''}
                onChange={(e) => setConceptos((s) => ({ ...s, [key]: e.target.value }))}
                placeholder="—"
                className="h-8"
              />
              <Input
                value={importes[key] ?? ''}
                onChange={(e) => setImportes((s) => ({ ...s, [key]: e.target.value }))}
                placeholder="—"
                inputMode="decimal"
                className="h-8"
              />
              <Select
                value={relevancias[key] || NO_REL}
                onValueChange={(v) => setRelevancias((s) => ({ ...s, [key]: v === NO_REL ? '' : v }))}
              >
                <SelectTrigger className="h-8"><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_REL}>Sin default</SelectItem>
                  {(Object.keys(RELEVANCIA_LABEL) as Relevancia[]).map((r) => (
                    <SelectItem key={r} value={r}>{RELEVANCIA_LABEL[r]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
