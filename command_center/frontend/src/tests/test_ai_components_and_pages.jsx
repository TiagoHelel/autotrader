/**
 * Coverage push: AI components (FeatureImportance, ModelMetrics, Predictions)
 * plus loaded-state branches of Backtest, Experiments and Symbols pages.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ---- useApi routed mock ----
let mockByKey = {}
const mockApiDefault = { data: null, loading: false, error: null, refetch: vi.fn() }
vi.mock('../hooks/useApi', () => ({
  default: (fetcher) => {
    const src = (fetcher && fetcher.toString && fetcher.toString()) || ''
    const m = src.match(/api\.(\w+)/)
    const key = m ? m[1] : null
    return mockByKey[key] || mockApiDefault
  },
}))

vi.mock('../services/api', () => ({
  api: {
    // ai
    getModelFeatures: vi.fn(),
    getModelMetrics: vi.fn(),
    getPredictions: vi.fn(),
    // backtest
    getBacktestSummary: vi.fn(),
    getSymbols: vi.fn(),
    runBacktest: vi.fn().mockResolvedValue({ status: 'started' }),
    getBacktestEquity: vi.fn(),
    getBacktestResults: vi.fn(),
    // experiments
    getExperimentsSummary: vi.fn(),
    getExperiments: vi.fn(),
    getFeatureExperiments: vi.fn(),
    runExperiments: vi.fn().mockResolvedValue({ status: 'started' }),
    // symbols
    getCandles: vi.fn(),
    getPredictPredictions: vi.fn(),
    getPredictionsDetail: vi.fn(),
    getRegimeCurrent: vi.fn(),
    getNewsFeatures: vi.fn(),
    getNewsBySymbol: vi.fn(),
  },
}))

// Stub recharts for jsdom
vi.mock('recharts', () => {
  const React = require('react')
  const Stub = (name) => ({ children }) =>
    React.createElement('div', { 'data-testid': `recharts-${name}` }, children)
  return {
    LineChart: Stub('line-chart'),
    Line: Stub('line'),
    AreaChart: Stub('area-chart'),
    Area: Stub('area'),
    BarChart: Stub('bar-chart'),
    Bar: Stub('bar'),
    ComposedChart: Stub('composed-chart'),
    XAxis: Stub('xaxis'),
    YAxis: Stub('yaxis'),
    CartesianGrid: Stub('grid'),
    Tooltip: Stub('tooltip'),
    Legend: Stub('legend'),
    ResponsiveContainer: ({ children }) =>
      React.createElement('div', { 'data-testid': 'responsive-container' }, children),
  }
})

beforeEach(() => {
  mockByKey = {}
})

const apiOk = (data) => ({ data, loading: false, error: null, refetch: vi.fn() })
const apiLoading = () => ({ data: null, loading: true, error: null, refetch: vi.fn() })

// =========================================================
// FeatureImportance
// =========================================================
import FeatureImportance from '../components/ai/FeatureImportance'

describe('FeatureImportance', () => {
  it('renders loading state', () => {
    mockByKey = { getModelFeatures: apiLoading() }
    render(<FeatureImportance />)
    expect(document.querySelector('[class*="animate-spin"]')).toBeTruthy()
  })

  it('renders empty state when no features', () => {
    mockByKey = { getModelFeatures: apiOk(null) }
    render(<FeatureImportance />)
    expect(screen.getByText(/No feature data available/)).toBeInTheDocument()
  })

  it('renders with array data', () => {
    const feats = [
      { feature_name: 'rsi_14', importance: 0.42 },
      { feature_name: 'sma_20', importance: 0.31 },
      { feature_name: 'a_really_long_feature_name_that_should_be_truncated', importance: 0.12 },
    ]
    mockByKey = { getModelFeatures: apiOk(feats) }
    render(<FeatureImportance />)
    expect(screen.getByText(/Feature Importance/)).toBeInTheDocument()
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument()
  })

  it('renders with dict-of-models data', () => {
    mockByKey = {
      getModelFeatures: apiOk({
        xgboost: [
          { feature_name: 'momentum', importance: 0.5 },
          { feature_name: 'volatility', importance: 0.3 },
        ],
      }),
    }
    render(<FeatureImportance />)
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument()
  })
})

// =========================================================
// ModelMetrics
// =========================================================
import ModelMetrics from '../components/ai/ModelMetrics'

describe('ModelMetrics', () => {
  it('renders loading state', () => {
    mockByKey = { getModelMetrics: apiLoading() }
    render(<ModelMetrics />)
    expect(document.querySelector('[class*="animate-spin"]')).toBeTruthy()
  })

  it('renders empty state', () => {
    mockByKey = { getModelMetrics: apiOk([]) }
    render(<ModelMetrics />)
    expect(screen.getByText(/No model metrics available/)).toBeInTheDocument()
  })

  it('renders model cards with all timeAgo branches', () => {
    const now = Date.now()
    // ISO without trailing Z; component appends Z
    const iso = (offsetSec) =>
      new Date(now - offsetSec * 1000).toISOString().replace('Z', '')
    mockByKey = {
      getModelMetrics: apiOk([
        {
          model_name: 'xgb-secs',
          timestamp: iso(30), // < 60s
          accuracy: 0.65,
          precision_val: 0.6,
          recall: 0.7,
          f1: 0.62,
          auc: 0.8,
        },
        { model_name: 'xgb-mins', timestamp: iso(120), accuracy: 0.5 }, // minutes
        { model_name: 'xgb-hrs', timestamp: iso(7200), accuracy: 0.55 }, // hours
        { model_name: 'xgb-days', timestamp: iso(2 * 86400), accuracy: 0.6 }, // days
        { model_name: 'xgb-no-ts' }, // no timestamp branch
      ]),
    }
    render(<ModelMetrics />)
    expect(screen.getByText('xgb-secs')).toBeInTheDocument()
    expect(screen.getByText('xgb-no-ts')).toBeInTheDocument()
    expect(screen.getByText(/s ago/)).toBeInTheDocument()
    expect(screen.getByText(/m ago/)).toBeInTheDocument()
    expect(screen.getByText(/h ago/)).toBeInTheDocument()
    expect(screen.getByText(/d ago/)).toBeInTheDocument()
  })
})

// =========================================================
// Predictions
// =========================================================
import Predictions from '../components/ai/Predictions'

describe('Predictions component', () => {
  it('renders loading state', () => {
    mockByKey = { getPredictions: apiLoading() }
    render(<Predictions />)
    expect(document.querySelector('[class*="animate-spin"]')).toBeTruthy()
  })

  it('renders empty state', () => {
    mockByKey = { getPredictions: apiOk([]) }
    render(<Predictions />)
    expect(screen.getByText(/No predictions available/)).toBeInTheDocument()
  })

  it('renders table with BUY/SELL/HOLD + confidence + timeAgo', () => {
    const now = Date.now()
    const iso = (offsetSec) =>
      new Date(now - offsetSec * 1000).toISOString().replace('Z', '')
    mockByKey = {
      getPredictions: apiOk([
        { id: 1, symbol: 'EURUSD', signal: 'buy', confidence: 0.82, model_name: 'xgb', timestamp: iso(10) },
        { id: 2, symbol: 'GBPUSD', signal: 'sell', confidence: 0.55, model_name: 'xgb', timestamp: iso(200) },
        { id: 3, symbol: 'USDJPY', signal: null, confidence: null, model_name: null, timestamp: null },
        { id: 4, symbol: 'AUDUSD', signal: 'hold', confidence: 0.4, model_name: 'linear', timestamp: iso(5000) },
        { id: 5, symbol: 'NZDUSD', signal: 'buy', confidence: 0.7, model_name: 'xgb', timestamp: iso(100000) },
      ]),
    }
    render(<Predictions />)
    expect(screen.getByText('EURUSD')).toBeInTheDocument()
    expect(screen.getAllByText('BUY').length).toBeGreaterThan(0)
    expect(screen.getByText('SELL')).toBeInTheDocument()
    // null signal -> HOLD
    expect(screen.getAllByText('HOLD').length).toBeGreaterThan(0)
    // null timestamp shows '-'
    expect(screen.getAllByText('-').length).toBeGreaterThan(0)
  })
})

// =========================================================
// Backtest page — loaded states
// =========================================================
import Backtest from '../pages/Backtest'

describe('Backtest page (loaded)', () => {
  it('renders summary cards, equity curves and trades', () => {
    mockByKey = {
      getBacktestSummary: apiOk({
        summary: [
          { symbol: 'EURUSD', model: 'xgb', pnl_total: 42.5, sharpe: 1.2, max_drawdown: -5, winrate: 65, total_trades: 20 },
          { symbol: 'EURUSD', model: 'linear', pnl_total: -8.1, sharpe: 0.3, max_drawdown: -15, winrate: 40, total_trades: 10 },
        ],
      }),
      getSymbols: apiOk({ symbols: [{ symbol: 'EURUSD' }, { symbol: 'GBPUSD' }] }),
      getBacktestEquity: apiOk({
        curves: {
          xgb: { equity: [0, 5, 3, 10, 8] },
          linear: { equity: [0, -2, -4, -3, -6] },
        },
      }),
      getBacktestResults: apiOk({
        trades: [
          {
            entry_time: '2026-04-16T10:00:00',
            model: 'xgb',
            direction: 'BUY',
            entry_price: 1.1000,
            exit_price: 1.1020,
            pnl_pips: 20,
            expected_return: 0.002,
          },
          {
            entry_time: '2026-04-16T11:00:00',
            model: 'xgb',
            direction: 'SELL',
            entry_price: 1.1030,
            exit_price: 1.1015,
            pnl_pips: -15,
            expected_return: -0.001,
          },
        ],
      }),
    }
    render(<Backtest />)
    expect(screen.getByRole('heading', { name: /Backtest/ })).toBeInTheDocument()
    expect(screen.getAllByText(/xgb/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText('BUY').length).toBeGreaterThan(0)
    expect(screen.getAllByText('SELL').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('responsive-container').length).toBeGreaterThan(0)
  })

  it('run backtest button triggers api call', async () => {
    mockByKey = {
      getBacktestSummary: apiOk({ summary: [] }),
      getSymbols: apiOk({ symbols: [] }),
      getBacktestEquity: apiOk({ curves: {} }),
      getBacktestResults: apiOk({ trades: [] }),
    }
    const { api } = await import('../services/api')
    render(<Backtest />)
    await act(async () => {
      fireEvent.click(screen.getByText('Run Backtest'))
    })
    expect(api.runBacktest).toHaveBeenCalled()
    expect(screen.getByText('Running...')).toBeInTheDocument()
  })

  it('symbol selector changes active symbol', () => {
    mockByKey = {
      getBacktestSummary: apiOk({ summary: [] }),
      getSymbols: apiOk({ symbols: [{ symbol: 'EURUSD' }, { symbol: 'GBPUSD' }] }),
      getBacktestEquity: apiOk({ curves: {} }),
      getBacktestResults: apiOk({ trades: [] }),
    }
    render(<Backtest />)
    const select = document.querySelector('select')
    fireEvent.change(select, { target: { value: 'GBPUSD' } })
    expect(select.value).toBe('GBPUSD')
  })
})

// =========================================================
// Experiments page — loaded
// =========================================================
import Experiments from '../pages/Experiments'

describe('Experiments page (loaded)', () => {
  it('renders summary cards with selectable models', () => {
    mockByKey = {
      getExperimentsSummary: apiOk({
        summary: [
          { model: 'xgb', total_trainings: 12, avg_train_size: 1000, latest_accuracy: 62.5, latest_mae: 0.001, last_trained: '2026-04-16T10:00:00' },
          { model: 'linear', total_trainings: 8, avg_train_size: 500, latest_accuracy: 48.0, latest_mae: 0.005, last_trained: '2026-04-15T09:00:00' },
          { model: 'rf', total_trainings: 3, avg_train_size: 300, latest_accuracy: null, latest_mae: null, last_trained: '2026-04-14T08:00:00' },
        ],
      }),
      getExperiments: apiOk({
        experiments: [
          { timestamp: '2026-04-16T10:00:00', model: 'xgb', symbol: 'EURUSD', train_size: 1000, accuracy: 62.5, mae: 0.001, params: '{"lr":0.1}' },
          { timestamp: '2026-04-15T09:00:00', model: 'xgb', symbol: 'GBPUSD', train_size: 900, accuracy: 55.0, mae: null, params: null },
          { timestamp: null, model: 'xgb', symbol: 'USDJPY', train_size: 800, accuracy: null, mae: 0.002, params: '' },
        ],
      }),
    }
    render(<Experiments />)
    expect(screen.getByRole('heading', { name: /Experiments/ })).toBeInTheDocument()
    expect(screen.getAllByText('xgb').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/EURUSD/).length).toBeGreaterThan(0)
  })

  it('clicking a model card filters and shows Show all button', () => {
    mockByKey = {
      getExperimentsSummary: apiOk({
        summary: [
          { model: 'xgb', total_trainings: 1, avg_train_size: 100, latest_accuracy: 60, latest_mae: 0.002, last_trained: '2026-04-16T10:00:00' },
        ],
      }),
      getExperiments: apiOk({ experiments: [] }),
    }
    render(<Experiments />)
    fireEvent.click(screen.getByText('xgb'))
    expect(screen.getByText(/Training History/)).toBeInTheDocument()
    expect(screen.getByText(/Show all/)).toBeInTheDocument()
    // click Show all resets filter
    fireEvent.click(screen.getByText(/Show all/))
  })

  it('FeatureExperiments section renders with results + filter + run button', async () => {
    mockByKey = {
      getExperimentsSummary: apiOk({ summary: [] }),
      getExperiments: apiOk({ experiments: [] }),
      getFeatureExperiments: apiOk({
        results: [
          { feature_set: 'basic', model: 'xgb', symbol: 'EURUSD', pnl: 10, sharpe: 1.0, drawdown: -5, accuracy: 60, winrate: 55, total_trades: 20 },
          { feature_set: 'advanced', model: 'xgb', symbol: 'EURUSD', pnl: -5, sharpe: -0.1, drawdown: -10, accuracy: 48, winrate: 45, total_trades: 15 },
          { feature_set: 'basic', model: 'linear', symbol: 'GBPUSD', pnl: 2, sharpe: 0.3, drawdown: -3, accuracy: 52, winrate: 50, total_trades: 10 },
        ],
      }),
    }
    const { api } = await import('../services/api')
    render(<Experiments />)
    expect(screen.getByText(/Feature Experiments/)).toBeInTheDocument()
    // filter
    const select = document.querySelector('select')
    fireEvent.change(select, { target: { value: 'basic' } })
    // run button
    await act(async () => {
      fireEvent.click(screen.getByText('Run Experiments'))
    })
    expect(api.runExperiments).toHaveBeenCalled()
    expect(screen.getByText('Running...')).toBeInTheDocument()
  })
})

// =========================================================
// Symbols page — loaded
// =========================================================
import Symbols from '../pages/Symbols'

describe('Symbols page (loaded)', () => {
  it('renders symbol selector and detail sections with data', () => {
    mockByKey = {
      getSymbols: apiOk({
        symbols: [
          { symbol: 'EURUSD', candles: 1000 },
          { symbol: 'GBPUSD', candles: 500 },
        ],
      }),
      getCandles: apiOk({
        candles: [
          { time: '2026-04-16T10:00:00', open: 1.10, high: 1.105, low: 1.098, close: 1.102 },
          { time: '2026-04-16T10:01:00', open: 1.102, high: 1.106, low: 1.101, close: 1.104 },
          { time: '2026-04-16T10:02:00', open: 1.104, high: 1.108, low: 1.103, close: 1.106 },
          { time: '2026-04-16T10:03:00', open: 1.106, high: 1.110, low: 1.105, close: 1.108 },
        ],
      }),
      getPredictPredictions: apiOk({
        predictions: [
          { model: 'xgb', timestamp: '2026-04-16T10:00', pred_t1: 1.109, pred_t2: 1.110, pred_t3: 1.111 },
          { model: 'linear', timestamp: '2026-04-16T10:00', pred_t1: 1.105, pred_t2: 1.106, pred_t3: 1.107 },
        ],
      }),
      getPredictionsDetail: apiOk({
        data: [
          { timestamp: '2026-04-16T10:00', model: 'xgb', pred_t1: 1.109 },
        ],
      }),
      getRegimeCurrent: apiOk({
        regime: {
          trend: 1, trend_label: 'UP',
          volatility_regime: 2, volatility_label: 'HIGH',
          momentum: 0.0025,
          range_flag: 0, range_label: 'TREND',
        },
      }),
      getNewsFeatures: apiOk({
        features: {
          news_sentiment_base: 0.5,
          news_sentiment_quote: -0.2,
          news_llm_sentiment_base: 0.1,
          news_llm_sentiment_quote: 0,
          news_impact_base: 2,
          news_impact_quote: 3,
          high_impact_flag: 1,
        },
      }),
      getNewsBySymbol: apiOk({
        base_currency: 'EUR',
        quote_currency: 'USD',
        events: [
          { name: 'CPI release', impact_num: 3, signal: 'good', timestamp: '2026-04-16T10:00:00' },
          { name: 'Retail sales', impact_num: 2, signal: 'bad', timestamp: '2026-04-16T11:00:00' },
          { name: 'PMI', impact_num: 1, signal: 'unknown', timestamp: '2026-04-16T12:00:00' },
        ],
      }),
    }
    render(<Symbols />)
    expect(screen.getByRole('heading', { name: /Symbol Analysis/ })).toBeInTheDocument()
    expect(screen.getByText(/Market Regime/)).toBeInTheDocument()
    expect(screen.getAllByText(/HIGH/).length).toBeGreaterThan(0)
    expect(screen.getByText('CPI release')).toBeInTheDocument()
    expect(screen.getByText('YES')).toBeInTheDocument() // high_impact_flag
  })

  it('renders with empty news events and negative values', () => {
    mockByKey = {
      getSymbols: apiOk({ symbols: [{ symbol: 'EURUSD', candles: 100 }] }),
      getCandles: apiOk({ candles: [] }),
      getPredictPredictions: apiOk({ predictions: [] }),
      getPredictionsDetail: apiOk({ data: [] }),
      getRegimeCurrent: apiOk({
        regime: { trend: -1, trend_label: 'DOWN', volatility_regime: 0, volatility_label: 'LOW', momentum: -0.001, range_flag: 1, range_label: 'RANGE' },
      }),
      getNewsFeatures: apiOk({ features: { high_impact_flag: 0 } }),
      getNewsBySymbol: apiOk({ events: [] }),
    }
    render(<Symbols />)
    expect(screen.getByText(/No recent news/)).toBeInTheDocument()
    expect(screen.getByText('NO')).toBeInTheDocument()
    expect(screen.getByText('DOWN')).toBeInTheDocument()
  })

  it('symbol selector change updates selected', () => {
    mockByKey = {
      getSymbols: apiOk({
        symbols: [
          { symbol: 'EURUSD', candles: 100 },
          { symbol: 'USDJPY', candles: 200 },
        ],
      }),
      getCandles: apiOk({ candles: [] }),
      getPredictPredictions: apiOk({ predictions: [] }),
      getPredictionsDetail: apiOk({ data: [] }),
      getRegimeCurrent: apiOk({ regime: {} }),
      getNewsFeatures: apiOk({ features: {} }),
      getNewsBySymbol: apiOk({ events: [] }),
    }
    render(<Symbols />)
    const select = document.querySelector('select')
    fireEvent.change(select, { target: { value: 'USDJPY' } })
    expect(select.value).toBe('USDJPY')
  })
})
