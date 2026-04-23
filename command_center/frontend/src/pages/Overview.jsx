import { useMemo } from 'react'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import {
  TrendingUp, TrendingDown, Target, AlertCircle, Activity, Zap,
} from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

const REFRESH_INTERVAL = 30_000 // 30 seconds

export default function Overview() {
  const { data: metricsData, loading: metricsLoading } = useApi(
    () => api.getPredictMetrics(), [], { interval: REFRESH_INTERVAL }
  )
  const { data: perfOverTime } = useApi(
    () => api.getModelsPerformanceOverTime(), [], { interval: REFRESH_INTERVAL }
  )
  const { data: systemStatus } = useApi(
    () => api.getSystemStatus(), [], { interval: REFRESH_INTERVAL }
  )
  const { data: analyticsData } = useApi(
    () => api.getNewsAnalytics(), [], { interval: REFRESH_INTERVAL }
  )

  const global = metricsData?.global || {}
  const modelMetrics = metricsData?.metrics || []

  const chartData = useMemo(() => {
    if (!perfOverTime?.data?.length) return []
    // Group by timestamp, pivot models
    const byTime = {}
    perfOverTime.data.forEach(d => {
      const t = d.timestamp?.slice(0, 16) || ''
      if (!byTime[t]) byTime[t] = { time: t }
      byTime[t][`${d.model}_acc`] = d.rolling_accuracy
      byTime[t][`${d.model}_mae`] = d.rolling_mae
    })
    return Object.values(byTime).sort((a, b) => a.time.localeCompare(b.time))
  }, [perfOverTime])

  const modelNames = useMemo(() => {
    return [...new Set((perfOverTime?.data || []).map(d => d.model))]
  }, [perfOverTime])

  const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7']

  if (metricsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Prediction Overview</h2>
          <p className="text-sm text-gray-500">Global performance across all symbols and models</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${
            systemStatus?.status === 'running' ? 'bg-green-500 animate-pulse-dot' : 'bg-gray-600'
          }`} />
          <span className="text-xs text-gray-400">
            {systemStatus?.active_symbols || 0} symbols active
          </span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Global Accuracy"
          value={`${(global.global_accuracy || 0).toFixed(1)}%`}
          icon={Target}
          color="blue"
        />
        <KPICard
          label="Mean Abs Error"
          value={(global.global_mae || 0).toFixed(5)}
          icon={AlertCircle}
          color="yellow"
        />
        <KPICard
          label="Mean % Error"
          value={`${(global.global_mape || 0).toFixed(2)}%`}
          icon={Activity}
          color="purple"
        />
        <KPICard
          label="Total Predictions"
          value={global.total_predictions || 0}
          icon={Zap}
          color="green"
          sub={`${global.total_correct || 0} correct`}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Accuracy Over Time */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Accuracy Over Time</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              {modelNames.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={`${name}_acc`}
                  name={name}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* MAE Over Time */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">MAE Over Time</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} />
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
                  dataKey={`${name}_mae`}
                  name={name}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Performance by Model */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Performance by Model</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={modelMetrics} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} domain={[0, 100]} />
            <YAxis type="category" dataKey="model" tick={{ fontSize: 11, fill: '#e2e8f0' }} width={120} />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
              labelStyle={{ color: '#e2e8f0' }}
            />
            <Legend />
            <Bar dataKey="accuracy" name="Accuracy %" fill="#3b82f6" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* News Sentiment Overview */}
      {analyticsData?.analytics?.by_currency && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">
              News Sentiment by Currency (Basic vs LLM)
            </h3>
            <div className="space-y-3">
              {Object.entries(analyticsData.analytics.by_currency).map(([currency, stats]) => (
                <div key={currency} className="flex items-center gap-3">
                  <span className="w-10 font-mono text-xs font-bold text-white">{currency}</span>
                  <div className="flex-1 flex gap-2 items-center">
                    <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden relative">
                      <div
                        className="absolute h-full bg-yellow-500 rounded-full"
                        style={{
                          left: '50%',
                          width: `${Math.abs(stats.sentiment_basic_avg || 0) * 50}%`,
                          transform: (stats.sentiment_basic_avg || 0) < 0 ? 'translateX(-100%)' : 'none',
                        }}
                      />
                    </div>
                    <span className={`w-12 text-right font-mono text-xs ${
                      (stats.sentiment_basic_avg || 0) > 0 ? 'text-green-400' : (stats.sentiment_basic_avg || 0) < 0 ? 'text-red-400' : 'text-gray-500'
                    }`}>
                      {(stats.sentiment_basic_avg || 0).toFixed(2)}
                    </span>
                  </div>
                  <span className="text-xs text-gray-600">{stats.total_events} ev</span>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">
              High Impact Events Summary
            </h3>
            <div className="space-y-3">
              {Object.entries(analyticsData.analytics.by_currency)
                .filter(([, stats]) => stats.high_impact_count > 0)
                .sort((a, b) => b[1].high_impact_count - a[1].high_impact_count)
                .map(([currency, stats]) => (
                  <div key={currency} className="flex items-center justify-between">
                    <span className="font-mono text-sm text-white">{currency}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-red-400 font-bold">
                        {stats.high_impact_count} high impact
                      </span>
                      <span className="text-xs text-gray-500">
                        / {stats.total_events} total
                      </span>
                    </div>
                  </div>
                ))}
              {Object.values(analyticsData.analytics.by_currency).every(s => s.high_impact_count === 0) && (
                <p className="text-xs text-gray-600 text-center py-4">No high impact events</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function KPICard({ label, value, icon: Icon, color, sub }) {
  const colorMap = {
    blue: 'bg-blue-500/20 text-blue-400',
    green: 'bg-green-500/20 text-green-400',
    yellow: 'bg-yellow-500/20 text-yellow-400',
    purple: 'bg-purple-500/20 text-purple-400',
    red: 'bg-red-500/20 text-red-400',
  }
  return (
    <div className="glass-card rounded-xl p-5">
      <div className="flex items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${colorMap[color]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs text-gray-500">{label}</p>
          <p className="text-lg font-bold text-white">{value}</p>
          {sub && <p className="text-xs text-gray-500">{sub}</p>}
        </div>
      </div>
    </div>
  )
}
