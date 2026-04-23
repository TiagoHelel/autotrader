import { ArrowUpCircle, ArrowDownCircle } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import Badge from '../common/Badge'
import LoadingSpinner from '../common/LoadingSpinner'

export default function OpenPositions() {
  const { data, loading } = useApi(() => api.getPositions(), [], { interval: 5000 })

  if (loading) return <LoadingSpinner text="Loading positions..." />

  const positions = data || []

  return (
    <div className="glass-card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">Open Positions</h3>
        <span className="rounded-md bg-gray-700 px-2 py-0.5 text-xs text-gray-400">
          {positions.length} open
        </span>
      </div>

      {positions.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-600">No open positions</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-gray-700 text-gray-500">
                <th className="pb-2 pr-4 font-medium">Symbol</th>
                <th className="pb-2 pr-4 font-medium">Type</th>
                <th className="pb-2 pr-4 font-medium text-right">Volume</th>
                <th className="pb-2 pr-4 font-medium text-right">Open</th>
                <th className="pb-2 pr-4 font-medium text-right">Current</th>
                <th className="pb-2 pr-4 font-medium text-right">SL</th>
                <th className="pb-2 pr-4 font-medium text-right">TP</th>
                <th className="pb-2 font-medium text-right">PnL</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => {
                const isBuy = pos.type?.toLowerCase() === 'buy'
                const pnl = pos.pnl ?? 0
                const isProfit = pnl >= 0

                return (
                  <tr
                    key={pos.id}
                    className="border-b border-gray-800/50 transition-colors hover:bg-gray-800/30"
                  >
                    <td className="py-2.5 pr-4 font-mono font-medium text-white">
                      {pos.symbol}
                    </td>
                    <td className="py-2.5 pr-4">
                      <div className="flex items-center gap-1">
                        {isBuy ? (
                          <ArrowUpCircle className="h-3.5 w-3.5 text-buy" />
                        ) : (
                          <ArrowDownCircle className="h-3.5 w-3.5 text-sell" />
                        )}
                        <Badge variant={isBuy ? 'buy' : 'sell'}>
                          {pos.type?.toUpperCase()}
                        </Badge>
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-gray-300">
                      {pos.volume}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-gray-400">
                      {formatPrice(pos.open_price)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-gray-300">
                      {formatPrice(pos.current_price)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-gray-500">
                      {formatPrice(pos.sl)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-gray-500">
                      {formatPrice(pos.tp)}
                    </td>
                    <td
                      className={`py-2.5 text-right font-mono font-semibold ${
                        isProfit ? 'text-profit' : 'text-loss'
                      }`}
                    >
                      {isProfit ? '+' : ''}
                      ${pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
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

function formatPrice(price) {
  if (price === null || price === undefined) return '-'
  return Number(price).toFixed(5)
}
