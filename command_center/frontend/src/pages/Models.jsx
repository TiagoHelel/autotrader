import { useMemo } from 'react'
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'
import { Trophy, Medal, Award, AlertTriangle, ShieldCheck } from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

const REFRESH_INTERVAL = 30_000 // 30 seconds
const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7']

export default function Models() {
  const { data: rankingData, loading } = useApi(
    () => api.getModelsPerformance(), [], { interval: REFRESH_INTERVAL }
  )
  const { data: perfOverTime } = useApi(
    () => api.getModelsPerformanceOverTime(), [], { interval: REFRESH_INTERVAL }
  )
  const { data: modelsInfo } = useApi(
    () => api.getModelsInfo(), [], {}
  )
  const { data: validationData } = useApi(
    () => api.getModelsValidation(), [], { interval: REFRESH_INTERVAL }
  )

  const ranking = rankingData?.ranking || []
  const models = modelsInfo?.models || []
  const validation = validationData?.validation || []

  // Map validation results by model name for quick lookup
  const validationByModel = useMemo(() => {
    const map = {}
    validation.forEach(v => { map[v.model] = v })
    return map
  }, [validation])

  // Chart data for performance over time
  const timeData = useMemo(() => {
    if (!perfOverTime?.data?.length) return []
    const byTime = {}
    perfOverTime.data.forEach(d => {
      const t = d.timestamp?.slice(0, 16) || ''
      if (!byTime[t]) byTime[t] = { time: t }
      byTime[t][d.model] = d.rolling_accuracy
    })
    return Object.values(byTime).sort((a, b) => a.time.localeCompare(b.time))
  }, [perfOverTime])

  const modelNames = useMemo(() => {
    return [...new Set((perfOverTime?.data || []).map(d => d.model))]
  }, [perfOverTime])

  // Radar data for model comparison
  const radarData = useMemo(() => {
    if (!ranking.length) return []
    const maxPred = Math.max(...ranking.map(r => r.total_predictions || 1))
    return ranking.map(r => ({
      model: r.model,
      accuracy: r.accuracy || 0,
      inverseMAE: Math.max(0, 100 - (r.mae || 0) * 10000),
      inverseMAPE: Math.max(0, 100 - (r.mape || 0)),
      volume: ((r.total_predictions || 0) / maxPred) * 100,
    }))
  }, [ranking])

  const rankIcons = [Trophy, Medal, Award]

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
        <h2 className="text-xl font-bold text-white">Model Ranking</h2>
        <p className="text-sm text-gray-500">Compare and track model performance</p>
      </div>

      {/* Ranking Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {ranking.map((r, i) => {
          const RankIcon = rankIcons[i] || null
          const val = validationByModel[r.model]
          return (
            <div key={r.model} className={`glass-card rounded-xl p-5 ${
              i === 0 ? 'ring-1 ring-yellow-500/30' : ''
            }`}>
              <div className="flex items-center gap-2 mb-3">
                <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  i === 0 ? 'bg-yellow-500/20 text-yellow-400' :
                  i === 1 ? 'bg-gray-400/20 text-gray-300' :
                  i === 2 ? 'bg-orange-500/20 text-orange-400' :
                  'bg-gray-700 text-gray-400'
                }`}>
                  {RankIcon ? <RankIcon className="h-3.5 w-3.5" /> : `#${i + 1}`}
                </span>
                <span className="text-sm font-semibold text-white truncate">{r.model}</span>
                {val?.overfit_warning && (
                  <AlertTriangle className="h-3.5 w-3.5 text-orange-400" title="Overfitting detected" />
                )}
                {val && !val.overfit_warning && (
                  <ShieldCheck className="h-3.5 w-3.5 text-green-400" title="Validation OK" />
                )}
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">Accuracy</span>
                  <span className={`font-mono font-semibold ${
                    r.accuracy >= 60 ? 'text-green-400' : r.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'
                  }`}>{(r.accuracy || 0).toFixed(1)}%</span>
                </div>
                {val?.cpcv_score != null && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">CPCV Score</span>
                    <span className={`font-mono font-semibold ${
                      val.cpcv_score >= 0.55 ? 'text-green-400' : val.cpcv_score >= 0.45 ? 'text-yellow-400' : 'text-red-400'
                    }`}>{(val.cpcv_score * 100).toFixed(1)}%</span>
                  </div>
                )}
                {val?.std != null && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Stability (std)</span>
                    <span className={`font-mono ${
                      val.std <= 0.05 ? 'text-green-400' : val.std <= 0.10 ? 'text-yellow-400' : 'text-red-400'
                    }`}>{(val.std * 100).toFixed(2)}%</span>
                  </div>
                )}
                {val?.overfit_gap != null && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Overfit Gap</span>
                    <span className={`font-mono ${
                      val.overfit_warning ? 'text-orange-400' : 'text-green-400'
                    }`}>{(val.overfit_gap * 100).toFixed(2)}%</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-500">MAE</span>
                  <span className="text-gray-300 font-mono">{(r.mae || 0).toFixed(5)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">MAPE</span>
                  <span className="text-gray-300 font-mono">{(r.mape || 0).toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Predictions</span>
                  <span className="text-gray-300">{r.total_predictions || 0}</span>
                </div>
              </div>
              {val?.overfit_warning && (
                <div className="mt-3 px-2 py-1 bg-orange-500/10 border border-orange-500/20 rounded text-[10px] text-orange-400">
                  Overfitting: train-val gap {(val.overfit_gap * 100).toFixed(1)}%
                </div>
              )}
            </div>
          )
        })}
        {ranking.length === 0 && (
          <div className="col-span-full glass-card rounded-xl p-8 text-center text-gray-500">
            No model performance data yet. Run the prediction engine first.
          </div>
        )}
      </div>

      {/* CPCV Validation Summary */}
      {validation.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">CPCV Validation (Purged Cross-Validation)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-2 px-3">Model</th>
                  <th className="text-right py-2 px-3">CPCV Score</th>
                  <th className="text-right py-2 px-3">Std (Stability)</th>
                  <th className="text-right py-2 px-3">Overfit Gap</th>
                  <th className="text-right py-2 px-3">Folds</th>
                  <th className="text-center py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {validation.map((v) => (
                  <tr key={v.model} className="border-b border-gray-800/50">
                    <td className="py-2 px-3 text-gray-300 font-medium">{v.model}</td>
                    <td className={`py-2 px-3 text-right font-mono font-semibold ${
                      (v.cpcv_score || 0) >= 0.55 ? 'text-green-400' :
                      (v.cpcv_score || 0) >= 0.45 ? 'text-yellow-400' : 'text-red-400'
                    }`}>{((v.cpcv_score || 0) * 100).toFixed(1)}%</td>
                    <td className={`py-2 px-3 text-right font-mono ${
                      (v.std || 0) <= 0.05 ? 'text-green-400' : 'text-yellow-400'
                    }`}>{((v.std || 0) * 100).toFixed(2)}%</td>
                    <td className={`py-2 px-3 text-right font-mono ${
                      v.overfit_warning ? 'text-orange-400' : 'text-green-400'
                    }`}>{((v.overfit_gap || 0) * 100).toFixed(2)}%</td>
                    <td className="py-2 px-3 text-right text-gray-400">{v.n_folds || '-'}</td>
                    <td className="py-2 px-3 text-center">
                      {v.overfit_warning ? (
                        <span className="inline-flex items-center gap-1 text-orange-400 text-xs">
                          <AlertTriangle className="h-3 w-3" /> Overfit
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-green-400 text-xs">
                          <ShieldCheck className="h-3 w-3" /> OK
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Performance Over Time */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Performance Over Time</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={timeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
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
        </div>

        {/* Model Comparison Bar */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Model Comparison</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={ranking}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="model" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              <Bar dataKey="accuracy" name="Accuracy %" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="mape" name="MAPE %" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* PnL-Based Ranking */}
      <PnlRanking />

      {/* Model Info Table */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Model Details</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-3">Model</th>
                <th className="text-left py-2 px-3">Parameters</th>
                <th className="text-left py-2 px-3">Features</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, i) => (
                <tr key={i} className="border-b border-gray-800/50">
                  <td className="py-2 px-3 text-gray-300 font-medium">{m.name}</td>
                  <td className="py-2 px-3 text-gray-400 font-mono text-xs">
                    {JSON.stringify(m.params)}
                  </td>
                  <td className="py-2 px-3 text-gray-400 text-xs">
                    {Array.isArray(m.features_used) ? m.features_used.join(', ') : m.features_used}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function PnlRanking() {
  const { data: rankingData } = useApi(
    () => api.getExperimentsRanking(), [], { interval: REFRESH_INTERVAL }
  )
  const { data: fsData } = useApi(
    () => api.getFeatureSetRanking(), [], { interval: REFRESH_INTERVAL }
  )

  const ranking = rankingData?.ranking || []
  const fsRanking = fsData?.ranking || []

  if (!ranking.length && !fsRanking.length) return null

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Ranking by PnL */}
      {ranking.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Ranking by PnL Score</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-2 px-2">#</th>
                  <th className="text-left py-2 px-2">Model</th>
                  <th className="text-right py-2 px-2">Avg PnL</th>
                  <th className="text-right py-2 px-2">Sharpe</th>
                  <th className="text-right py-2 px-2">Drawdown</th>
                  <th className="text-right py-2 px-2">Score</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((r, i) => (
                  <tr key={r.model} className="border-b border-gray-800/50">
                    <td className="py-2 px-2 text-gray-500 font-mono">{r.rank || i + 1}</td>
                    <td className="py-2 px-2 text-gray-300 font-medium">{r.model}</td>
                    <td className={`py-2 px-2 text-right font-mono ${
                      (r.avg_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>{(r.avg_pnl || 0).toFixed(1)}</td>
                    <td className="py-2 px-2 text-right font-mono text-gray-300">{(r.avg_sharpe || 0).toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-red-400">{(r.avg_drawdown || 0).toFixed(1)}</td>
                    <td className="py-2 px-2 text-right font-mono font-semibold text-blue-400">{(r.avg_score || 0).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Ranking by Feature Set */}
      {fsRanking.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Ranking by Feature Set</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-2 px-2">Feature Set</th>
                  <th className="text-right py-2 px-2">Avg PnL</th>
                  <th className="text-right py-2 px-2">Sharpe</th>
                  <th className="text-right py-2 px-2">Accuracy</th>
                  <th className="text-right py-2 px-2">Score</th>
                </tr>
              </thead>
              <tbody>
                {fsRanking.map((r) => (
                  <tr key={r.feature_set} className="border-b border-gray-800/50">
                    <td className="py-2 px-2 text-gray-300 font-medium">{r.feature_set}</td>
                    <td className={`py-2 px-2 text-right font-mono ${
                      (r.avg_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>{(r.avg_pnl || 0).toFixed(1)}</td>
                    <td className="py-2 px-2 text-right font-mono text-gray-300">{(r.avg_sharpe || 0).toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-gray-300">{(r.avg_accuracy || 0).toFixed(1)}%</td>
                    <td className="py-2 px-2 text-right font-mono font-semibold text-blue-400">{(r.avg_score || 0).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
