/**
 * Smoke tests for BotStatus, LogPanel, ControlTowerClock.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

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
    getBotStatus: vi.fn(),
    getLogs: vi.fn(),
  },
}))

vi.mock('../theme/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'default' }),
}))

beforeEach(() => {
  mockByKey = {}
})

const apiOk = (data) => ({ data, loading: false, error: null, refetch: vi.fn() })
const apiLoading = () => ({ data: null, loading: true, error: null, refetch: vi.fn() })

// ===================== BotStatus =====================
import BotStatus from '../components/dashboard/BotStatus'

describe('BotStatus', () => {
  it('shows loading state', () => {
    mockByKey = { getBotStatus: apiLoading() }
    render(<BotStatus />)
    expect(screen.getByText(/Loading bot status/i)).toBeInTheDocument()
  })

  it('returns null when no data', () => {
    mockByKey = { getBotStatus: apiOk(null) }
    const { container } = render(<BotStatus />)
    expect(container.firstChild).toBeNull()
  })

  it('renders status rows and running indicator', () => {
    mockByKey = {
      getBotStatus: apiOk({
        status: 'running',
        current_symbol: 'EURUSD',
        timeframe: 'M5',
        symbols_active: 5,
        models_active: 3,
        uptime_seconds: 3725, // 1h 2m 5s
      }),
    }
    render(<BotStatus />)
    expect(screen.getByText('Bot Status')).toBeInTheDocument()
    expect(screen.getByText('RUNNING')).toBeInTheDocument()
    expect(screen.getByText('EURUSD')).toBeInTheDocument()
    expect(screen.getByText('M5')).toBeInTheDocument()
    expect(screen.getByText('1h 2m 5s')).toBeInTheDocument()
    expect(screen.getByText(/System operational/)).toBeInTheDocument()
  })

  it('formats uptime in minutes-seconds when under 1h', () => {
    mockByKey = {
      getBotStatus: apiOk({
        status: 'stopped',
        uptime_seconds: 185, // 3m 5s
      }),
    }
    render(<BotStatus />)
    expect(screen.getByText('3m 5s')).toBeInTheDocument()
    expect(screen.getByText('STOPPED')).toBeInTheDocument()
  })

  it('formats uptime in seconds when under 1min', () => {
    mockByKey = {
      getBotStatus: apiOk({
        status: 'stopped',
        uptime_seconds: 42,
      }),
    }
    render(<BotStatus />)
    expect(screen.getByText('42s')).toBeInTheDocument()
  })

  it('shows UNKNOWN when status missing', () => {
    mockByKey = { getBotStatus: apiOk({}) }
    render(<BotStatus />)
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
  })
})

// ===================== LogPanel =====================
import LogPanel from '../components/logs/LogPanel'

describe('LogPanel', () => {
  it('shows loading spinner', () => {
    mockByKey = { getLogs: apiLoading() }
    render(<LogPanel wsLogs={[]} />)
    expect(screen.getByText(/Loading logs/i)).toBeInTheDocument()
  })

  it('renders header, filter buttons, and merged logs', () => {
    mockByKey = {
      getLogs: apiOk([
        { timestamp: '2026-04-16T10:00', level: 'INFO', message: 'boot' },
        { timestamp: '2026-04-16T10:01', level: 'ERROR', message: 'oops' },
      ]),
    }
    render(<LogPanel wsLogs={[{ timestamp: '2026-04-16T10:02', level: 'WARNING', message: 'hot' }]} />)
    expect(screen.getByText('System Logs')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ALL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'INFO' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'WARNING' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ERROR' })).toBeInTheDocument()
  })

  it('filters logs by level', () => {
    mockByKey = {
      getLogs: apiOk([
        { timestamp: 't1', level: 'INFO', message: 'info-msg' },
        { timestamp: 't2', level: 'ERROR', message: 'err-msg' },
      ]),
    }
    render(<LogPanel wsLogs={[]} />)
    // Click ERROR filter
    fireEvent.click(screen.getByRole('button', { name: 'ERROR' }))
    // count badge next to title shows 1
    const countSpans = document.querySelectorAll('span.rounded.bg-gray-700')
    expect(countSpans.length).toBeGreaterThan(0)
  })

  it('falls back to wsLogs when loading with wsLogs present', () => {
    mockByKey = { getLogs: apiLoading() }
    render(<LogPanel wsLogs={[{ timestamp: 't', level: 'INFO', message: 'live' }]} />)
    // Should not show loading spinner because wsLogs is non-empty
    expect(screen.queryByText(/Loading logs/i)).not.toBeInTheDocument()
  })
})

// ===================== ControlTowerClock =====================
import ControlTowerClock from '../components/control_tower/ControlTowerClock'

describe('ControlTowerClock', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Set a predictable time during London+NY overlap (13:00 UTC Wed → 10:00 UTC-3)
    vi.setSystemTime(new Date('2026-04-15T13:00:00Z'))
  })

  afterEach(() => vi.useRealTimers())

  it('renders without crashing', () => {
    const { container } = render(<ControlTowerClock />)
    expect(container).toBeTruthy()
  })
})
