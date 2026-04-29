const BASE_URL = `http://${window.location.hostname}:8000`

async function fetchJson(endpoint, options = {}) {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  // Existing endpoints
  getAccount: () => fetchJson('/api/account'),
  getPositions: () => fetchJson('/api/positions'),
  getPositionHistory: (limit = 50) => fetchJson(`/api/positions/history?limit=${limit}`),
  getPredictions: () => fetchJson('/api/predictions'),
  getLatestPredictions: () => fetchJson('/api/predictions/latest'),
  getNews: (limit = 30) => fetchJson(`/api/news?limit=${limit}`),
  getModelMetrics: () => fetchJson('/api/model/metrics'),
  getModelFeatures: () => fetchJson('/api/model/features'),
  getEquityHistory: () => fetchJson('/api/equity/history'),
  getLogs: (limit = 100, level = 'ALL') => fetchJson(`/api/logs?limit=${limit}&level=${level}`),
  getBotStatus: () => fetchJson('/api/bot/status'),

  // Prediction system endpoints
  getSymbols: () => fetchJson('/api/predict/symbols'),
  getPredictMetrics: (symbol = null) =>
    fetchJson(`/api/predict/metrics${symbol ? `?symbol=${symbol}` : ''}`),
  getPredictPredictions: (symbol = null, model = null, limit = 100) => {
    const params = new URLSearchParams()
    if (symbol) params.set('symbol', symbol)
    if (model) params.set('model', model)
    params.set('limit', limit)
    return fetchJson(`/api/predict/predictions?${params}`)
  },
  getLatestPrediction: (symbol) =>
    fetchJson(`/api/predict/predictions/latest?symbol=${symbol}`),
  getPredictionsDetail: (symbol, limit = 50) =>
    fetchJson(`/api/predict/predictions/detail?symbol=${symbol}&limit=${limit}`),
  getModelsPerformance: () => fetchJson('/api/predict/models/performance'),
  getModelsPerformanceOverTime: (symbol = null, model = null) => {
    const params = new URLSearchParams()
    if (symbol) params.set('symbol', symbol)
    if (model) params.set('model', model)
    return fetchJson(`/api/predict/models/performance/over-time?${params}`)
  },
  getModelsInfo: (symbol = null) =>
    fetchJson(`/api/predict/models/info${symbol ? `?symbol=${symbol}` : ''}`),
  getHpoChampions: () => fetchJson('/api/predict/hpo/champions'),
  getModelsValidation: (symbol = null) =>
    fetchJson(`/api/predict/models/validation${symbol ? `?symbol=${symbol}` : ''}`),
  getModelsFeatureImportance: (symbol = null, model = null) => {
    const params = new URLSearchParams()
    if (symbol) params.set('symbol', symbol)
    if (model) params.set('model', model)
    return fetchJson(`/api/predict/models/feature-importance?${params}`)
  },
  getExperiments: (model = null, symbol = null) => {
    const params = new URLSearchParams()
    if (model) params.set('model', model)
    if (symbol) params.set('symbol', symbol)
    return fetchJson(`/api/predict/experiments?${params}`)
  },
  getExperimentsSummary: () => fetchJson('/api/predict/experiments/summary'),
  getCandles: (symbol, limit = 100) =>
    fetchJson(`/api/predict/candles?symbol=${symbol}&limit=${limit}`),
  getSystemStatus: () => fetchJson('/api/predict/system/status'),
  getRecentLogs: (limit = 50) => fetchJson(`/api/predict/logs/recent?limit=${limit}`),

  // News & Regime endpoints
  getNewsLatest: (limit = 50) => fetchJson(`/api/news/latest?limit=${limit}`),
  getNewsFeatures: (symbol = 'EURUSD') => fetchJson(`/api/news/features?symbol=${symbol}`),
  getNewsLlm: (limit = 50) => fetchJson(`/api/news/llm?limit=${limit}`),
  getNewsBySymbol: (symbol = 'EURUSD', limit = 50) =>
    fetchJson(`/api/news/by-symbol?symbol=${symbol}&limit=${limit}`),
  getNewsAnalytics: () => fetchJson('/api/news/analytics'),
  getRegimeCurrent: (symbol = 'EURUSD') => fetchJson(`/api/regime/current?symbol=${symbol}`),
  refreshNews: () => fetchJson('/api/news/refresh', { method: 'POST' }),
  getNewsRefreshStatus: () => fetchJson('/api/news/refresh/status'),

  // Backtest endpoints
  getBacktestResults: (symbol = null, model = null, limit = 200) => {
    const params = new URLSearchParams()
    if (symbol) params.set('symbol', symbol)
    if (model) params.set('model', model)
    params.set('limit', limit)
    return fetchJson(`/api/backtest/results?${params}`)
  },
  getBacktestSummary: () => fetchJson('/api/backtest/summary'),
  runBacktest: (symbol = null) =>
    fetchJson(`/api/backtest/run${symbol ? `?symbol=${symbol}` : ''}`, { method: 'POST' }),
  getBacktestEquity: (symbol, model = null) => {
    const params = new URLSearchParams({ symbol })
    if (model) params.set('model', model)
    return fetchJson(`/api/backtest/equity?${params}`)
  },

  // Feature experiments endpoints
  getFeatureExperiments: (symbol = null, featureSet = null, model = null) => {
    const params = new URLSearchParams()
    if (symbol) params.set('symbol', symbol)
    if (featureSet) params.set('feature_set', featureSet)
    if (model) params.set('model', model)
    return fetchJson(`/api/experiments/results?${params}`)
  },
  getExperimentsRanking: (symbol = null) =>
    fetchJson(`/api/experiments/ranking${symbol ? `?symbol=${symbol}` : ''}`),
  getFeatureSetRanking: () => fetchJson('/api/experiments/ranking/feature-sets'),
  runExperiments: (symbol = null, force = false) => {
    const params = new URLSearchParams()
    if (symbol) params.set('symbol', symbol)
    if (force) params.set('force', 'true')
    return fetchJson(`/api/experiments/run?${params}`, { method: 'POST' })
  },

  // Model selection endpoints
  getBestModel: (symbol = null) =>
    fetchJson(`/api/models/best${symbol ? `?symbol=${symbol}` : ''}`),
  getModelsByRegime: (symbol = 'EURUSD') =>
    fetchJson(`/api/models/by-regime?symbol=${symbol}`),
  selectModel: (symbol, regime = {}) => {
    const params = new URLSearchParams({ symbol })
    if (regime.trend != null) params.set('trend', regime.trend)
    if (regime.volatility_regime != null) params.set('volatility_regime', regime.volatility_regime)
    if (regime.range_flag != null) params.set('range_flag', regime.range_flag)
    return fetchJson(`/api/models/select?${params}`)
  },

  // Session endpoints
  getSessionCurrent: (symbol = 'EURUSD') =>
    fetchJson(`/api/session/current?symbol=${symbol}`),
  getSessionWeights: () => fetchJson('/api/session/weights'),

  // Radar (ensemble signals for all symbols)
  getRadarSignals: () => fetchJson('/api/predict/signals/radar'),

  // Signals
  getLatestSignals: (symbol = null, limit = 50) => {
    const params = new URLSearchParams({ limit })
    if (symbol) params.set('symbol', symbol)
    return fetchJson(`/api/signals/latest?${params}`)
  },
}

export const WS_URL = `ws://${window.location.hostname}:8000/ws`
