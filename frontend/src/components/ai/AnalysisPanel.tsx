import { toast } from 'sonner'
import { Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAiStatus, useAnalysisCached, useGenerateAnalysis } from '@/api/queries'
import { ApiError } from '@/api/client'

/**
 * Panel de análisis IA reutilizable para un periodo (mes o año).
 * Muestra el análisis cacheado y permite (re)generarlo si Ollama está activo.
 */
export function AnalysisPanel({
  periodType,
  periodId,
}: {
  periodType: 'month' | 'year'
  periodId: string
}) {
  const { data: status } = useAiStatus()
  const { data: cached } = useAnalysisCached(periodType, periodId)
  const gen = useGenerateAnalysis()

  const available = status?.enabled && status?.ollama_running
  const text = gen.data?.text ?? cached?.text ?? ''

  function run(regenerate: boolean) {
    gen.mutate(
      { period_type: periodType, period_id: periodId, regenerate },
      {
        onError: (err) =>
          toast.error(err instanceof ApiError ? err.message : 'Error al generar análisis'),
      },
    )
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-txt">
          <Sparkles className="size-4 text-accent2" /> Análisis IA
        </h2>
        {available && (
          <Button
            variant="outline"
            size="sm"
            disabled={gen.isPending}
            onClick={() => run(!!text)}
          >
            {gen.isPending ? 'Generando…' : text ? 'Regenerar' : 'Generar'}
          </Button>
        )}
      </div>

      {!available ? (
        <p className="text-sm text-txt3">
          IA desactivada. Actívala en Utilidades y arranca Ollama para obtener análisis.
        </p>
      ) : text ? (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-txt2">{text}</p>
      ) : (
        <p className="text-sm text-txt3">Sin análisis todavía. Pulsa «Generar».</p>
      )}
    </Card>
  )
}
