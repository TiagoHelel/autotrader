import { useEffect, useMemo, useRef, useState } from 'react'
import { Terminal } from 'lucide-react'
import useWebSocket from '../../hooks/useWebSocket'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import { useTheme } from '../../theme/ThemeProvider'

const TYPE_LABELS = {
  signal: 'SIGNAL',
  prediction: 'MODEL',
  news: 'NEWS',
  error: 'ERROR',
  warning: 'WARN',
  info: 'INFO',
  trade: 'TRADE',
  decision: 'MODEL',
  session: 'SESSION',
  system: 'SYS',
  healthcheck: 'HEALTH',
}

function classifyLog(entry) {
  if (entry.log_type && TYPE_LABELS[entry.log_type]) return entry.log_type

  const msg = (entry.message || entry.msg || '').toLowerCase()
  const level = (entry.level || '').toLowerCase()

  if (level === 'error') return 'error'
  if (level === 'warning' || level === 'warn') return 'warning'
  if (msg.includes('health')) return 'healthcheck'
  if (msg.includes('session') && msg.includes('score')) return 'session'
  if (msg.includes('signal') || msg.includes('buy') || msg.includes('sell') || msg.includes('hold')) return 'signal'
  if (msg.includes('predict') || msg.includes('pred_t') || msg.includes('model=')) return 'prediction'
  if (msg.includes('news') || msg.includes('sentiment') || msg.includes('impact')) return 'news'
  if (msg.includes('trade') || msg.includes('pnl') || msg.includes('backtest')) return 'trade'
  if (msg.includes('decision') || msg.includes('consensus')) return 'decision'
  return 'info'
}

function formatTimestamp(ts) {
  if (!ts) return '--:--:--'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return String(ts).slice(11, 19) || String(ts).slice(0, 8)
  return d.toLocaleTimeString('en-US', { hour12: false })
}

function extractMessage(log) {
  if (log.message && typeof log.message === 'string') return log.message
  if (log.msg && typeof log.msg === 'string') return log.msg
  if (log.details) return `${log.action || ''} ${log.details}`.trim()
  if (log.action) return `${log.action}: ${log.symbol || ''}`.trim()

  const { _src, _type, timestamp, ts, ...rest } = log
  const keys = Object.keys(rest)
  if (keys.length === 0) return 'NO DATA'
  return keys.slice(0, 4).map((k) => `${k}=${rest[k]}`).join(' ')
}

function toTerminalLine(log) {
  const ts = formatTimestamp(log.timestamp || log.ts)
  const type = TYPE_LABELS[log._type] || 'INFO'
  const raw = extractMessage(log).replace(/\s+/g, ' ').trim()
  return `[${ts}] [${type}] ${raw || 'NO MESSAGE'}`
}

function TypewriterLine({ text, active }) {
  const [visible, setVisible] = useState(active ? '' : text)

  useEffect(() => {
    if (!active) {
      setVisible(text)
      return
    }

    let cancelled = false
    let index = 0

    const tick = () => {
      if (cancelled) return
      index += 3
      setVisible(text.slice(0, index))
      if (index < text.length) {
        setTimeout(tick, 12)
      }
    }

    setVisible('')
    tick()

    return () => {
      cancelled = true
    }
  }, [text, active])

  return <span>{visible}</span>
}

