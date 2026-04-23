/**
 * TrendSparklineCard tests — covers the useMemo path (points/pct/color/path).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

let mockApiState = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({ default: () => mockApiState }))
vi.mock('../services/api', () => ({ api: { getEquityHistory: vi.fn() } }))

let currentTheme = 'dark'
vi.mock('../theme/ThemeProvider', () => ({
  useTheme: () => ({ theme: currentTheme, setTheme: vi.fn() }),
}))

import TrendSparklineCard from '../components/dashboard/TrendSparklineCard'

beforeEach(() => {
  mockApiState = { data: null, loading: false, error: null, refetch: vi.fn() }
  currentTheme = 'dark'
})

describe('TrendSparklineCard', () => {
  it('shows loading state', () => {
    mockApiState = { data: null, loading: true, error: null, refetch: vi.fn() }
    render(<TrendSparklineCard />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows "No data" when data empty', () => {
    mockApiState = { data: [], loading: false, error: null, refetch: vi.fn() }
    render(<TrendSparklineCard />)
    expect(screen.getByText('No data')).toBeInTheDocument()
  })

  it('renders sparkline with positive trend (green)', () => {
    mockApiState = {
      data: [
        { equity: 10000 },
        { equity: 10100 },
        { equity: 10300 },
        { equity: 10450 },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<TrendSparklineCard label="30D Equity" />)
    expect(screen.getByText('30D Equity')).toBeInTheDocument()
    expect(screen.getByText(/\+4\.\d+%/)).toBeInTheDocument()
  })

  it('renders sparkline with negative trend (red)', () => {
    mockApiState = {
      data: [
        { equity: 10000 },
        { equity: 9500 },
        { equity: 9200 },
      ],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<TrendSparklineCard />)
    expect(screen.getByText(/-8\.\d+%/)).toBeInTheDocument()
  })

  it('renders matrix variant', () => {
    currentTheme = 'matrix'
    mockApiState = {
      data: [{ equity: 100 }, { equity: 110 }],
      loading: false, error: null, refetch: vi.fn(),
    }
    render(<TrendSparklineCard label="TREND" />)
    expect(screen.getByText('TREND')).toBeInTheDocument()
  })
})
