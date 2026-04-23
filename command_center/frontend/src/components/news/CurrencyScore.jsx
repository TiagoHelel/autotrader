import { useMemo } from 'react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import LoadingSpinner from '../common/LoadingSpinner'

export default function CurrencyScore() {
  const { data, loading } = useApi(() => api.getNews(50), [], { interval: 30000 })

  const scores = useMemo(() => {
    if (!data?.length) return []

    const currencyMap = {}
    data.forEach((item) => {
      if (!item.currency) return
      if (!currencyMap[item.currency]) {
        currencyMap[item.currency] = { sum: 0, count: 0 }
      }
      currencyMap[item.currency].sum += item.score ?? 0
      currencyMap[item.currency].count += 1
    })

    return Object.entries(currencyMap)
      .map(([currency, { sum, count }]) => ({
        currency,
        avgScore: sum / count,
        count,
      }))
      .sort((a, b) => b.avgScore - a.avgScore)
  }, [data])

  if (loading) return <LoadingSpinner text="Loading sentiment..." />

  const maxAbs = Math.max(...scores.map((s) => Math.abs(s.avgScore)), 0.01)

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="mb-4 text-sm font-semibold text-gray-300">Currency Sentiment</h3>

      {scores.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-600">No sentiment data</p>
      ) : (
        <div className="space-y-3">
          {scores.map(({ currency, avgScore, count }) => {
            const isPositive = avgScore >= 0
            const widthPct = Math.min((Math.abs(avgScore) / maxAbs) * 100, 100)

            return (
              <div key={currency}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-white">{currency}</span>
                    <span className="text-gray-600">{count} news</span>
                  </div>
                  <span
                    className={`font-mono font-medium ${
                      isPositive ? 'text-profit' : 'text-loss'
                    }`}
                  >
                    {isPositive ? '+' : ''}
                    {avgScore.toFixed(3)}
                  </span>
                </div>
                <div className="relative h-2 overflow-hidden rounded-full bg-gray-800">
                  {isPositive ? (
                    <div
                      className="absolute left-1/2 h-full rounded-full bg-gradient-to-r from-green-600 to-green-400 transition-all duration-500"
                      style={{ width: `${widthPct / 2}%` }}
                    />
                  ) : (
                    <div
                      className="absolute right-1/2 h-full rounded-full bg-gradient-to-l from-red-600 to-red-400 transition-all duration-500"
                      style={{ width: `${widthPct / 2}%` }}
                    />
                  )}
                  <div className="absolute left-1/2 top-0 h-full w-px bg-gray-600" />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
