import { Brain, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import { useTheme } from '../../theme/ThemeProvider'

const SIGNALS_REFRESH_INTERVAL = 60_000

export default function AICorePanel() {
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'
  const { data: performance } = useApi(() => api.getModelsPerformance(), [], { interval: 10000 })
  const { data: signals } = useApi(() => api.getLatestSignals(null, 50), [], { interval: SIGNALS_REFRESH_INTERVAL })

  const signalList = Array.isArray(signals) ? signals : signals?.signals || []
  const rankingList = performance?.ranking || (Array.isArray(performance) ? performance : [])
  const consensus = computeConsensus(signalList)
  const topModels = computeTopModels(rankingList)

  return (
    <div
      className={`themed-card h-full ${isMatrix ? 'rounded-sm p-3' : 'rounded-xl p-4'}`}
      style={isMatrix ? { background: '#000', border: '1px solid rgba(0,255,65,0.2)' } : undefined}
    >
      <h3
        className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider"
        style={{ color: 'var(--theme-text-muted)', letterSpacing: isMatrix ? '0.18em' : undefined }}
      >
        <Brain className="h-3.5 w-3.5" style={{ color: 'var(--theme-accent)' }} />
        AI Core
      </h3>

      {topModels.best && (
        <div
          className={`mb-3 p-3 ${isMatrix ? 'rounded-sm' : 'rounded-lg'}`}
          style={{
            background: isMatrix ? '#000' : 'rgba(17, 24, 39, 0.5)',
            border: isMatrix ? '1px solid rgba(0,255,65,0.12)' : 'none',
          }}
        >
          <div className="text-xs uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)' }}>
            Top Model
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span
              className="font-mono text-sm font-bold"
              style={{ color: 'var(--theme-text)', textShadow: isMatrix ? 'none' : '0 0 8px rgba(59,130,246,0.4)' }}
            >
              {topModels.best.model}
            </span>
            <span
              className={`px-2 py-0.5 text-xs font-mono ${isMatrix ? 'rounded-sm' : 'rounded-full'}`}
              style={{
                color: 'var(--theme-text)',
                background: isMatrix ? 'transparent' : 'rgba(59,130,246,0.1)',
                border: isMatrix ? '1px solid rgba(0,255,65,0.18)' : 'none',
              }}
            >
              {(topModels.best.accuracy ?? topModels.best.win_rate ?? 0).toFixed(1)}%
            </span>
          </div>
        </div>
      )}

      <div
        className={`mb-3 p-3 ${isMatrix ? 'rounded-sm' : 'rounded-lg'}`}
        style={{
          background: isMatrix ? '#000' : 'rgba(17, 24, 39, 0.5)',
          border: isMatrix ? '1px solid rgba(0,255,65,0.12)' : 'none',
        }}
      >
        <div className="text-xs uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)' }}>
          Avg. Confidence
        </div>
        <div className="mt-1">
          <div className="flex items-center justify-between">
            <span className="font-mono text-lg font-bold" style={{ color: 'var(--theme-text)' }}>
              {consensus.avgConfidence.toFixed(1)}%
            </span>
            <ConfidenceBadge value={consensus.avgConfidence} isMatrix={isMatrix} />
          </div>
          <div
            className={`mt-2 h-1.5 w-full overflow-hidden ${isMatrix ? '' : 'rounded-full'}`}
            style={{ backgroundColor: isMatrix ? 'rgba(0,255,65,0.08)' : '#1f2937' }}
          >
            <div
              className={`h-full transition-all ${isMatrix ? '' : 'rounded-full'}`}
              style={{
                width: `${consensus.avgConfidence}%`,
                background: isMatrix
                  ? 'var(--theme-text)'
                  : `linear-gradient(90deg, #3b82f6, ${consensus.avgConfidence > 60 ? '#22c55e' : '#f97316'})`,
                boxShadow: isMatrix ? 'none' : '0 0 8px rgba(59,130,246,0.5)',
                opacity: isMatrix ? Math.max(0.35, consensus.avgConfidence / 100) : 1,
              }}
            />
          </div>
        </div>
      </div>

      <div
        className={`p-3 ${isMatrix ? 'rounded-sm' : 'rounded-lg'}`}
        style={{
          background: isMatrix ? '#000' : 'rgba(17, 24, 39, 0.5)',
          border: isMatrix ? '1px solid rgba(0,255,65,0.12)' : 'none',
        }}
      >
        <div className="text-xs uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)' }}>
          Model Consensus
        </div>
        <div className="mt-2 space-y-1.5">
          {consensus.models.map(({ model, direction, confidence }) => (
            <div key={model} className="flex items-center justify-between">
              <span className="font-mono text-xs" style={{ color: 'var(--theme-text-secondary)' }}>{model}</span>
              <div className="flex items-center gap-2">
                <span
                  className={`px-1.5 py-0.5 text-xs font-bold ${isMatrix ? 'rounded-sm' : 'rounded-full'}`}
                  style={{
                    color: 'var(--theme-text)',
                    background: isMatrix ? 'transparent' : directionColor(direction, 0.1),
                    border: isMatrix ? `1px solid rgba(0,255,65,${0.12 + confidence * 0.2})` : 'none',
                    opacity: isMatrix ? Math.max(0.45, confidence) : 1,
                  }}
                >
                  {isMatrix ? `[${direction}]` : direction}
                </span>
                <span className="font-mono text-xs" style={{ color: 'var(--theme-text-muted)' }}>
                  {(confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>

        <div
          className="mt-3 flex items-center gap-2 pt-2"
          style={{ borderTop: `1px solid ${isMatrix ? 'rgba(0,255,65,0.12)' : '#1f2937'}` }}
        >
          <ConsensusIcon strength={consensus.strength} isMatrix={isMatrix} />
          <span className="text-xs font-medium" style={{ color: 'var(--theme-text)' }}>
            {isMatrix ? `[${consensus.direction}]` : consensus.direction}{' '}
            <span style={{ color: 'var(--theme-text-muted)' }}>({consensus.strength})</span>
          </span>
        </div>
      </div>
    </div>
  )
}

function directionColor(direction, alpha = 1) {
  if (direction === 'BUY') return `rgba(34, 197, 94, ${alpha})`
  if (direction === 'SELL') return `rgba(239, 68, 68, ${alpha})`
  return `rgba(107, 114, 128, ${alpha})`
}

function computeConsensus(signals) {
  if (!signals || !Array.isArray(signals) || signals.length === 0) {
    return {
      models: [],
      direction: 'HOLD',
      strength: 'NO DATA',
      avgConfidence: 0,
    }
  }

  const byModel = {}
  signals.forEach((s) => {
    const model = s.model || s.model_name || 'unknown'
    if (!byModel[model]) byModel[model] = s
  })

  const models = Object.entries(byModel).map(([model, s]) => ({
    model,
    direction: (s.direction || s.signal || 'HOLD').toUpperCase(),
    confidence: s.confidence ?? s.probability ?? 0.5,
  }))

  const totalConf = models.reduce((sum, m) => sum + m.confidence, 0)
  const avgConfidence = models.length > 0 ? (totalConf / models.length) * 100 : 0

  const votes = { BUY: 0, SELL: 0, HOLD: 0 }
  models.forEach((m) => {
    const dir = m.direction === 'LONG' ? 'BUY' : m.direction === 'SHORT' ? 'SELL' : m.direction
    votes[dir] = (votes[dir] || 0) + 1
  })

  const sorted = Object.entries(votes).sort((a, b) => b[1] - a[1])
  const topDir = sorted[0][0]
  const topCount = sorted[0][1]
  const total = models.length

  let strength = 'WEAK'
  if (total > 0) {
    const ratio = topCount / total
    if (ratio >= 0.8) strength = 'STRONG'
    else if (ratio >= 0.6) strength = 'MODERATE'
  }

  return { models: models.slice(0, 6), direction: topDir, strength, avgConfidence }
}

function computeTopModels(performance) {
  if (!performance || !Array.isArray(performance) || performance.length === 0) {
    return { best: null }
  }
  const sorted = [...performance].sort((a, b) => {
    const scoreA = (a.accuracy ?? a.win_rate ?? 0)
    const scoreB = (b.accuracy ?? b.win_rate ?? 0)
    return scoreB - scoreA
  })
  return { best: sorted[0] }
}

function ConfidenceBadge({ value, isMatrix }) {
  if (isMatrix) {
    if (value >= 70) return <span className="text-xs" style={{ color: 'var(--theme-text)' }}>HIGH</span>
    if (value >= 50) return <span className="text-xs" style={{ color: 'var(--theme-text-secondary)' }}>MED</span>
    return <span className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>LOW</span>
  }

  if (value >= 70) return <span className="text-xs text-green-400">High</span>
  if (value >= 50) return <span className="text-xs text-yellow-400">Medium</span>
  return <span className="text-xs text-red-400">Low</span>
}

function ConsensusIcon({ strength, isMatrix }) {
  const style = isMatrix ? { color: 'var(--theme-text)' } : undefined
  if (strength === 'STRONG') return <CheckCircle className="h-4 w-4" style={style} />
  if (strength === 'MODERATE') return <AlertTriangle className="h-4 w-4" style={style} />
  return <XCircle className="h-4 w-4" style={isMatrix ? { color: 'var(--theme-text-muted)' } : undefined} />
}
