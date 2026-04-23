import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Stub child components — they have their own heavy API calls
vi.mock('../components/positions/OpenPositions', () => ({
  default: () => <div data-testid="open-positions">OpenPositions</div>,
}))
vi.mock('../components/positions/TradeHistory', () => ({
  default: () => <div data-testid="trade-history">TradeHistory</div>,
}))

import Positions from '../pages/Positions'

describe('Positions page', () => {
  it('renders heading and description', () => {
    render(<Positions />)
    expect(screen.getByText('Positions')).toBeInTheDocument()
    expect(screen.getByText('Open positions and trade history')).toBeInTheDocument()
  })

  it('renders OpenPositions and TradeHistory children', () => {
    render(<Positions />)
    expect(screen.getByTestId('open-positions')).toBeInTheDocument()
    expect(screen.getByTestId('trade-history')).toBeInTheDocument()
  })
})
