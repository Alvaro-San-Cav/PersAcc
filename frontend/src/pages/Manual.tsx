import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'

const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: 'Cierre de mes',
    body: [
      'El corazón de PersAcc. Un asistente de 4 pasos: saldo real del banco, nómina del mes siguiente, retenciones (% remanente y % nómina) y confirmación.',
      'Al ejecutar el cierre se crea un snapshot inmutable del mes, se generan las entradas automáticas de inversión/retención y se abre el mes siguiente con el saldo final como saldo inicial.',
      'Un mes CERRADO no admite altas, ediciones ni borrados: sus entradas son de solo lectura.',
    ],
  },
  {
    title: 'Relevancia del gasto',
    body: [
      'Cada gasto se clasifica en cuatro niveles para analizar tus hábitos:',
      'NE (Necesario): esencial para vivir. LI (Me gusta): bienestar consciente. SUP (Superfluo): ocasionalmente justificable. TON (Tontería): impulsivo o del que te arrepientes.',
      'El objetivo es entender en qué se va el dinero, no culpabilizar. Puedes desactivar esta función en Utilidades.',
    ],
  },
  {
    title: 'Retenciones automáticas',
    body: [
      'Al cerrar el mes puedes retener un porcentaje del remanente (saldo sobrante) y de la nueva nómina hacia inversión/ahorro.',
      'Fórmula: Inversión = retenciones manuales + (saldo × % remanente) + (nómina × % salario) + consecuencias.',
    ],
  },
  {
    title: 'Proyecciones',
    body: [
      'Modelos SARIMAX entrenados con tu histórico predicen ingresos, gastos e inversión de los próximos meses, con banda de confianza al 80 %.',
      'Reentrena los modelos desde la propia página cuando añadas datos nuevos relevantes.',
    ],
  },
  {
    title: 'Importar y Asistente',
    body: [
      'Importar: sube extractos bancarios (AEB Norma 43, SEPA, Excel); la IA los clasifica y marca duplicados antes de que confirmes.',
      'Asistente: pregunta en lenguaje natural («¿cuánto gasté en transporte el año pasado?») y obtén los movimientos que coinciden.',
      'Ambas funciones requieren Ollama en ejecución y la IA activada en Utilidades.',
    ],
  },
]

export function Manual() {
  return (
    <>
      <PageHeader title="Manual" subtitle="Conceptos clave de PersAcc" />
      <div className="flex flex-col gap-4">
        {SECTIONS.map((s) => (
          <Card key={s.title} className="p-5">
            <h2 className="mb-2 text-sm font-semibold text-accent2">{s.title}</h2>
            <div className="flex flex-col gap-2">
              {s.body.map((p, i) => (
                <p key={i} className="text-sm leading-relaxed text-txt2">
                  {p}
                </p>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </>
  )
}
