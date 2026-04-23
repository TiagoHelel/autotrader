/**
 * Tests for src/services/api.js — the HTTP helper.
 * Verifies URL construction, query-param handling, error propagation.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

let fetchMock

beforeEach(() => {
  fetchMock = vi.fn((_url, _opts) =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ok: true }),
    })
  )
  globalThis.fetch = fetchMock
})

afterEach(() => {
  delete globalThis.fetch
})

import { api, WS_URL } from '../services/api'

const lastUrl = () => fetchMock.mock.calls[0][0]
const lastOpts = () => fetchMock.mock.calls[0][1]

describe('api — simple GETs', () => {
  it('getAccount hits /api/account', async () => {
    await api.getAccount()
    expect(lastUrl()).toMatch(/\/api\/account$/)
    expect(lastOpts().headers['Content-Type']).toBe('application/json')
  })

  it('getPositions hits /api/positions', async () => {
    await api.getPositions()
    expect(lastUrl()).toMatch(/\/api\/positions$/)
  })

  it('getPositionHistory uses limit query', async () => {
    await api.getPositionHistory(25)
    expect(lastUrl()).toMatch(/\/api\/positions\/history\?limit=25/)
  })

  it('getBotStatus hits /api/bot/status', async () => {
    await api.getBotStatus()
    expect(lastUrl()).toMatch(/\/api\/bot\/status$/)
  })

  it('getLogs with default params', async () => {
    await api.getLogs()
    expect(lastUrl()).toMatch(/limit=100/)
    expect(lastUrl()).toMatch(/level=ALL/)
  })

  it('getLogs with custom level', async () => {
    await api.getLogs(50, 'ERROR')
    expect(lastUrl()).toMatch(/limit=50/)
    expect(lastUrl()).toMatch(/level=ERROR/)
  })
})

describe('api — query-param builders', () => {
  it('getPredictMetrics without symbol', async () => {
    await api.getPredictMetrics()
    expect(lastUrl()).toMatch(/\/api\/predict\/metrics$/)
  })

  it('getPredictMetrics with symbol', async () => {
    await api.getPredictMetrics('EURUSD')
    expect(lastUrl()).toMatch(/symbol=EURUSD/)
  })

  it('getPredictPredictions with all params', async () => {
    await api.getPredictPredictions('EURUSD', 'xgb', 20)
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/model=xgb/)
    expect(u).toMatch(/limit=20/)
  })

  it('getModelsPerformanceOverTime handles empty params', async () => {
    await api.getModelsPerformanceOverTime()
    expect(lastUrl()).toMatch(/\/api\/predict\/models\/performance\/over-time\?$/)
  })

  it('getModelsValidation without symbol', async () => {
    await api.getModelsValidation()
    expect(lastUrl()).toMatch(/\/api\/predict\/models\/validation$/)
  })

  it('getExperiments with model only', async () => {
    await api.getExperiments('xgboost')
    expect(lastUrl()).toMatch(/model=xgboost/)
  })

  it('getBacktestResults with symbol and model', async () => {
    await api.getBacktestResults('GBPUSD', 'linear', 100)
    const u = lastUrl()
    expect(u).toMatch(/symbol=GBPUSD/)
    expect(u).toMatch(/model=linear/)
    expect(u).toMatch(/limit=100/)
  })

  it('getBacktestEquity requires symbol', async () => {
    await api.getBacktestEquity('EURUSD', 'xgb')
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/model=xgb/)
  })

  it('getFeatureExperiments with featureSet', async () => {
    await api.getFeatureExperiments('EURUSD', 'technical', 'xgb')
    const u = lastUrl()
    expect(u).toMatch(/feature_set=technical/)
  })

  it('selectModel with regime params', async () => {
    await api.selectModel('EURUSD', { trend: 1, volatility_regime: 2, range_flag: 0 })
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/trend=1/)
    expect(u).toMatch(/volatility_regime=2/)
    expect(u).toMatch(/range_flag=0/)
  })

  it('selectModel without optional regime keys', async () => {
    await api.selectModel('EURUSD', {})
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).not.toMatch(/trend=/)
  })
})

describe('api — POSTs', () => {
  it('runBacktest with symbol uses POST', async () => {
    await api.runBacktest('EURUSD')
    expect(lastUrl()).toMatch(/symbol=EURUSD/)
    expect(lastOpts().method).toBe('POST')
  })

  it('runBacktest without symbol still POSTs', async () => {
    await api.runBacktest()
    expect(lastOpts().method).toBe('POST')
  })

  it('refreshNews POSTs', async () => {
    await api.refreshNews()
    expect(lastOpts().method).toBe('POST')
  })

  it('runExperiments with force flag', async () => {
    await api.runExperiments('EURUSD', true)
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/force=true/)
    expect(lastOpts().method).toBe('POST')
  })
})

describe('api — errors', () => {
  it('throws when response is not ok', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Server Error',
      json: () => Promise.resolve({}),
    })
    await expect(api.getAccount()).rejects.toThrow(/API error: 500 Server Error/)
  })

  it('propagates network errors', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'))
    await expect(api.getAccount()).rejects.toThrow(/network down/)
  })
})

describe('WS_URL', () => {
  it('exposes a ws:// URL', () => {
    expect(WS_URL).toMatch(/^ws:\/\/.*\/ws$/)
  })
})

describe('api — additional endpoints for coverage', () => {
  it('getPredictions', async () => {
    await api.getPredictions()
    expect(lastUrl()).toMatch(/\/api\/predictions$/)
  })

  it('getLatestPredictions', async () => {
    await api.getLatestPredictions()
    expect(lastUrl()).toMatch(/\/api\/predictions\/latest$/)
  })

  it('getNews with default limit', async () => {
    await api.getNews()
    expect(lastUrl()).toMatch(/\/api\/news\?limit=30/)
  })

  it('getNews custom limit', async () => {
    await api.getNews(10)
    expect(lastUrl()).toMatch(/limit=10/)
  })

  it('getModelMetrics', async () => {
    await api.getModelMetrics()
    expect(lastUrl()).toMatch(/\/api\/model\/metrics$/)
  })

  it('getModelFeatures', async () => {
    await api.getModelFeatures()
    expect(lastUrl()).toMatch(/\/api\/model\/features$/)
  })

  it('getEquityHistory', async () => {
    await api.getEquityHistory()
    expect(lastUrl()).toMatch(/\/api\/equity\/history$/)
  })

  it('getSymbols', async () => {
    await api.getSymbols()
    expect(lastUrl()).toMatch(/\/api\/predict\/symbols$/)
  })

  it('getLatestPrediction', async () => {
    await api.getLatestPrediction('EURUSD')
    expect(lastUrl()).toMatch(/symbol=EURUSD/)
  })

  it('getPredictionsDetail', async () => {
    await api.getPredictionsDetail('EURUSD', 100)
    expect(lastUrl()).toMatch(/symbol=EURUSD/)
    expect(lastUrl()).toMatch(/limit=100/)
  })

  it('getModelsPerformance', async () => {
    await api.getModelsPerformance()
    expect(lastUrl()).toMatch(/\/api\/predict\/models\/performance$/)
  })

  it('getModelsPerformanceOverTime with both params', async () => {
    await api.getModelsPerformanceOverTime('EURUSD', 'xgb')
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/model=xgb/)
  })

  it('getModelsInfo', async () => {
    await api.getModelsInfo()
    expect(lastUrl()).toMatch(/\/api\/predict\/models\/info$/)
  })

  it('getModelsValidation with symbol', async () => {
    await api.getModelsValidation('EURUSD')
    expect(lastUrl()).toMatch(/\?symbol=EURUSD/)
  })

  it('getModelsFeatureImportance empty', async () => {
    await api.getModelsFeatureImportance()
    expect(lastUrl()).toMatch(/feature-importance\?$/)
  })

  it('getModelsFeatureImportance with both', async () => {
    await api.getModelsFeatureImportance('EURUSD', 'xgb')
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/model=xgb/)
  })

  it('getExperiments no args', async () => {
    await api.getExperiments()
    expect(lastUrl()).toMatch(/experiments\?$/)
  })

  it('getExperiments with both', async () => {
    await api.getExperiments('xgb', 'EURUSD')
    const u = lastUrl()
    expect(u).toMatch(/model=xgb/)
    expect(u).toMatch(/symbol=EURUSD/)
  })

  it('getExperimentsSummary', async () => {
    await api.getExperimentsSummary()
    expect(lastUrl()).toMatch(/experiments\/summary$/)
  })

  it('getCandles', async () => {
    await api.getCandles('EURUSD', 500)
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/limit=500/)
  })

  it('getSystemStatus', async () => {
    await api.getSystemStatus()
    expect(lastUrl()).toMatch(/system\/status$/)
  })

  it('getRecentLogs', async () => {
    await api.getRecentLogs(200)
    expect(lastUrl()).toMatch(/limit=200/)
  })

  it('getNewsLatest', async () => {
    await api.getNewsLatest(25)
    expect(lastUrl()).toMatch(/\/api\/news\/latest\?limit=25/)
  })

  it('getNewsFeatures default', async () => {
    await api.getNewsFeatures()
    expect(lastUrl()).toMatch(/symbol=EURUSD/)
  })

  it('getNewsLlm', async () => {
    await api.getNewsLlm(33)
    expect(lastUrl()).toMatch(/\/api\/news\/llm\?limit=33/)
  })

  it('getNewsBySymbol', async () => {
    await api.getNewsBySymbol('GBPUSD', 5)
    const u = lastUrl()
    expect(u).toMatch(/symbol=GBPUSD/)
    expect(u).toMatch(/limit=5/)
  })

  it('getNewsAnalytics', async () => {
    await api.getNewsAnalytics()
    expect(lastUrl()).toMatch(/\/api\/news\/analytics$/)
  })

  it('getRegimeCurrent', async () => {
    await api.getRegimeCurrent('USDJPY')
    expect(lastUrl()).toMatch(/symbol=USDJPY/)
  })

  it('getNewsRefreshStatus', async () => {
    await api.getNewsRefreshStatus()
    expect(lastUrl()).toMatch(/\/api\/news\/refresh\/status$/)
  })

  it('getBacktestResults with no args', async () => {
    await api.getBacktestResults()
    expect(lastUrl()).toMatch(/limit=200/)
  })

  it('getBacktestSummary', async () => {
    await api.getBacktestSummary()
    expect(lastUrl()).toMatch(/\/api\/backtest\/summary$/)
  })

  it('getBacktestEquity without model', async () => {
    await api.getBacktestEquity('EURUSD')
    expect(lastUrl()).toMatch(/symbol=EURUSD/)
  })

  it('getFeatureExperiments no args', async () => {
    await api.getFeatureExperiments()
    expect(lastUrl()).toMatch(/experiments\/results\?$/)
  })

  it('getExperimentsRanking with symbol', async () => {
    await api.getExperimentsRanking('EURUSD')
    expect(lastUrl()).toMatch(/\?symbol=EURUSD/)
  })

  it('getExperimentsRanking no symbol', async () => {
    await api.getExperimentsRanking()
    expect(lastUrl()).toMatch(/experiments\/ranking$/)
  })

  it('getFeatureSetRanking', async () => {
    await api.getFeatureSetRanking()
    expect(lastUrl()).toMatch(/ranking\/feature-sets$/)
  })

  it('runExperiments without args', async () => {
    await api.runExperiments()
    expect(lastOpts().method).toBe('POST')
  })

  it('getBestModel with symbol', async () => {
    await api.getBestModel('EURUSD')
    expect(lastUrl()).toMatch(/\?symbol=EURUSD/)
  })

  it('getBestModel without symbol', async () => {
    await api.getBestModel()
    expect(lastUrl()).toMatch(/\/api\/models\/best$/)
  })

  it('getModelsByRegime', async () => {
    await api.getModelsByRegime('USDJPY')
    expect(lastUrl()).toMatch(/symbol=USDJPY/)
  })

  it('getSessionCurrent', async () => {
    await api.getSessionCurrent('GBPUSD')
    expect(lastUrl()).toMatch(/symbol=GBPUSD/)
  })

  it('getSessionWeights', async () => {
    await api.getSessionWeights()
    expect(lastUrl()).toMatch(/\/api\/session\/weights$/)
  })

  it('getRadarSignals', async () => {
    await api.getRadarSignals()
    expect(lastUrl()).toMatch(/signals\/radar$/)
  })

  it('getLatestSignals no symbol', async () => {
    await api.getLatestSignals()
    expect(lastUrl()).toMatch(/limit=50/)
  })

  it('getLatestSignals with symbol', async () => {
    await api.getLatestSignals('EURUSD', 10)
    const u = lastUrl()
    expect(u).toMatch(/symbol=EURUSD/)
    expect(u).toMatch(/limit=10/)
  })
})
