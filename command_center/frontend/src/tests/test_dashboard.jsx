import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock useWebSocket
const mockWs = { ticks: {}, logs: [], kpis: null, predictions: [], connected: false }
vi.mock('../hooks/useWebSocket', () => ({ default: () => mockWs }))

// Mock useApi — returns configurable data
let mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({ default: () => mockApiReturn }))

// Stub heavy child components
vi.mock('../components/dashboard/KPICards', () => ({
  default: ({ wsKpis }) => <div data-testid="kpi-cards">{wsKpis ? 'has-kpis' : 'no-kpis'}</div>,
}))
vi.mock('../components/dashboard/EquityChart', () => ({
  default: () => <div data-testid="equity-chart">EquityChart</div>,
}))
vi.mock('../components/dashboard/BotStatus', () => ({
  default: () => <div data-testid="bot-status">BotStatus</div>,
}))
vi.mock('../components/dashboard/ModelDecision', () => ({
  default: ({ wsPredictions }) => (
    <div data-testid="model-decision">{wsPredictions?.length || 0} preds</div>
  ),
}))

import Dashboard from '../pages/Dashboard'

describe('Dashboard page', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    render(<Dashboard />)
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Real-time trading overview')).toBeInTheDocument()
  })

  it('renders child components', () => {
    render(<Dashboard />)
    expect(screen.getByTestId('kpi-cards')).toBeInTheDocument()
    expect(screen.getByTestId('equity-chart')).toBeInTheDocument()
    expect(screen.getByTestId('bot-status')).toBeInTheDocument()
    expect(screen.getByTestId('model-decision')).toBeInTheDocument()
  })

  it('passes kpis to KPICards', () => {
    mockWs.kpis = { balance: 10000 }
    render(<Dashboard />)
    expect(screen.getByTestId('kpi-cards')).toHaveTextContent('has-kpis')
    mockWs.kpis = null
  })

  it('BestModelCard hidden when no data', () => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
    render(<Dashboard />)
    expect(screen.queryByText('Best Model')).not.toBeInTheDocument()
  })

  it('BestModelCard shows model info when data available', () => {
    mockApiReturn = {
      data: {
        model: {
          model: 'xgboost',
          pnl_total: 42.5,
          sharpe: 1.23,
          max_drawdown: -8.1,
          accuracy: 65.2,
          feature_set: 'technical+regime',
        },
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    }
    render(<Dashboard />)
    expect(screen.getByText('Best Model')).toBeInTheDocument()
    expect(screen.getByText('xgboost')).toBeInTheDocument()
    expect(screen.getByText('technical+regime')).toBeInTheDocument()
    expect(screen.getByText(/42\.5 pips/)).toBeInTheDocument()
    expect(screen.getByText('1.23')).toBeInTheDocument()
    expect(screen.getByText('-8.1')).toBeInTheDocument()
    expect(screen.getByText('65.2%')).toBeInTheDocument()
  })

  it('BestModelCard handles alternative field names (pnl vs pnl_total)', () => {
    mockApiReturn = {
      data: { model: { model: 'rf', pnl: 20.0, avg_sharpe: 0.5, drawdown: -3.0 } },
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<Dashboard />)
    expect(screen.getByText(/20\.0 pips/)).toBeInTheDocument()
    expect(screen.getByText('0.50')).toBeInTheDocument()
  })

  it('BestModelCard hides accuracy when null', () => {
    mockApiReturn = {
      data: { model: { model: 'xgb', pnl: 10 } },
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<Dashboard />)
    expect(screen.queryByText('Accuracy:')).not.toBeInTheDocument()
  })
})
