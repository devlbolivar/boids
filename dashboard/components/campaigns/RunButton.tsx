"use client"
import { useState } from "react"
import { api } from "@/lib/api"
import { useQueryClient } from "@tanstack/react-query"

type PipelineStep = "find-leads" | "research" | "copywrite" | "send"

const STEP_LABELS: Record<PipelineStep, string> = {
  "find-leads": "Buscar leads",
  "research":   "Investigar",
  "copywrite":  "Generar emails",
  "send":       "Enviar",
}

interface Props {
  campaignId: string
  step:       PipelineStep
}

export function RunButton({ campaignId, step }: Props) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle")
  const qc = useQueryClient()

  async function run() {
    setState("loading")
    try {
      await api.post(`/campaigns/${campaignId}/run/${step}`)
      setState("done")
      qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      setTimeout(() => setState("idle"), 3000)
    } catch {
      setState("error")
      setTimeout(() => setState("idle"), 3000)
    }
  }

  const label =
    state === "loading" ? "Iniciando..."         :
    state === "done"    ? "✓ En cola"            :
    state === "error"   ? "Error — reintentar"   :
    STEP_LABELS[step]

  return (
    <button
      onClick={run}
      disabled={state === "loading"}
      className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors
        ${state === "done"
          ? "bg-emerald-100 text-emerald-700 border border-emerald-300"
          : state === "error"
          ? "bg-red-100 text-red-700 border border-red-300"
          : state === "loading"
          ? "bg-muted text-muted-foreground border border-border"
          : "bg-primary text-primary-foreground hover:bg-primary/90 border border-transparent"
        }`}
    >
      {label}
    </button>
  )
}
