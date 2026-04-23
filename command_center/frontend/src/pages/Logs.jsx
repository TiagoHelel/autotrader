import { useState } from 'react'
import { Filter } from 'lucide-react'
import useWebSocket from '../hooks/useWebSocket'
import useApi from '../hooks/useApi'
import { api } from '../services/api'
import LogPanel from '../components/logs/LogPanel'

const REFRESH_INTERVAL = 30_000 // 30 seconds

export default function Logs() {
  const { logs } = useWebSocket()
  const [tab, setTab] = useState('system')
  const [symbolFilter, setSymbolFilter] = useState('')
  const [modelFilter, setModelFilter] = useState('')

  const { data: predLogs } = useApi(
    () => api.getRecentLogs(200), [], { interval: REFRESH_INTERVAL }
  )
  const { data: symbolsData } = useApi(() => api.getSymbols(), [])

  const allLogs = predLogs?.logs || []
  const symbols = (symbolsData?.symbols || []).map(s => s.symbol)

  // Filter logs
  const filteredLogs = allLogs.filter(l => {
    if (tab !== 'all' && l.type !== tab) return false
    if (symbolFilter && l.symbol !== symbolFilter) return false
    if (modelFilter && l.model && !l.model.includes(modelFilter)) return false
    return true
  })

  return (
    <div className="animate-fade-in flex h-full flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: 'var(--theme-text)' }}>Logs</h2>
          <p className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>System, prediction, and decision logs</p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <select
            value={symbolFilter}
            onChange={e => setSymbolFilter(e.target.value)}
            className="text-xs bg-transparent border border-gray-700 rounded px-2 py-1 text-gray-300 focus:outline-none focus:border-blue-500"
          >
            <option value="" className="bg-gray-900">All Symbols</option>
            {symbols.map(s => (
              <option key={s} value={s} className="bg-gray-900">{s}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Filter model..."
            value={modelFilter}
            onChange={e => setModelFilter(e.target.value)}
            className="text-xs bg-transparent border border-gray-700 rounded px-2 py-1 text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500 w-28"
          />
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-800 pb-0">
        {[
          { key: 'system', label: 'System' },
          { key: 'prediction', label: 'Predictions' },
          { key: 'decision', label: 'Decisions' },
          { key: 'signal', label: 'Signals' },
          { key: 'session', label: 'Sessions' },
          { key: 'trade', label: 'Trades' },
          { key: 'all', label: 'All' },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Prediction Logs Table */}
      {tab !== 'system' ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-gray-950">
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-2">Timestamp</th>
                <th className="text-left py-2 px-2">Type</th>
                <th className="text-left py-2 px-2">Symbol</th>
                <th className="text-left py-2 px-2">Model</th>
                <th className="text-left py-2 px-2">Details</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log, i) => (
                <tr key={i} className="border-b border-gray-800/30 hover:bg-gray-800/20">
                  <td className="py-1.5 px-2 text-gray-500 font-mono">{log.timestamp?.slice(0, 19)}</td>
                  <td className="py-1.5 px-2">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-xs ${
                      log.type === 'prediction' ? 'bg-blue-500/20 text-blue-400' :
                      log.type === 'decision' ? 'bg-green-500/20 text-green-400' :
                      log.type === 'signal' ? 'bg-emerald-500/20 text-emerald-400' :
                      log.type === 'session' ? 'bg-amber-500/20 text-amber-400' :
                      log.type === 'trade' ? 'bg-purple-500/20 text-purple-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>{log.type}</span>
                  </td>
                  <td className="py-1.5 px-2 text-gray-300">{log.symbol || '-'}</td>
                  <td className="py-1.5 px-2 text-gray-400">{log.model || '-'}</td>
                  <td className="py-1.5 px-2 text-gray-500 truncate max-w-md">
                    {log.current_price ? `price=${log.current_price} t1=${log.pred_t1} t2=${log.pred_t2} t3=${log.pred_t3}` :
                     log.action ? `${log.action}: ${log.details}` :
                     log.message || '-'}
                  </td>
                </tr>
              ))}
              {filteredLogs.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-gray-500">
                    No logs to display
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="min-h-0 flex-1">
          <LogPanel wsLogs={logs} fullPage />
        </div>
      )}
    </div>
  )
}
