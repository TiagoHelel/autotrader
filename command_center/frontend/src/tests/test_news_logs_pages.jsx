/**
 * Tests for News, NewsAnalytics, and Logs pages.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ---- Shared useApi mock: routes by which api.xxx the fetcher's source references ----
let mockByKey = {}
const mockApiDefault = { data: null, loading: false, error: null, refetch: vi.fn() }

vi.mock('../hooks/useApi', () => ({
  default: (fetcher) => {
    const src = (fetcher && fetcher.toString && fetcher.toString()) || ''
    // Find the first api.xxx reference in the source
    const match = src.match(/api\.(\w+)/)
    const key = match ? match[1] : null
    return mockByKey[key] || mockApiDefault
  },
}))

const mockWs = { logs: [] }
vi.mock('../hooks/useWebSocket', () => ({ default: () => mockWs }))

vi.mock('../services/api', () => ({
  api: {
    getNewsLatest: vi.fn(),
    getNewsLlm: vi.fn(),
    getNewsAnalytics: vi.fn(),
    getNewsRefreshStatus: vi.fn(() => Promise.resolve({ running: false })),
    refreshNews: vi.fn(() => Promise.resolve()),
    getRecentLogs: vi.fn(),
    getSymbols: vi.fn(),
  },
}))

// Stub recharts
vi.mock('recharts', () => {
  const React = require('react')
  const Stub = (name) => ({ children }) =>
    React.createElement('div', { 'data-testid': `recharts-${name}` }, children)
  return {
    AreaChart: Stub('area'),
    Area: Stub('area-series'),
    BarChart: Stub('bar-chart'),
    Bar: Stub('bar'),
    LineChart: Stub('line-chart'),
    Line: Stub('line'),
    XAxis: Stub('xaxis'),
    YAxis: Stub('yaxis'),
    CartesianGrid: Stub('grid'),
    Tooltip: Stub('tooltip'),
    Legend: Stub('legend'),
    ResponsiveContainer: ({ children }) =>
      React.createElement('div', { 'data-testid': 'responsive-container' }, children),
  }
})

// Stub LogPanel component
vi.mock('../components/logs/LogPanel', () => ({
  default: ({ wsLogs, fullPage }) => {
    const React = require('react')
    return React.createElement('div', { 'data-testid': 'log-panel' }, `logs:${(wsLogs || []).length} full:${!!fullPage}`)
  },
}))

beforeEach(() => {
  mockByKey = {}
  mockWs.logs = []
})

const apiOk = (data) => ({ data, loading: false, error: null, refetch: vi.fn() })

// ===================== News =====================
import News from '../pages/News'

describe('News page', () => {
  it('shows loading spinner', () => {
    mockByKey = {
      getNewsLatest: { data: null, loading: true, error: null, refetch: vi.fn() },
      getNewsLlm: apiOk(null),
    }
    render(<News />)
    const spinner = document.querySelector('[class*="animate-spin"]')
    expect(spinner).toBeTruthy()
  })

  it('shows error banner when news fails', () => {
    mockByKey = {
      getNewsLatest: { data: null, loading: false, error: 'boom', refetch: vi.fn() },
      getNewsLlm: apiOk(null),
    }
    render(<News />)
    expect(screen.getByText(/Failed to load news feed/)).toBeInTheDocument()
  })

  it('shows empty state when no events', () => {
    mockByKey = {
      getNewsLatest: apiOk({ events: [] }),
      getNewsLlm: apiOk({ llm_features: [] }),
    }
    render(<News />)
    expect(screen.getByText(/No news available/)).toBeInTheDocument()
  })

  it('renders events with currency aggregation and LLM scores', () => {
    mockByKey = {
      getNewsLatest: apiOk({
        events: [
          {
            name: 'US GDP', currency: 'USD', impact_num: 3,
            signal: 'good', sentiment_basic: 0.4,
            timestamp: '2026-04-16T12:00:00', event_type: 'None',
            actual: '2.5', forecast: '2.0', previous: '1.8',
          },
          {
            name: 'EU CPI', currency: 'EUR', impact_num: 2,
            signal: 'bad', sentiment_basic: -0.2,
            timestamp: '2026-04-16T10:00:00',
          },
        ],
      }),
      getNewsLlm: apiOk({
        llm_features: [{ name: 'US GDP', sentiment_score: 0.5 }],
      }),
    }
    render(<News />)
    expect(screen.getByText('US GDP')).toBeInTheDocument()
    expect(screen.getByText('EU CPI')).toBeInTheDocument()
    expect(screen.getAllByText('USD').length).toBeGreaterThan(0)
    expect(screen.getAllByText('EUR').length).toBeGreaterThan(0)
    expect(screen.getByText('LLM')).toBeInTheDocument()
  })

  it('shows refresh button', () => {
    mockByKey = {
      getNewsLatest: apiOk({ events: [] }),
      getNewsLlm: apiOk({ llm_features: [] }),
    }
    render(<News />)
    expect(screen.getByText(/Refresh News/i)).toBeInTheDocument()
  })

  it('clicking refresh invokes refreshNews and polls status', async () => {
    const refetchNewsMock = vi.fn()
    const refetchLlmMock = vi.fn()
    mockByKey = {
      getNewsLatest: { data: { events: [] }, loading: false, error: null, refetch: refetchNewsMock },
      getNewsLlm: { data: { llm_features: [] }, loading: false, error: null, refetch: refetchLlmMock },
    }
    const { api } = await import('../services/api')
    // First poll returns running, second returns idle
    api.getNewsRefreshStatus
      .mockReset()
      .mockResolvedValueOnce({ running: true })
      .mockResolvedValue({ running: false })

    render(<News />)
    const btn = screen.getByText(/Refresh News/i)
    fireEvent.click(btn)
    // wait a bit so the async for-loop progresses
    await new Promise((r) => setTimeout(r, 60))
    expect(api.refreshNews).toHaveBeenCalled()
  })

  it('refresh error path is swallowed', async () => {
    mockByKey = {
      getNewsLatest: apiOk({ events: [] }),
      getNewsLlm: apiOk({ llm_features: [] }),
    }
    const { api } = await import('../services/api')
    api.refreshNews.mockRejectedValueOnce(new Error('nope'))
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<News />)
    fireEvent.click(screen.getByText(/Refresh News/i))
    await new Promise((r) => setTimeout(r, 20))
    expect(api.refreshNews).toHaveBeenCalled()
    errorSpy.mockRestore()
  })

  it('shows llm_unavailable hint when llmError is set', () => {
    mockByKey = {
      getNewsLatest: apiOk({ events: [] }),
      getNewsLlm: { data: null, loading: false, error: 'llm down', refetch: vi.fn() },
    }
    render(<News />)
    expect(screen.getByText(/LLM unavailable/)).toBeInTheDocument()
  })
})

// ===================== NewsAnalytics =====================
import NewsAnalytics from '../pages/NewsAnalytics'

describe('NewsAnalytics page', () => {
  it('shows loading spinner', () => {
    mockByKey = {
      getNewsAnalytics: { data: null, loading: true, error: null, refetch: vi.fn() },
      getNewsLatest: apiOk(null),
    }
    render(<NewsAnalytics />)
    const spinner = document.querySelector('[class*="animate-spin"]')
    expect(spinner).toBeTruthy()
  })

  it('renders heading and events count', () => {
    mockByKey = {
      getNewsAnalytics: apiOk({
        analytics: {
          total_events: 42,
          by_currency: {
            USD: { total_events: 20, avg_impact: 2.1, sentiment_basic_avg: 0.3, sentiment_llm_avg: 0.4 },
            EUR: { total_events: 22, avg_impact: 1.8, sentiment_basic_avg: -0.1, sentiment_llm_avg: 0.0 },
          },
          by_impact: { 1: 10, 2: 20, 3: 12 },
          basic_vs_llm: [
            { name: 'Fed rate decision very long name here', basic: 0.6, llm: 0.5, confidence: 0.9 },
          ],
        },
      }),
      getNewsLatest: apiOk({
        events: [
          { name: 'e1', currency: 'USD', impact_num: 3 },
          { name: 'e2', currency: 'EUR', impact_num: 1 },
        ],
      }),
    }
    render(<NewsAnalytics />)
    expect(screen.getByText(/News Analytics/i)).toBeInTheDocument()
    expect(screen.getByText(/42 events/)).toBeInTheDocument()
  })

  it('filters events by currency and impact', () => {
    mockByKey = {
      getNewsAnalytics: apiOk({
        analytics: { total_events: 3, by_currency: {}, by_impact: {}, basic_vs_llm: [] },
      }),
      getNewsLatest: apiOk({
        events: [
          { name: 'a', currency: 'USD', impact_num: 3 },
          { name: 'b', currency: 'USD', impact_num: 1 },
          { name: 'c', currency: 'EUR', impact_num: 2 },
        ],
      }),
    }
    render(<NewsAnalytics />)
    const selects = document.querySelectorAll('select')
    fireEvent.change(selects[0], { target: { value: 'USD' } })
    expect(screen.getByText(/Showing 2 events/)).toBeInTheDocument()
    fireEvent.change(selects[1], { target: { value: '3' } })
    expect(screen.getByText(/Showing 1 events/)).toBeInTheDocument()
  })
})

// ===================== Logs =====================
import Logs from '../pages/Logs'

describe('Logs page', () => {
  it('renders heading and tab bar', () => {
    mockByKey = {
      getRecentLogs: apiOk({ logs: [] }),
      getSymbols: apiOk({ symbols: [{ symbol: 'EURUSD' }, { symbol: 'GBPUSD' }] }),
    }
    render(<Logs />)
    expect(screen.getByRole('heading', { name: /Logs/i })).toBeInTheDocument()
    expect(screen.getByText('Predictions')).toBeInTheDocument()
    expect(screen.getByText('Decisions')).toBeInTheDocument()
    expect(screen.getByTestId('log-panel')).toBeInTheDocument()
  })

  it('shows prediction log rows when prediction tab selected', () => {
    mockByKey = {
      getRecentLogs: apiOk({
        logs: [
          {
            timestamp: '2026-04-16T12:00:00Z', type: 'prediction',
            symbol: 'EURUSD', model: 'xgboost',
            current_price: 1.1, pred_t1: 1.11, pred_t2: 1.12, pred_t3: 1.13,
          },
          {
            timestamp: '2026-04-16T12:05:00Z', type: 'decision',
            symbol: 'GBPUSD', model: 'linear', action: 'BUY', details: 'strong signal',
          },
        ],
      }),
      getSymbols: apiOk({ symbols: [] }),
    }
    render(<Logs />)
    fireEvent.click(screen.getByText('Predictions'))
    expect(screen.getByText('EURUSD')).toBeInTheDocument()
    expect(screen.getByText('xgboost')).toBeInTheDocument()
  })

  it('applies symbol filter', () => {
    mockByKey = {
      getRecentLogs: apiOk({
        logs: [
          { timestamp: 't', type: 'prediction', symbol: 'EURUSD', model: 'm', current_price: 1 },
          { timestamp: 't', type: 'prediction', symbol: 'GBPUSD', model: 'm', current_price: 1 },
        ],
      }),
      getSymbols: apiOk({ symbols: [{ symbol: 'EURUSD' }, { symbol: 'GBPUSD' }] }),
    }
    render(<Logs />)
    fireEvent.click(screen.getByText('Predictions'))
    const selects = document.querySelectorAll('select')
    fireEvent.change(selects[0], { target: { value: 'EURUSD' } })
    // Both EURUSD option AND EURUSD row exist; GBPUSD row should be filtered out
    const rows = document.querySelectorAll('tbody tr')
    expect(rows.length).toBe(1)
    // The remaining row's symbol cell is EURUSD
    expect(rows[0].textContent).toContain('EURUSD')
    expect(rows[0].textContent).not.toContain('GBPUSD')
  })

  it('shows "No logs" empty row when filter removes everything', () => {
    mockByKey = {
      getRecentLogs: apiOk({
        logs: [{ timestamp: 't', type: 'signal', symbol: 'EURUSD', model: 'm' }],
      }),
      getSymbols: apiOk({ symbols: [] }),
    }
    render(<Logs />)
    fireEvent.click(screen.getByText('Trades'))
    expect(screen.getByText(/No logs to display/i)).toBeInTheDocument()
  })
})
