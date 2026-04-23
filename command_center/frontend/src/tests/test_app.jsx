import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, test, vi, beforeEach } from 'vitest'
import ThemeProvider from '../theme/ThemeProvider'

// Mock useWebSocket so App tree doesn't attempt a real WebSocket connection.
vi.mock('../hooks/useWebSocket', () => ({
  default: () => ({
    ticks: {},
    logs: [],
    kpis: null,
    predictions: [],
    connected: false,
  }),
}))

// Mock api service so lazy-loaded pages don't hit the network.
vi.mock('../services/api', () => ({
  api: new Proxy({}, { get: () => () => Promise.resolve({}) }),
  WS_URL: 'ws://localhost:8000/ws',
}))

import App from '../App'

describe('App', () => {
  beforeEach(() => {
    // reset localStorage so ThemeProvider is deterministic
    localStorage.clear()
  })

  test('renders without crashing', () => {
    render(
      <MemoryRouter initialEntries={['/control-tower']}>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </MemoryRouter>,
    )
  })
})
