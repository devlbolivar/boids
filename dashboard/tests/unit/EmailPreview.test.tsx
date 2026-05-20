import { render, screen, fireEvent } from "@testing-library/react"
import { EmailPreview }              from "@/components/review/EmailPreview"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { vi, describe, it, expect }  from "vitest"

const mockItem = {
  lead: {
    id:           "lead-1",
    email:        "cto@startup.cl",
    full_name:    "Carlos Vega",
    company:      "Startup Chile",
    title:        "CTO",
    research_ctx: {},
  },
  email_draft: {
    id:            "email-1",
    subject:       "Vi que levantaron $2M",
    body:          "Hola Carlos, vi el funding reciente...".repeat(5),
    quality_score: 0.62,
    qa_details:    { issues: ["Primera línea poco específica"] },
  },
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("EmailPreview", () => {
  it("renders lead name and company", () => {
    render(<EmailPreview item={mockItem} />, { wrapper })
    expect(screen.getByText("Carlos Vega")).toBeInTheDocument()
    expect(screen.getByText(/Startup Chile/)).toBeInTheDocument()
  })

  it("shows QA score", () => {
    render(<EmailPreview item={mockItem} />, { wrapper })
    expect(screen.getByText("QA 62%")).toBeInTheDocument()
  })

  it("shows QA issues", () => {
    render(<EmailPreview item={mockItem} />, { wrapper })
    expect(screen.getByText(/Primera línea poco específica/)).toBeInTheDocument()
  })

  it("expands body on click", () => {
    render(<EmailPreview item={mockItem} />, { wrapper })
    fireEvent.click(screen.getByText("Ver completo"))
    expect(screen.getByText("Ver menos")).toBeInTheDocument()
  })

  it("renders approve and reject buttons", () => {
    render(<EmailPreview item={mockItem} />, { wrapper })
    expect(screen.getByText("Aprobar y enviar")).toBeInTheDocument()
    expect(screen.getByText("Rechazar")).toBeInTheDocument()
  })
})
