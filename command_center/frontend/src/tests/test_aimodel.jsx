import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../components/ai/FeatureImportance', () => ({
  default: () => <div data-testid="feature-importance">FeatureImportance</div>,
}))
vi.mock('../components/ai/Predictions', () => ({
  default: () => <div data-testid="predictions">Predictions</div>,
}))
vi.mock('../components/ai/ModelMetrics', () => ({
  default: () => <div data-testid="model-metrics">ModelMetrics</div>,
}))

import AIModel from '../pages/AIModel'

describe('AIModel page', () => {
  it('renders heading and description', () => {
    render(<AIModel />)
    expect(screen.getByText('AI / Model')).toBeInTheDocument()
    expect(screen.getByText('Model performance and predictions')).toBeInTheDocument()
  })

  it('renders all three child components', () => {
    render(<AIModel />)
    expect(screen.getByTestId('model-metrics')).toBeInTheDocument()
    expect(screen.getByTestId('feature-importance')).toBeInTheDocument()
    expect(screen.getByTestId('predictions')).toBeInTheDocument()
  })
})
