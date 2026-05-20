import { Suspense } from "react"
import { DashboardOverview } from "@/components/dashboard/DashboardOverview"

export default function DashboardPage() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-medium">Dashboard</h1>
      <Suspense
        fallback={<div className="animate-pulse h-64 rounded-xl bg-muted" />}
      >
        <DashboardOverview />
      </Suspense>
    </div>
  )
}
