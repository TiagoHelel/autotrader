import { ExternalLink, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import Badge from '../common/Badge'
import LoadingSpinner from '../common/LoadingSpinner'

export default function NewsFeed() {
  const { data, loading } = useApi(() => api.getNews(30), [], { interval: 30000 })

  if (loading) return <LoadingSpinner text="Loading news..." />

  const news = data || []

  return (
    <div className="glass-card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">News Feed</h3>
        <span className="rounded-md bg-gray-700 px-2 py-0.5 text-xs text-gray-400">
          {news.length} items
        </span>
      </div>

      {news.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-600">No news available</p>
      ) : (
        <div className="max-h-[600px] space-y-2 overflow-y-auto pr-1">
          {news.map((item) => {
            const impact = item.impact?.toUpperCase()
            const impactBadge =
              impact === 'HIGH' ? 'high' : impact === 'MEDIUM' ? 'medium' : 'low'

            const sentiment = item.sentiment?.toLowerCase()
            const SentimentIcon =
              sentiment === 'positive'
                ? TrendingUp
                : sentiment === 'negative'
                ? TrendingDown
                : Minus
            const sentimentColor =
              sentiment === 'positive'
                ? 'text-profit'
                : sentiment === 'negative'
                ? 'text-loss'
                : 'text-gray-500'

            return (
              <div
                key={item.id}
                className="rounded-lg border border-gray-800/50 bg-gray-900/30 p-3 transition-colors hover:bg-gray-800/30"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium leading-snug text-gray-200">
                      {item.title}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge variant={impactBadge}>{impact || 'LOW'}</Badge>
                      {item.currency && (
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-400">
                          {item.currency}
                        </span>
                      )}
                      <span className="text-xs text-gray-600">{item.source}</span>
                      <span className="text-xs text-gray-600">&middot;</span>
                      <span className="text-xs text-gray-600">{timeAgo(item.timestamp)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <SentimentIcon className={`h-4 w-4 ${sentimentColor}`} />
                    {item.score !== undefined && item.score !== null && (
                      <span
                        className={`font-mono text-xs font-medium ${
                          item.score > 0 ? 'text-profit' : item.score < 0 ? 'text-loss' : 'text-gray-500'
                        }`}
                      >
                        {item.score > 0 ? '+' : ''}
                        {item.score.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
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
