import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Calculator as CalcIcon, ChevronDown, Euro, Plus } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Combobox } from '@/components/ui/combobox'
import {
  useCategories,
  useCategoryUsageStats,
  useConfig,
  useCreateEntry,
  useDashboard,
  useLedgerByYear,
} from '@/api/queries'
import { parseAmount } from '@/lib/utils'
import { RELEVANCIA_LABEL } from '@/lib/format'
import type { Relevancia, TipoMovimiento } from '@/api/types'
import { ApiError } from '@/api/client'
import { Calculator } from '@/components/dashboard/Calculator'
import { DatePicker } from '@/components/ui/date-picker'

const TIPOS: TipoMovimiento[] = [
  'GASTO',
  'INGRESO',
  'TRASPASO_ENTRADA',
  'TRASPASO_SALIDA',
  'INVERSION_AHORRO',
]

/** Color por tipo (paridad con los tonos de la tabla de movimientos). */
const TIPO_TONE: Record<TipoMovimiento, { active: string; dot: string }> = {
  GASTO: { active: 'border-red bg-red/10 text-red', dot: 'bg-red' },
  INGRESO: { active: 'border-green bg-green/10 text-green', dot: 'bg-green' },
  INVERSION_AHORRO: { active: 'border-purple bg-purple/10 text-purple', dot: 'bg-purple' },
  TRASPASO_ENTRADA: { active: 'border-indigo bg-indigo/10 text-indigo', dot: 'bg-indigo' },
  TRASPASO_SALIDA: { active: 'border-indigo bg-indigo/10 text-indigo', dot: 'bg-indigo' },
}

/** Etiqueta corta para los botones (evita el salto de línea en la rejilla). */
const TIPO_BTN_LABEL: Record<TipoMovimiento, string> = {
  GASTO: 'Gasto',
  INGRESO: 'Ingreso',
  INVERSION_AHORRO: 'Inversión',
  TRASPASO_ENTRADA: 'Traspaso +',
  TRASPASO_SALIDA: 'Traspaso −',
}

/**
 * Fecha por defecto (paridad con legacy/ui/sidebar.py:38-48):
 * hoy si el mes fiscal activo es el mes actual; día 1 del mes en otro caso.
 */
function defaultDate(mesFiscal: string): string {
  const now = new Date()
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  if (mesFiscal === currentMonth) {
    return `${currentMonth}-${String(now.getDate()).padStart(2, '0')}`
  }
  return `${mesFiscal}-01`
}

/** Clave de defaults: nombre en minúsculas con espacios → guion bajo (paridad legacy). */
function defaultKey(nombre: string): string {
  return nombre.toLowerCase().replace(/\s+/g, '_')
}

/**
 * Formulario de alta rápida. Vive en el panel derecho persistente del shell.
 * Si no se pasa `mesFiscal`, se resuelve del dashboard (mes fiscal activo).
 */
