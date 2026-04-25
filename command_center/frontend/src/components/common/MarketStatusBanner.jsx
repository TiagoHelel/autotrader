import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import { useTheme } from '../../theme/ThemeProvider'

const REFRESH_INTERVAL = 60_000

export default function MarketStatusBanner() {
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'
  const { data } = useApi(() => api.getRadarSignals(), [], { interval: REFRESH_INTERVAL })

  if (!data?.market_closed) return null

  const message = data?.message || 'Forex market is closed.'

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="market-closed-banner"
      className={`flex items-center justify-center gap-3 px-4 py-2 text-xs font-semibold uppercase tracking-widest ${
        isMatrix ? 'rounded-sm font-mono' : 'rounded-lg'
      }`}
      style={{
        background: isMatrix
          ? 'rgba(0, 255, 65, 0.06)'
          : 'color-mix(in srgb, var(--theme-warning, #f59e0b) 18%, transparent)',
        border: `1px solid ${isMatrix ? 'rgba(0,255,65,0.35)' : 'var(--theme-warning, #f59e0b)'}`,
        color: isMatrix ? 'var(--theme-text)' : 'var(--theme-warning, #f59e0b)',
        letterSpacing: isMatrix ? '0.22em' : undefined,
      }}
    >
      <span aria-hidden>{isMatrix ? '[!]' : '⚠'}</span>
      <span>Market Closed</span>
      <span
        className="hidden sm:inline text-[10px] font-normal normal-case"
        style={{ color: 'var(--theme-text-muted)', letterSpacing: 'normal' }}
      >
        {message}
      </span>
    </div>
  )
}
