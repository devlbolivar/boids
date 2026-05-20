import type { CostBreakdown } from "@/lib/types"

interface Props {
  data: CostBreakdown
}

export function CostCard({ data }: Props) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-muted-foreground">
          Costo API — {data.period}
        </h3>
        <span className="text-sm font-medium">
          ${data.total_usd.toFixed(4)} USD
        </span>
      </div>
      {data.breakdown.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin uso este mes</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground border-b">
              <th className="text-left pb-2">Agente</th>
              <th className="text-right pb-2">Ejecuciones</th>
              <th className="text-right pb-2">Costo</th>
            </tr>
          </thead>
          <tbody>
            {data.breakdown.map(row => (
              <tr key={row.agent_type} className="border-b last:border-0">
                <td className="py-2 capitalize">{row.agent_type}</td>
                <td className="py-2 text-right text-muted-foreground">{row.runs}</td>
                <td className="py-2 text-right">${row.cost_usd.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
