import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { useConfig, useNotionStatus, useSaveConfig, useAiModels } from '@/api/queries'
import { CategoriesEditor } from '@/components/utilidades/CategoriesEditor'
import { ConsequencesEditor } from '@/components/utilidades/ConsequencesEditor'
import { DefaultsEditor } from '@/components/utilidades/DefaultsEditor'
import { DataTab } from '@/components/utilidades/DataTab'
import { NotionReviewDialog } from '@/components/utilidades/NotionReviewDialog'

const CURRENCIES = ['EUR', 'USD', 'GBP', 'CHF', 'JPY', 'MXN']
const LANGS = [
  { code: 'es', label: 'Español' },
  { code: 'en', label: 'English' },
]
const LLM_TASKS = [
  { key: 'model_analysis', label: 'Análisis' },
  { key: 'model_chat', label: 'Chat' },
  { key: 'model_summary', label: 'Resúmenes' },
  { key: 'model_import', label: 'Importación' },
]

type Cfg = Record<string, unknown>

export function Utilidades() {
  const { data, isLoading } = useConfig()
  const save = useSaveConfig()
  const [cfg, setCfg] = useState<Cfg>({})

  useEffect(() => {
    if (data?.config) setCfg(data.config)
  }, [data?.config])

  const llm = (cfg.llm as Cfg) ?? {}
  const retenciones = (cfg.retenciones as Cfg) ?? {}
  const notion = (cfg.notion as Cfg) ?? {}
  const advanced = (cfg.automatic_load as Cfg) ?? {}
  const aiEnabled = llm.enabled !== false
  const { data: models } = useAiModels(aiEnabled)

  function set(key: string, value: unknown) {
    setCfg((c) => ({ ...c, [key]: value }))
  }
  function setNested(section: string, key: string, value: unknown) {
    setCfg((c) => ({ ...c, [section]: { ...((c[section] as Cfg) ?? {}), [key]: value } }))
  }

  function persist() {
    save.mutate(cfg, {
      onSuccess: () => toast.success('Configuración guardada'),
      onError: () => toast.error('Error al guardar'),
    })
  }

  const modelOptions = models ?? []

  return (
    <>
      <PageHeader title="Utilidades" subtitle="Configuración, categorías, defaults y datos" />

      {isLoading ? (
        <Skeleton className="h-72" />
      ) : (
        <Tabs defaultValue="config">
          <TabsList>
            <TabsTrigger value="config">Configuración</TabsTrigger>
            <TabsTrigger value="categorias">Categorías</TabsTrigger>
            <TabsTrigger value="defaults">Defaults</TabsTrigger>
            <TabsTrigger value="consecuencias">Consecuencias</TabsTrigger>
            <TabsTrigger value="datos">Datos</TabsTrigger>
          </TabsList>

          <TabsContent value="config">
            <div className="flex max-w-xl flex-col gap-4">
              <Card className="flex flex-col gap-4 p-6">
                <h3 className="text-sm font-semibold text-txt">General</h3>
                <div className="flex flex-col gap-1.5">
                  <Label>Idioma (requiere i18n)</Label>
                  <Select value={(cfg.language as string) ?? 'es'} onValueChange={(v) => set('language', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {LANGS.map((l) => (
                        <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-txt3">Se guarda la preferencia; la traducción llega en Fase F.</p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Divisa</Label>
                  <Select value={(cfg.currency as string) ?? 'EUR'} onValueChange={(v) => set('currency', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CURRENCIES.map((c) => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>URL del banco</Label>
                  <Input value={(cfg.bank_url as string) ?? ''} onChange={(e) => set('bank_url', e.target.value)} placeholder="https://…" />
                </div>
                <ToggleRow label="Tema oscuro" checked={cfg.dark_mode !== false} onChange={(v) => set('dark_mode', v)} />
                <ToggleRow label="Análisis de relevancia" checked={!!cfg.enable_relevance} onChange={(v) => set('enable_relevance', v)} />
                <ToggleRow label="Retenciones automáticas" checked={!!cfg.enable_retentions} onChange={(v) => set('enable_retentions', v)} />
                <ToggleRow label="Cuenta de consecuencias" checked={!!cfg.enable_consequences} onChange={(v) => set('enable_consequences', v)} />
              </Card>

              <Card className="flex flex-col gap-4 p-6">
                <h3 className="text-sm font-semibold text-txt">Retenciones por defecto</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <Label>% remanente</Label>
                    <Input
                      value={String(retenciones.pct_remanente_default ?? 0)}
                      onChange={(e) => setNested('retenciones', 'pct_remanente_default', Number(e.target.value) || 0)}
                      inputMode="decimal"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label>% salario</Label>
                    <Input
                      value={String(retenciones.pct_salario_default ?? 0)}
                      onChange={(e) => setNested('retenciones', 'pct_salario_default', Number(e.target.value) || 0)}
                      inputMode="decimal"
                    />
                  </div>
                </div>
              </Card>

              <Card className="flex flex-col gap-4 p-6">
                <h3 className="text-sm font-semibold text-txt">Inteligencia artificial (Ollama)</h3>
                <ToggleRow label="IA activada" checked={aiEnabled} onChange={(v) => setNested('llm', 'enabled', v)} />
                {aiEnabled && (
                  <>
                    {modelOptions.length === 0 && (
                      <p className="text-xs text-amber">Ollama no responde o sin modelos instalados.</p>
                    )}
                    {LLM_TASKS.map((task) => (
                      <div key={task.key} className="flex flex-col gap-1.5">
                        <Label>Modelo · {task.label}</Label>
                        <Select
                          value={(llm[task.key] as string) ?? ''}
                          onValueChange={(v) => setNested('llm', task.key, v)}
                        >
                          <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                          <SelectContent>
                            {(modelOptions.length ? modelOptions : [llm[task.key] as string].filter(Boolean)).map((m) => (
                              <SelectItem key={m} value={m}>{m}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    ))}
                  </>
                )}
              </Card>

              <NotionCard
                notion={notion}
                onChange={(k, v) => setNested('notion', k, v)}
              />

              <details className="rounded-[var(--radius-card)] border border-border-subtle">
                <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-txt">Avanzado · deduplicación de carga</summary>
                <div className="grid grid-cols-2 gap-3 p-4 pt-0">
                  <AdvNum label="Tolerancia importe" v={advanced.amount_abs_tolerance} onChange={(x) => setNested('automatic_load', 'amount_abs_tolerance', x)} />
                  <AdvNum label="Ventana días" v={advanced.date_window_days} onChange={(x) => setNested('automatic_load', 'date_window_days', x)} />
                  <AdvNum label="Umbral texto" v={advanced.text_similarity_threshold} onChange={(x) => setNested('automatic_load', 'text_similarity_threshold', x)} />
                  <AdvNum label="Score mínimo" v={advanced.min_score} onChange={(x) => setNested('automatic_load', 'min_score', x)} />
                </div>
              </details>

              <Button onClick={persist} disabled={save.isPending} className="self-start">
                {save.isPending ? 'Guardando…' : 'Guardar configuración'}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="categorias"><CategoriesEditor /></TabsContent>
          <TabsContent value="defaults"><DefaultsEditor /></TabsContent>
          <TabsContent value="consecuencias"><ConsequencesEditor /></TabsContent>
          <TabsContent value="datos"><DataTab /></TabsContent>
        </Tabs>
      )}
    </>
  )
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between text-sm text-txt">
      {label}
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  )
}

function AdvNum({ label, v, onChange }: { label: string; v: unknown; onChange: (n: number) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs">{label}</Label>
      <Input value={String(v ?? 0)} onChange={(e) => onChange(Number(e.target.value) || 0)} inputMode="decimal" className="h-8" />
    </div>
  )
}

function NotionCard({ notion, onChange }: { notion: Cfg; onChange: (k: string, v: unknown) => void }) {
  const { data: status, refetch, isFetching } = useNotionStatus()
  const [testing, setTesting] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)

  async function test() {
    setTesting(true)
    try {
      await refetch()
      toast.success('Estado de Notion actualizado')
    } finally {
      setTesting(false)
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-6">
      <h3 className="text-sm font-semibold text-txt">Notion</h3>
      <ToggleRow label="Sincronización activada" checked={notion.enabled !== false} onChange={(v) => onChange('enabled', v)} />
      <div className="flex flex-col gap-1.5">
        <Label>Token de integración</Label>
        <Input type="password" value={(notion.api_token as string) ?? ''} onChange={(e) => onChange('api_token', e.target.value)} placeholder="ntn_…" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Database ID</Label>
        <Input value={(notion.database_id as string) ?? ''} onChange={(e) => onChange('database_id', e.target.value)} />
      </div>
      <ToggleRow label="Comprobar al arrancar" checked={!!notion.check_on_startup} onChange={(v) => onChange('check_on_startup', v)} />
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={test} disabled={testing || isFetching}>
          {testing || isFetching ? 'Probando…' : 'Probar conexión'}
        </Button>
        <Button variant="subtle" size="sm" onClick={() => setReviewOpen(true)}>
          Revisar entradas
        </Button>
        {status && (
          <span className={`text-xs ${status.ok ? 'text-green' : 'text-txt3'}`}>
            {status.configured ? status.detail : 'No configurado'}
          </span>
        )}
      </div>
      <NotionReviewDialog open={reviewOpen} onOpenChange={setReviewOpen} />
    </Card>
  )
}
