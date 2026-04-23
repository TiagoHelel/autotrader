import { Brain, ArrowUpCircle, ArrowDownCircle, MinusCircle } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import Badge from '../common/Badge'
import LoadingSpinner from '../common/LoadingSpinner'

const signalConfig = {
  BUY: { icon: ArrowUpCircle, color: 'text-buy', badge: 'buy', bg: 'bg-blue-500/10' },
  SELL: { icon: ArrowDownCircle, color: 'text-sell', badge: 'sell', bg: 'bg-orange-500/10' },
  HOLD: { icon: MinusCircle, color: 'text-gray-400', badge: 'hold', bg: 'bg-gray-500/10' },
}

export default function ModelDecision({ wsPredictions }) {
  const { data, loading } = useApi(() => api.getLatestPredictions(), [], { interval: 15000 })

  const predictions = wsPredictions?.length ? wsPredictions : data

  if (loading && !predictions) return <LoadingSpinner text="Loading predictions..." />

  const latest = Array.isArray(predictions) ? predictions[0] : predictions

  if (!latest) {
    return (
      <div className="glass-card rounded-xl p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-300">Latest Prediction</h3>
        <p className="text-sm text-gray-500">No predictions available</p>
      </div>
    )
  }

  const signal = latest.signal?.toUpperCase() || 'HOLD'
  const cfg = signalConfig[signal] || signalConfig.HOLD
  const SignalIcon = cfg.icon
  const confidence = latest.confidence ?? 0

  return (
    <div className="glass-card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">Latest Prediction</h3>
        <Brain className="h-4 w-4 text-purple-400" />
      </div>

      <div className="flex items-center gap-4">
        <div className={`flex h-14 w-14 items-center justify-center rounded-xl ${cfg.bg}`}>
          <SignalIcon className={`h-7 w-7 ${cfg.color}`} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-lg font-bold text-white">
              {latest.symbol || '-'}
            </span>
            <Badge variant={cfg.badge}>{signal}</Badge>
          </div>
          <p className="mt-0.5 text-xs text-gray-500">
            {latest.model_name || 'Model'} &middot; {timeAgo(latest.timestamp)}
          </p>
        </div>
      </div>

      {/* Confidence Bar */}
      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="text-gray-500">Confidence</span>
          <span className="font-mono font-medium text-gray-300">
            {(confidence * 100).toFixed(1)}%
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-gray-900">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              signal === 'BUY' ? 'bg-buy' : signal === 'SELL' ? 'bg-sell' : 'bg-gray-500'
            }`}
            style={{ width: `${(confidence * 100).toFixed(1)}%` }}
          />
        </div>
      </div>
    </div>
  )
}

function timeAgo(ts) {
  if (!ts) return ''
  const now = Date.now()
  const t = new Date(ts).getTime()
  const diff = Math.max(0, Math.floor((now - t) / 1000))
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
