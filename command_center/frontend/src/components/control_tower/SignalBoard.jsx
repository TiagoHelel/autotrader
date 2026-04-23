import { useState, useMemo, useRef, useEffect } from 'react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import { useTheme } from '../../theme/ThemeProvider'

const SIGNAL_REFRESH_INTERVAL = 60_000

const SIGNAL_COLORS = {
  BUY: 'var(--theme-buy)',
  SELL: 'var(--theme-sell)',
  HOLD: 'var(--theme-hold)',
}

export default function SignalBoard() {
  const { theme } = useTheme()
  const { data: radarData } = useApi(() => api.getRadarSignals(), [], { interval: SIGNAL_REFRESH_INTERVAL })
  const prevSignals = useRef({})
  const [flashMap, setFlashMap] = useState({})

  const signals = useMemo(() => {
    const raw = radarData?.signals || []
    return [...raw]
      .map((sig) => ({
        symbol: sig.symbol,
        signal: (sig.signal || 'HOLD').toUpperCase(),
        confidence: sig.confidence ?? 0,
      }))
      .sort((a, b) => b.confidence - a.confidence)
  }, [radarData])

  // Detect signal changes for flash animation
  useEffect(() => {
    const newFlash = {}
    for (const sig of signals) {
      const prev = prevSignals.current[sig.symbol]
      if (prev && prev !== sig.signal) {
        newFlash[sig.symbol] = true
      }
    }
    if (Object.keys(newFlash).length > 0) {
      setFlashMap(newFlash)
      const timer = setTimeout(() => setFlashMap({}), 800)
      return () => clearTimeout(timer)
    }
    // Update previous signals ref
    const map = {}
    for (const sig of signals) map[sig.symbol] = sig.signal
    prevSignals.current = map
  }, [signals])

  const breakdown = radarData?.breakdown || { BUY: 0, SELL: 0, HOLD: 0 }
  const total = radarData?.total || 0
  const isMatrix = theme === 'matrix'

  return (
    <div
      className={`themed-card h-full flex flex-col ${isMatrix ? 'rounded-sm p-3' : 'rounded-xl p-4'}`}
      style={isMatrix ? { background: '#000', border: '1px solid rgba(0,255,65,0.2)' } : undefined}
    >
      {/* Header */}
      <div className="mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)', letterSpacing: isMatrix ? '0.18em' : undefined }}>
          Signal Board
        </h3>
        <div className="mt-1 flex items-center gap-3">
          <span className="text-sm font-bold" style={{ color: 'var(--theme-text)' }}>
            Active Signals: {total}
          </span>
          {total > 0 && (
            <span className="text-xs font-mono" style={{ color: 'var(--theme-text-secondary)' }}>
              <span style={{ color: 'var(--theme-buy)' }}>{breakdown.BUY} [BUY]</span>
              {' | '}
              <span style={{ color: 'var(--theme-sell)' }}>{breakdown.SELL} [SELL]</span>
              {' | '}
              <span style={{ color: 'var(--theme-hold)' }}>{breakdown.HOLD} [HOLD]</span>
            </span>
          )}
        </div>
      </div>

      {/* Column header */}
      <div
        className="grid gap-2 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest"
        style={{
          gridTemplateColumns: '1fr 70px 1fr',
          color: 'var(--theme-text-muted)',
          borderBottom: '1px solid var(--theme-border)',
        }}
      >
        <span>Symbol</span>
        <span className="text-center">Signal</span>
        <span className="text-right">Confidence</span>
      </div>

      {/* Signal rows */}
      <div className="flex-1 overflow-y-auto mt-1 space-y-0.5">
        {signals.length === 0 && (
          <div className="flex items-center justify-center h-full text-xs" style={{ color: 'var(--theme-text-muted)' }}>
            Waiting for signals...
          </div>
        )}
        {signals.map((sig) => (
          <SignalRow key={sig.symbol} sig={sig} flash={!!flashMap[sig.symbol]} isMatrix={isMatrix} />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-2 pt-2 flex justify-center gap-4" style={{ borderTop: '1px solid var(--theme-border)' }}>
        {['BUY', 'SELL', 'HOLD'].map((label) => (
          <div key={label} className="flex items-center gap-1.5">
            <span
              className={`inline-block h-2 w-2 ${isMatrix ? '' : 'rounded-full'}`}
              style={{ backgroundColor: SIGNAL_COLORS[label], boxShadow: isMatrix ? 'none' : `0 0 4px ${SIGNAL_COLORS[label]}` }}
            />
            <span className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function SignalRow({ sig, flash, isMatrix }) {
  const color = SIGNAL_COLORS[sig.signal] || SIGNAL_COLORS.HOLD
  const pct = Math.round(sig.confidence * 100)
  const signalLabel = `[${sig.signal}]`

  return (
    <div
      className={`grid gap-2 px-3 py-1.5 transition-all duration-200 signal-row ${isMatrix ? '' : 'rounded-md'}`}
      style={{
        gridTemplateColumns: '1fr 70px 1fr',
        background: flash ? (isMatrix ? 'rgba(0,255,65,0.06)' : 'rgba(255,255,255,0.06)') : 'transparent',
        animation: flash ? 'signal-flash 0.8s ease-out' : undefined,
        borderBottom: isMatrix ? '1px solid rgba(0,255,65,0.08)' : undefined,
      }}
    >
      {/* Symbol */}
      <span className="font-mono text-xs font-bold truncate" style={{ color: 'var(--theme-text)' }}>
        {sig.symbol}
      </span>

      {/* Signal badge */}
      <span className="text-center">
        <span
          className={`inline-block px-2 py-0.5 text-[10px] font-bold ${isMatrix ? '' : 'rounded'}`}
          style={{
            color,
            backgroundColor: isMatrix ? 'transparent' : `color-mix(in srgb, ${color} 12%, transparent)`,
            textShadow: isMatrix ? 'none' : `0 0 6px ${color}`,
            border: isMatrix ? `1px solid ${color}33` : undefined,
          }}
        >
          {signalLabel}
        </span>
      </span>

      {/* Confidence bar + number */}
      <div className="flex items-center gap-2 justify-end">
        <div className={`flex-1 max-w-[80px] h-1.5 overflow-hidden ${isMatrix ? '' : 'rounded-full'}`} style={{ backgroundColor: 'var(--theme-border)' }}>
          <div
            className={`h-full transition-all duration-500 ${isMatrix ? '' : 'rounded-full'}`}
            style={{
              width: `${pct}%`,
              backgroundColor: color,
              boxShadow: isMatrix ? 'none' : `0 0 4px ${color}`,
              opacity: isMatrix ? Math.max(0.35, sig.confidence) : 1,
            }}
          />
        </div>
        <span className="font-mono text-[11px] w-8 text-right" style={{ color: 'var(--theme-text-secondary)' }}>
          {pct}%
        </span>
      </div>
    </div>
  )
}
