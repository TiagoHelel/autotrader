import { useMemo } from 'react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import { useTheme } from '../../theme/ThemeProvider'

/**
 * Mini KPI card with a 30-day equity sparkline.
 * Replaces the large EquityChart in the Control Tower top strip.
 */
export default function TrendSparklineCard({ label = '30D Trend', icon: Icon }) {
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'
  const { data, loading } = useApi(() => api.getEquityHistory(), [], { interval: 60000 })

  const { points, pct, color, path } = useMemo(() => {
    const series = (data || []).map((d) => Number(d.equity)).filter((v) => Number.isFinite(v))
    if (series.length < 2) {
      return { points: [], pct: null, color: '#22c55e', path: '' }
    }
    const min = Math.min(...series)
    const max = Math.max(...series)
    const range = max - min || 1
    const w = 100
    const h = 36
    const step = w / (series.length - 1)
    const path = series
      .map((v, i) => {
        const x = i * step
        const y = h - ((v - min) / range) * h
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
      })
      .join(' ')
    const first = series[0]
    const last = series[series.length - 1]
    const pct = first ? ((last - first) / first) * 100 : 0
    const color = pct >= 0 ? '#22c55e' : '#ef4444'
    return { points: series, pct, color, path }
  }, [data])

  return (
    <div className={`glass-card p-5 transition-all ${isMatrix ? 'rounded-sm' : 'rounded-xl'}`}>
      <div className="flex items-center justify-between">
        <span
          className="text-xs font-medium uppercase tracking-wider"
          style={{ color: 'var(--theme-text-muted)', letterSpacing: isMatrix ? '0.18em' : undefined }}
        >
          {label}
        </span>
        {Icon && <Icon className="h-4 w-4" style={{ color: 'var(--theme-text-muted)' }} />}
      </div>

      {loading || !points.length ? (
        <div className="mt-3 flex h-[44px] items-center">
          <span className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>
            {loading ? 'Loading...' : 'No data'}
          </span>
        </div>
      ) : (
        <>
          <div className="mt-3">
            <svg viewBox="0 0 100 36" preserveAspectRatio="none" className="h-9 w-full">
              <defs>
                <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={isMatrix ? '0.18' : '0.35'} />
                  <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
                <filter id="sparkGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="1.2" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <path d={`${path} L100,36 L0,36 Z`} fill="url(#sparkFill)" />
              <path
                d={path}
                fill="none"
                stroke={isMatrix ? 'var(--theme-text)' : color}
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                filter={isMatrix ? undefined : 'url(#sparkGlow)'}
              />
            </svg>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="font-mono text-xs" style={{ color: 'var(--theme-text-muted)' }}>
              30d
            </span>
            <span
              className="font-mono text-xs font-semibold"
              style={{
                color: 'var(--theme-text)',
                textShadow: isMatrix ? 'none' : `0 0 6px ${color}55`,
                opacity: isMatrix ? 0.9 : 1,
              }}
            >
              {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
            </span>
          </div>
        </>
      )}
    </div>
  )
}
