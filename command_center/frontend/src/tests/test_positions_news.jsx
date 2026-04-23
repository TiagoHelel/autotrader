/**
 * Tests for positions and news P1 widgets:
 * OpenPositions, TradeHistory, NewsFeed, CurrencyScore
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

let mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({ default: () => mockApiReturn }))

vi.mock('../services/api', () => ({
  api: {
    getPositions: vi.fn(),
    getPositionHistory: vi.fn(),
    getNews: vi.fn(),
  },
}))

// ===================== OpenPositions =====================
import OpenPositions from '../components/positions/OpenPositions'

describe('OpenPositions', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    render(<OpenPositions />)
    expect(screen.getByRole('heading', { name: /Open Positions/i })).toBeInTheDocument()
  })

  it('shows table headers', () => {
    mockApiReturn = {
      data: [
        {
          symbol: 'EURUSD', type: 'BUY', volume: 0.1,
          open_price: 1.10000, current_price: 1.10200,
          sl: 1.09500, tp: 1.11000, profit: 20.0,
        },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<OpenPositions />)
    expect(screen.getByText('Symbol')).toBeInTheDocument()
    expect(screen.getByText('Volume')).toBeInTheDocument()
  })

  it('shows positions when data available', () => {
    mockApiReturn = {
      data: [
        {
          symbol: 'EURUSD', type: 'BUY', volume: 0.1,
          open_price: 1.10000, current_price: 1.10200,
          sl: 1.09500, tp: 1.11000, profit: 20.0,
        },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<OpenPositions />)
    expect(screen.getByText('EURUSD')).toBeInTheDocument()
    expect(screen.getByText('BUY')).toBeInTheDocument()
  })

  it('shows empty state', () => {
    mockApiReturn = { data: [], loading: false, error: null, refetch: vi.fn() }
    render(<OpenPositions />)
    expect(screen.getByText(/no.*position/i)).toBeInTheDocument()
  })

  it('shows loading state', () => {
    mockApiReturn = { data: null, loading: true, error: null, refetch: vi.fn() }
    render(<OpenPositions />)
    const spinner = document.querySelector('[class*="animate"]')
    expect(spinner).toBeTruthy()
  })
})

// ===================== TradeHistory =====================
import TradeHistory from '../components/positions/TradeHistory'

describe('TradeHistory', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    render(<TradeHistory />)
    expect(screen.getByRole('heading', { name: /Trade History/i })).toBeInTheDocument()
  })

  it('shows trades', () => {
    mockApiReturn = {
      data: [
        {
          symbol: 'GBPUSD', type: 'SELL', volume: 0.2,
          open_price: 1.25000, close_price: 1.24500,
          profit: 100.0, duration_minutes: 45,
          close_time: new Date().toISOString(),
        },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<TradeHistory />)
    expect(screen.getByText('GBPUSD')).toBeInTheDocument()
    expect(screen.getByText('SELL')).toBeInTheDocument()
  })

  it('shows empty state', () => {
    mockApiReturn = { data: [], loading: false, error: null, refetch: vi.fn() }
    render(<TradeHistory />)
    expect(screen.getByText(/no.*trade/i)).toBeInTheDocument()
  })

  it('shows pagination controls', () => {
    // Generate 20 trades to trigger pagination (15 per page)
    const trades = Array.from({ length: 20 }, (_, i) => ({
      symbol: 'EURUSD', type: 'BUY', volume: 0.1,
      open_price: 1.1, close_price: 1.1 + i * 0.0001,
      profit: i * 5, duration_minutes: 30,
      close_time: new Date(2025, 0, i + 1).toISOString(),
    }))
    mockApiReturn = { data: trades, loading: false, error: null, refetch: vi.fn() }
    render(<TradeHistory />)
    // Should have page navigation text "Page 1 of N"
    expect(screen.getByText(/Page 1 of/)).toBeInTheDocument()
  })
})

// ===================== NewsFeed =====================
import NewsFeed from '../components/news/NewsFeed'

describe('NewsFeed', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    render(<NewsFeed />)
    expect(screen.getByText(/News Feed/i)).toBeInTheDocument()
  })

  it('shows news items', () => {
    mockApiReturn = {
      data: [
        {
          title: 'US GDP Q4', country: 'US', currency: 'USD',
          impact: 'high', sentiment_score: 0.7, score: 0.7,
          source: 'Investing.com', timestamp: new Date().toISOString(),
        },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<NewsFeed />)
    expect(screen.getByText('US GDP Q4')).toBeInTheDocument()
  })

  it('shows empty state', () => {
    mockApiReturn = { data: [], loading: false, error: null, refetch: vi.fn() }
    render(<NewsFeed />)
    expect(screen.getByText(/no.*news/i)).toBeInTheDocument()
  })
})

// ===================== CurrencyScore =====================
import CurrencyScore from '../components/news/CurrencyScore'

describe('CurrencyScore', () => {
  beforeEach(() => {
    mockApiReturn = { data: null, loading: false, error: null, refetch: vi.fn() }
  })

  it('renders heading', () => {
    render(<CurrencyScore />)
    expect(screen.getByText(/Currency Sentiment/i)).toBeInTheDocument()
  })

  it('aggregates by currency', () => {
    mockApiReturn = {
      data: [
        { currency: 'USD', sentiment_score: 0.8 },
        { currency: 'USD', sentiment_score: 0.4 },
        { currency: 'EUR', sentiment_score: -0.3 },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<CurrencyScore />)
    expect(screen.getByText('USD')).toBeInTheDocument()
    expect(screen.getByText('EUR')).toBeInTheDocument()
  })

  it('shows empty state', () => {
    mockApiReturn = { data: [], loading: false, error: null, refetch: vi.fn() }
    render(<CurrencyScore />)
    expect(screen.getByText(/no.*sentiment/i)).toBeInTheDocument()
  })
})
