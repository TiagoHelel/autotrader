/**
 * Final coverage push: EquityChart with data + Overview with analytics branch.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

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

vi.mock('../services/api', () => ({
  api: {
    getEquityHistory: vi.fn(),
    getPredictMetrics: vi.fn(),
    getModelsPerformanceOverTime: vi.fn(),
    getSystemStatus: vi.fn(),
    getNewsAnalytics: vi.fn(),
  },
}))

vi.mock('recharts', () => {
  const React = require('react')
  const Stub = (name) => ({ children }) =>
    React.createElement('div', { 'data-testid': `recharts-${name}` }, children)
  return {
    LineChart: Stub('line-chart'),
    Line: Stub('line'),
    AreaChart: Stub('area-chart'),
    Area: Stub('area'),
    BarChart: Stub('bar-chart'),
    Bar: Stub('bar'),
    XAxis: Stub('xaxis'),
    YAxis: Stub('yaxis'),
    CartesianGrid: Stub('grid'),
    Tooltip: Stub('tooltip'),
    Legend: Stub('legend'),
    ResponsiveContainer: ({ children }) =>
      React.createElement('div', { 'data-testid': 'responsive-container' }, children),
  }
})

beforeEach(() => {
  mockByKey = {}
})

const apiOk = (data) => ({ data, loading: false, error: null, refetch: vi.fn() })
const apiLoading = () => ({ data: null, loading: true, error: null, refetch: vi.fn() })

// =========================================================
// EquityChart
// =========================================================
import EquityChart from '../components/dashboard/EquityChart'

describe('EquityChart', () => {
  it('shows loading state', () => {
    mockByKey = { getEquityHistory: apiLoading() }
    render(<EquityChart />)
    expect(document.querySelector('[class*="animate-spin"]')).toBeTruthy()
  })

  it('renders with data', () => {
    mockByKey = {
      getEquityHistory: apiOk([
        { date: '2026-04-01', equity: 10000 },
        { date: '2026-04-02', equity: 10250.5 },
        { date: '2026-04-03', equity: 9800 },
      ]),
    }
    render(<EquityChart />)
    expect(screen.getByText(/Equity Curve/)).toBeInTheDocument()
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument()
  })

  it('renders with null/empty data', () => {
    mockByKey = { getEquityHistory: apiOk(null) }
    render(<EquityChart />)
    expect(screen.getByText(/Equity Curve/)).toBeInTheDocument()
  })
})

// =========================================================
// Overview with news analytics
// =========================================================
import Overview from '../pages/Overview'

describe('Overview with news analytics', () => {
  it('renders news sentiment section with high impact events', () => {
    mockByKey = {
      getPredictMetrics: apiOk({
        global: {
          global_accuracy: 62.5,
          global_mae: 0.001,
          global_mape: 1.5,
          total_predictions: 1000,
          total_correct: 625,
        },
        metrics: [
          { model: 'xgb', accuracy: 65 },
          { model: 'linear', accuracy: 55 },
        ],
      }),
      getModelsPerformanceOverTime: apiOk({
        data: [
          { timestamp: '2026-04-16T10:00', model: 'xgb', rolling_accuracy: 0.65, rolling_mae: 0.001 },
          { timestamp: '2026-04-16T11:00', model: 'xgb', rolling_accuracy: 0.66, rolling_mae: 0.0009 },
          { timestamp: '2026-04-16T10:00', model: 'linear', rolling_accuracy: 0.55, rolling_mae: 0.002 },
        ],
      }),
      getSystemStatus: apiOk({ status: 'running', active_symbols: 5 }),
      getNewsAnalytics: apiOk({
        analytics: {
          by_currency: {
            USD: { sentiment_basic_avg: 0.3, total_events: 20, high_impact_count: 5 },
            EUR: { sentiment_basic_avg: -0.2, total_events: 15, high_impact_count: 3 },
            GBP: { sentiment_basic_avg: 0, total_events: 10, high_impact_count: 0 },
          },
        },
      }),
    }
    render(<Overview />)
    expect(screen.getByText(/News Sentiment by Currency/)).toBeInTheDocument()
    expect(screen.getByText(/High Impact Events Summary/)).toBeInTheDocument()
    expect(screen.getAllByText('USD').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/high impact/).length).toBeGreaterThan(0)
  })

  it('shows "No high impact events" when all zero', () => {
    mockByKey = {
      getPredictMetrics: apiOk({ global: {}, metrics: [] }),
      getModelsPerformanceOverTime: apiOk({ data: [] }),
      getSystemStatus: apiOk({ status: 'idle', active_symbols: 0 }),
      getNewsAnalytics: apiOk({
        analytics: {
          by_currency: {
            USD: { sentiment_basic_avg: 0, total_events: 5, high_impact_count: 0 },
            EUR: { sentiment_basic_avg: 0, total_events: 3, high_impact_count: 0 },
          },
        },
      }),
    }
    render(<Overview />)
    expect(screen.getByText(/No high impact events/)).toBeInTheDocument()
  })
})
