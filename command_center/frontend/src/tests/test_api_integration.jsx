import { render, screen, waitFor } from '@testing-library/react'
import { describe, test, expect, beforeAll, afterAll, afterEach, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import ThemeProvider from '../theme/ThemeProvider'
import { server } from './mocks/server'
import { handlers } from './mocks/handlers'

// Provide fetch in node — vitest 4 uses node's global fetch, MSW intercepts it.
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => server.resetHandlers(...handlers))
afterAll(() => server.close())

// Don't mock the api service — we want the real fetch path, intercepted by MSW.
vi.unmock('../services/api')

import SignalBoard from '../components/control_tower/SignalBoard'

function renderBoard() {
  return render(
    <ThemeProvider>
      <SignalBoard />
    </ThemeProvider>,
  )
}

describe('API integration (MSW)', () => {
  test('SignalBoard fetches and displays signals from /api/predict/signals/radar', async () => {
    renderBoard()
    expect(await screen.findByText('EURUSD')).toBeInTheDocument()
    expect(screen.getByText('GBPUSD')).toBeInTheDocument()
  })

  test('confidence values from API are within [0, 1]', async () => {
    // Attach a side-effect handler that asserts the contract.
    let captured = null
    server.use(
      http.get(/\/api\/predict\/signals\/radar$/, () => {
        captured = {
          signals: [
            { symbol: 'EURUSD', signal: 'BUY', confidence: 0.75 },
            { symbol: 'GBPUSD', signal: 'SELL', confidence: 0.12 },
          ],
          breakdown: { BUY: 1, SELL: 1, HOLD: 0 },
          total: 2,
        }
        return HttpResponse.json(captured)
      }),
    )
    renderBoard()
    await waitFor(() => expect(screen.getByText('EURUSD')).toBeInTheDocument())
    captured.signals.forEach((s) => {
      expect(s.confidence).toBeGreaterThanOrEqual(0)
      expect(s.confidence).toBeLessThanOrEqual(1)
    })
  })

  test('handles API error gracefully (no crash)', async () => {
    server.use(
      http.get(/\/api\/predict\/signals\/radar$/, () =>
        HttpResponse.json({ error: 'boom' }, { status: 500 }),
      ),
    )
    renderBoard()
    // Should render the empty state ("Waiting for signals...") without throwing.
    await waitFor(() => {
      expect(screen.getByText(/Waiting for signals/i)).toBeInTheDocument()
    })
  })
})
