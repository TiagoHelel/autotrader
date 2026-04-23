import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// --- Fake WebSocket ---
class FakeWebSocket {
  static OPEN = 1
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = 0 // CONNECTING
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null
    FakeWebSocket.instances.push(this)
  }

  close() {
    this.readyState = 3
    if (this.onclose) this.onclose()
  }

  // Helper: simulate server opening the connection
  _open() {
    this.readyState = FakeWebSocket.OPEN
    if (this.onopen) this.onopen()
  }

  // Helper: simulate server sending a message
  _send(data) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) })
  }

  // Helper: simulate error
  _error() {
    if (this.onerror) this.onerror(new Event('error'))
  }
}

// Patch global
const originalWS = globalThis.WebSocket
beforeEach(() => {
  FakeWebSocket.instances = []
  globalThis.WebSocket = FakeWebSocket
  vi.useFakeTimers()
})
afterEach(() => {
  globalThis.WebSocket = originalWS
  vi.useRealTimers()
})

// Mock WS_URL
vi.mock('../services/api', () => ({
  WS_URL: 'ws://localhost:8000/ws',
}))

import useWebSocket from '../hooks/useWebSocket'

describe('useWebSocket', () => {
  it('connects on mount', () => {
    renderHook(() => useWebSocket())
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(FakeWebSocket.instances[0].url).toBe('ws://localhost:8000/ws')
  })

  it('sets connected=true on open', () => {
    const { result } = renderHook(() => useWebSocket())
    expect(result.current.connected).toBe(false)
    act(() => FakeWebSocket.instances[0]._open())
    expect(result.current.connected).toBe(true)
  })

  it('handles tick message', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0]._open())
    act(() => {
      FakeWebSocket.instances[0]._send({
        type: 'tick',
        data: { symbol: 'EURUSD', bid: 1.1, ask: 1.1002 },
      })
    })
    expect(result.current.ticks.EURUSD).toEqual({ symbol: 'EURUSD', bid: 1.1, ask: 1.1002 })
  })

  it('handles log message with 200-item rolling buffer', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0]._open())
    // Send 210 log messages
    for (let i = 0; i < 210; i++) {
      act(() => {
        FakeWebSocket.instances[0]._send({ type: 'log', data: { msg: `log-${i}` } })
      })
    }
    expect(result.current.logs).toHaveLength(200)
    // Oldest should be log-10, newest log-209
    expect(result.current.logs[0].msg).toBe('log-10')
    expect(result.current.logs[199].msg).toBe('log-209')
  })

  it('handles kpi message', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0]._open())
    act(() => {
      FakeWebSocket.instances[0]._send({ type: 'kpi', data: { balance: 10000, equity: 10500 } })
    })
    expect(result.current.kpis).toEqual({ balance: 10000, equity: 10500 })
  })

  it('handles prediction message with 50-item rolling buffer', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0]._open())
    for (let i = 0; i < 60; i++) {
      act(() => {
        FakeWebSocket.instances[0]._send({ type: 'prediction', data: { id: i } })
      })
    }
    expect(result.current.predictions).toHaveLength(50)
    // Most recent first
    expect(result.current.predictions[0].id).toBe(59)
  })

  it('reconnects after close with 10s delay', () => {
    renderHook(() => useWebSocket())
    expect(FakeWebSocket.instances).toHaveLength(1)
    act(() => FakeWebSocket.instances[0].close())
    // Not reconnected yet
    expect(FakeWebSocket.instances).toHaveLength(1)
    // Advance 10 seconds
    act(() => vi.advanceTimersByTime(10_000))
    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it('closes socket on error', () => {
    const { result } = renderHook(() => useWebSocket())
    const ws = FakeWebSocket.instances[0]
    act(() => ws._open())
    expect(result.current.connected).toBe(true)
    act(() => ws._error())
    expect(ws.readyState).toBe(3) // CLOSED
  })

  it('ignores invalid JSON', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0]._open())
    // Send raw invalid JSON
    act(() => {
      FakeWebSocket.instances[0].onmessage({ data: 'not-json' })
    })
    // Should not crash — state unchanged
    expect(result.current.ticks).toEqual({})
  })

  it('cleans up on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket())
    const ws = FakeWebSocket.instances[0]
    unmount()
    expect(ws.readyState).toBe(3) // closed
  })
})
