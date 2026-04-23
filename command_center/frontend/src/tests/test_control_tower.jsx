import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import ThemeProvider from '../theme/ThemeProvider'

// useWebSocket supplies KPIs to Control Tower — give it plausible data.
vi.mock('../hooks/useWebSocket', () => ({
  default: () => ({
    ticks: {},
    logs: [],
    kpis: {
      pnl: 1234.56,
      equity: 10000,
      balance: 9800,
      drawdown: 0.02,
      win_rate: 0.58,
      sharpe: 1.4,
      trend_30d: [1, 2, 3, 4, 5],
    },
    predictions: [],
    connected: true,
  }),
}))

// Return a response shape that satisfies every consumer downstream.
// Arrays are needed by history/sparkline components; objects are needed by
// signals/predictions panels. Pick the right shape per endpoint name.
vi.mock('../services/api', () => {
  const arrayLikeKeys = /history|Logs|Positions|Predictions|Experiments|Symbols/i
  return {
    api: new Proxy({}, {
      get: (_, key) => () => {
        if (typeof key === 'string' && arrayLikeKeys.test(key)) return Promise.resolve([])
        return Promise.resolve({
          signals: [],
          candles: [],
          breakdown: { BUY: 0, SELL: 0, HOLD: 0 },
          total: 0,
        })
      },
    }),
    WS_URL: 'ws://localhost:8000/ws',
  }
})

// The real WorldMap / LivePredictionChart depend on WebGL / canvas libs that
// are painful in jsdom. Replace them with stubs.
vi.mock('../components/control_tower/WorldMap', () => ({
  default: () => <div data-testid="worldmap-stub" />,
}))
vi.mock('../components/control_tower/LivePredictionChart', () => ({
  default: () => <div data-testid="livechart-stub" />,
}))

import ControlTower from '../pages/ControlTower'

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ControlTower />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ControlTower page', () => {
  beforeEach(() => localStorage.clear())

  test('renders the Control Tower title', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Control Tower|CONTROL NODE/i)).toBeInTheDocument()
    })
  })

  test('renders KPI strip (has at least one KPI-related label)', async () => {
    renderPage()
    // KPICards renders labels like "PnL", "Equity", "Win Rate"…
    await waitFor(() => {
      const candidates = screen.queryAllByText(/PnL|Equity|Win Rate|Sharpe|Balance/i)
      expect(candidates.length).toBeGreaterThan(0)
    })
  })
})
