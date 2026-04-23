import '@testing-library/jest-dom'
import { afterEach, afterAll, beforeAll, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// jsdom doesn't implement matchMedia
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })
}

// ResizeObserver not implemented in jsdom — needed by recharts/lightweight-charts
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

// IntersectionObserver stub
if (!window.IntersectionObserver) {
  window.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() { return [] }
  }
}

// Canvas getContext stub — lightweight-charts pokes at it during init
if (typeof HTMLCanvasElement !== 'undefined' && !HTMLCanvasElement.prototype.getContext.__stubbed) {
  const original = HTMLCanvasElement.prototype.getContext
  HTMLCanvasElement.prototype.getContext = function (...args) {
    try {
      return original.apply(this, args)
    } catch {
      return null
    }
  }
  HTMLCanvasElement.prototype.getContext.__stubbed = true
}

// Silence noisy console.error during tests unless debugging
const origError = console.error
beforeAll(() => {
  console.error = (...args) => {
    const msg = args[0]
    if (typeof msg === 'string' && (
      msg.includes('Not implemented: HTMLCanvasElement') ||
      msg.includes('not wrapped in act')
    )) return
    origError(...args)
  }
})
afterAll(() => {
  console.error = origError
})
