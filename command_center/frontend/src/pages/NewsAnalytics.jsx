import { useState, useMemo, useCallback } from 'react'
import {
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { RefreshCw } from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

const REFRESH_INTERVAL = 60_000

export default function NewsAnalytics() {
  const { data: analyticsData, loading, refetch: refetchAnalytics } = useApi(
    () => api.getNewsAnalytics(), [], { interval: REFRESH_INTERVAL }
  )
  const { data: newsData, refetch: refetchNews } = useApi(
    () => api.getNewsLatest(100), [], { interval: REFRESH_INTERVAL }
  )

  const [filterCurrency, setFilterCurrency] = useState('')
  const [filterImpact, setFilterImpact] = useState(0)
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

      refetchAnalytics()
      refetchNews()
    } catch (e) {
      console.error('Refresh failed:', e)
    } finally {
      setRefreshing(false)
    }
  }, [refetchAnalytics, refetchNews])

  const analytics = analyticsData?.analytics || {}
  const byCurrency = analytics.by_currency || {}
  const byImpact = analytics.by_impact || {}
  const basicVsLlm = analytics.basic_vs_llm || []
  const events = newsData?.events || []

  // Filter events
  const filteredEvents = useMemo(() => {
    let filtered = events
    if (filterCurrency) {
      filtered = filtered.filter(e => e.currency === filterCurrency)
    }
    if (filterImpact > 0) {
      filtered = filtered.filter(e => Number(e.impact_num) >= filterImpact)
    }
    return filtered
  }, [events, filterCurrency, filterImpact])

  // Currency chart data
  const currencyChartData = useMemo(() => {
    return Object.entries(byCurrency).map(([currency, stats]) => ({
      currency,
      events: stats.total_events,
      avg_impact: stats.avg_impact,
      sentiment: stats.sentiment_basic_avg,
      llm_sentiment: stats.sentiment_llm_avg || 0,
    })).sort((a, b) => b.events - a.events)
  }, [byCurrency])

  // Comparison chart data
  const comparisonData = useMemo(() => {
    return basicVsLlm.map(item => ({
      name: item.name?.slice(0, 30) || '',
      basic: item.basic,
      llm: item.llm,
      confidence: item.confidence,
    }))
  }, [basicVsLlm])

  const currencies = useMemo(() => {
    return [...new Set(events.map(e => e.currency).filter(Boolean))].sort()
  }, [events])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">News Analytics</h2>
          <p className="text-sm text-gray-500">
            Economic calendar analysis — {analytics.total_events || 0} events
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

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <select
          value={filterCurrency}
          onChange={(e) => setFilterCurrency(e.target.value)}
          className="glass-card rounded-lg px-3 py-2 text-sm text-white bg-transparent border border-gray-700 focus:border-blue-500 focus:outline-none"
        >
          <option value="" className="bg-gray-900">All Currencies</option>
          {currencies.map(c => (
            <option key={c} value={c} className="bg-gray-900">{c}</option>
          ))}
        </select>
        <select
          value={filterImpact}
          onChange={(e) => setFilterImpact(Number(e.target.value))}
          className="glass-card rounded-lg px-3 py-2 text-sm text-white bg-transparent border border-gray-700 focus:border-blue-500 focus:outline-none"
        >
          <option value={0} className="bg-gray-900">All Impact</option>
          <option value={1} className="bg-gray-900">Impact 1+</option>
          <option value={2} className="bg-gray-900">Impact 2+</option>
          <option value={3} className="bg-gray-900">Impact 3 (High)</option>
        </select>
        <span className="text-xs text-gray-500">
          Showing {filteredEvents.length} events
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Events by Currency */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Events by Currency</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={currencyChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="currency" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              <Bar dataKey="events" name="Events" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Impact Distribution */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Impact Distribution</h3>
          <div className="space-y-4 mt-6">
            {['1', '2', '3'].map(level => {
              const count = byImpact[level] || 0
              const max = Math.max(...Object.values(byImpact), 1)
              const pct = (count / max) * 100
              const colors = { '1': 'bg-green-500', '2': 'bg-yellow-500', '3': 'bg-red-500' }
              const labels = { '1': 'Low', '2': 'Medium', '3': 'High' }

              return (
                <div key={level}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-400">Impact {level} ({labels[level]})</span>
                    <span className="text-gray-300 font-mono">{count}</span>
                  </div>
                  <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${colors[level]} rounded-full transition-all duration-500`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Basic vs LLM Sentiment Comparison */}
      {comparisonData.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">
            Basic vs LLM Sentiment Comparison
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={comparisonData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" domain={[-1, 1]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis
                type="category" dataKey="name"
                tick={{ fontSize: 9, fill: '#e2e8f0' }}
                width={200}
              />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              <Bar dataKey="basic" name="Basic Sentiment" fill="#f59e0b" />
              <Bar dataKey="llm" name="LLM Sentiment" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Events Table */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Events</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-3">Time</th>
                <th className="text-left py-2 px-3">Currency</th>
                <th className="text-left py-2 px-3">Event</th>
                <th className="text-center py-2 px-3">Impact</th>
                <th className="text-center py-2 px-3">Signal</th>
                <th className="text-right py-2 px-3">Actual</th>
                <th className="text-right py-2 px-3">Forecast</th>
                <th className="text-right py-2 px-3">Previous</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.slice(0, 50).map((ev, i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 px-3 text-gray-400 font-mono text-xs">
                    {ev.timestamp?.slice(0, 16)}
                  </td>
                  <td className="py-2 px-3">
                    <span className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-300">
                      {ev.currency || ev.country}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-gray-300 max-w-[300px] truncate">
                    {ev.name}
                  </td>
                  <td className="py-2 px-3 text-center">
                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                      Number(ev.impact_num) >= 3
                        ? 'bg-red-500/20 text-red-400'
                        : Number(ev.impact_num) >= 2
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-gray-700 text-gray-400'
                    }`}>
                      {ev.impact_num}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <span className={`text-xs font-medium ${
                      ev.signal === 'good' ? 'text-green-400'
                        : ev.signal === 'bad' ? 'text-red-400'
                        : 'text-gray-500'
                    }`}>
                      {ev.signal}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-xs text-gray-300">
                    {ev.actual || '-'}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-xs text-gray-400">
                    {ev.forecast || '-'}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-xs text-gray-400">
                    {ev.previous || '-'}
                  </td>
                </tr>
              ))}
              {filteredEvents.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-gray-500">
                    No events match filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
