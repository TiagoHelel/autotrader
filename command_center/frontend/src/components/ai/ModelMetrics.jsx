import { Activity, Target, Crosshair, BarChart3, Gauge } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import LoadingSpinner from '../common/LoadingSpinner'

const metricConfig = [
  { key: 'accuracy', label: 'Accuracy', icon: Target, color: 'text-blue-400' },
  { key: 'precision_val', label: 'Precision', icon: Crosshair, color: 'text-purple-400' },
  { key: 'recall', label: 'Recall', icon: Activity, color: 'text-cyan-400' },
  { key: 'f1', label: 'F1 Score', icon: BarChart3, color: 'text-green-400' },
  { key: 'auc', label: 'AUC', icon: Gauge, color: 'text-yellow-400' },
]

export default function ModelMetrics() {
  const { data, loading } = useApi(() => api.getModelMetrics(), [])

  if (loading) return <LoadingSpinner text="Loading model metrics..." />

  const models = data || []

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-300">Model Performance</h3>

      {models.length === 0 ? (
        <div className="glass-card rounded-xl p-5">
          <p className="py-8 text-center text-sm text-gray-600">No model metrics available</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {models.map((model) => (
            <div key={model.model_name} className="glass-card rounded-xl p-5">
              <div className="mb-4 flex items-center justify-between">
                <h4 className="text-sm font-semibold text-white">{model.model_name}</h4>
                <span className="text-xs text-gray-500">
                  {model.timestamp ? timeAgo(model.timestamp) : ''}
                </span>
              </div>

              <div className="space-y-3">
                {metricConfig.map(({ key, label, icon: Icon, color }) => {
                  const val = model[key]
                  if (val === undefined || val === null) return null

                  return (
                    <div key={key} className="flex items-center gap-3">
                      <Icon className={`h-3.5 w-3.5 ${color}`} />
                      <span className="w-16 text-xs text-gray-500">{label}</span>
                      <div className="flex-1">
                        <div className="h-1.5 overflow-hidden rounded-full bg-gray-800">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all duration-500"
                            style={{ width: `${(val * 100).toFixed(0)}%` }}
                          />
                        </div>
                      </div>
                      <span className="w-12 text-right font-mono text-xs font-medium text-gray-300">
                        {(val * 100).toFixed(1)}%
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function timeAgo(ts) {
  if (!ts) return ''
  const diff = Math.max(0, Math.floor((Date.now() - new Date(ts + 'Z').getTime()) / 1000))
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
