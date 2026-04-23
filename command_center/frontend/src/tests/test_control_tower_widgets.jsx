/**
 * Tests for control_tower P1 widgets:
 * SignalRadar, AICorePanel, SessionPanel, DataStream
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

// ---- Shared mocks ----
let mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({ default: () => mockApiReturn }))

const mockWs = { ticks: {}, logs: [], kpis: null, predictions: [], connected: true }
vi.mock('../hooks/useWebSocket', () => ({ default: () => mockWs }))

vi.mock('../theme/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'default' }),
}))

vi.mock('../services/api', () => ({
  api: {
    getRadarSignals: vi.fn(),
    getModelsPerformance: vi.fn(),
    getLatestSignals: vi.fn(),
    getSessionCurrent: vi.fn(() => Promise.resolve({
      active_sessions: ['london', 'new_york'],
      active_overlaps: ['london_new_york'],
      session_score: 0.85,
      session_strength: 'STRONG',
      weights: { sydney: 0.7, tokyo: 0.8, london: 1.5, new_york: 1.2 },
      regime: { trend_label: 'Bullish', volatility_label: 'Low' },
    })),
    getRecentLogs: vi.fn(),
  },
}))

// Stub requestAnimationFrame for SignalRadar
if (!globalThis.requestAnimationFrame) {
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0)
  globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
}

// ===================== SignalRadar =====================
import SignalRadar from '../components/control_tower/SignalRadar'

describe('SignalRadar', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders radar container', () => {
    render(<SignalRadar />)
    const svg = document.querySelector('svg')
    expect(svg).toBeTruthy()
  })

  it('shows signal dots when data available', () => {
    mockApiReturn = {
      data: {
        signals: [
          { symbol: 'EURUSD', signal: 'BUY', confidence: 0.82, expected_return: 0.002, model_count: 3 },
          { symbol: 'GBPUSD', signal: 'SELL', confidence: 0.64, expected_return: -0.001, model_count: 2 },
        ],
        breakdown: { BUY: 1, SELL: 1, HOLD: 0 },
        total: 2,
      },
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<SignalRadar />)
    const circles = document.querySelectorAll('circle')
    expect(circles.length).toBeGreaterThan(0)
  })

  it('shows legend with breakdown', () => {
    mockApiReturn = {
      data: {
        signals: [{ symbol: 'EURUSD', signal: 'BUY', confidence: 0.82 }],
        breakdown: { BUY: 1, SELL: 0, HOLD: 0 },
        total: 1,
      },
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<SignalRadar />)
    expect(screen.getByText('BUY')).toBeInTheDocument()
  })
})

// ===================== AICorePanel =====================
import AICorePanel from '../components/control_tower/AICorePanel'

describe('AICorePanel', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    render(<AICorePanel />)
    expect(screen.getByText(/AI Core/i)).toBeInTheDocument()
  })

  it('shows model performance data', () => {
    mockApiReturn = {
      data: {
        ranking: [
          { model: 'xgboost', accuracy: 68.5, total_predictions: 100 },
          { model: 'linear', accuracy: 55.0, total_predictions: 80 },
        ],
      },
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<AICorePanel />)
    expect(screen.getByText('xgboost')).toBeInTheDocument()
  })
})

// ===================== SessionPanel =====================
import SessionPanel from '../components/control_tower/SessionPanel'

describe('SessionPanel', () => {
  it('renders session heading', async () => {
    render(<SessionPanel />)
    await waitFor(() => {
      expect(screen.getByText(/Session/i)).toBeInTheDocument()
    })
  })

  it('shows forex session names after data loads', async () => {
    render(<SessionPanel />)
    await waitFor(() => {
      expect(screen.getByText('Sydney')).toBeInTheDocument()
    })
    expect(screen.getByText('Tokyo')).toBeInTheDocument()
    expect(screen.getByText('London')).toBeInTheDocument()
    expect(screen.getByText('New York')).toBeInTheDocument()
  })

  it('shows symbol selector', () => {
    render(<SessionPanel />)
    const select = document.querySelector('select')
    expect(select).toBeTruthy()
  })
})

// ===================== DataStream =====================
import DataStream from '../components/control_tower/DataStream'

describe('DataStream', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
    mockWs.logs = []
    mockWs.connected = true
  })

  it('renders terminal container', () => {
    render(<DataStream />)
    // DataStream renders a glass-card container
    const container = document.querySelector('[class*="glass-card"]') || document.querySelector('[class*="card"]')
    expect(container).toBeTruthy()
  })

  it('shows websocket logs', () => {
    mockWs.logs = [
      { timestamp: '2025-01-01T12:00:00', message: 'Signal BUY EURUSD', level: 'info' },
    ]
    render(<DataStream />)
    expect(screen.getByText(/Signal BUY EURUSD/)).toBeInTheDocument()
  })

  it('shows LIVE status when connected', () => {
    mockWs.connected = true
    render(<DataStream />)
    expect(screen.getByText('LIVE')).toBeInTheDocument()
  })

  it('handles empty logs without crashing', () => {
    mockWs.logs = []
    render(<DataStream />)
    expect(document.body.querySelector('div')).toBeTruthy()
  })
})
