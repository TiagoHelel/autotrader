import { useEffect, useRef, useState } from 'react'
import { Terminal, ArrowDown } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import LoadingSpinner from '../common/LoadingSpinner'

const levelColors = {
  INFO: 'text-gray-400',
  DEBUG: 'text-gray-500',
  WARNING: 'text-yellow-400',
  WARN: 'text-yellow-400',
  ERROR: 'text-red-400',
  CRITICAL: 'text-red-500',
}

const levelBg = {
  ERROR: 'bg-red-500/5',
  CRITICAL: 'bg-red-500/10',
  WARNING: 'bg-yellow-500/5',
  WARN: 'bg-yellow-500/5',
}

export default function LogPanel({ wsLogs = [], fullPage = false }) {
  const { data, loading } = useApi(() => api.getLogs(200), [])
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('ALL')
  const containerRef = useRef(null)

  const allLogs = [...(data || []), ...wsLogs]

  const filteredLogs =
    filter === 'ALL'
      ? allLogs
      : allLogs.filter((l) => l.level?.toUpperCase() === filter)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [filteredLogs.length, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  if (loading && !wsLogs.length) return <LoadingSpinner text="Loading logs..." />

  return (
    <div className={`glass-card rounded-xl ${fullPage ? 'flex h-full flex-col' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700/50 px-5 py-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-300">System Logs</h3>
          <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-500">
            {filteredLogs.length}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {['ALL', 'INFO', 'WARNING', 'ERROR'].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setFilter(lvl)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                filter === lvl
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>

      {/* Log content */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className={`overflow-y-auto p-3 font-mono text-xs leading-relaxed ${
          fullPage ? 'flex-1' : 'max-h-[500px]'
        }`}
      >
        {filteredLogs.length === 0 ? (
          <p className="py-8 text-center text-gray-600">No logs to display</p>
        ) : (
          filteredLogs.map((log, i) => {
            const level = log.level?.toUpperCase() || 'INFO'
            const color = levelColors[level] || 'text-gray-400'
            const bg = levelBg[level] || ''

            return (
              <div
                key={log.id || i}
                className={`flex gap-3 rounded px-2 py-1 hover:bg-gray-800/50 ${bg}`}
              >
                <span className="shrink-0 text-gray-600">
                  {formatTimestamp(log.timestamp)}
                </span>
                <span className={`w-12 shrink-0 font-semibold ${color}`}>
                  {level.slice(0, 4).padEnd(4)}
                </span>
                <span className="shrink-0 text-gray-600">
                  {log.module || '-'}
                </span>
                <span className="text-gray-300">{log.message}</span>
              </div>
            )
          })
        )}
      </div>

      {/* Auto-scroll indicator */}
      {!autoScroll && (
        <div className="border-t border-gray-700/50 px-3 py-2">
          <button
            onClick={() => {
              setAutoScroll(true)
              if (containerRef.current) {
                containerRef.current.scrollTop = containerRef.current.scrollHeight
              }
            }}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
          >
            <ArrowDown className="h-3 w-3" />
            Scroll to bottom
          </button>
        </div>
      )}
    </div>
  )
}

function formatTimestamp(ts) {
  if (!ts) return '--:--:--'
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false })
}
