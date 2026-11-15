import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Trash2 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCategories, useConfig, useSaveConfig } from '@/api/queries'

interface Rule {
  id: string
  active: boolean
  name: string
  filter_relevance: string
  filter_category: string
  filter_concept: string
  action_type: 'percent' | 'fixed'
  action_value: number
}

const RELEVANCIAS = ['', 'NE', 'LI', 'SUP', 'TON']

// uuid v4 sin depender de Math.random en tiempo de módulo: usa crypto del navegador.
function uuid(): string {
  return crypto.randomUUID()
}

export function ConsequencesEditor() {
  const { data: config } = useConfig()
  const { data: cats } = useCategories()
  const save = useSaveConfig()
  const [rules, setRules] = useState<Rule[]>([])

  useEffect(() => {
    if (config?.config) setRules((config.config.consequences_rules as Rule[]) ?? [])
  }, [config?.config])

  const enabled = config?.config?.enable_consequences !== false
  const gastoCats = (cats ?? []).filter((c) => c.tipo_movimiento === 'GASTO')

  function update(i: number, patch: Partial<Rule>) {
    setRules((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }

  function addRule() {
    setRules((rs) => [
      ...rs,
      { id: uuid(), active: true, name: '', filter_relevance: '', filter_category: '', filter_concept: '', action_type: 'fixed', action_value: 0 },
    ])
  }

  function persist() {
    // Merge sobre la config fresca para no pisar otros campos.
    save.mutate(
      { ...(config?.config ?? {}), consequences_rules: rules },
      {
        onSuccess: () => toast.success('Reglas guardadas'),
        onError: () => toast.error('Error al guardar'),
      },
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {!enabled && (
        <Card className="p-3 text-sm text-amber" style={{ borderColor: 'var(--amber)' }}>
          La cuenta de consecuencias está desactivada. Las reglas se guardan pero no se aplican al
          cierre hasta activarla en Configuración.
        </Card>
      )}

      <Card className="flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-txt">Reglas de consecuencias</h3>
          <Button variant="outline" size="sm" onClick={addRule}>
            <Plus className="size-4" /> Añadir regla
          </Button>
        </div>

        {rules.length === 0 && (
          <p className="rounded-[var(--radius-card)] border border-dashed border-border-subtle px-4 py-6 text-center text-sm text-txt2">
            Sin reglas configuradas. Añade una para penalizar ciertos gastos al cierre.
          </p>
        )}

        {rules.map((r, i) => (
          <div
            key={r.id}
            className={`grid grid-cols-1 gap-2 rounded-[var(--radius-card)] border border-border-subtle p-3 md:grid-cols-[auto_1fr_1fr_1fr_1fr_auto_auto] ${r.active ? '' : 'opacity-60'}`}
          >
            <label className="flex items-center gap-2 text-xs text-txt2">
              <Switch checked={r.active} onCheckedChange={(v) => update(i, { active: v })} aria-label="Regla activa" />
            </label>
            <Input value={r.name} onChange={(e) => update(i, { name: e.target.value })} placeholder="Nombre" className="h-8" />
            <Select value={r.filter_relevance || '__any__'} onValueChange={(v) => update(i, { filter_relevance: v === '__any__' ? '' : v })}>
              <SelectTrigger className="h-8"><SelectValue placeholder="Relevancia" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__any__">Cualquiera</SelectItem>
                {RELEVANCIAS.filter(Boolean).map((rel) => (
                  <SelectItem key={rel} value={rel}>{rel}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={r.filter_category || '__any__'} onValueChange={(v) => update(i, { filter_category: v === '__any__' ? '' : v })}>
              <SelectTrigger className="h-8"><SelectValue placeholder="Categoría" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__any__">Cualquiera</SelectItem>
                {gastoCats.map((c) => (
                  <SelectItem key={c.id} value={c.nombre}>{c.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input value={r.filter_concept} onChange={(e) => update(i, { filter_concept: e.target.value })} placeholder="Concepto contiene…" className="h-8" />
            <Select value={r.action_type} onValueChange={(v) => update(i, { action_type: v as 'percent' | 'fixed' })}>
              <SelectTrigger className="h-8 w-24"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="fixed">Fijo €</SelectItem>
                <SelectItem value="percent">% </SelectItem>
              </SelectContent>
            </Select>
            <div className="flex items-center gap-1">
              <Input
                value={String(r.action_value)}
                onChange={(e) => update(i, { action_value: Number(e.target.value) || 0 })}
                inputMode="decimal"
                className="h-8 w-20"
              />
              <Button variant="ghost" size="icon" className="size-8 text-txt3 hover:text-red" onClick={() => setRules((rs) => rs.filter((_, idx) => idx !== i))}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          </div>
        ))}

        <Button onClick={persist} disabled={save.isPending} className="self-start">
          {save.isPending ? 'Guardando…' : 'Guardar reglas'}
        </Button>
      </Card>
    </div>
  )
}
