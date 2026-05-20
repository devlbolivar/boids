"use client"
import { useState } from "react"
import { useApproveReview, useRejectReview } from "@/lib/hooks/useReviewQueue"
import type { ReviewItem } from "@/lib/types"

interface Props {
  item: ReviewItem
}

export function EmailPreview({ item }: Props) {
  const [expanded, setExpanded] = useState(false)
  const approve = useApproveReview()
  const reject  = useRejectReview()
  const loading = approve.isPending || reject.isPending

  const score = item.email_draft?.quality_score
  const scoreColor =
    score == null   ? "text-muted-foreground" :
    score >= 0.7    ? "text-emerald-600"       :
    score >= 0.5    ? "text-amber-600"         : "text-red-500"

  const issues = item.email_draft?.qa_details?.issues as string[] | undefined

  return (
    <div className="rounded-xl border bg-card p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">{item.lead.full_name || item.lead.email}</p>
          <p className="text-sm text-muted-foreground">
            {item.lead.title} · {item.lead.company}
          </p>
        </div>
        {score != null && (
          <span className={`text-sm font-medium ${scoreColor}`}>
            QA {Math.round(score * 100)}%
          </span>
        )}
      </div>

      {item.email_draft ? (
        <div className="rounded-lg bg-muted/50 p-4 space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Subject
          </p>
          <p className="text-sm font-medium">{item.email_draft.subject}</p>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mt-2">
            Body
          </p>
          <p className="text-sm whitespace-pre-wrap text-muted-foreground">
            {expanded
              ? item.email_draft.body
              : item.email_draft.body.slice(0, 180) + "..."}
          </p>
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-xs text-primary hover:underline"
          >
            {expanded ? "Ver menos" : "Ver completo"}
          </button>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground italic">
          Sin email draft — el agente no generó uno.
        </p>
      )}

      {issues && issues.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-medium text-amber-700 mb-1">
            Por qué el QA lo marcó para revisión:
          </p>
          <ul className="space-y-1">
            {issues.map((issue, i) => (
              <li key={i} className="text-xs text-amber-800">· {issue}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => approve.mutate(item.lead.id)}
          disabled={loading}
          className="flex-1 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium
                     text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
        >
          {approve.isPending ? "Aprobando..." : "Aprobar y enviar"}
        </button>
        <button
          onClick={() => reject.mutate(item.lead.id)}
          disabled={loading}
          className="flex-1 rounded-lg border border-border px-4 py-2 text-sm font-medium
                     text-muted-foreground hover:bg-muted disabled:opacity-50 transition-colors"
        >
          Rechazar
        </button>
      </div>
    </div>
  )
}
