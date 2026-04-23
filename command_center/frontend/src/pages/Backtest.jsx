import { useState, useMemo } from 'react'
import {
  LineChart, Line, AreaChart, Area,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { DollarSign, TrendingUp, TrendingDown, Activity, Play, ChevronDown } from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

const REFRESH = 30_000
const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7']

export default function Backtest() {
  const { data: summaryData, loading } = useApi(() => api.getBacktestSummary(), [], { interval: REFRESH })
  const { data: symbolsData } = useApi(() => api.getSymbols(), [])
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [running, setRunning] = useState(false)

  const summary = summaryData?.summary || []
  const symbols = symbolsData?.symbols || []
  const activeSymbol = selectedSymbol || symbols[0]?.symbol || 'EURUSD'

  const handleRunBacktest = async () => {
    setRunning(true)
    try {
      await api.runBacktest(selectedSymbol)
    } catch (e) { console.error(e) }
    setTimeout(() => setRunning(false), 3000)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Backtest</h2>
          <p className="text-sm text-gray-500">Simulated PnL and trade analysis</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={activeSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="appearance-none glass-card rounded-lg px-4 py-2 pr-8 text-sm text-white bg-transparent border border-gray-700 focus:border-blue-500 focus:outline-none"
            >
              {symbols.map(s => (
                <option key={s.symbol} value={s.symbol} className="bg-gray-900">{s.symbol}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
          </div>
          <button
            onClick={handleRunBacktest}
            disabled={running}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-all"
          >
            <Play className="h-4 w-4" />
            {running ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <SummaryCards summary={summary} />

      {/* Equity Curve + Drawdown */}
      <EquitySection symbol={activeSymbol} />

      {/* Trades Table */}
      <TradesTable symbol={activeSymbol} />
    </div>
  )
}

function SummaryCards({ summary }) {
  const topModels = useMemo(() => {
    return [...summary].sort((a, b) => (b.pnl_total || 0) - (a.pnl_total || 0)).slice(0, 5)
  }, [summary])

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
      {topModels.map((s, i) => (
        <div key={`${s.symbol}_${s.model}`} className={`glass-card rounded-xl p-5 ${
          i === 0 ? 'ring-1 ring-green-500/30' : ''
        }`}>
          <div className="flex items-center gap-2 mb-3">
            <DollarSign className={`h-4 w-4 ${(s.pnl_total || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`} />
            <span className="text-sm font-semibold text-white truncate">{s.model}</span>
          </div>
          <div className="text-xs text-gray-500 mb-2">{s.symbol}</div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500">PnL (pips)</span>
              <span className={`font-mono font-semibold ${
                (s.pnl_total || 0) >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>{(s.pnl_total || 0).toFixed(1)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Sharpe</span>
              <span className="text-gray-300 font-mono">{(s.sharpe || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Drawdown</span>
              <span className="text-red-400 font-mono">{(s.max_drawdown || 0).toFixed(1)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Win Rate</span>
              <span className="text-gray-300 font-mono">{(s.winrate || 0).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Trades</span>
              <span className="text-gray-300">{s.total_trades || 0}</span>
            </div>
          </div>
        </div>
      ))}
      {topModels.length === 0 && (
        <div className="col-span-full glass-card rounded-xl p-8 text-center text-gray-500">
          No backtest results yet. Click "Run Backtest" to start.
        </div>
      )}
    </div>
  )
}

function EquitySection({ symbol }) {
  const { data: equityData } = useApi(
    () => api.getBacktestEquity(symbol), [symbol], { interval: REFRESH }
  )

  const curves = equityData?.curves || {}
  const modelNames = Object.keys(curves)

  const chartData = useMemo(() => {
    if (!modelNames.length) return []
    const maxLen = Math.max(...modelNames.map(m => curves[m]?.equity?.length || 0))
    const data = []
    for (let i = 0; i < maxLen; i++) {
      const point = { trade: i + 1 }
      modelNames.forEach(m => {
        const eq = curves[m]?.equity
        if (eq && i < eq.length) point[m] = eq[i]
      })
      data.push(point)
    }
    return data
  }, [curves, modelNames])

  // Drawdown data
  const drawdownData = useMemo(() => {
    if (!modelNames.length) return []
    const maxLen = Math.max(...modelNames.map(m => curves[m]?.equity?.length || 0))
    const data = []
    for (let i = 0; i < maxLen; i++) {
      const point = { trade: i + 1 }
      modelNames.forEach(m => {
        const eq = curves[m]?.equity
        if (eq && i < eq.length) {
          const peak = Math.max(...eq.slice(0, i + 1))
          point[`${m}_dd`] = eq[i] - peak
        }
      })
      data.push(point)
    }
    return data
  }, [curves, modelNames])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Equity Curve */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Equity Curve (pips)</h3>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="trade" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              {modelNames.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-[300px] text-gray-500 text-sm">
            No equity data available
          </div>
        )}
      </div>

      {/* Drawdown Chart */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Drawdown</h3>
        {drawdownData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={drawdownData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="trade" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              {modelNames.map((name, i) => (
                <Area
                  key={name}
                  type="monotone"
                  dataKey={`${name}_dd`}
                  name={`${name} DD`}
                  stroke={COLORS[i % COLORS.length]}
                  fill={COLORS[i % COLORS.length]}
                  fillOpacity={0.15}
                  strokeWidth={1.5}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-[300px] text-gray-500 text-sm">
            No drawdown data available
          </div>
        )}
      </div>
    </div>
  )
}

function TradesTable({ symbol }) {
  const { data: tradesData } = useApi(
    () => api.getBacktestResults(symbol, null, 100), [symbol], { interval: REFRESH }
  )

  const trades = tradesData?.trades || []

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="text-sm font-semibold text-gray-300 mb-4">
        Simulated Trades ({trades.length})
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-2 px-3">Time</th>
              <th className="text-left py-2 px-3">Model</th>
              <th className="text-center py-2 px-3">Direction</th>
              <th className="text-right py-2 px-3">Entry</th>
              <th className="text-right py-2 px-3">Exit</th>
              <th className="text-right py-2 px-3">PnL (pips)</th>
              <th className="text-right py-2 px-3">Expected Return</th>
            </tr>
          </thead>
          <tbody>
            {trades.slice(0, 50).map((t, i) => (
              <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-2 px-3 text-gray-400 font-mono text-xs">
                  {t.entry_time?.slice(0, 16)}
                </td>
                <td className="py-2 px-3 text-gray-300">{t.model}</td>
                <td className="py-2 px-3 text-center">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                    t.direction === 'BUY'
                      ? 'bg-green-500/10 text-green-400'
                      : 'bg-red-500/10 text-red-400'
                  }`}>
                    {t.direction === 'BUY' ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                    {t.direction}
                  </span>
                </td>
                <td className="py-2 px-3 text-right font-mono text-gray-300 text-xs">
                  {Number(t.entry_price)?.toFixed(5)}
                </td>
                <td className="py-2 px-3 text-right font-mono text-gray-300 text-xs">
                  {Number(t.exit_price)?.toFixed(5)}
                </td>
                <td className={`py-2 px-3 text-right font-mono font-semibold ${
                  (t.pnl_pips || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {(t.pnl_pips || 0).toFixed(1)}
                </td>
                <td className="py-2 px-3 text-right font-mono text-gray-400 text-xs">
                  {((t.expected_return || 0) * 100).toFixed(3)}%
                </td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr>
                <td colSpan={7} className="py-8 text-center text-gray-500">
                  No simulated trades yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
