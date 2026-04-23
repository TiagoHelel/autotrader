import { useState, useMemo } from 'react'
import {
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { ChevronDown, FlaskConical, Clock, Database, Play } from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7']

export default function Experiments() {
  const { data: summaryData, loading } = useApi(() => api.getExperimentsSummary(), [])
  const [selectedModel, setSelectedModel] = useState(null)
  const { data: experimentsData } = useApi(
    () => api.getExperiments(selectedModel), [selectedModel]
  )

  const summary = summaryData?.summary || []
  const experiments = experimentsData?.experiments || []

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Experiments</h2>
        <p className="text-sm text-gray-500">Training history and model parameters</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {summary.map((s, i) => (
          <button
            key={s.model}
            onClick={() => setSelectedModel(selectedModel === s.model ? null : s.model)}
            className={`glass-card rounded-xl p-5 text-left transition-all hover:ring-1 hover:ring-blue-500/30 ${
              selectedModel === s.model ? 'ring-1 ring-blue-500/50' : ''
            }`}
          >
            <div className="flex items-center gap-2 mb-3">
              <FlaskConical className="h-4 w-4 text-blue-400" />
              <span className="text-sm font-semibold text-white">{s.model}</span>
            </div>
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-500">Trainings</span>
                <span className="text-gray-300">{s.total_trainings}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Avg Samples</span>
                <span className="text-gray-300">{Math.round(s.avg_train_size || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Last Accuracy</span>
                <span className={`font-mono ${
                  s.latest_accuracy >= 60 ? 'text-green-400' :
                  s.latest_accuracy >= 50 ? 'text-yellow-400' : 'text-gray-400'
                }`}>
                  {s.latest_accuracy != null ? `${Number(s.latest_accuracy).toFixed(1)}%` : '-'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Last MAE</span>
                <span className="text-gray-400 font-mono">
                  {s.latest_mae != null ? Number(s.latest_mae).toFixed(5) : '-'}
                </span>
              </div>
              <div className="flex items-center gap-1 mt-2 text-gray-500">
                <Clock className="h-3 w-3" />
                <span>{s.last_trained?.slice(0, 16)}</span>
              </div>
            </div>
          </button>
        ))}
        {summary.length === 0 && (
          <div className="col-span-full glass-card rounded-xl p-8 text-center text-gray-500">
            No experiments recorded yet. Run the prediction engine first.
          </div>
        )}
      </div>

      {/* Feature Experiments Section */}
      <FeatureExperiments />

      {/* Experiment History */}
      <div className="glass-card rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-300">
            {selectedModel ? `${selectedModel} — Training History` : 'All Training History'}
          </h3>
          {selectedModel && (
            <button
              onClick={() => setSelectedModel(null)}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              Show all
            </button>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-3">Timestamp</th>
                <th className="text-left py-2 px-3">Model</th>
                <th className="text-left py-2 px-3">Symbol</th>
                <th className="text-right py-2 px-3">Train Size</th>
                <th className="text-right py-2 px-3">Accuracy</th>
                <th className="text-right py-2 px-3">MAE</th>
                <th className="text-left py-2 px-3">Parameters</th>
              </tr>
            </thead>
            <tbody>
              {experiments.slice(0, 50).map((exp, i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 px-3 text-gray-400 font-mono text-xs">
                    {exp.timestamp?.slice(0, 16)}
                  </td>
                  <td className="py-2 px-3 text-gray-300">{exp.model}</td>
                  <td className="py-2 px-3 text-gray-400">{exp.symbol}</td>
                  <td className="py-2 px-3 text-right text-gray-400">{exp.train_size}</td>
                  <td className="py-2 px-3 text-right font-mono">
                    {exp.accuracy != null ? (
                      <span className={
                        exp.accuracy >= 60 ? 'text-green-400' :
                        exp.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'
                      }>{Number(exp.accuracy).toFixed(1)}%</span>
                    ) : <span className="text-gray-600">-</span>}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-gray-400">
                    {exp.mae != null ? Number(exp.mae).toFixed(5) : '-'}
                  </td>
                  <td className="py-2 px-3 text-gray-500 text-xs font-mono max-w-xs truncate">
                    {exp.params}
                  </td>
                </tr>
              ))}
              {experiments.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500">
                    No experiments to show
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

function FeatureExperiments() {
  const { data: feData } = useApi(() => api.getFeatureExperiments(), [], { interval: 30000 })
  const [filterFs, setFilterFs] = useState('')
  const [running, setRunning] = useState(false)

  const results = feData?.results || []

  const featureSets = useMemo(() => {
    return [...new Set(results.map(r => r.feature_set))]
  }, [results])

  const filtered = filterFs ? results.filter(r => r.feature_set === filterFs) : results

  // Chart: compare feature sets
  const chartData = useMemo(() => {
    const byFs = {}
    results.forEach(r => {
      if (!byFs[r.feature_set]) byFs[r.feature_set] = { feature_set: r.feature_set, pnl: 0, sharpe: 0, count: 0 }
      byFs[r.feature_set].pnl += r.pnl || 0
      byFs[r.feature_set].sharpe += r.sharpe || 0
      byFs[r.feature_set].count += 1
    })
    return Object.values(byFs).map(v => ({
      feature_set: v.feature_set,
      avg_pnl: v.count > 0 ? v.pnl / v.count : 0,
      avg_sharpe: v.count > 0 ? v.sharpe / v.count : 0,
    }))
  }, [results])

  const handleRun = async () => {
    setRunning(true)
    try { await api.runExperiments() } catch (e) { console.error(e) }
    setTimeout(() => setRunning(false), 3000)
  }

  if (!results.length) return null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-white">Feature Experiments</h3>
        <div className="flex items-center gap-3">
          {featureSets.length > 0 && (
            <select
              value={filterFs}
              onChange={e => setFilterFs(e.target.value)}
              className="glass-card rounded-lg px-3 py-1.5 text-xs text-white bg-transparent border border-gray-700"
            >
              <option value="" className="bg-gray-900">All Feature Sets</option>
              {featureSets.map(fs => (
                <option key={fs} value={fs} className="bg-gray-900">{fs}</option>
              ))}
            </select>
          )}
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-1 rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-500 disabled:opacity-50"
          >
            <Play className="h-3 w-3" />
            {running ? 'Running...' : 'Run Experiments'}
          </button>
        </div>
      </div>

      {/* Comparison Chart */}
      {chartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card rounded-xl p-5">
            <h4 className="text-sm font-semibold text-gray-300 mb-4">Avg PnL by Feature Set</h4>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="feature_set" tick={{ fontSize: 9, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }} />
                <Bar dataKey="avg_pnl" name="Avg PnL" fill="#22c55e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="glass-card rounded-xl p-5">
            <h4 className="text-sm font-semibold text-gray-300 mb-4">Avg Sharpe by Feature Set</h4>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="feature_set" tick={{ fontSize: 9, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }} />
                <Bar dataKey="avg_sharpe" name="Avg Sharpe" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Results Table */}
      <div className="glass-card rounded-xl p-5">
        <h4 className="text-sm font-semibold text-gray-300 mb-4">
          Experiment Results ({filtered.length})
        </h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-2">Feature Set</th>
                <th className="text-left py-2 px-2">Model</th>
                <th className="text-left py-2 px-2">Symbol</th>
                <th className="text-right py-2 px-2">PnL</th>
                <th className="text-right py-2 px-2">Sharpe</th>
                <th className="text-right py-2 px-2">Drawdown</th>
                <th className="text-right py-2 px-2">Accuracy</th>
                <th className="text-right py-2 px-2">Win Rate</th>
                <th className="text-right py-2 px-2">Trades</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 50).map((r, i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 px-2 text-gray-300 text-xs">{r.feature_set}</td>
                  <td className="py-2 px-2 text-gray-300">{r.model}</td>
                  <td className="py-2 px-2 text-gray-400 text-xs">{r.symbol}</td>
                  <td className={`py-2 px-2 text-right font-mono ${
                    (r.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>{(r.pnl || 0).toFixed(1)}</td>
                  <td className="py-2 px-2 text-right font-mono text-gray-300">{(r.sharpe || 0).toFixed(2)}</td>
                  <td className="py-2 px-2 text-right font-mono text-red-400">{(r.drawdown || 0).toFixed(1)}</td>
                  <td className="py-2 px-2 text-right font-mono text-gray-300">{(r.accuracy || 0).toFixed(1)}%</td>
                  <td className="py-2 px-2 text-right font-mono text-gray-300">{(r.winrate || 0).toFixed(1)}%</td>
                  <td className="py-2 px-2 text-right text-gray-400">{r.total_trades || 0}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-gray-500">
                    No feature experiment results yet
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
