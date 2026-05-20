interface MetricCardProps {
  label:   string
  value:   string | number
  sub?:    string
  trend?:  "up" | "down" | "neutral"
  alert?:  boolean
}

export function MetricCard({ label, value, sub, trend, alert }: MetricCardProps) {
  return (
    <div
      className={`rounded-xl border p-5 ${
        alert ? "border-amber-300 bg-amber-50" : "border-border bg-card"
      }`}
    >
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-3xl font-medium tracking-tight">{value}</p>
      {sub && (
        <p
          className={`mt-1 text-xs ${
            trend === "up"
              ? "text-emerald-600"
              : trend === "down"
              ? "text-red-500"
              : "text-muted-foreground"
          }`}
        >
          {sub}
        </p>
      )}
    </div>
  )
}
