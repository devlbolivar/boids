"use client"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { RunButton } from "@/components/campaigns/RunButton"

interface Campaign {
  id:          string
  name:        string
  status:      string
  leads_count: number
}

export default function CampaignsPage() {
  const { data: campaigns, isLoading } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn:  () => api.get("/campaigns").then(r => r.data),
    refetchInterval: 30_000,
  })

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-medium">Campañas</h1>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      )}

      {campaigns?.length === 0 && (
        <div className="rounded-xl border border-dashed p-12 text-center">
          <p className="text-muted-foreground">Sin campañas aún</p>
        </div>
      )}

      {campaigns?.map(campaign => (
        <div
          key={campaign.id}
          data-testid="campaign-card"
          className="rounded-xl border bg-card p-5 space-y-4"
        >
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-medium">{campaign.name}</h2>
              <p className="text-sm text-muted-foreground">
                {campaign.leads_count} leads · {campaign.status}
              </p>
            </div>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                campaign.status === "running"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {campaign.status}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <RunButton campaignId={campaign.id} step="find-leads" />
            <RunButton campaignId={campaign.id} step="research" />
            <RunButton campaignId={campaign.id} step="copywrite" />
            <RunButton campaignId={campaign.id} step="send" />
          </div>
        </div>
      ))}
    </div>
  )
}
