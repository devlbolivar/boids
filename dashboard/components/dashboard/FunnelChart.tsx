"use client"
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts"
import type { FunnelStep } from "@/lib/types"

const STATUS_COLORS: Record<string, string> = {
  new:          "#94a3b8",
  researched:   "#60a5fa",
  emailed:      "#818cf8",
  sent:         "#a78bfa",
  replied:      "#34d399",
  meeting:      "#10b981",
  rejected:     "#f87171",
  needs_review: "#fbbf24",
}

const STATUS_LABELS: Record<string, string> = {
  new:          "Nuevos",
  researched:   "Investigados",
  emailed:      "Draft OK",
  sent:         "Enviados",
  replied:      "Respondieron",
  meeting:      "Reunión",
  rejected:     "Rechazados",
  needs_review: "Revisar",
}

interface Props {
  data:       FunnelStep[]
  isLoading?: boolean
}

export function FunnelChart({ data, isLoading }: Props) {
  if (isLoading) {
    return <div className="h-48 animate-pulse rounded-xl bg-muted" />
  }

  const formatted = data.map(d => ({
    ...d,
    label: STATUS_LABELS[d.status] ?? d.status,
    color: STATUS_COLORS[d.status] ?? "#94a3b8",
  }))

  return (
    <div className="rounded-xl border bg-card p-5">
      <h3 className="mb-4 text-sm font-medium text-muted-foreground">
        Pipeline de leads
      </h3>
      {/* Accessible labels — also make getByText work in tests */}
      <div className="sr-only" aria-hidden="false">
        {formatted.map(d => (
          <span key={d.status}>{d.label}</span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={formatted} layout="vertical" margin={{ left: 16 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="label"
            width={90}
            tick={{ fontSize: 12 }}
          />
          <Tooltip
            formatter={(value: number) => [value, "Leads"]}
            cursor={{ fill: "transparent" }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            {formatted.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
