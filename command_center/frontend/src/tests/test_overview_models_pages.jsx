/**
 * Smoke tests for Overview, Models, Experiments, Symbols pages.
 * Focused on rendering and empty-state branches to lift coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ---- useApi mock that routes by source of fetcher ----
let mockByKey = {}
const mockApiDefault = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({
  default: (fetcher) => {
    const src = (fetcher && fetcher.toString && fetcher.toString()) || ''
    const match = src.match(/api\.(\w+)/)
    const key = match ? match[1] : null
    return mockByKey[key] || mockApiDefault
  },
}))

vi.mock('../services/api', () => ({
  api: {
    getPredictMetrics: vi.fn(),
    getModelsPerformance: vi.fn(),
    getModelsPerformanceOverTime: vi.fn(),
    getModelsInfo: vi.fn(),
    getModelsValidation: vi.fn(),
    getSystemStatus: vi.fn(),
    getNewsAnalytics: vi.fn(),
    getExperimentsSummary: vi.fn(),
    getExperiments: vi.fn(),
    getSymbols: vi.fn(),
    getSymbolCandles: vi.fn(),
    getSymbolPredictions: vi.fn(),
  },
}))

// Stub recharts
vi.mock('recharts', () => {
  const React = require('react')
  const Stub = (name) => ({ children }) =>
    React.createElement('div', { 'data-testid': `recharts-${name}` }, children)
  return {
    LineChart: Stub('line-chart'),
    Line: Stub('line'),
    BarChart: Stub('bar-chart'),
    Bar: Stub('bar'),
    RadarChart: Stub('radar-chart'),
    Radar: Stub('radar'),
    PolarGrid: Stub('polar-grid'),
    PolarAngleAxis: Stub('polar-angle-axis'),
    PolarRadiusAxis: Stub('polar-radius-axis'),
    ComposedChart: Stub('composed-chart'),
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

// ===================== Overview =====================
import Overview from '../pages/Overview'

describe('Overview page', () => {
  it('shows loading spinner', () => {
    mockByKey = { getPredictMetrics: apiLoading() }
    render(<Overview />)
    expect(document.querySelector('[class*="animate-spin"]')).toBeTruthy()
  })

  it('renders heading and system status indicator', () => {
    mockByKey = {
      getPredictMetrics: apiOk({ global: { global_accuracy: 62.5 }, metrics: [] }),
      getSystemStatus: apiOk({ status: 'running', active_symbols: 5 }),
    }
    render(<Overview />)
    expect(screen.getByRole('heading', { name: /Prediction Overview/i })).toBeInTheDocument()
    expect(screen.getByText(/5 symbols active/)).toBeInTheDocument()
  })

  it('renders with performance-over-time data', () => {
    mockByKey = {
      getPredictMetrics: apiOk({ global: { global_accuracy: 55 }, metrics: [{ model: 'xgb', accuracy: 60 }] }),
      getModelsPerformanceOverTime: apiOk({
        data: [
          { timestamp: '2026-04-16T10:00', model: 'xgb', rolling_accuracy: 0.62, rolling_mae: 0.01 },
          { timestamp: '2026-04-16T11:00', model: 'xgb', rolling_accuracy: 0.63, rolling_mae: 0.009 },
        ],
      }),
      getSystemStatus: apiOk({ status: 'running', active_symbols: 3 }),
    }
    render(<Overview />)
    expect(screen.getAllByTestId('responsive-container').length).toBeGreaterThan(0)
  })
})

// ===================== Models =====================
import Models from '../pages/Models'

describe('Models page', () => {
  it('shows loading spinner', () => {
    mockByKey = { getModelsPerformance: apiLoading() }
    render(<Models />)
    expect(document.querySelector('[class*="animate-spin"]')).toBeTruthy()
  })

  it('renders with ranking data', () => {
    mockByKey = {
      getModelsPerformance: apiOk({
        ranking: [
          { model: 'xgboost', accuracy: 68.5, total_predictions: 100 },
          { model: 'linear', accuracy: 55.0, total_predictions: 80 },
        ],
      }),
      getModelsInfo: apiOk({ models: [{ name: 'xgboost', type: 'boosted' }] }),
      getModelsValidation: apiOk({
        validation: [{ model: 'xgboost', overfit_score: 0.12, risk: 'low' }],
      }),
      getModelsPerformanceOverTime: apiOk({
        data: [{ timestamp: '2026-04-16T10:00', model: 'xgboost', rolling_accuracy: 0.68 }],
      }),
    }
    render(<Models />)
    expect(screen.getAllByText(/xgboost/i).length).toBeGreaterThan(0)
  })

  it('renders empty-data state gracefully', () => {
    mockByKey = {
      getModelsPerformance: apiOk({ ranking: [] }),
      getModelsInfo: apiOk({ models: [] }),
      getModelsValidation: apiOk({ validation: [] }),
      getModelsPerformanceOverTime: apiOk({ data: [] }),
    }
    render(<Models />)
    // should not crash
    expect(document.body).toBeTruthy()
  })
})

// ===================== Experiments =====================
import Experiments from '../pages/Experiments'

describe('Experiments page', () => {
  it('shows loading spinner', () => {
    mockByKey = { getExperimentsSummary: apiLoading() }
    render(<Experiments />)
    expect(document.querySelector('[class*="animate-spin"]')).toBeTruthy()
  })

  it('renders heading and summary cards', () => {
    mockByKey = {
      getExperimentsSummary: apiOk({
        summary: [
          { model: 'xgboost', total_trainings: 12, avg_train_size: 1500, best_acc: 0.68 },
          { model: 'linear', total_trainings: 8, avg_train_size: 1400, best_acc: 0.52 },
        ],
      }),
      getExperiments: apiOk({ experiments: [] }),
    }
    render(<Experiments />)
    expect(screen.getByRole('heading', { name: /Experiments/i })).toBeInTheDocument()
    expect(screen.getByText('xgboost')).toBeInTheDocument()
    expect(screen.getByText('linear')).toBeInTheDocument()
  })

  it('selects a model on click', () => {
    mockByKey = {
      getExperimentsSummary: apiOk({
        summary: [{ model: 'xgboost', total_trainings: 5, avg_train_size: 1000 }],
      }),
      getExperiments: apiOk({ experiments: [] }),
    }
    render(<Experiments />)
    fireEvent.click(screen.getByText('xgboost'))
    // No crash — selected state toggles
    expect(screen.getByText('xgboost')).toBeInTheDocument()
  })
})

// ===================== Symbols =====================
import Symbols from '../pages/Symbols'

describe('Symbols page', () => {
  it('renders heading with no symbols', () => {
    mockByKey = { getSymbols: apiOk({ symbols: [] }) }
    render(<Symbols />)
    expect(screen.getByRole('heading', { name: /Symbol Analysis/i })).toBeInTheDocument()
  })

  it('renders symbol list in selector', () => {
    mockByKey = {
      getSymbols: apiOk({
        symbols: [
          { symbol: 'EURUSD', candles: 1000 },
          { symbol: 'GBPUSD', candles: 800 },
        ],
      }),
    }
    render(<Symbols />)
    const select = document.querySelector('select')
    expect(select).toBeTruthy()
    expect(select.querySelectorAll('option').length).toBe(2)
  })

  it('changes selected symbol on selector change', () => {
    mockByKey = {
      getSymbols: apiOk({
        symbols: [
          { symbol: 'EURUSD', candles: 1000 },
          { symbol: 'GBPUSD', candles: 800 },
        ],
      }),
    }
    render(<Symbols />)
    const select = document.querySelector('select')
    fireEvent.change(select, { target: { value: 'GBPUSD' } })
    expect(select.value).toBe('GBPUSD')
  })
})
