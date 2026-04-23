import { TrendingUp, TrendingDown } from 'lucide-react'
import { useTheme } from '../../theme/ThemeProvider'

export default function KPICard({ label, value, prefix = '', suffix = '', change, icon: Icon, format = 'number' }) {
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'
  const isPositive = change > 0
  const isNegative = change < 0

  const formattedValue = formatValue(value, format)

  return (
    <div className={`glass-card p-5 transition-all ${isMatrix ? 'rounded-sm' : 'rounded-xl'}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)', letterSpacing: isMatrix ? '0.18em' : undefined }}>
          {label}
        </span>
        {Icon && <Icon className="h-4 w-4" style={{ color: 'var(--theme-text-muted)' }} />}
      </div>
      <div className="mt-3 flex items-end gap-2">
        <span className="font-mono text-2xl font-bold" style={{ color: 'var(--theme-text)' }}>
          {prefix}{formattedValue}{suffix}
        </span>
      </div>
      {change !== undefined && change !== null && (
        <div className="mt-2 flex items-center gap-1">
          {isPositive ? (
            <TrendingUp className="h-3 w-3 text-profit" />
          ) : isNegative ? (
            <TrendingDown className="h-3 w-3 text-loss" />
          ) : null}
          <span
            className="font-mono text-xs font-medium"
            style={{
              color: isPositive || isNegative ? 'var(--theme-text)' : 'var(--theme-text-muted)',
              opacity: isPositive || isNegative ? Math.max(0.45, Math.abs(Number(change)) / 10) : 1,
            }}
          >
            {isPositive ? '+' : ''}{typeof change === 'number' ? change.toFixed(2) : change}%
          </span>
        </div>
      )}
    </div>
  )
}

function formatValue(val, format) {
  if (val === null || val === undefined) return '-'
  if (format === 'percent') return `${Number(val).toFixed(1)}`
  if (format === 'integer') return Number(val).toLocaleString('en-US')
  return Number(val).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
