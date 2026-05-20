"use client"
import { useReviewQueue } from "@/lib/hooks/useReviewQueue"
import { EmailPreview }   from "@/components/review/EmailPreview"

export default function ReviewPage() {
  const { data: queue, isLoading } = useReviewQueue()

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-medium">Cola de revisión</h1>
        {queue && (
          <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-700">
            {queue.length} pendientes
          </span>
        )}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      )}

      {!isLoading && queue?.length === 0 && (
        <div className="rounded-xl border border-dashed p-12 text-center">
          <p className="text-muted-foreground">
            No hay emails pendientes de revisión
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            Los emails con QA score bajo aparecerán aquí
          </p>
        </div>
      )}

      {queue?.map(item => (
        <EmailPreview key={item.lead.id} item={item} />
      ))}
    </div>
  )
}
