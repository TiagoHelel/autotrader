import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import Badge from '../common/Badge'
import LoadingSpinner from '../common/LoadingSpinner'

const PAGE_SIZE = 15

export default function TradeHistory() {
  const [page, setPage] = useState(0)
  const { data, loading } = useApi(() => api.getPositionHistory(200), [], { interval: 30000 })

  if (loading) return <LoadingSpinner text="Loading history..." />

  const trades = data || []
  const totalPages = Math.ceil(trades.length / PAGE_SIZE)
  const paginated = trades.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div className="glass-card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">Trade History</h3>
        <span className="rounded-md bg-gray-700 px-2 py-0.5 text-xs text-gray-400">
          {trades.length} trades
        </span>
      </div>

      {trades.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-600">No trade history</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-gray-700 text-gray-500">
                  <th className="pb-2 pr-4 font-medium">Symbol</th>
                  <th className="pb-2 pr-4 font-medium">Type</th>
                  <th className="pb-2 pr-4 font-medium text-right">Volume</th>
                  <th className="pb-2 pr-4 font-medium text-right">Open</th>
                  <th className="pb-2 pr-4 font-medium text-right">Close</th>
                  <th className="pb-2 pr-4 font-medium text-right">PnL</th>
                  <th className="pb-2 pr-4 font-medium text-right">Duration</th>
                  <th className="pb-2 font-medium">Closed</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((t) => {
                  const pnl = t.pnl ?? 0
                  const isProfit = pnl >= 0
                  const isBuy = t.type?.toLowerCase() === 'buy'

                  return (
                    <tr
                      key={t.id}
                      className="border-b border-gray-800/50 transition-colors hover:bg-gray-800/30"
                    >
                      <td className="py-2.5 pr-4 font-mono font-medium text-white">
                        {t.symbol}
                      </td>
                      <td className="py-2.5 pr-4">
                        <Badge variant={isBuy ? 'buy' : 'sell'}>
                          {t.type?.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-gray-300">
                        {t.volume}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-gray-400">
                        {Number(t.open_price).toFixed(5)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-gray-400">
                        {Number(t.close_price).toFixed(5)}
                      </td>
                      <td
                        className={`py-2.5 pr-4 text-right font-mono font-semibold ${
                          isProfit ? 'text-profit' : 'text-loss'
                        }`}
                      >
                        {isProfit ? '+' : ''}${pnl.toFixed(2)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-gray-500">
                        {formatDuration(t.duration_minutes)}
                      </td>
                      <td className="py-2.5 text-gray-500">
                        {timeAgo(t.close_time)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-30"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-30"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function formatDuration(mins) {
  if (!mins && mins !== 0) return '-'
  if (mins < 60) return `${Math.round(mins)}m`
  const h = Math.floor(mins / 60)
  const m = Math.round(mins % 60)
  return `${h}h ${m}m`
}

function timeAgo(ts) {
  if (!ts) return '-'
  const diff = Math.max(0, Math.floor((Date.now() - new Date(ts + 'Z').getTime()) / 1000))
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
