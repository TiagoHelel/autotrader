import { useState, useMemo } from 'react'
import {
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ComposedChart, Bar,
} from 'recharts'
import { ChevronDown, CheckCircle, XCircle } from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

const REFRESH_INTERVAL = 30_000 // 30 seconds

function getPriceDecimals(value) {
  if (!Number.isFinite(value)) return 5
  if (value >= 1000) return 1
  if (value >= 100) return 2
  if (value >= 1) return 4
  return 5
}

function getPriceStep(value) {
  if (!Number.isFinite(value)) return 0.0001
  if (value >= 1000) return 0.1
  if (value >= 100) return 0.01
  if (value >= 1) return 0.0001
  return 0.00001
}

export default function Symbols() {
  const { data: symbolsData } = useApi(() => api.getSymbols(), [], { interval: REFRESH_INTERVAL })
  const [selectedSymbol, setSelectedSymbol] = useState(null)

  const symbols = symbolsData?.symbols || []
  const activeSymbol = selectedSymbol || symbols[0]?.symbol || ''

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Symbol Analysis</h2>
          <p className="text-sm text-gray-500">Price vs predictions per symbol</p>
        </div>

        {/* Symbol Selector */}
        <div className="relative">
          <select
            value={activeSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="appearance-none glass-card rounded-lg px-4 py-2 pr-8 text-sm text-white bg-transparent border border-gray-700 focus:border-blue-500 focus:outline-none cursor-pointer"
          >
            {symbols.map(s => (
              <option key={s.symbol} value={s.symbol} className="bg-gray-900">
                {s.symbol} ({s.candles} candles)
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        </div>
      </div>

      {activeSymbol && <SymbolDetail symbol={activeSymbol} />}
    </div>
  )
}

function SymbolDetail({ symbol }) {
  const { data: candleData, loading: candleLoading } = useApi(
    () => api.getCandles(symbol, 200), [symbol], { interval: REFRESH_INTERVAL }
  )
  const { data: predData } = useApi(
    () => api.getPredictPredictions(symbol, null, 200), [symbol], { interval: REFRESH_INTERVAL }
  )
  const { data: detailData } = useApi(
    () => api.getPredictionsDetail(symbol, 50), [symbol], { interval: REFRESH_INTERVAL }
  )
  const { data: regimeData } = useApi(
    () => api.getRegimeCurrent(symbol), [symbol], { interval: REFRESH_INTERVAL }
  )
  const { data: newsFeatures } = useApi(
    () => api.getNewsFeatures(symbol), [symbol], { interval: REFRESH_INTERVAL }
  )
  const { data: symbolNews } = useApi(
    () => api.getNewsBySymbol(symbol, 10), [symbol], { interval: REFRESH_INTERVAL }
  )

  // Price chart with predictions overlay
  const chartData = useMemo(() => {
    if (!candleData?.candles?.length) return []
    const candles = candleData.candles
    const predictions = predData?.predictions || []

    // Build price data
    const data = candles.map(c => ({
      time: c.time?.slice(11, 16) || '',
      fullTime: c.time,
      close: c.close,
      open: c.open,
      high: c.high,
      low: c.low,
    }))

    // Overlay predictions (latest per model)
    const latestPreds = {}
    predictions.forEach(p => {
      if (!latestPreds[p.model] || p.timestamp > latestPreds[p.model].timestamp) {
        latestPreds[p.model] = p
      }
    })

    // Add prediction markers on last 3 candles
    const len = data.length
    Object.entries(latestPreds).forEach(([model, p]) => {
      if (len >= 1) data[len - 1][`${model}_t1`] = p.pred_t1
      if (len >= 2) data[len - 2][`${model}_t2`] = p.pred_t2
      if (len >= 3) data[len - 3][`${model}_t3`] = p.pred_t3
    })

    const closeValues = data
      .map(d => d.close)
      .filter(v => Number.isFinite(v))

    if (!closeValues.length) return data

    const minClose = Math.min(...closeValues)
    const maxClose = Math.max(...closeValues)
    const latestClose = closeValues[closeValues.length - 1]
    const step = getPriceStep(latestClose)
    const range = Math.max(maxClose - minClose, step * 6)
    const plausibleMin = minClose - range * 1.5
    const plausibleMax = maxClose + range * 1.5

    data.forEach((point) => {
      Object.keys(point)
        .filter((key) => key.endsWith('_t1') || key.endsWith('_t2') || key.endsWith('_t3'))
        .forEach((key) => {
          const value = point[key]
          if (!Number.isFinite(value) || value < plausibleMin || value > plausibleMax) {
            point[key] = null
          }
        })
    })

    return data
  }, [candleData, predData])

  const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7']
  const modelNames = useMemo(() => {
    return [...new Set((predData?.predictions || []).map(p => p.model))]
  }, [predData])

  const priceDomain = useMemo(() => {
    if (!chartData.length) return ['auto', 'auto']

    const closeValues = chartData.map(d => d.close)
      .filter(v => Number.isFinite(v))
    const wickValues = chartData.flatMap(d => [d.low, d.high])
      .filter(v => Number.isFinite(v))

    if (!closeValues.length) return ['auto', 'auto']

    const minClose = Math.min(...closeValues)
    const maxClose = Math.max(...closeValues)
    const latestPrice = chartData[chartData.length - 1]?.close ?? maxClose
    const step = getPriceStep(latestPrice)
    const observedRange = Math.max(maxClose - minClose, step * 6)
    const padding = Math.max(observedRange * 0.08, step * 3)
    const plausibleMin = minClose - observedRange * 1.5
    const plausibleMax = maxClose + observedRange * 1.5

    const predictionValues = chartData
      .flatMap(d => Object.entries(d)
        .filter(([key, value]) => key.endsWith('_t1') && Number.isFinite(value))
        .map(([, value]) => value)
      )
      .filter(v => v >= plausibleMin && v <= plausibleMax)

    const visibleWicks = wickValues.filter(v => v >= plausibleMin && v <= plausibleMax)
    const allValues = [...closeValues, ...visibleWicks, ...predictionValues]
    const domainMin = Math.min(...allValues) - padding
    const domainMax = Math.max(...allValues) + padding

    return [domainMin, domainMax]
  }, [chartData])

  const priceDecimals = useMemo(() => {
    if (!chartData.length) return 5
    return getPriceDecimals(chartData[chartData.length - 1]?.close)
  }, [chartData])

  const detailRows = detailData?.data || []

  const regime = regimeData?.regime || {}
  const nf = newsFeatures?.features || {}
  const newsEvents = symbolNews?.events || []

  return (
    <div className="space-y-6">
      {/* Regime + News Indicators Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Regime Card */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Market Regime</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Trend</span>
              <span className={`text-sm font-bold ${
                regime.trend === 1 ? 'text-green-400' : regime.trend === -1 ? 'text-red-400' : 'text-gray-400'
              }`}>
                {regime.trend_label || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Volatility</span>
              <span className={`text-sm font-bold ${
                regime.volatility_regime === 2 ? 'text-red-400' : regime.volatility_regime === 1 ? 'text-yellow-400' : 'text-green-400'
              }`}>
                {regime.volatility_label || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Momentum</span>
              <span className={`text-sm font-mono ${
                (regime.momentum || 0) > 0 ? 'text-green-400' : (regime.momentum || 0) < 0 ? 'text-red-400' : 'text-gray-400'
              }`}>
                {((regime.momentum || 0) * 100).toFixed(3)}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Range</span>
              <span className={`text-sm font-bold ${
                regime.range_flag === 1 ? 'text-yellow-400' : 'text-blue-400'
              }`}>
                {regime.range_label || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* News Indicators Card */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">News Indicators</h3>
          <div className="space-y-2">
            {[
              ['Sentiment Base', nf.news_sentiment_base],
              ['Sentiment Quote', nf.news_sentiment_quote],
              ['LLM Sent. Base', nf.news_llm_sentiment_base],
              ['LLM Sent. Quote', nf.news_llm_sentiment_quote],
              ['Impact Base', nf.news_impact_base],
              ['Impact Quote', nf.news_impact_quote],
            ].map(([label, val]) => (
              <div key={label} className="flex justify-between items-center">
                <span className="text-xs text-gray-500">{label}</span>
                <span className={`text-xs font-mono ${
                  (val || 0) > 0 ? 'text-green-400' : (val || 0) < 0 ? 'text-red-400' : 'text-gray-500'
                }`}>
                  {(val || 0).toFixed(3)}
                </span>
              </div>
            ))}
            <div className="flex justify-between items-center pt-1 border-t border-gray-800">
              <span className="text-xs text-gray-500">High Impact</span>
              <span className={`text-xs font-bold ${nf.high_impact_flag ? 'text-red-400' : 'text-gray-500'}`}>
                {nf.high_impact_flag ? 'YES' : 'NO'}
              </span>
            </div>
          </div>
        </div>

        {/* Recent News for Symbol */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">
            Recent News ({symbolNews?.base_currency}/{symbolNews?.quote_currency})
          </h3>
          <div className="max-h-[200px] space-y-2 overflow-y-auto pr-1">
            {newsEvents.length === 0 ? (
              <p className="text-xs text-gray-600 text-center py-4">No recent news</p>
            ) : (
              newsEvents.map((ev, i) => (
                <div key={i} className="border-b border-gray-800/50 pb-1.5">
                  <p className="text-xs text-gray-300 leading-snug">{ev.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-xs ${
                      Number(ev.impact_num) >= 3 ? 'text-red-400' : Number(ev.impact_num) >= 2 ? 'text-yellow-400' : 'text-gray-500'
                    }`}>
                      Impact: {ev.impact_num}
                    </span>
                    <span className={`text-xs ${
                      ev.signal === 'good' ? 'text-green-400' : ev.signal === 'bad' ? 'text-red-400' : 'text-gray-500'
                    }`}>
                      {ev.signal}
                    </span>
                    <span className="text-xs text-gray-600">{ev.timestamp?.slice(11, 16)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Price Chart */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">
          {symbol} — Price + Predictions
        </h3>
        {candleLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin h-6 w-6 border-2 border-blue-500 border-t-transparent rounded-full" />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis
                domain={priceDomain}
                allowDataOverflow
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickFormatter={(value) => Number(value).toFixed(priceDecimals)}
                width={80}
              />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
                formatter={(value, name) => [
                  Number.isFinite(value) ? Number(value).toFixed(priceDecimals) : value,
                  name,
                ]}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="close"
                name="Price"
                stroke="#e2e8f0"
                strokeWidth={2}
                dot={false}
              />
              {modelNames.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={`${name}_t1`}
                  name={`${name} t+1`}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={1.5}
                  strokeDasharray="5 5"
                  dot={{ r: 3, fill: COLORS[i % COLORS.length] }}
                  connectNulls={false}
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Best Model for Symbol */}
      <BestModelForSymbol symbol={symbol} />

      {/* Predictions Detail Table */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">
          Prediction Details
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-3">Timestamp</th>
                <th className="text-left py-2 px-3">Model</th>
                <th className="text-right py-2 px-3">Horizon</th>
                <th className="text-right py-2 px-3">Predicted</th>
                <th className="text-right py-2 px-3">Actual</th>
                <th className="text-right py-2 px-3">Error %</th>
                <th className="text-center py-2 px-3">Direction</th>
              </tr>
            </thead>
            <tbody>
              {detailRows.slice(0, 30).map((row, i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 px-3 text-gray-400 font-mono text-xs">
                    {row.timestamp?.slice(0, 16)}
                  </td>
                  <td className="py-2 px-3 text-gray-300">{row.model}</td>
                  <td className="py-2 px-3 text-right text-gray-400">t+{row.horizon}</td>
                  <td className="py-2 px-3 text-right font-mono text-gray-300">
                    {Number(row.predicted)?.toFixed(5)}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-gray-300">
                    {Number(row.actual)?.toFixed(5)}
                  </td>
                  <td className={`py-2 px-3 text-right font-mono ${
                    row.pct_error < 0.1 ? 'text-green-400' : row.pct_error < 0.5 ? 'text-yellow-400' : 'text-red-400'
                  }`}>
                    {Number(row.pct_error)?.toFixed(4)}%
                  </td>
                  <td className="py-2 px-3 text-center">
                    {row.direction_correct ? (
                      <CheckCircle className="inline h-4 w-4 text-green-400" />
                    ) : (
                      <XCircle className="inline h-4 w-4 text-red-400" />
                    )}
                  </td>
                </tr>
              ))}
              {detailRows.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500">
                    No evaluated predictions yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function BestModelForSymbol({ symbol }) {
  const { data: bestData } = useApi(
    () => api.getBestModel(symbol), [symbol], { interval: REFRESH_INTERVAL }
  )
  const { data: regimeData } = useApi(
    () => api.getModelsByRegime(symbol), [symbol], { interval: REFRESH_INTERVAL }
  )

  const best = bestData?.model
  const regimes = regimeData?.regimes || {}

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Best Model */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">Best Model for {symbol}</h3>
        {best && best.model ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-yellow-500/10 px-3 py-1 text-sm font-bold text-yellow-400">
                {best.model}
              </span>
              {best.feature_set && (
                <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">
                  {best.feature_set}
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-3 mt-3 text-xs">
              <div>
                <span className="text-gray-500">PnL</span>
                <p className={`font-mono font-semibold ${
                  (best.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>{(best.pnl || 0).toFixed(1)}</p>
              </div>
              <div>
                <span className="text-gray-500">Sharpe</span>
                <p className="font-mono text-gray-300">{(best.sharpe || 0).toFixed(2)}</p>
              </div>
              <div>
                <span className="text-gray-500">Accuracy</span>
                <p className="font-mono text-gray-300">{(best.accuracy || 0).toFixed(1)}%</p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-gray-500">No model data yet</p>
        )}
      </div>

      {/* Best by Regime */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">Best Model by Regime</h3>
        {Object.keys(regimes).length > 0 ? (
          <div className="space-y-1.5">
            {Object.entries(regimes).map(([regime, info]) => (
              <div key={regime} className="flex justify-between items-center text-xs">
                <span className="text-gray-500 capitalize">{regime.replace('_', ' ')}</span>
                <div className="flex items-center gap-2">
                  <span className="text-gray-300 font-medium">{info.model || '-'}</span>
                  {info.pnl != null && (
                    <span className={`font-mono ${
                      (info.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>{(info.pnl || 0).toFixed(1)}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-500">No regime analysis data yet</p>
        )}
      </div>
    </div>
  )
}