export default function DataStream() {
  const { logs: wsLogs, connected } = useWebSocket()
  const { theme } = useTheme()
  const { data: recentLogs } = useApi(() => api.getRecentLogs(30), [], { interval: 15000 })
  const scrollRef = useRef(null)
  const lastKeyRef = useRef(null)
  const [typingKey, setTypingKey] = useState(null)

  const allLogs = useMemo(() => {
    const raw = Array.isArray(recentLogs) ? recentLogs : recentLogs?.logs ?? recentLogs?.data ?? []
    const apiLogs = raw.map((l) => ({ ...l, _src: 'api', _type: classifyLog(l) }))
    const ws = (wsLogs || []).map((l) => ({ ...l, _src: 'ws', _type: classifyLog(l) }))
    const merged = [...apiLogs, ...ws]
    const seen = new Set()
    const unique = merged.filter((l) => {
      const msg = extractMessage(l)
      const key = `${l.timestamp || l.ts || ''}_${msg.slice(0, 80)}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    return unique.slice(-80)
  }, [recentLogs, wsLogs])

  const renderedLogs = useMemo(() => (
    allLogs.map((log, index) => {
      const line = toTerminalLine(log)
      const key = `${log.timestamp || log.ts || 'no-ts'}_${index}_${line.slice(0, 40)}`
      return { key, line }
    })
  ), [allLogs])

  useEffect(() => {
    const last = renderedLogs[renderedLogs.length - 1]
    if (!last) return
    if (last.key !== lastKeyRef.current) {
      setTypingKey(last.key)
      lastKeyRef.current = last.key
    }
  }, [renderedLogs])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [renderedLogs.length, typingKey])

  const isMatrix = theme === 'matrix'

  if (!isMatrix) {
    return (
      <div className="themed-card rounded-xl p-4 flex flex-col h-full">
        <div className="mb-3 flex items-center justify-between shrink-0">
          <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)' }}>
            <Terminal className="h-3.5 w-3.5" style={{ color: 'var(--theme-accent)' }} />
            Data Stream
          </h3>
          <div className="flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-full ${connected ? 'bg-green-500 animate-pulse-dot' : 'bg-gray-600'}`} />
            <span className="text-xs text-gray-600">{connected ? 'LIVE' : 'OFFLINE'}</span>
          </div>
        </div>

        <div
          ref={scrollRef}
          className="overflow-y-auto rounded-lg p-3 font-mono text-xs leading-relaxed"
          style={{ background: 'var(--theme-bg-secondary)', height: '0', flex: '1 1 0', scrollBehavior: 'smooth' }}
        >
          {renderedLogs.length === 0 && (
            <div className="flex h-full items-center justify-center text-gray-600">Waiting for data...</div>
          )}
          {renderedLogs.map((log) => (
            <div key={log.key} className="animate-data-scroll border-b border-gray-900/50 py-0.5 text-gray-400">
              {log.line}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <section
      className="themed-card relative flex h-full flex-col overflow-hidden p-0"
      style={{
        background: '#000000',
        border: '1px solid rgba(0,255,65,0.2)',
      }}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          backgroundImage: 'repeating-linear-gradient(to bottom, rgba(0,255,65,0.05), rgba(0,255,65,0.05) 1px, transparent 1px, transparent 3px)',
        }}
      />

      <div className="relative z-10 border-b px-4 py-3" style={{ borderColor: 'rgba(0,255,65,0.18)' }}>
        <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.24em]" style={{ color: 'var(--theme-text-muted)' }}>
          <div className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5" style={{ color: 'var(--theme-accent)' }} />
            <span>Data Stream</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ color: connected ? 'var(--theme-text)' : 'var(--theme-text-muted)' }}>
              {connected ? 'ONLINE' : 'OFFLINE'}
            </span>
            <span className={`inline-block h-1.5 w-1.5 ${connected ? 'animate-pulse-dot' : ''}`} style={{ background: 'var(--theme-accent)' }} />
          </div>
        </div>
        <div className="mt-2 text-[10px]" style={{ color: 'var(--theme-text-secondary)' }}>
          STREAM: LIVE LOG BUS / MODE: FOLLOW / FORMAT: CLI
        </div>
      </div>

      <div
        ref={scrollRef}
        className="relative z-10 flex-1 overflow-y-auto px-4 py-3 font-mono text-[11px] leading-[1.35]"
        style={{
          color: 'var(--theme-text)',
          scrollBehavior: 'auto',
          letterSpacing: '0.04em',
        }}
      >
        {renderedLogs.length === 0 ? (
          <div style={{ color: 'var(--theme-text-muted)' }}>
            [--:--:--] [SYS] WAITING FOR DATA
          </div>
        ) : (
          renderedLogs.map((log, index) => (
            <div
              key={log.key}
              className="py-[2px]"
              style={{
                color: index === renderedLogs.length - 1 ? 'var(--theme-text)' : 'var(--theme-text-secondary)',
                animation: index === renderedLogs.length - 1 ? 'matrix-flicker 3.8s linear infinite' : undefined,
              }}
            >
              <TypewriterLine text={log.line} active={log.key === typingKey} />
            </div>
          ))
        )}

        <div className="mt-2 flex items-center gap-1 text-[11px]" style={{ color: 'var(--theme-text)' }}>
          <span>&gt;</span>
          <span className="animate-matrix-cursor">_</span>
        </div>
      </div>
    </section>
  )
}
