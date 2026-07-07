import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useCategories,
  useCategoryUsageStats,
  useConfig,
  useCreateEntry,
  useLedgerByYear,
} from '@/api/queries'
import { parseAmount } from '@/lib/utils'
import { RELEVANCIA_LABEL, TIPO_LABEL } from '@/lib/format'
import type { Relevancia, TipoMovimiento } from '@/api/types'
import { ApiError } from '@/api/client'

const TIPOS: TipoMovimiento[] = [
  'GASTO',
  'INGRESO',
  'INVERSION_AHORRO',
  'TRASPASO_ENTRADA',
  'TRASPASO_SALIDA',
]

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

export function QuickAddForm({ mesFiscal }: { mesFiscal: string }) {
  const [tipo, setTipo] = useState<TipoMovimiento>('GASTO')
  const [fecha, setFecha] = useState(() => defaultDate(mesFiscal))
  const [catId, setCatId] = useState<string>('')
  const [concepto, setConcepto] = useState('')
  const [importe, setImporte] = useState('')
  const [relevancia, setRelevancia] = useState<Relevancia | ''>('')
  const [flagLiquidez, setFlagLiquidez] = useState(false)

  const { data: cats } = useCategories()
  const { data: config } = useConfig()
  const { data: usage } = useCategoryUsageStats(tipo)
  const { data: yearLedger } = useLedgerByYear(Number(mesFiscal.slice(0, 4)))
  const create = useCreateEntry()

  // Al cambiar el mes fiscal activo, reajustar la fecha por defecto a ese contexto.
  useEffect(() => {
    setFecha(defaultDate(mesFiscal))
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

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const amount = parseAmount(importe)
    if (!catId) return toast.error('Selecciona una categoría')
    if (!Number.isFinite(amount) || amount <= 0) return toast.error('Importe inválido')

    create.mutate(
      {
        fecha_real: fecha,
        tipo_movimiento: tipo,
        categoria_id: Number(catId),
        concepto: concepto || null,
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

  return (
    <Card className="p-4">
      <h2 className="mb-3 text-sm font-semibold text-txt">Añadir movimiento</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label>Tipo</Label>
          <Select value={tipo} onValueChange={(v) => setTipo(v as TipoMovimiento)}>
            <SelectTrigger>
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
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Categoría</Label>
          <Select value={catId} onValueChange={onCategoryChange}>
            <SelectTrigger>
              <SelectValue placeholder="Selecciona…" />
            </SelectTrigger>
            <SelectContent>
              {catsForTipo.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.nombre}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Fecha</Label>
          <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Concepto</Label>
          <Input
            value={concepto}
            onChange={(e) => setConcepto(e.target.value)}
            placeholder="Opcional"
            list="quickadd-conceptos"
          />
          <datalist id="quickadd-conceptos">
            {conceptSuggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Importe</Label>
          <Input data-quickadd-importe value={importe} onChange={(e) => setImporte(e.target.value)} placeholder="0,00" inputMode="decimal" />
        </div>

        {tipo === 'GASTO' && (
          <div className="flex flex-col gap-1.5">
            <Label>Relevancia</Label>
            <Select value={relevancia} onValueChange={(v) => setRelevancia(v as Relevancia)}>
              <SelectTrigger>
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

        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? 'Añadiendo…' : 'Añadir'}
        </Button>
      </form>
    </Card>
  )
}
