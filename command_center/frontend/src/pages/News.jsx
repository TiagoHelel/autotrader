import { useMemo, useState, useCallback } from 'react'
import { TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

export default function News() {
  const { data: newsData, loading, error: newsError, refetch: refetchNews } = useApi(
    () => api.getNewsLatest(50), [], { interval: 60000 }
  )
  const { data: llmData, error: llmError, refetch: refetchLlm } = useApi(
    () => api.getNewsLlm(50), [], { interval: 60000 }
  )
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      await api.refreshNews()

      for (let attempt = 0; attempt < 5; attempt += 1) {
        await new Promise((r) => setTimeout(r, 1500))
        const status = await api.getNewsRefreshStatus()
        if (!status.running) break
      }

      refetchNews()
      refetchLlm()
    } catch (e) {
      console.error('Refresh failed:', e)
    } finally {
      setRefreshing(false)
    }
  }, [refetchNews, refetchLlm])

  const events = Array.isArray(newsData?.events) ? newsData.events : []
  const llmFeatures = Array.isArray(llmData?.llm_features) ? llmData.llm_features : []

  const llmMap = useMemo(() => {
    const map = {}
    llmFeatures.forEach((feature) => {
      if (feature.name) {
        map[feature.name] = feature
      }
    })
    return map
  }, [llmFeatures])

  const currencyScores = useMemo(() => {
    const map = {}
    events.forEach((event) => {
      if (!event.currency) return

      if (!map[event.currency]) {
        map[event.currency] = { basic: 0, llm: 0, count: 0 }
      }

      map[event.currency].basic += Number(event.sentiment_basic) || 0
      map[event.currency].count += 1

      const llm = llmMap[event.name]
      if (llm) {
        map[event.currency].llm += Number(llm.sentiment_score) || 0
      }
    })

    return Object.entries(map)
      .map(([currency, { basic, llm, count }]) => ({
        currency,
        basicAvg: count ? basic / count : 0,
        llmAvg: count ? llm / count : 0,
        count,
      }))
      .sort((a, b) => b.basicAvg - a.basicAvg)
  }, [events, llmMap])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    )
  }

  if (newsError) {
    return (
      <div className="animate-fade-in space-y-6">
        <div>
          <h2 className="text-xl font-bold text-white">News</h2>
          <p className="text-sm text-red-400">Failed to load news feed: {newsError}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">News</h2>
          <p className="text-sm text-gray-500">
            {`Economic calendar - ${events.length} events${llmError ? ' (LLM unavailable)' : ' with sentiment analysis'}`}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Fetching...' : 'Refresh News'}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="glass-card rounded-xl p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-300">Economic Events</h3>
              <span className="rounded-md bg-gray-700 px-2 py-0.5 text-xs text-gray-400">
                {events.length} events
              </span>
            </div>

            <div className="max-h-[600px] space-y-2 overflow-y-auto pr-1">
              {events.length === 0 ? (
                <p className="py-8 text-center text-sm text-gray-600">
                  No news available. Run news ingestion first.
                </p>
              ) : (
                events.map((event, index) => {
                  const llm = llmMap[event.name]
                  const impact = Number(event.impact_num) || 0
                  const signal = event.signal

                  return (
                    <div
                      key={`${event.name}-${event.timestamp}-${index}`}
                      className="rounded-lg border border-gray-800/50 bg-gray-900/30 p-3 transition-colors hover:bg-gray-800/30"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <p className="text-sm font-medium leading-snug text-gray-200">
                            {event.name}
                          </p>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${
                              impact >= 3 ? 'bg-red-500/20 text-red-400'
                                : impact >= 2 ? 'bg-yellow-500/20 text-yellow-400'
                                : 'bg-gray-700 text-gray-400'
                            }`}>
                              Impact {impact}
                            </span>
                            {event.currency && (
                              <span className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-400">
                                {event.currency}
                              </span>
                            )}
                            {event.event_type && event.event_type !== 'None' && (
                              <span className="text-xs text-gray-600">{event.event_type}</span>
                            )}
                            <span className="text-xs text-gray-600">
                              {event.timestamp?.slice(0, 16)}
                            </span>
                          </div>
                          {(event.actual || event.forecast || event.previous) && (
                            <div className="mt-1 flex gap-3 text-xs">
                              {event.actual && event.actual !== 'None' && (
                                <span className="text-gray-300">Act: <span className="font-mono">{event.actual}</span></span>
                              )}
                              {event.forecast && event.forecast !== 'None' && (
                                <span className="text-gray-500">Fcst: <span className="font-mono">{event.forecast}</span></span>
                              )}
                              {event.previous && event.previous !== 'None' && (
                                <span className="text-gray-500">Prev: <span className="font-mono">{event.previous}</span></span>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <div className="flex items-center gap-1">
                            {signal === 'good' ? (
                              <TrendingUp className="h-3.5 w-3.5 text-green-400" />
                            ) : signal === 'bad' ? (
                              <TrendingDown className="h-3.5 w-3.5 text-red-400" />
                            ) : (
                              <Minus className="h-3.5 w-3.5 text-gray-500" />
                            )}
                            <span className="text-xs text-gray-500">basic</span>
                          </div>
                          {llm && (
                            <div className="flex items-center gap-1">
                              <span className={`font-mono text-xs font-medium ${
                                Number(llm.sentiment_score) > 0.1 ? 'text-green-400'
                                  : Number(llm.sentiment_score) < -0.1 ? 'text-red-400'
                                  : 'text-gray-500'
                              }`}>
                                {Number(llm.sentiment_score) > 0 ? '+' : ''}
                                {Number(llm.sentiment_score).toFixed(2)}
                              </span>
                              <span className="text-xs text-gray-600">LLM</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>

        <div>
          <div className="glass-card rounded-xl p-5">
            <h3 className="mb-4 text-sm font-semibold text-gray-300">Currency Sentiment</h3>
            {currencyScores.length === 0 ? (
              <p className="py-8 text-center text-sm text-gray-600">No sentiment data</p>
            ) : (
              <div className="space-y-3">
                {currencyScores.map(({ currency, basicAvg, llmAvg, count }) => {
                  const maxAbs = Math.max(
                    ...currencyScores.map((score) => Math.max(Math.abs(score.basicAvg), Math.abs(score.llmAvg))),
                    0.01
                  )

                  return (
                    <div key={currency}>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-white">{currency}</span>
                          <span className="text-gray-600">{count} ev</span>
                        </div>
                        <div className="flex gap-2">
                          <span className={`font-mono ${
                            basicAvg > 0 ? 'text-green-400' : basicAvg < 0 ? 'text-red-400' : 'text-gray-500'
                          }`}>
                            B:{basicAvg.toFixed(2)}
                          </span>
                          <span className={`font-mono ${
                            llmAvg > 0 ? 'text-green-400' : llmAvg < 0 ? 'text-red-400' : 'text-gray-500'
                          }`}>
                            L:{llmAvg.toFixed(2)}
                          </span>
                        </div>
                      </div>
                      <div className="relative h-2 overflow-hidden rounded-full bg-gray-800">
                        <div
                          className={`absolute h-full rounded-full transition-all duration-500 ${
                            basicAvg >= 0
                              ? 'left-1/2 bg-gradient-to-r from-green-600 to-green-400'
                              : 'right-1/2 bg-gradient-to-l from-red-600 to-red-400'
                          }`}
                          style={{ width: `${Math.abs(basicAvg) / maxAbs * 50}%` }}
                        />
                        <div className="absolute left-1/2 top-0 h-full w-px bg-gray-600" />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
