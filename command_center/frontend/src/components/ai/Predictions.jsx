import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import Badge from '../common/Badge'
import LoadingSpinner from '../common/LoadingSpinner'

export default function Predictions() {
  const { data, loading } = useApi(() => api.getPredictions(), [], { interval: 10000 })

  if (loading) return <LoadingSpinner text="Loading predictions..." />

  const predictions = data || []

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="mb-4 text-sm font-semibold text-gray-300">Recent Predictions</h3>

      {predictions.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-600">No predictions available</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-gray-700 text-gray-500">
                <th className="pb-2 pr-4 font-medium">Symbol</th>
                <th className="pb-2 pr-4 font-medium">Signal</th>
                <th className="pb-2 pr-4 font-medium text-right">Confidence</th>
                <th className="pb-2 pr-4 font-medium">Model</th>
                <th className="pb-2 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map((p) => {
                const signal = p.signal?.toUpperCase() || 'HOLD'
                const badgeVariant =
                  signal === 'BUY' ? 'buy' : signal === 'SELL' ? 'sell' : 'hold'

                return (
                  <tr
                    key={p.id}
                    className="border-b border-gray-800/50 transition-colors hover:bg-gray-800/30"
                  >
                    <td className="py-2.5 pr-4 font-mono font-medium text-white">
                      {p.symbol}
                    </td>
                    <td className="py-2.5 pr-4">
                      <Badge variant={badgeVariant}>{signal}</Badge>
                    </td>
                    <td className="py-2.5 pr-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-700">
                          <div
                            className={`h-full rounded-full ${
                              signal === 'BUY'
                                ? 'bg-buy'
                                : signal === 'SELL'
                                ? 'bg-sell'
                                : 'bg-gray-500'
                            }`}
                            style={{ width: `${((p.confidence ?? 0) * 100).toFixed(0)}%` }}
                          />
                        </div>
                        <span className="font-mono text-gray-300">
                          {((p.confidence ?? 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 text-gray-400">{p.model_name || '-'}</td>
                    <td className="py-2.5 text-gray-500">{timeAgo(p.timestamp)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function timeAgo(ts) {
  if (!ts) return '-'
  const diff = Math.max(0, Math.floor((Date.now() - new Date(ts + 'Z').getTime()) / 1000))
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
