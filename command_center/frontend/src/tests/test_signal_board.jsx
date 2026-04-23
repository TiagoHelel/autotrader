import { render, screen, waitFor } from '@testing-library/react'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import ThemeProvider from '../theme/ThemeProvider'

// Mock the api module — SignalBoard reads via api.getRadarSignals().
const mockRadar = vi.fn()
vi.mock('../services/api', () => ({
  api: {
    getRadarSignals: () => mockRadar(),
  },
  WS_URL: 'ws://localhost:8000/ws',
}))

import SignalBoard from '../components/control_tower/SignalBoard'

function renderBoard() {
  return render(
    <ThemeProvider>
      <SignalBoard />
    </ThemeProvider>,
  )
}

describe('SignalBoard', () => {
  beforeEach(() => {
    mockRadar.mockReset()
    localStorage.clear()
  })

  test('renders header', async () => {
    mockRadar.mockResolvedValue({
      signals: [], breakdown: { BUY: 0, SELL: 0, HOLD: 0 }, total: 0,
    })
    renderBoard()
    expect(screen.getByText(/Signal Board/i)).toBeInTheDocument()
  })

  test('renders signals from API', async () => {
    mockRadar.mockResolvedValue({
      signals: [
        { symbol: 'EURUSD', signal: 'BUY', confidence: 0.8 },
        { symbol: 'GBPUSD', signal: 'SELL', confidence: 0.6 },
      ],
      breakdown: { BUY: 1, SELL: 1, HOLD: 0 },
      total: 2,
    })
    renderBoard()
    expect(await screen.findByText('EURUSD')).toBeInTheDocument()
    expect(await screen.findByText('GBPUSD')).toBeInTheDocument()
  })

  test('displays signal badges (BUY/SELL/HOLD)', async () => {
    mockRadar.mockResolvedValue({
      signals: [
        { symbol: 'EURUSD', signal: 'BUY', confidence: 0.8 },
        { symbol: 'USDJPY', signal: 'HOLD', confidence: 0.3 },
      ],
      breakdown: { BUY: 1, SELL: 0, HOLD: 1 },
      total: 2,
    })
    renderBoard()
    await waitFor(() => expect(screen.getByText('[BUY]')).toBeInTheDocument())
    expect(screen.getByText('[HOLD]')).toBeInTheDocument()
  })

  test('handles empty signals gracefully', async () => {
    mockRadar.mockResolvedValue({
      signals: [], breakdown: { BUY: 0, SELL: 0, HOLD: 0 }, total: 0,
    })
    renderBoard()
    expect(await screen.findByText(/Waiting for signals/i)).toBeInTheDocument()
  })

  test('sorts by confidence descending', async () => {
    mockRadar.mockResolvedValue({
      signals: [
        { symbol: 'LOW', signal: 'BUY', confidence: 0.3 },
        { symbol: 'HIGH', signal: 'BUY', confidence: 0.9 },
        { symbol: 'MID', signal: 'BUY', confidence: 0.6 },
      ],
      breakdown: { BUY: 3, SELL: 0, HOLD: 0 },
      total: 3,
    })
    const { container } = renderBoard()
    await screen.findByText('HIGH')
    const rows = container.querySelectorAll('.signal-row')
    expect(rows.length).toBe(3)
    expect(rows[0].textContent).toContain('HIGH')
    expect(rows[1].textContent).toContain('MID')
    expect(rows[2].textContent).toContain('LOW')
  })
})
