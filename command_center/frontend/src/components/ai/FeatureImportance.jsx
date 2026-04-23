import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import LoadingSpinner from '../common/LoadingSpinner'

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card rounded-lg px-3 py-2 text-xs">
      <p className="font-medium text-white">{payload[0].payload.feature_name}</p>
      <p className="font-mono text-gray-400">
        Importance: {(payload[0].value * 100).toFixed(2)}%
      </p>
    </div>
  )
}

export default function FeatureImportance() {
  const { data, loading } = useApi(() => api.getModelFeatures(), [])

  if (loading) return <LoadingSpinner text="Loading features..." />

  // data pode ser um dict {model_name: [...]} ou um array [...]
  let rawFeatures = []
  if (Array.isArray(data)) {
    rawFeatures = data
  } else if (data && typeof data === 'object') {
    // Pega o primeiro modelo (XGBoost por padrao) ou combina todos
    const firstModel = Object.keys(data)[0]
    rawFeatures = firstModel ? data[firstModel] : []
  }

  const features = rawFeatures
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 15)
    .map((f) => ({
      ...f,
      feature_short: f.feature_name?.length > 20
        ? f.feature_name.slice(0, 18) + '...'
        : f.feature_name,
    }))

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="mb-4 text-sm font-semibold text-gray-300">Feature Importance (Top 15)</h3>
      {features.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-600">No feature data available</p>
      ) : (
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={features} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 10, fill: '#64748b' }}
                axisLine={{ stroke: '#334155' }}
                tickLine={false}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              />
              <YAxis
                type="category"
                dataKey="feature_short"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                axisLine={{ stroke: '#334155' }}
                tickLine={false}
                width={130}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar
                dataKey="importance"
                fill="#3b82f6"
                radius={[0, 4, 4, 0]}
                barSize={16}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
