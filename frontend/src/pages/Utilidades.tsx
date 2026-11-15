import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import {
  Bot,
  Building2,
  Database,
  Landmark,
  Percent,
  Scale,
  SlidersHorizontal,
  Smartphone,
  Tags,
  Wand2,
} from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { useConfig, useNotionStatus, useSaveConfig, useAiModels, useLifeDeckStatus, useLifeDeckSync } from '@/api/queries'
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
  { key: 'model_analysis', label: 'Análisis', hint: 'Clasifica relevancia y sugiere categorías.' },
  { key: 'model_chat', label: 'Chat', hint: 'Responde en el Asistente.' },
  { key: 'model_summary', label: 'Resúmenes', hint: 'Redacta los resúmenes mensuales.' },
  { key: 'model_import', label: 'Importación', hint: 'Interpreta movimientos al importar.' },
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
  const lifedeck = (cfg.lifedeck as Cfg) ?? {}
  const advanced = (cfg.automatic_load as Cfg) ?? {}
  const cierre = (cfg.cierre as Cfg) ?? {}
  const aiEnabled = llm.enabled !== false
  const { data: models } = useAiModels(aiEnabled)

  const dirty = useMemo(
    () => !!data?.config && JSON.stringify(cfg) !== JSON.stringify(data.config),
    [cfg, data?.config],
  )

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
  function discard() {
    if (data?.config) setCfg(data.config)
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
            <TabsTrigger value="config" className="gap-1.5">
              <SlidersHorizontal className="size-3.5" /> Configuración
            </TabsTrigger>
            <TabsTrigger value="categorias" className="gap-1.5">
              <Tags className="size-3.5" /> Categorías
            </TabsTrigger>
            <TabsTrigger value="defaults" className="gap-1.5">
              <Wand2 className="size-3.5" /> Defaults
            </TabsTrigger>
            <TabsTrigger value="consecuencias" className="gap-1.5">
              <Scale className="size-3.5" /> Consecuencias
            </TabsTrigger>
            <TabsTrigger value="datos" className="gap-1.5">
              <Database className="size-3.5" /> Datos
            </TabsTrigger>
          </TabsList>

          <TabsContent value="config">
            <div className="mx-auto flex max-w-2xl flex-col gap-4 pb-24">
              <Section
                icon={<Building2 className="size-4" />}
                title="General"
                description="Idioma, divisa y acceso rápido a tu banco."
              >
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Idioma" hint="La traducción llega en Fase F.">
                    <Select value={(cfg.language as string) ?? 'es'} onValueChange={(v) => set('language', v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {LANGS.map((l) => (
                          <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Divisa">
                    <Select value={(cfg.currency as string) ?? 'EUR'} onValueChange={(v) => set('currency', v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map((c) => (
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
                <Field label="URL del banco" hint="Se abre desde el enlace «Banco» de la barra superior.">
                  <Input value={(cfg.bank_url as string) ?? ''} onChange={(e) => set('bank_url', e.target.value)} placeholder="https://…" />
                </Field>
              </Section>

              <Section
                icon={<SlidersHorizontal className="size-4" />}
                title="Funcionalidades"
                description="Activa o desactiva módulos de la aplicación."
              >
                <SettingRow
                  label="Tema oscuro"
                  description="Paleta oscura en toda la interfaz."
                  checked={cfg.dark_mode !== false}
                  onChange={(v) => set('dark_mode', v)}
                />
                <Divider />
                <SettingRow
                  label="Análisis de relevancia"
                  description="La IA clasifica cada gasto (necesario, superfluo…)."
                  checked={!!cfg.enable_relevance}
                  onChange={(v) => set('enable_relevance', v)}
                />
                <Divider />
                <SettingRow
                  label="Retenciones automáticas"
                  description="Aparta un % del remanente y del salario al cierre."
                  checked={!!cfg.enable_retentions}
                  onChange={(v) => set('enable_retentions', v)}
                />
                <Divider />
                <SettingRow
                  label="Cuenta de consecuencias"
                  description="Aplica reglas de penalización configurables al cierre."
                  checked={!!cfg.enable_consequences}
                  onChange={(v) => set('enable_consequences', v)}
                />
              </Section>

              <Section
                icon={<Percent className="size-4" />}
                title="Retenciones por defecto"
                description="Porcentajes que se apartan al cerrar el mes."
              >
                <div className="grid grid-cols-2 gap-3">
                  <Field label="% remanente">
                    <PctInput
                      value={retenciones.pct_remanente_default}
                      onChange={(n) => setNested('retenciones', 'pct_remanente_default', n)}
                    />
                  </Field>
                  <Field label="% salario">
                    <PctInput
                      value={retenciones.pct_salario_default}
                      onChange={(n) => setNested('retenciones', 'pct_salario_default', n)}
                    />
                  </Field>
                </div>
              </Section>

              <Section
                icon={<Scale className="size-4" />}
                title="Cierre mensual"
                description="Cómo se calcula el saldo del mes al cerrar."
              >
                <Field
                  label="Método de saldo"
                  hint="«Antes del salario» mide el gasto neto del mes; «después» incluye ya la nómina."
                >
                  <Select
                    value={(cierre.metodo_saldo as string) ?? 'antes_salario'}
                    onValueChange={(v) => setNested('cierre', 'metodo_saldo', v)}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="antes_salario">Antes del salario</SelectItem>
                      <SelectItem value="despues_salario">Después del salario</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              </Section>

              <AiSection
                enabled={aiEnabled}
                llm={llm}
                models={modelOptions}
                onToggle={(v) => setNested('llm', 'enabled', v)}
                onModel={(k, v) => setNested('llm', k, v)}
              />

              <LifeDeckCard lifedeck={lifedeck} dirty={dirty} onChange={(k, v) => setNested('lifedeck', k, v)} />

              <NotionCard notion={notion} onChange={(k, v) => setNested('notion', k, v)} />

              <details className="rounded-[var(--radius-card-lg)] border border-border-subtle bg-card shadow-[var(--shadow-sm)]">
                <summary className="cursor-pointer select-none px-5 py-4 text-sm font-semibold text-txt">
                  Avanzado · deduplicación de carga
                </summary>
                <div className="flex flex-col gap-4 px-5 pb-5">
                  <p className="text-xs text-txt2">
                    Al importar, se detectan movimientos ya cargados para evitar duplicados.
                  </p>
                  <div className="flex flex-col gap-3">
                    <SettingRow
                      label="Deduplicación activada"
                      description="Busca coincidencias antes de insertar."
                      checked={advanced.dedup_enabled !== false}
                      onChange={(v) => setNested('automatic_load', 'dedup_enabled', v)}
                    />
                    <Divider />
                    <SettingRow
                      label="Solo mismo tipo"
                      description="Compara únicamente movimientos del mismo tipo."
                      checked={advanced.same_type_only !== false}
                      onChange={(v) => setNested('automatic_load', 'same_type_only', v)}
                    />
                    <Divider />
                    <SettingRow
                      label="Ignorar fuera del periodo"
                      description="No compara con movimientos de otros meses."
                      checked={advanced.ignore_outside_current_period !== false}
                      onChange={(v) => setNested('automatic_load', 'ignore_outside_current_period', v)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <AdvNum label="Tolerancia importe" v={advanced.amount_abs_tolerance} onChange={(x) => setNested('automatic_load', 'amount_abs_tolerance', x)} />
                    <AdvNum label="Ventana días" v={advanced.date_window_days} onChange={(x) => setNested('automatic_load', 'date_window_days', x)} />
                    <AdvNum label="Umbral texto" v={advanced.text_similarity_threshold} onChange={(x) => setNested('automatic_load', 'text_similarity_threshold', x)} />
                    <AdvNum label="Score mínimo" v={advanced.min_score} onChange={(x) => setNested('automatic_load', 'min_score', x)} />
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Coincidencias mínimas</Label>
                      <Select
                        value={String(advanced.min_rule_hits ?? 1)}
                        onValueChange={(v) => setNested('automatic_load', 'min_rule_hits', Number(v))}
                      >
                        <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {[1, 2, 3].map((n) => (
                            <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </details>
            </div>

            <SaveBar dirty={dirty} saving={save.isPending} onSave={persist} onDiscard={discard} />
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

/* ---------- primitivos de layout ---------- */

function Section({
  icon,
  title,
  description,
  children,
}: {
  icon: ReactNode
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-card)] bg-card2 text-accent2">
          {icon}
        </span>
        <div className="flex flex-col gap-0.5">
          <h3 className="text-sm font-semibold text-txt">{title}</h3>
          {description && <p className="text-xs text-txt2">{description}</p>}
        </div>
      </div>
      {children}
    </Card>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
      {hint && <p className="text-xs text-txt3">{hint}</p>}
    </div>
  )
}

function Divider() {
  return <div className="h-px bg-border-subtle" />
}

function SettingRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm text-txt">{label}</span>
        {description && <span className="text-xs text-txt2">{description}</span>}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
    </div>
  )
}

function PctInput({ value, onChange }: { value: unknown; onChange: (n: number) => void }) {
  return (
    <div className="relative">
      <Input
        value={String(value ?? 0)}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
        inputMode="decimal"
        className="pr-8"
      />
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-txt3">%</span>
    </div>
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

/* ---------- barra de guardado pegajosa ---------- */

function SaveBar({
  dirty,
  saving,
  onSave,
  onDiscard,
}: {
  dirty: boolean
  saving: boolean
  onSave: () => void
  onDiscard: () => void
}) {
  if (!dirty && !saving) return null
  return (
    <div className="fixed inset-x-0 bottom-4 z-30 flex justify-center px-4">
      <div className="flex w-full max-w-2xl items-center justify-between gap-3 rounded-[var(--radius-card-lg)] border border-border-strong bg-card2 px-4 py-3 shadow-[var(--shadow)]">
        <span className="text-sm text-txt2">Tienes cambios sin guardar.</span>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onDiscard} disabled={saving}>
            Descartar
          </Button>
          <Button size="sm" onClick={onSave} disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar cambios'}
          </Button>
        </div>
      </div>
    </div>
  )
}

/* ---------- IA (Ollama) ---------- */

function AiSection({
  enabled,
  llm,
  models,
  onToggle,
  onModel,
}: {
  enabled: boolean
  llm: Cfg
  models: string[]
  onToggle: (v: boolean) => void
  onModel: (key: string, v: string) => void
}) {
  const online = models.length > 0
  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-card)] bg-card2 text-accent2">
            <Bot className="size-4" />
          </span>
          <div className="flex flex-col gap-0.5">
            <h3 className="text-sm font-semibold text-txt">Inteligencia artificial (Ollama)</h3>
            <p className="text-xs text-txt2">Modelos locales para análisis, chat y resúmenes.</p>
          </div>
        </div>
        <Switch checked={enabled} onCheckedChange={onToggle} aria-label="IA activada" />
      </div>

      {enabled && (
        <>
          <div className="flex items-center gap-2 rounded-[var(--radius-card)] bg-card2 px-3 py-2">
            <span className={`size-2 rounded-full ${online ? 'bg-green' : 'bg-red'}`} />
            <span className="text-xs text-txt2">
              {online ? `Ollama conectado · ${models.length} modelo(s) disponibles` : 'Ollama no responde o sin modelos instalados.'}
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {LLM_TASKS.map((task) => (
              <Field key={task.key} label={`Modelo · ${task.label}`} hint={task.hint}>
                <Select value={(llm[task.key] as string) ?? ''} onValueChange={(v) => onModel(task.key, v)}>
                  <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    {(models.length ? models : [llm[task.key] as string].filter(Boolean)).map((m) => (
                      <SelectItem key={m} value={m}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            ))}
          </div>
        </>
      )}
    </Card>
  )
}

/* ---------- LifeDeck ---------- */

function LifeDeckCard({ lifedeck, dirty, onChange }: { lifedeck: Cfg; dirty: boolean; onChange: (k: string, v: unknown) => void }) {
  const { data: status, refetch, isFetching } = useLifeDeckStatus()
  const sync = useLifeDeckSync()
  const [reviewOpen, setReviewOpen] = useState(false)
  const enabled = !!lifedeck.enabled

  async function test() {
    if (dirty) return toast.error('Guarda los cambios antes de probar la conexión')
    const res = await refetch()
    if (res.data?.ok) toast.success('LifeDeck conectado')
    else toast.error(res.data?.detail ?? 'No se pudo conectar con LifeDeck')
  }

  function upload() {
    if (dirty) return toast.error('Guarda los cambios antes de subir el resumen')
    sync.mutate(undefined, {
      onSuccess: (r) => toast.success(r.detail),
      onError: (e) => toast.error(e instanceof Error ? e.message : 'No se pudo subir el resumen'),
    })
  }

  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-card)] bg-card2 text-accent2">
            <Smartphone className="size-4" />
          </span>
          <div className="flex flex-col gap-0.5">
            <h3 className="text-sm font-semibold text-txt">LifeDeck</h3>
            <p className="text-xs text-txt2">
              Bandeja de apuntes rápidos desde el móvil. Si está activada, sustituye a Notion; PersAcc sube a LifeDeck el resumen del mes y las categorías.
            </p>
          </div>
        </div>
        <Switch checked={enabled} onCheckedChange={(v) => onChange('enabled', v)} aria-label="Bandeja de LifeDeck activada" />
      </div>

      <Field label="URL de LifeDeck">
        <Input value={(lifedeck.url as string) ?? ''} onChange={(e) => onChange('url', e.target.value)} placeholder="https://life-deck-one.vercel.app" />
      </Field>
      <Field label="Token">
        <Input
          type="password"
          value={(lifedeck.token as string) ?? ''}
          onChange={(e) => onChange('token', e.target.value)}
          placeholder="Pégalo desde LifeDeck › Finanzas › Conexión con PersAcc"
          autoComplete="off"
        />
      </Field>
      {enabled && (
        <SettingRow
          label="Comprobar al arrancar"
          description="Consulta apuntes pendientes al abrir la app y abre la revisión."
          checked={lifedeck.check_on_startup !== false}
          onChange={(v) => onChange('check_on_startup', v)}
        />
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={test} disabled={isFetching}>
          {isFetching ? 'Probando…' : 'Probar conexión'}
        </Button>
        <Button variant="outline" size="sm" onClick={upload} disabled={sync.isPending}>
          {sync.isPending ? 'Subiendo…' : 'Subir resumen ahora'}
        </Button>
        {enabled && (
          <Button variant="subtle" size="sm" onClick={() => setReviewOpen(true)}>
            Revisar entradas
          </Button>
        )}
        {status && (
          <span className={`inline-flex items-center gap-1.5 text-xs ${status.ok ? 'text-green' : 'text-txt3'}`}>
            <span className={`size-2 rounded-full ${status.ok ? 'bg-green' : 'bg-txt3'}`} />
            {status.detail}
          </span>
        )}
      </div>
      {enabled && <NotionReviewDialog open={reviewOpen} onOpenChange={setReviewOpen} />}
    </Card>
  )
}

/* ---------- Notion ---------- */

function NotionCard({ notion, onChange }: { notion: Cfg; onChange: (k: string, v: unknown) => void }) {
  const { data: status, refetch, isFetching } = useNotionStatus()
  const [testing, setTesting] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)
  const enabled = notion.enabled !== false

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
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-card)] bg-card2 text-accent2">
            <Landmark className="size-4" />
          </span>
          <div className="flex flex-col gap-0.5">
            <h3 className="text-sm font-semibold text-txt">Notion</h3>
            <p className="text-xs text-txt2">Sincroniza movimientos con una base de datos de Notion.</p>
          </div>
        </div>
        <Switch checked={enabled} onCheckedChange={(v) => onChange('enabled', v)} aria-label="Sincronización activada" />
      </div>

      {enabled && (
        <>
          <Field label="Token de integración">
            <Input type="password" value={(notion.api_token as string) ?? ''} onChange={(e) => onChange('api_token', e.target.value)} placeholder="ntn_…" />
          </Field>
          <Field label="Database ID">
            <Input value={(notion.database_id as string) ?? ''} onChange={(e) => onChange('database_id', e.target.value)} />
          </Field>
          <SettingRow
            label="Comprobar al arrancar"
            description="Consulta entradas pendientes al abrir la app."
            checked={!!notion.check_on_startup}
            onChange={(v) => onChange('check_on_startup', v)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={test} disabled={testing || isFetching}>
              {testing || isFetching ? 'Probando…' : 'Probar conexión'}
            </Button>
            <Button variant="subtle" size="sm" onClick={() => setReviewOpen(true)}>
              Revisar entradas
            </Button>
            {status && (
              <span className={`inline-flex items-center gap-1.5 text-xs ${status.ok ? 'text-green' : 'text-txt3'}`}>
                <span className={`size-2 rounded-full ${status.ok ? 'bg-green' : 'bg-txt3'}`} />
                {status.source && status.source !== 'Notion'
                  ? `La bandeja activa es ${status.source}`
                  : status.configured ? status.detail : 'No configurado'}
              </span>
            )}
          </div>
        </>
      )}
      <NotionReviewDialog open={reviewOpen} onOpenChange={setReviewOpen} />
    </Card>
  )
}
