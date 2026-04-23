/**
 * Coverage for DataStream and AICorePanel — covers classifyLog branches,
 * formatTimestamp, extractMessage, matrix theme path, AICorePanel consensus
 * compute paths (BUY/SELL ratios + strength tiers).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// ---- routed useApi mock ----
let mockByKey = {}
const mockApiDefault = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({
  default: (fetcher) => {
    const src = (fetcher && fetcher.toString && fetcher.toString()) || ''
    const m = src.match(/api\.(\w+)/)
    const key = m ? m[1] : null
    return mockByKey[key] || mockApiDefault
  },
}))

// useWebSocket mock configurable per-test
let wsReturn = { logs: [], connected: false }
vi.mock('../hooks/useWebSocket', () => ({
  default: () => wsReturn,
}))

// Theme provider mock: configurable theme
let currentTheme = 'dark'
vi.mock('../theme/ThemeProvider', () => ({
  useTheme: () => ({ theme: currentTheme, setTheme: vi.fn() }),
}))

vi.mock('../services/api', () => ({
  api: {
    getRecentLogs: vi.fn(),
    getModelsPerformance: vi.fn(),
    getLatestSignals: vi.fn(),
  },
}))

beforeEach(() => {
  mockByKey = {}
  wsReturn = { logs: [], connected: false }
  currentTheme = 'dark'
})

const apiOk = (data) => ({ data, loading: false, error: null, refetch: vi.fn() })

// =========================================================
// DataStream — dark theme path
// =========================================================
import DataStream from '../components/control_tower/DataStream'

describe('DataStream (dark theme)', () => {
  it('shows waiting message when no logs', () => {
    render(<DataStream />)
    expect(screen.getByText(/Waiting for data/i)).toBeInTheDocument()
    expect(screen.getByText(/OFFLINE/)).toBeInTheDocument()
  })

  it('renders LIVE when ws connected', () => {
    wsReturn = { logs: [], connected: true }
    render(<DataStream />)
    expect(screen.getByText(/LIVE/)).toBeInTheDocument()
  })

  it('renders classified log lines from api (array form)', () => {
    const iso = '2026-04-16T10:00:00'
    mockByKey = {
      getRecentLogs: apiOk([
        { timestamp: iso, level: 'error', message: 'blow up' },
        { timestamp: iso, level: 'warn', message: 'careful' },
        { timestamp: iso, message: 'healthcheck ok' },
        { timestamp: iso, message: 'session score changed' },
        { timestamp: iso, message: 'signal buy EURUSD' },
        { timestamp: iso, message: 'pred_t1 0.5' },
        { timestamp: iso, message: 'news sentiment bump' },
        { timestamp: iso, message: 'trade pnl closed' },
        { timestamp: iso, message: 'decision consensus BUY' },
        { timestamp: iso, message: 'just an info note' },
        { timestamp: iso, log_type: 'system', message: 'sys boot' },
      ]),
    }
    render(<DataStream />)
    // Several ERROR / WARN / SIGNAL / MODEL / NEWS / TRADE / SYS lines rendered
    expect(screen.getByText(/\[ERROR\]/)).toBeInTheDocument()
    expect(screen.getByText(/\[WARN\]/)).toBeInTheDocument()
    expect(screen.getByText(/\[HEALTH\]/)).toBeInTheDocument()
    expect(screen.getAllByText(/\[SIGNAL\]/).length).toBeGreaterThan(0)
    expect(screen.getByText(/\[NEWS\]/)).toBeInTheDocument()
    expect(screen.getByText(/\[TRADE\]/)).toBeInTheDocument()
  })

  it('handles recentLogs wrapped in {logs: [...]}', () => {
    mockByKey = {
      getRecentLogs: apiOk({
        logs: [
          { timestamp: '2026-04-16T10:00:00', msg: 'short msg', level: 'INFO' },
        ],
      }),
    }
    render(<DataStream />)
    expect(screen.getByText(/short msg/)).toBeInTheDocument()
  })

  it('extractMessage handles action+details and empty object', () => {
    mockByKey = {
      getRecentLogs: apiOk({
        data: [
          { timestamp: 'bad-ts', action: 'CLOSE', details: 'tp hit', symbol: 'EURUSD' },
          { timestamp: null, _type: 'info' }, // no message fields -> NO DATA
          { timestamp: '2026-04-16T10:00:00', action: 'OPEN', symbol: 'GBPUSD' },
          { timestamp: '2026-04-16T10:00:00', foo: 1, bar: 2, baz: 3, qux: 4, extra: 5 }, // fallback
        ],
      }),
    }
    render(<DataStream />)
    expect(screen.getByText(/CLOSE tp hit/)).toBeInTheDocument()
    expect(screen.getByText(/NO DATA/)).toBeInTheDocument()
    expect(screen.getByText(/OPEN: GBPUSD/)).toBeInTheDocument()
  })

  it('merges ws logs into the feed', () => {
    wsReturn = {
      logs: [{ timestamp: '2026-04-16T10:00:00', level: 'INFO', message: 'ws live msg' }],
      connected: true,
    }
    render(<DataStream />)
    expect(screen.getByText(/ws live msg/)).toBeInTheDocument()
  })
})

// =========================================================
// DataStream — matrix theme path
// =========================================================
describe('DataStream (matrix theme)', () => {
  it('renders matrix variant with waiting line', () => {
    currentTheme = 'matrix'
    render(<DataStream />)
    expect(screen.getByText(/WAITING FOR DATA/i)).toBeInTheDocument()
  })

  it('renders matrix variant with typewriter logs', async () => {
    currentTheme = 'matrix'
    wsReturn = { logs: [], connected: true }
    mockByKey = {
      getRecentLogs: apiOk([
        { timestamp: '2026-04-16T10:00:00', level: 'info', message: 'matrix online' },
      ]),
    }
    render(<DataStream />)
    expect(screen.getAllByText(/ONLINE/).length).toBeGreaterThan(0)
  })
})

// =========================================================
// AICorePanel
// =========================================================
import AICorePanel from '../components/control_tower/AICorePanel'

describe('AICorePanel', () => {
  it('renders empty (no signals, no performance)', () => {
    render(<AICorePanel />)
    expect(screen.getByText(/AI Core/i)).toBeInTheDocument()
    expect(screen.getByText('HOLD')).toBeInTheDocument()
    expect(screen.getByText(/NO DATA/i)).toBeInTheDocument()
  })

  it('renders with performance ranking (top model)', () => {
    mockByKey = {
      getModelsPerformance: apiOk({
        ranking: [
          { model: 'xgb', accuracy: 68.5 },
          { model: 'linear', accuracy: 52.1 },
        ],
      }),
      getLatestSignals: apiOk({ signals: [] }),
    }
    render(<AICorePanel />)
    expect(screen.getByText('xgb')).toBeInTheDocument()
    expect(screen.getByText(/68.5%/)).toBeInTheDocument()
  })

  it('renders with performance as plain array (win_rate fallback)', () => {
    mockByKey = {
      getModelsPerformance: apiOk([
        { model: 'rf', win_rate: 55.5 },
        { model: 'xgb', win_rate: 60.0 },
      ]),
      getLatestSignals: apiOk([]),
    }
    render(<AICorePanel />)
    expect(screen.getByText('xgb')).toBeInTheDocument()
  })

  it('computes STRONG consensus (>=80% same direction)', () => {
    mockByKey = {
      getModelsPerformance: apiOk({ ranking: [] }),
      getLatestSignals: apiOk([
        { model: 'a', direction: 'BUY', confidence: 0.9 },
        { model: 'b', direction: 'long', confidence: 0.8 }, // LONG → BUY
        { model: 'c', signal: 'BUY', probability: 0.7 },
        { model: 'd', direction: 'BUY', confidence: 0.6 },
        { model: 'e', direction: 'SELL', confidence: 0.5 },
      ]),
    }
    render(<AICorePanel />)
    expect(screen.getAllByText('BUY').length).toBeGreaterThan(0)
    expect(screen.getByText(/STRONG/)).toBeInTheDocument()
    expect(screen.getByText(/High/)).toBeInTheDocument() // avg conf > 70
  })

  it('computes MODERATE consensus (>=60%)', () => {
    mockByKey = {
      getModelsPerformance: apiOk({ ranking: [] }),
      getLatestSignals: apiOk([
        { model: 'a', direction: 'SELL', confidence: 0.5 },
        { model: 'b', direction: 'short', confidence: 0.5 }, // SHORT → SELL
        { model: 'c', direction: 'BUY', confidence: 0.5 },
      ]),
    }
    render(<AICorePanel />)
    expect(screen.getAllByText('SELL').length).toBeGreaterThan(0)
    expect(screen.getByText(/MODERATE/)).toBeInTheDocument()
    expect(screen.getByText(/Medium/)).toBeInTheDocument() // 50% avg conf
  })

  it('computes WEAK consensus with Low confidence badge', () => {
    mockByKey = {
      getModelsPerformance: apiOk({ ranking: [] }),
      getLatestSignals: apiOk([
        { model: 'a', direction: 'BUY', confidence: 0.3 },
        { model: 'b', direction: 'SELL', confidence: 0.3 },
        { model: 'c', direction: 'HOLD', confidence: 0.3 },
      ]),
    }
    render(<AICorePanel />)
    expect(screen.getByText(/Low/)).toBeInTheDocument()
  })

  it('renders matrix variant with HIGH badge', () => {
    currentTheme = 'matrix'
    mockByKey = {
      getModelsPerformance: apiOk({ ranking: [{ model: 'xgb', accuracy: 75 }] }),
      getLatestSignals: apiOk([
        { model_name: 'xgb', direction: 'BUY', confidence: 0.8 },
      ]),
    }
    render(<AICorePanel />)
    expect(screen.getByText(/HIGH/)).toBeInTheDocument()
    expect(screen.getAllByText(/\[BUY\]/).length).toBeGreaterThan(0)
  })
})
