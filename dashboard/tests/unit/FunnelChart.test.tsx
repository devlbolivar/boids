import { render, screen } from "@testing-library/react"
import { FunnelChart }    from "@/components/dashboard/FunnelChart"
import { describe, it, expect } from "vitest"

describe("FunnelChart", () => {
  it("renders loading skeleton when isLoading=true", () => {
    const { container } = render(<FunnelChart data={[]} isLoading />)
    expect(container.firstChild).toHaveClass("animate-pulse")
  })

  it("renders labels for each status", () => {
    const data = [
      { status: "new" as const, count: 50 },
      { status: "sent" as const, count: 20 },
      { status: "meeting" as const, count: 5 },
    ]
    render(<FunnelChart data={data} />)
    // Use getAllByText because the label appears in both the sr-only div and the chart axis
    expect(screen.getAllByText("Nuevos").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Enviados").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Reunión").length).toBeGreaterThan(0)
  })

  it("renders pipeline title", () => {
    render(<FunnelChart data={[]} />)
    expect(screen.getByText("Pipeline de leads")).toBeInTheDocument()
  })
})