export function QuickAddForm({ mesFiscal: mesProp }: { mesFiscal?: string }) {
  const { data: dashboard } = useDashboard(undefined)
  const mesFiscal = mesProp ?? dashboard?.mes_fiscal ?? ''
  const isCerrado = mesProp ? false : !!dashboard?.is_cerrado

  const [tipo, setTipo] = useState<TipoMovimiento>('GASTO')
  const [fecha, setFecha] = useState('')
  const [catId, setCatId] = useState<string>('')
  const [concepto, setConcepto] = useState('')
  const [importe, setImporte] = useState('')
  const [relevancia, setRelevancia] = useState<Relevancia | ''>('')
  const [flagLiquidez, setFlagLiquidez] = useState(false)
  const [calcOpen, setCalcOpen] = useState(false)

  const { data: cats } = useCategories()
  const { data: config } = useConfig()
  const { data: usage } = useCategoryUsageStats(tipo)
  const { data: yearLedger } = useLedgerByYear(mesFiscal ? Number(mesFiscal.slice(0, 4)) : undefined)
  const create = useCreateEntry()

  const enableRelevance = config?.config?.enable_relevance !== false

  // Al cambiar el mes fiscal activo, reajustar la fecha por defecto a ese contexto.
  useEffect(() => {
    if (mesFiscal) setFecha(defaultDate(mesFiscal))
  }, [mesFiscal])

  const conceptosDefault = (config?.config?.conceptos_default as Record<string, string>) ?? {}
  const importesDefault = (config?.config?.importes_default as Record<string, number>) ?? {}
  const relevanciasDefault = (config?.config?.relevancias_default as Record<string, string>) ?? {}

  // Orden inteligente: histórico desc, uso del año actual desc, nombre. Cae a `count`
  // global si aún no hay stats (endpoint /api/categories/usage-stats).
  const catsForTipo = useMemo(() => {
    const list = (cats ?? []).filter((c) => c.tipo_movimiento === tipo)
    if (!usage) return [...list].sort((a, b) => b.count - a.count)
    const stat = (id: number) => usage[String(id)] ?? { history: 0, curr_year: 0 }
    return [...list].sort((a, b) => {
      const sa = stat(a.id)
      const sb = stat(b.id)
      return (
        sb.history - sa.history ||
        sb.curr_year - sa.curr_year ||
        a.nombre.localeCompare(b.nombre)
      )
    })
  }, [cats, tipo, usage])

  // Conceptos recientes de la categoría elegida (autocomplete datalist).
  const conceptSuggestions = useMemo(() => {
    if (!catId || !yearLedger) return []
    const id = Number(catId)
    const seen = new Set<string>()
    for (const e of yearLedger) {
      if (e.categoria_id === id && e.concepto?.trim()) seen.add(e.concepto.trim())
    }
    return [...seen].slice(0, 20)
  }, [catId, yearLedger])

  // Aplicar defaults al elegir categoría, sin pisar lo que el usuario ya escribió:
  // solo se resetea si el campo está vacío o su valor es un default conocido.
  function onCategoryChange(id: string) {
    setCatId(id)
    const cat = (cats ?? []).find((c) => String(c.id) === id)
    if (!cat) return
    const key = defaultKey(cat.nombre)

    const cDef = conceptosDefault[key] ?? ''
    const iDef = importesDefault[key]
    const rDef = relevanciasDefault[key] as Relevancia | undefined

    const knownConceptos = new Set(Object.values(conceptosDefault))
    if (concepto.trim() === '' || knownConceptos.has(concepto)) setConcepto(cDef)

    const knownImportes = new Set(Object.values(importesDefault).map(String))
    if (importe.trim() === '' || knownImportes.has(importe)) {
      setImporte(iDef != null ? String(iDef) : '')
    }

    if (tipo === 'GASTO') {
      const knownRels = new Set(Object.values(relevanciasDefault))
      if (relevancia === '' || knownRels.has(relevancia)) setRelevancia(rDef ?? '')
    }
  }

  // Si la categoría elegida ya no aplica al tipo, resetear; y si solo hay una
  // opción para el tipo, autoseleccionarla (aplicando sus defaults).
  useEffect(() => {
    const ids = catsForTipo.map((c) => String(c.id))
    if (catId && ids.includes(catId)) return
    if (catsForTipo.length === 1) onCategoryChange(ids[0])
    else if (catId) setCatId('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catsForTipo])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const amount = parseAmount(importe)
    if (!catId) return toast.error('Selecciona una categoría')
    if (!concepto.trim()) return toast.error('El concepto es obligatorio')
    if (!Number.isFinite(amount) || amount <= 0) return toast.error('Importe inválido')
    if (tipo === 'GASTO' && enableRelevance && !relevancia)
      return toast.error('Selecciona la relevancia')

    create.mutate(
      {
        fecha_real: fecha,
        tipo_movimiento: tipo,
        categoria_id: Number(catId),
        concepto: concepto.trim(),
        importe: amount,
        relevancia_code: tipo === 'GASTO' && relevancia ? relevancia : null,
        flag_liquidez: tipo === 'INGRESO' ? flagLiquidez : false,
      },
      {
        onSuccess: () => {
          toast.success('Movimiento añadido')
          setConcepto('')
          setImporte('')
          setFlagLiquidez(false)
        },
        onError: (err) =>
          toast.error(err instanceof ApiError ? err.message : 'Error al añadir'),
      },
    )
  }

  if (isCerrado) {
    return (
      <Card className="p-4 text-sm text-txt2">
        <h2 className="mb-1 text-sm font-semibold text-txt">Añadir movimiento</h2>
        Mes cerrado — no se pueden añadir movimientos.
      </Card>
    )
  }

  return (
    <Card className="flex h-full flex-1 flex-col p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex size-7 items-center justify-center rounded-[var(--radius-card)] bg-accent/10 text-accent">
          <Plus className="size-4" />
        </span>
        <h2 className="text-sm font-semibold text-txt">Añadir movimiento</h2>
      </div>
      <form onSubmit={submit} className="flex flex-1 flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label>Tipo</Label>
          <div className="grid grid-cols-2 gap-2">
            {TIPOS.map((t) => {
              const active = tipo === t
              const tone = TIPO_TONE[t]
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTipo(t)}
                  aria-pressed={active}
                  className={cn(
                    'flex h-10 items-center justify-center gap-1.5 whitespace-nowrap rounded-[var(--radius-card)] border px-2.5 text-xs font-medium transition-colors',
                    t === 'INVERSION_AHORRO' && 'col-span-2',
                    active
                      ? tone.active
                      : 'border-border-strong bg-bg2 text-txt2 hover:text-txt',
                  )}
                >
                  <span
                    className={cn(
                      'size-2 shrink-0 rounded-full transition-colors',
                      active ? tone.dot : 'bg-txt3/40',
                    )}
                  />
                  {TIPO_BTN_LABEL[t]}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Categoría</Label>
          <Combobox
            value={catId}
            onValueChange={onCategoryChange}
            options={catsForTipo.map((c) => ({ value: String(c.id), label: c.nombre }))}
            searchPlaceholder="Buscar categoría…"
            emptyText="Sin categorías."
            className="h-11"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Fecha</Label>
          <DatePicker value={fecha} onChange={setFecha} className="h-11" />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Concepto</Label>
          <Input
            value={concepto}
            onChange={(e) => setConcepto(e.target.value)}
            placeholder="Descripción del movimiento"
            list="quickadd-conceptos"
            className="h-11"
          />
          <datalist id="quickadd-conceptos">
            {conceptSuggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <Label>Importe</Label>
            <button
              type="button"
              onClick={() => setCalcOpen((o) => !o)}
              className="flex items-center gap-1 text-[11px] text-txt3 transition-colors hover:text-txt"
            >
              <CalcIcon className="size-3.5" /> Calculadora
              <ChevronDown className={cn('size-3 transition-transform', calcOpen && 'rotate-180')} />
            </button>
          </div>
          <div className="relative">
            <Euro className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-txt3" />
            <Input
              data-quickadd-importe
              value={importe}
              onChange={(e) => setImporte(e.target.value)}
              placeholder="0,00"
              inputMode="decimal"
              className="h-11 pl-8 tabular-nums"
            />
          </div>
          {calcOpen && (
            <div className="mt-1">
              <Calculator
                onUse={(v) => {
                  setImporte(v.toFixed(2))
                  setCalcOpen(false)
                }}
              />
            </div>
          )}
        </div>

        {tipo === 'GASTO' && enableRelevance && (
          <div className="flex flex-col gap-1.5">
            <Label>Relevancia</Label>
            <Select value={relevancia} onValueChange={(v) => setRelevancia(v as Relevancia)}>
              <SelectTrigger className="h-11">
                <SelectValue placeholder="Sin clasificar" />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(RELEVANCIA_LABEL) as Relevancia[]).map((r) => (
                  <SelectItem key={r} value={r}>
                    {RELEVANCIA_LABEL[r]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {tipo === 'INGRESO' && (
          <label className="flex items-center gap-2 text-sm text-txt2">
            <input
              type="checkbox"
              checked={flagLiquidez}
              onChange={(e) => setFlagLiquidez(e.target.checked)}
            />
            ⚡ Liquidez inmediata
          </label>
        )}

        <Button type="submit" disabled={create.isPending} className="mt-auto h-11">
          {create.isPending ? 'Añadiendo…' : 'Añadir'}
        </Button>
      </form>
    </Card>
  )
}
