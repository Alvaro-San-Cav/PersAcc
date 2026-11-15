import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { useClosingStatus, useClosingPreview, useClosingExecute, useConfig } from '@/api/queries'
import { fmtMoney, fmtMonth, signColor } from '@/lib/format'
import { parseAmount } from '@/lib/utils'
import type {
  ClosingExecuteResponse,
  ClosingPreview,
  ClosingPreviewRequest,
} from '@/api/types'
import { ApiError } from '@/api/client'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Se invoca al completar el cierre con el mes siguiente, para que el panel salte a él. */
  onClosed?: (mesSiguiente: string) => void
}

export function CierreModal({ open, onOpenChange, onClosed }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Cambio de mes</DialogTitle>
          <DialogDescription>Cierra el mes en curso y arranca el siguiente.</DialogDescription>
        </DialogHeader>
        {/* key fuerza remount al reabrir → wizard reinicia en el paso 1. */}
        <CierreWizard key={open ? 'open' : 'closed'} onClosed={onClosed} />
      </DialogContent>
    </Dialog>
  )
}

function CierreWizard({ onClosed }: { onClosed?: (mesSiguiente: string) => void }) {
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
  const [done, setDone] = useState<ClosingExecuteResponse | null>(null)

  // Sembrar valores por defecto del cierre desde config.json (paridad con Streamlit legacy).
  const cfg = config?.config as Record<string, unknown> | undefined
  const enableConsequences = cfg?.enable_consequences === true
  const retentionsOn = cfg?.enable_retentions !== false
  const bankUrl = typeof cfg?.bank_url === 'string' ? (cfg.bank_url as string) : ''
  const seeded = useRef(false)
  useEffect(() => {
    if (!cfg || seeded.current) return
    seeded.current = true
    const ret = (cfg.retenciones as Record<string, unknown>) ?? {}
    const cierre = (cfg.cierre as Record<string, unknown>) ?? {}
    const on = cfg.enable_retentions !== false
    setPctRemanente(on ? String(ret.pct_remanente_default ?? 0) : '0')
    setPctSalario(on ? String(ret.pct_salario_default ?? 20) : '0')
    setSalarioIncluido(cierre.metodo_saldo === 'despues_salario')
  }, [cfg])

  // Prefill del saldo con el esperado (saldo inicial registrado del mes a cerrar).
  const saldoSeeded = useRef(false)
  useEffect(() => {
    if (saldoSeeded.current || !status?.mes_a_cerrar) return
    saldoSeeded.current = true
    if (status.saldo_inicio > 0) setSaldo(String(status.saldo_inicio))
  }, [status])

  if (isLoading) return <Skeleton className="h-64" />

  if (!status?.mes_a_cerrar || status.is_cerrado) {
    return <Card className="p-6 text-sm text-txt2">No hay ningún mes pendiente de cierre.</Card>
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
        setDone(r)
        toast.success(`Mes ${mes} cerrado`)
        // El panel salta al mes siguiente en cuanto se completa el cierre.
        onClosed?.(r.mes_siguiente)
      },
      onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Error al cerrar'),
    })
  }

  if (done) {
    const nomNueva = parseAmount(nomina) || 0
    return (
      <div className="flex flex-col items-center gap-4 py-2 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-dim text-2xl text-green">
          ✓
        </div>
        <div>
          <h2 className="text-lg font-semibold text-txt">
            {fmtMonth(done.mes_cerrado)} cerrado correctamente
          </h2>
          <p className="mt-1 text-sm text-txt2">
            El panel ya muestra {fmtMonth(done.mes_siguiente)}.
          </p>
        </div>
        <div className="grid w-full grid-cols-1 gap-2 text-left sm:grid-cols-2">
          <StatTile label="Retención ejecutada" value={fmtMoney(done.retencion_ejecutada)} />
          <StatTile
            label={`Saldo inicial ${fmtMonth(done.mes_siguiente)}`}
            value={fmtMoney(done.saldo_inicial_nuevo)}
            accent
          />
        </div>
        {nomNueva > 0 && (
          <p className="w-full rounded-[var(--radius-card)] bg-green-dim px-3 py-2 text-left text-xs text-green">
            Nómina de {fmtMoney(nomNueva)} registrada como ingreso de {fmtMonth(done.mes_siguiente)}.
          </p>
        )}
      </div>
    )
  }

  return (
    <div>
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

      {step === 1 && (
        <div className="flex flex-col gap-4">
          <StepIntro
            title={salarioIncluido ? 'Saldo tras cobrar la nómina' : 'Saldo antes de la nómina'}
            desc={
              salarioIncluido
                ? 'Introduce el saldo real de tu cuenta ahora que ya has cobrado la nómina del mes que empieza.'
                : 'Introduce el saldo real de tu cuenta al terminar el mes, antes de cobrar la nómina siguiente.'
            }
          />
          <div className="flex flex-col gap-1.5">
            <Label>Saldo real en el banco</Label>
            <Input
              value={saldo}
              onChange={(e) => setSaldo(e.target.value)}
              placeholder="0,00"
              inputMode="decimal"
            />
            {status.saldo_inicio > 0 && (
              <InfoBanner>
                Saldo esperado según el registro: <b>{fmtMoney(status.saldo_inicio)}</b>
              </InfoBanner>
            )}
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
          <StepIntro
            title="Nómina del mes que empieza"
            desc="Indica el importe neto de la nómina que cobrarás. Se registrará como ingreso del mes siguiente y sirve para calcular la retención sobre salario."
          />
          <div className="flex flex-col gap-1.5">
            <Label>Nómina del mes siguiente</Label>
            <Input
              value={nomina}
              onChange={(e) => setNomina(e.target.value)}
              placeholder="0,00"
              inputMode="decimal"
            />
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
        <div className="flex flex-col gap-5">
          <StepIntro
            title="Retenciones"
            desc={
              retentionsOn
                ? 'Elige qué porcentaje apartas del remanente y de la nómina. Se transferirá a tus cuentas de ahorro/inversión al cerrar.'
                : 'Las retenciones automáticas están desactivadas en la configuración. Puedes continuar sin apartar nada.'
            }
          />
          <RangeSlider
            label="Retención del remanente"
            value={pctRemanente}
            onChange={setPctRemanente}
            help="Sobre el saldo que sobra tras los gastos del mes."
          />
          <RangeSlider
            label="Retención de la nómina"
            value={pctSalario}
            onChange={setPctSalario}
            help="Sobre la nómina nueva del mes que empieza."
          />
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
        <Step4Summary
          prev={prev}
          nomina={parseAmount(nomina) || 0}
          bankUrl={bankUrl}
          executing={execute.isPending}
          onBack={() => setStep(3)}
          onConfirm={confirm}
        />
      )}
    </div>
  )
}

