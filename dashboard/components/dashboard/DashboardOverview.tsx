"use client"
import { MetricCard }   from "./MetricCard"
import { FunnelChart }  from "./FunnelChart"
import { MeetingsCard } from "./MeetingsCard"
import { CostCard }     from "./CostCard"
import {
  useDashboardSummary,
  useFunnel,
  useUpcomingMeetings,
  useCostSummary,
} from "@/lib/hooks/useDashboard"

export function DashboardOverview() {
  const { data: summary, isLoading: loadingSummary } = useDashboardSummary()
  const { data: funnel,  isLoading: loadingFunnel }  = useFunnel()
  const { data: meetings }                            = useUpcomingMeetings()
  const { data: cost }                                = useCostSummary()

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Reuniones este mes"
          value={summary?.meetings.this_month ?? "—"}
        />
        <MetricCard
          label="Tasa de apertura"
          value={summary ? `${Math.round(summary.emails.open_rate * 100)}%` : "—"}
          sub={`${summary?.emails.opened ?? 0} de ${summary?.emails.sent ?? 0} enviados`}
          trend={summary && summary.emails.open_rate > 0.25 ? "up" : "neutral"}
        />
        <MetricCard
          label="Tasa de respuesta"
          value={summary ? `${Math.round(summary.emails.reply_rate * 100)}%` : "—"}
          sub={`${summary?.emails.replied ?? 0} replies`}
          trend={summary && summary.emails.reply_rate > 0.05 ? "up" : "neutral"}
        />
        <MetricCard
          label="En revisión manual"
          value={summary?.leads.needs_review ?? "—"}
          sub="Requieren atención"
          alert={(summary?.leads.needs_review ?? 0) > 0}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <FunnelChart data={funnel ?? []} isLoading={loadingFunnel} />
        </div>
        <MeetingsCard meetings={meetings ?? []} />
      </div>

      {cost && <CostCard data={cost} />}
    </div>
  )
}
