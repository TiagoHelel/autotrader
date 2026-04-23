import { render } from '@testing-library/react'
import { describe, test, vi, beforeEach } from 'vitest'
import ThemeProvider from '../theme/ThemeProvider'

// lightweight-charts + jsdom don't play well (no canvas). Stub the lib.
vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    applyOptions: () => {},
    addSeries: () => ({
      setData: () => {},
      update: () => {},
      applyOptions: () => {},
      priceScale: () => ({ applyOptions: () => {} }),
    }),
    timeScale: () => ({ fitContent: () => {}, applyOptions: () => {} }),
    priceScale: () => ({ applyOptions: () => {} }),
    subscribeCrosshairMove: () => {},
    unsubscribeCrosshairMove: () => {},
    remove: () => {},
    resize: () => {},
  }),
  CrosshairMode: { Normal: 0, Magnet: 1 },
  CandlestickSeries: 'CandlestickSeries',
  createSeriesMarkers: () => ({ setMarkers: () => {}, detach: () => {} }),
}))

const mockGetCandles = vi.fn()
const mockGetLatest = vi.fn()

vi.mock('../services/api', () => ({
  api: {
    getCandles: (...args) => mockGetCandles(...args),
    getLatestPrediction: (...args) => mockGetLatest(...args),
  },
  WS_URL: 'ws://localhost:8000/ws',
}))

import LivePredictionChart from '../components/control_tower/LivePredictionChart'

function renderChart(props = {}) {
  return render(
    <ThemeProvider>
      <LivePredictionChart {...props} />
    </ThemeProvider>,
  )
}

describe('LivePredictionChart', () => {
  beforeEach(() => {
    mockGetCandles.mockResolvedValue({ candles: [] })
    mockGetLatest.mockResolvedValue(null)
    localStorage.clear()
  })

  test('renders without crashing (default symbol)', () => {
    renderChart()
  })

  test('accepts a symbol prop', () => {
    renderChart({ symbol: 'GBPUSD' })
  })

  test('handles valid candle data', async () => {
    mockGetCandles.mockResolvedValue({
      candles: [
        { time: 1700000000, open: 1.1, high: 1.11, low: 1.09, close: 1.105 },
        { time: 1700000060, open: 1.105, high: 1.115, low: 1.1, close: 1.11 },
      ],
    })
    mockGetLatest.mockResolvedValue({ ensemble: { t1: 1.112, t2: 1.113, t3: 1.114 } })
    renderChart({ symbol: 'EURUSD' })
  })
})