function StepIntro({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-base font-semibold text-txt">{title}</h3>
      <p className="text-sm text-txt2">{desc}</p>
    </div>
  )
}

function InfoBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-[var(--radius-card)] bg-accent/10 px-3 py-2 text-xs text-accent2">
      <span aria-hidden>ℹ️</span>
      <span>{children}</span>
    </div>
  )
}

function RangeSlider({
  label,
  value,
  onChange,
  help,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  help: string
}) {
  const pct = Math.min(100, Math.max(0, parseAmount(value) || 0))
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <Label>{label}</Label>
        <span className="text-sm font-semibold tabular-nums text-accent2">{pct}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={pct}
        onChange={(e) => onChange(e.target.value)}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-card3 accent-[var(--accent)]"
      />
      <p className="text-xs text-txt3">{help}</p>
    </div>
  )
}

function StatTile({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div className="rounded-[var(--radius-card)] border border-border-subtle px-3 py-2">
      <p className="text-xs text-txt3">{label}</p>
      <p className={`text-sm font-semibold tabular-nums ${accent ? 'text-accent2' : 'text-txt'}`}>
        {value}
      </p>
    </div>
  )
}

function Step4Summary({
  prev,
  nomina,
  bankUrl,
  executing,
  onBack,
  onConfirm,
}: {
  prev: ClosingPreview
  nomina: number
  bankUrl: string
  executing: boolean
  onBack: () => void
  onConfirm: () => void
}) {
  // Saldo del que dispondrás el mes que viene, ya con la nómina cobrada.
  const saldoConSalario =
    prev.saldo_fin + nomina - prev.retencion_salario - prev.consequences_total
  // Validación: la desviación (real vs calculado) la aporta el preview.
  const desv = prev.desviacion
  const desvOk = desv == null || Math.abs(desv) <= 10

  return (
    <div className="flex flex-col gap-5 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-txt3">
          Resumen del cierre
        </span>
        <Badge variant="outline">{fmtMonth(prev.mes_fiscal)}</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="Movimientos del mes">
          <Line label="Ingresos" value={fmtMoney(prev.kpis.total_ingresos)} tone="text-green" />
          <Line label="Gastos" value={fmtMoney(prev.kpis.total_gastos)} tone="text-red" last />
        </Section>

        <Section title="Retenciones">
          <Line label="Remanente" value={fmtMoney(prev.retencion_remanente)} muted />
          <Line label="Nómina" value={fmtMoney(prev.retencion_salario)} muted />
          {prev.consequences_total > 0 && (
            <Line
              label="Cuenta de consecuencias"
              value={fmtMoney(prev.consequences_total)}
              muted
            />
          )}
          <Line label="Total apartado" value={fmtMoney(prev.retencion_total)} strong last />
        </Section>
      </div>

      {/* Héroe: lo que tendrás disponible el mes que viene */}
      <div className="overflow-hidden rounded-[var(--radius-card-lg)] border border-accent/30 bg-accent/10">
        <div className="flex items-center justify-between gap-4 px-5 py-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-accent2">Disponible el mes que viene</span>
              {desv != null && (
                <Badge variant={desvOk ? 'green' : 'amber'}>
                  {desvOk ? '✓ Cuadra' : '⚠ Revisar'}
                </Badge>
              )}
            </div>
            <span className="text-xs text-txt3">
              Saldo final ({fmtMoney(prev.saldo_fin)}) con la nómina ya cobrada.
            </span>
          </div>
          <span className="shrink-0 text-3xl font-semibold tabular-nums tracking-tight text-accent2">
            {fmtMoney(saldoConSalario)}
          </span>
        </div>
        {desv != null && (
          <div
            className={`flex items-center justify-between border-t px-5 py-2 text-xs ${
              desvOk ? 'border-accent/20 text-txt3' : 'border-amber/30 bg-amber-dim text-amber'
            }`}
          >
            <span>Desviación real vs. calculado</span>
            <span className={`tabular-nums font-medium ${desvOk ? signColor(desv) : ''}`}>
              {fmtMoney(desv)}
            </span>
          </div>
        )}
      </div>

      <p className="text-xs text-txt3">
        Se abrirá <b className="text-txt2">{fmtMonth(prev.mes_siguiente)}</b> con saldo inicial{' '}
        {fmtMoney(prev.saldo_fin)}.
      </p>

      {bankUrl && (
        <a
          href={bankUrl}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-center gap-1.5 rounded-[var(--radius-card)] border border-border-strong px-4 py-2 text-xs font-medium text-txt2 transition-colors hover:bg-card2"
        >
          Abrir el banco para transferir ↗
        </a>
      )}

      <div className="flex gap-2 pt-1">
        <Button variant="outline" onClick={onBack}>
          Atrás
        </Button>
        <Button className="flex-1" onClick={onConfirm} disabled={executing}>
          {executing ? 'Cerrando…' : 'Confirmar cierre'}
        </Button>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium uppercase tracking-wide text-txt3">{title}</span>
      <div className="rounded-[var(--radius-card)] border border-border-subtle bg-card2/40 px-3 py-1">
        {children}
      </div>
    </div>
  )
}

function Line({
  label,
  value,
  tone,
  strong,
  muted,
  last,
}: {
  label: string
  value: string
  tone?: string
  strong?: boolean
  muted?: boolean
  last?: boolean
}) {
  return (
    <div
      className={`flex items-center justify-between py-2 ${
        last ? '' : 'border-b border-border-subtle'
      }`}
    >
      <span className={strong ? 'font-medium text-txt' : muted ? 'text-txt3' : 'text-txt2'}>
        {label}
      </span>
      <span
        className={`tabular-nums ${tone ?? (strong ? 'font-semibold text-txt' : 'text-txt')}`}
      >
        {value}
      </span>
    </div>
  )
}
