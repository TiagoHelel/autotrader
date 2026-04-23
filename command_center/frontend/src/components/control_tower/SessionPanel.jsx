import { useState, useEffect, useCallback } from 'react'
import { useTheme } from '../../theme/ThemeProvider'
import { api } from '../../services/api'

const SYMBOLS = [
  'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD',
  'USDCAD', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY', 'XAUUSD',
]

const SESSION_COLORS = {
  sydney: '#a78bfa',
  tokyo: '#f472b6',
  london: '#60a5fa',
  new_york: '#34d399',
}

const SESSION_LABELS = {
  sydney: 'Sydney',
  tokyo: 'Tokyo',
  london: 'London',
  new_york: 'New York',
}

function ScoreBadge({ score, isMatrix }) {
  const mGreen = '#00ff41'
  const mGreenDim = 'rgba(0,255,65,0.2)'
  const mFont = "'JetBrains Mono', 'Fira Code', monospace"
  const label = score >= 0.6 ? 'HIGH' : score >= 0.3 ? 'MED' : 'LOW'

  if (isMatrix) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-bold"
        style={{ color: mGreen, border: `1px solid ${mGreenDim}`, borderRadius: '2px', fontFamily: mFont }}
      >
        {(score * 100).toFixed(0)}% {label}
      </span>
    )
  }

  const color = score >= 0.6 ? '#22c55e' : score >= 0.3 ? '#f59e0b' : '#ef4444'
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold"
      style={{ color, backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {(score * 100).toFixed(0)}% {label}
    </span>
  )
}

