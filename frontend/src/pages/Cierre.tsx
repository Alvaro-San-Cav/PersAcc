import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { useClosingStatus, useClosingPreview, useClosingExecute, useConfig } from '@/api/queries'
import { fmtMoney, fmtMonth, signColor } from '@/lib/format'
import { parseAmount } from '@/lib/utils'
import type { ClosingPreview, ClosingPreviewRequest } from '@/api/types'
import { ApiError } from '@/api/client'

export function Cierre() {
  const navigate = useNavigate()
  const { data: status, isLoading } = useClosingStatus()
  const { data: config } = useConfig()
  const preview = useClosingPreview()
  const execute = useClosingExecute()

  const [step, setStep] = useState(1)
  const [saldo, setSaldo] = useState('')
  const [nomina, setNomina] = useState('')
  const [pctRemanente, setPctRemanente] = useState('0')
  const [pctSalario, setPctSalario] = useState('20')
  const [salarioIncluido, setSalarioIncluido] = useState(false)
  const [prev, setPrev] = useState<ClosingPreview | null>(null)
  const [done, setDone] = useState<string | null>(null)

  // Sembrar valores por defecto del cierre desde config.json (paridad con Streamlit legacy).
  const cfg = config?.config as Record<string, unknown> | undefined
  const enableConsequences = cfg?.enable_consequences === true
  const seeded = useRef(false)
  useEffect(() => {
    if (!cfg || seeded.current) return
    seeded.current = true
    const ret = (cfg.retenciones as Record<string, unknown>) ?? {}
    const cierre = (cfg.cierre as Record<string, unknown>) ?? {}
    const retentionsOn = cfg.enable_retentions !== false
    setPctRemanente(retentionsOn ? String(ret.pct_remanente_default ?? 0) : '0')
    setPctSalario(retentionsOn ? String(ret.pct_salario_default ?? 20) : '0')
    setSalarioIncluido(cierre.metodo_saldo === 'despues_salario')
  }, [cfg])

  if (isLoading) return <Skeleton className="h-64" />

  if (!status?.mes_a_cerrar || status.is_cerrado) {
    return (
      <>
        <PageHeader title="Cierre de mes" />
        <Card className="p-6 text-sm text-txt2">No hay ningún mes pendiente de cierre.</Card>
      </>
    )
  }

  const mes = status.mes_a_cerrar

  function buildReq(): ClosingPreviewRequest {
    return {
      mes_fiscal: mes,
      saldo_banco_real: parseAmount(saldo) || 0,
      nomina_nueva: parseAmount(nomina) || 0,
      pct_retencion_remanente: (parseAmount(pctRemanente) || 0) / 100,
      pct_retencion_salario: (parseAmount(pctSalario) || 0) / 100,
      salario_ya_incluido: salarioIncluido,
      aplicar_consecuencias: enableConsequences,
    }
  }

  function goPreview() {
    preview.mutate(buildReq(), {
      onSuccess: (p) => {
        setPrev(p)
        setStep(4)
      },
      onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Error en preview'),
    })
  }

  function confirm() {
    execute.mutate(buildReq(), {
      onSuccess: (r) => {
        setDone(r.mes_siguiente)
        toast.success(`Mes ${mes} cerrado`)
      },
      onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Error al cerrar'),
    })
  }

  if (done) {
    return (
      <>
        <PageHeader title="Cierre de mes" />
        <Card className="flex flex-col items-start gap-3 p-6">
          <p className="text-sm text-green">✓ Mes {fmtMonth(mes)} cerrado correctamente.</p>
          <p className="text-sm text-txt2">Mes activo ahora: {fmtMonth(done)}</p>
          <Button onClick={() => navigate('/')}>Ir al dashboard</Button>
        </Card>
      </>
    )
  }

  return (
    <>
      <PageHeader title="Cierre de mes" subtitle={`Cerrando ${fmtMonth(mes)}`} />

      <div className="mb-5 flex gap-2">
        {['Saldo real', 'Nómina', 'Retenciones', 'Confirmación'].map((label, i) => (
          <div
            key={label}
            className={`flex-1 rounded-[var(--radius-card)] border px-3 py-2 text-center text-xs ${
              step === i + 1
                ? 'border-accent text-accent2'
                : step > i + 1
                  ? 'border-green/40 text-green'
                  : 'border-border-subtle text-txt3'
            }`}
          >
            {i + 1}. {label}
          </div>
        ))}
      </div>

      <Card className="max-w-lg p-6">
        {step === 1 && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Saldo real en el banco</Label>
              <Input value={saldo} onChange={(e) => setSaldo(e.target.value)} placeholder="0,00" inputMode="decimal" />
              <p className="text-xs text-txt3">Saldo inicial registrado: {fmtMoney(status.saldo_inicio)}</p>
            </div>
            <label className="flex items-center gap-2 text-sm text-txt2">
              <input
                type="checkbox"
                checked={salarioIncluido}
                onChange={(e) => setSalarioIncluido(e.target.checked)}
              />
              El saldo ya incluye la nómina nueva
            </label>
            <Button onClick={() => setStep(2)} disabled={!saldo}>
              Siguiente
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Nómina del mes siguiente</Label>
              <Input value={nomina} onChange={(e) => setNomina(e.target.value)} placeholder="0,00" inputMode="decimal" />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(1)}>
                Atrás
              </Button>
              <Button onClick={() => setStep(3)}>Siguiente</Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>% retención del remanente</Label>
              <Input value={pctRemanente} onChange={(e) => setPctRemanente(e.target.value)} inputMode="decimal" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>% retención de la nómina</Label>
              <Input value={pctSalario} onChange={(e) => setPctSalario(e.target.value)} inputMode="decimal" />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(2)}>
                Atrás
              </Button>
              <Button onClick={goPreview} disabled={preview.isPending}>
                {preview.isPending ? 'Calculando…' : 'Revisar'}
              </Button>
            </div>
          </div>
        )}

        {step === 4 && prev && (
          <div className="flex flex-col gap-3 text-sm">
            <Row label="Ingresos del mes" value={fmtMoney(prev.kpis.total_ingresos)} />
            <Row label="Gastos del mes" value={fmtMoney(prev.kpis.total_gastos)} />
            <Row label="Retención remanente" value={fmtMoney(prev.retencion_remanente)} />
            <Row label="Retención nómina" value={fmtMoney(prev.retencion_salario)} />
            {prev.consequences_total > 0 && (
              <Row label="Cuenta de consecuencias" value={fmtMoney(prev.consequences_total)} />
            )}
            <Row label="Retención total" value={fmtMoney(prev.retencion_total)} strong />
            <Row label="Saldo final" value={fmtMoney(prev.saldo_fin)} strong />
            {prev.desviacion != null && (
              <Row
                label="Desviación"
                value={fmtMoney(prev.desviacion)}
                tone={signColor(prev.desviacion)}
              />
            )}
            <p className="text-xs text-txt3">
              Se abrirá {fmtMonth(prev.mes_siguiente)} con saldo inicial {fmtMoney(prev.saldo_fin)}.
            </p>
            <div className="flex gap-2 pt-1">
              <Button variant="outline" onClick={() => setStep(3)}>
                Atrás
              </Button>
              <Button onClick={confirm} disabled={execute.isPending}>
                {execute.isPending ? 'Cerrando…' : 'Confirmar cierre'}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </>
  )
}

function Row({
  label,
  value,
  strong,
  tone,
}: {
  label: string
  value: string
  strong?: boolean
  tone?: string
}) {
  return (
    <div className="flex items-center justify-between border-b border-border-subtle pb-2">
      <span className="text-txt2">{label}</span>
      <span className={`tabular-nums ${tone ?? (strong ? 'font-semibold text-txt' : 'text-txt')}`}>
        {value}
      </span>
    </div>
  )
}
