import { render, screen } from "@testing-library/react"
import { MetricCard }     from "@/components/dashboard/MetricCard"
import { describe, it, expect } from "vitest"

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Reuniones" value={12} />)
    expect(screen.getByText("Reuniones")).toBeInTheDocument()
    expect(screen.getByText("12")).toBeInTheDocument()
  })

  it("shows alert styling when alert=true", () => {
    const { container } = render(
      <MetricCard label="Revisar" value={3} alert />,
    )
    expect(container.firstChild).toHaveClass("border-amber-300")
  })

  it("shows trend up in green", () => {
    render(<MetricCard label="Tasa" value="25%" sub="Subiendo" trend="up" />)
    const sub = screen.getByText("Subiendo")
    expect(sub).toHaveClass("text-emerald-600")
  })
})