export default function SessionPanel({ selectedSymbol, onSymbolChange }) {
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'
  const mGreen = '#00ff41'
  const mGreenDim = 'rgba(0,255,65,0.2)'
  const mGreenMuted = '#008f2a'
  const mFont = "'JetBrains Mono', 'Fira Code', monospace"

  const [internalSelected, setInternalSelected] = useState('EURUSD')
  const selected = selectedSymbol ?? internalSelected
  const setSelected = (s) => {
    if (onSymbolChange) onSymbolChange(s)
    else setInternalSelected(s)
  }
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchSession = useCallback(async () => {
    try {
      const result = await api.getSessionCurrent(selected)
      setData(result)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [selected])

  useEffect(() => {
    fetchSession()
    const id = setInterval(fetchSession, 30000) // refresh every 30s
    return () => clearInterval(id)
  }, [fetchSession])

  const activeSessions = data?.active_sessions || []
  const activeOverlaps = data?.active_overlaps || []
  const score = data?.session_score ?? 0
  const strength = data?.session_strength ?? 0
  const weights = data?.weights || {}
  const regime = data?.regime || {}

  const scoreColor = isMatrix ? mGreen : (score >= 0.6 ? '#22c55e' : score >= 0.3 ? '#f59e0b' : '#ef4444')

  return (
    <div className={`themed-card ${isMatrix ? 'rounded-sm' : 'rounded-xl'} p-4 h-full flex flex-col`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h3
          className="text-xs font-semibold uppercase tracking-wider"
          style={isMatrix ? { color: mGreen, fontFamily: mFont } : { color: '#9ca3af' }}
        >
          {isMatrix ? '> Session Intelligence' : 'Session Intelligence'}
        </h3>
        {activeOverlaps.length > 0 && (
          <span
            className="px-2 py-0.5 text-xs font-bold"
            style={isMatrix
              ? { color: mGreen, border: `1px solid ${mGreenDim}`, borderRadius: '2px', fontFamily: mFont }
              : { color: '#facc15', background: 'rgba(234,179,8,0.1)', borderRadius: '9999px' }
            }
          >
            OVERLAP
          </span>
        )}
      </div>

      {/* Symbol selector */}
      <div className="shrink-0 mb-3">
        <select
          value={selected}
          onChange={(e) => { setSelected(e.target.value); setLoading(true) }}
          className="w-full px-2 py-1.5 text-xs focus:outline-none"
          style={isMatrix
            ? { background: '#000', color: mGreen, border: `1px solid rgba(0,255,65,0.3)`, borderRadius: '2px', fontFamily: mFont }
            : { background: 'rgba(30,41,59,0.8)', color: '#fff', border: '1px solid #374151', borderRadius: '0.375rem' }
          }
        >
          {SYMBOLS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-xs animate-pulse" style={{ color: isMatrix ? mGreenMuted : '#6b7280', fontFamily: isMatrix ? mFont : undefined }}>
            {isMatrix ? '> loading...' : 'Loading...'}
          </span>
        </div>
      ) : (
        <>
          {/* Score + Strength */}
          <div className="shrink-0 mb-3 flex items-center justify-between">
            <div>
              <p className="text-xs mb-0.5" style={{ color: isMatrix ? mGreenMuted : '#6b7280', fontFamily: isMatrix ? mFont : undefined }}>
                {isMatrix ? '> score' : 'Session Score'}
              </p>
              <p className="font-mono text-lg font-bold" style={{ color: scoreColor, textShadow: isMatrix ? 'none' : `0 0 8px ${scoreColor}40`, fontFamily: isMatrix ? mFont : undefined }}>
                {(score * 100).toFixed(0)}%
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs mb-0.5" style={{ color: isMatrix ? mGreenMuted : '#6b7280', fontFamily: isMatrix ? mFont : undefined }}>
                {isMatrix ? '> str' : 'Strength'}
              </p>
              <div className="flex gap-1">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-4 w-2"
                    style={{
                      borderRadius: isMatrix ? '0' : '0.125rem',
                      backgroundColor: i <= strength
                        ? (isMatrix ? mGreen : scoreColor)
                        : (isMatrix ? 'rgba(0,255,65,0.1)' : '#1e293b'),
                      boxShadow: isMatrix ? 'none' : (i <= strength ? `0 0 4px ${scoreColor}60` : 'none'),
                    }}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Score bar */}
          <div className="shrink-0 mb-3">
            <div className="h-1.5 w-full overflow-hidden bg-gray-800" style={{ borderRadius: isMatrix ? '0' : '9999px' }}>
              <div
                className="h-full transition-all duration-500"
                style={{
                  width: `${score * 100}%`,
                  borderRadius: isMatrix ? '0' : '9999px',
                  background: isMatrix ? mGreen : `linear-gradient(90deg, #3b82f6, ${scoreColor})`,
                  boxShadow: isMatrix ? 'none' : `0 0 8px ${scoreColor}40`,
                }}
              />
            </div>
            {score < 0.3 && (
              <p className="mt-1 text-xs text-center" style={{ color: isMatrix ? mGreenMuted : '#f87171', fontFamily: isMatrix ? mFont : undefined }}>
                {isMatrix ? '> low liquidity — HOLD only' : 'Low liquidity — signals filtered to HOLD'}
              </p>
            )}
          </div>

          {/* Active sessions with weights */}
          <div className="flex-1 space-y-1.5 min-h-0 overflow-y-auto">
            {Object.entries(SESSION_LABELS).map(([key, label]) => {
              const active = activeSessions.includes(key)
              const weight = weights[key] ?? 0
              const inOverlap = activeOverlaps.some((o) => o.includes(key))

              return (
                <div
                  key={key}
                  style={isMatrix && active ? { borderLeft: `2px solid ${mGreen}`, paddingLeft: '6px' } : undefined}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`inline-block h-2 w-2 ${isMatrix ? 'rounded-none' : 'rounded-full'} ${active ? 'animate-dot-pulse' : ''}`}
                        style={{
                          backgroundColor: isMatrix ? mGreen : SESSION_COLORS[key],
                          opacity: active ? 1 : 0.25,
                          boxShadow: active && !isMatrix ? `0 0 6px ${SESSION_COLORS[key]}` : 'none',
                        }}
                      />
                      <span
                        className="text-xs"
                        style={isMatrix
                          ? { color: active ? mGreen : mGreenMuted, fontFamily: mFont }
                          : { color: active ? '#fff' : '#4b5563', fontWeight: active ? 500 : 400 }
                        }
                      >
                        {label}
                      </span>
                      {inOverlap && <span className="text-xs" style={{ color: isMatrix ? mGreen : '#facc15' }}>*</span>}
                    </div>
                    <span className="font-mono text-xs" style={{ color: isMatrix ? mGreenMuted : '#6b7280', fontFamily: isMatrix ? mFont : undefined }}>
                      w={weight.toFixed(2)}
                    </span>
                  </div>
                  <div className="h-1 w-full overflow-hidden bg-gray-800" style={{ borderRadius: isMatrix ? '0' : '9999px' }}>
                    <div
                      className="h-full transition-all"
                      style={{
                        width: active ? `${weight * 100}%` : '0%',
                        borderRadius: isMatrix ? '0' : '9999px',
                        backgroundColor: isMatrix ? (active ? mGreen : 'transparent') : (inOverlap ? '#f59e0b' : SESSION_COLORS[key]),
                        boxShadow: active && !isMatrix ? `0 0 4px ${SESSION_COLORS[key]}` : 'none',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Regime info — CLI style for Matrix */}
          {regime.trend_label && (
            <div
              className="shrink-0 mt-2 flex items-center justify-between px-2 py-1.5"
              style={isMatrix
                ? { border: `1px solid ${mGreenDim}`, borderRadius: '2px', background: '#000' }
                : { borderRadius: '0.375rem', background: 'rgba(30,41,59,0.5)' }
              }
            >
              <div className="flex items-center gap-2 text-xs" style={isMatrix ? { fontFamily: mFont } : undefined}>
                <span style={{ color: isMatrix ? mGreen : (regime.trend === 1 ? '#4ade80' : '#f87171') }}>
                  {isMatrix ? '>' : ''} {regime.trend_label === 'bull' ? '\u25B2' : '\u25BC'} {regime.trend_label}
                </span>
                <span style={{ color: isMatrix ? mGreenMuted : '#4b5563' }}>|</span>
                <span style={{ color: isMatrix ? mGreenMuted : '#9ca3af' }}>
                  vol: {regime.volatility_label}
                </span>
              </div>
              <ScoreBadge score={score} isMatrix={isMatrix} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
