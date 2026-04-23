/**
 * Tests for dashboard P1 widgets: EquityChart, ModelDecision
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

let mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({ default: () => mockApiReturn }))

// Stub recharts
vi.mock('recharts', () => {
  const React = require('react')
  const Stub = (name) => ({ children, ...props }) =>
    React.createElement('div', { 'data-testid': `recharts-${name}` }, children)
  return {
    AreaChart: Stub('area-chart'),
    Area: Stub('area'),
    XAxis: Stub('xaxis'),
    YAxis: Stub('yaxis'),
    CartesianGrid: Stub('grid'),
    Tooltip: Stub('tooltip'),
    ResponsiveContainer: ({ children }) =>
      React.createElement('div', { 'data-testid': 'responsive-container' }, children),
  }
})

// ===================== EquityChart =====================
import EquityChart from '../components/dashboard/EquityChart'

describe('EquityChart', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    mockApiReturn = { data: [], loading: false, error: null, refetch: vi.fn() }
    render(<EquityChart />)
    expect(screen.getByText(/Equity/i)).toBeInTheDocument()
  })

  it('shows chart when data available', () => {
    mockApiReturn = {
      data: [
        { date: '2025-01-01', equity: 10000 },
        { date: '2025-01-02', equity: 10200 },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<EquityChart />)
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    mockApiReturn = { data: null, loading: true, error: null, refetch: vi.fn() }
    render(<EquityChart />)
    // LoadingSpinner should be present
    const spinner = document.querySelector('[class*="animate"]')
    expect(spinner).toBeTruthy()
  })
})

// ===================== ModelDecision =====================
import ModelDecision from '../components/dashboard/ModelDecision'

describe('ModelDecision', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    render(<ModelDecision wsPredictions={[]} />)
    expect(screen.getByRole('heading', { name: /Prediction/i })).toBeInTheDocument()
  })

  it('shows prediction from API data', () => {
    mockApiReturn = {
      data: [
        {
          symbol: 'EURUSD', model: 'xgboost', signal: 'BUY',
          confidence: 0.85, timestamp: new Date().toISOString(),
        },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<ModelDecision wsPredictions={[]} />)
    expect(screen.getByText('BUY')).toBeInTheDocument()
    expect(screen.getByText(/EURUSD/)).toBeInTheDocument()
  })

  it('falls back to websocket predictions', () => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
    render(
      <ModelDecision
        wsPredictions={[{
          symbol: 'GBPUSD', model: 'linear', signal: 'SELL',
          confidence: 0.6, timestamp: new Date().toISOString(),
        }]}
      />
    )
    expect(screen.getByText('SELL')).toBeInTheDocument()
  })

  it('shows empty state with no data', () => {
    render(<ModelDecision wsPredictions={[]} />)
    // Should render without crash
    expect(screen.getByRole('heading', { name: /Prediction/i })).toBeInTheDocument()
  })
})
