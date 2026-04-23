/**
 * Sidebar tests — covers botStatus card and formatUptime branches.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

let mockData = null
vi.mock('../hooks/useApi', () => ({
  default: () => ({ data: mockData, loading: false, error: null, refetch: vi.fn() }),
}))

vi.mock('../services/api', () => ({
  api: { getBotStatus: vi.fn() },
}))

import Sidebar from '../components/Sidebar'

const renderWithRouter = () =>
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>
  )

beforeEach(() => {
  mockData = null
})

describe('Sidebar', () => {
  it('renders nav items and shows Bot Offline when no status', () => {
    renderWithRouter()
    expect(screen.getByText('AutoTrader')).toBeInTheDocument()
    expect(screen.getByText('Control Tower')).toBeInTheDocument()
    expect(screen.getByText('Bot Offline')).toBeInTheDocument()
  })

  it('renders Bot Running with uptime hours+minutes', () => {
    mockData = {
      status: 'running',
      symbols_active: 5,
      models_active: 3,
      uptime_seconds: 3*3600 + 15*60,
    }
    renderWithRouter()
    expect(screen.getByText('Bot Running')).toBeInTheDocument()
    expect(screen.getByText('3h 15m')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('renders uptime in minutes only when < 1h', () => {
    mockData = { status: 'running', uptime_seconds: 45 * 60 }
    renderWithRouter()
    expect(screen.getByText('45m')).toBeInTheDocument()
  })

  it('renders "-" when uptime is undefined', () => {
    mockData = { status: 'idle' }
    renderWithRouter()
    expect(screen.getAllByText('-').length).toBeGreaterThan(0)
  })

  it('renders 0m when uptime_seconds is 0', () => {
    mockData = { status: 'running', uptime_seconds: 0 }
    renderWithRouter()
    expect(screen.getByText('0m')).toBeInTheDocument()
  })
})
