import "@testing-library/jest-dom"
import { vi } from "vitest"

// Recharts needs ResizeObserver
class ResizeObserverMock {
  private callback: ResizeObserverCallback
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }
  observe(el: Element) {
    this.callback(
      [{ contentRect: { width: 500, height: 300 } } as ResizeObserverEntry],
      this as unknown as ResizeObserver,
    )
  }
  unobserve = vi.fn()
  disconnect = vi.fn()
}

global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

// Stable getBoundingClientRect for Recharts layout calculations
Element.prototype.getBoundingClientRect = vi.fn(() => ({
  width: 500,
  height: 300,
  top: 0,
  left: 0,
  bottom: 300,
  right: 500,
  x: 0,
  y: 0,
  toJSON: vi.fn(),
}))
