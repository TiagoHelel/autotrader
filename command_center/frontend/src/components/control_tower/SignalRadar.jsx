import { useState, useEffect, useMemo, useCallback } from 'react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'

function polarToXY(cx, cy, r, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

const SIGNAL_COLORS = {
  BUY: '#22c55e',
  SELL: '#ef4444',
  HOLD: '#6b7280',
}

export default function SignalRadar() {
  const { data: radarData } = useApi(() => api.getRadarSignals(), [], { interval: 5000 })
  const [sweepAngle, setSweepAngle] = useState(0)
  const [hoveredSymbol, setHoveredSymbol] = useState(null)

  useEffect(() => {
    let raf
    let start = performance.now()
    function tick(now) {
      const elapsed = (now - start) / 1000
      setSweepAngle((elapsed * 60) % 360)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  const cx = 150, cy = 150
  const maxRadius = 100

  const points = useMemo(() => {
    const signals = radarData?.signals || []
    if (!signals.length) return []

    return signals.map((sig, i) => {
      const angle = (i / signals.length) * 360 - 90
      const confidence = sig.confidence ?? 0
      // Higher confidence = closer to center
      const dist = 14 + (1 - confidence) * (maxRadius - 20)
      const { x, y } = polarToXY(cx, cy, dist, angle)
      const direction = (sig.signal || 'HOLD').toUpperCase()
      const color = SIGNAL_COLORS[direction] || SIGNAL_COLORS.HOLD

      // Label offset — push label well outside the dot
      const labelDist = maxRadius + 22
      const label = polarToXY(cx, cy, labelDist, angle)

      return {
        ...sig,
        x, y,
        labelX: label.x,
        labelY: label.y,
        color,
        direction,
        confidence,
        angle,
      }
    })
  }, [radarData])

  const breakdown = radarData?.breakdown || { BUY: 0, SELL: 0, HOLD: 0 }
  const total = radarData?.total || 0

  const handleMouseEnter = useCallback((symbol) => setHoveredSymbol(symbol), [])
  const handleMouseLeave = useCallback(() => setHoveredSymbol(null), [])

  const hoveredPoint = hoveredSymbol ? points.find(p => p.symbol === hoveredSymbol) : null

  return (
    <div className="glass-card neon-border rounded-xl p-4 h-full">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
        Signal Radar
      </h3>
      <div className="flex items-center justify-center relative">
        <svg viewBox="0 0 300 300" className="h-64 w-64">
          <defs>
            {/* Glow filters per signal type */}
            <filter id="glowBuy" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="glowSell" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* Concentric rings */}
          {[100, 75, 50, 25].map((r) => (
            <circle
              key={r}
              cx={cx} cy={cy} r={r}
              fill="none"
              stroke="#1e293b"
              strokeWidth="0.5"
              strokeDasharray="3 3"
            />
          ))}

          {/* Cross hairs */}
          <line x1={cx - 105} y1={cy} x2={cx + 105} y2={cy} stroke="#1e293b" strokeWidth="0.5" />
          <line x1={cx} y1={cy - 105} x2={cx} y2={cy + 105} stroke="#1e293b" strokeWidth="0.5" />

          {/* Ring labels (confidence zones) */}
          <text x={cx + 3} y={cy - 101} style={{ fontSize: '7px', fill: '#475569' }}>0.25</text>
          <text x={cx + 3} y={cy - 76} style={{ fontSize: '7px', fill: '#475569' }}>0.50</text>
          <text x={cx + 3} y={cy - 51} style={{ fontSize: '7px', fill: '#475569' }}>0.75</text>
          <text x={cx + 3} y={cy - 26} style={{ fontSize: '7px', fill: '#475569' }}>1.00</text>

          {/* Sweep line */}
          {(() => {
            const tip = polarToXY(cx, cy, 103, sweepAngle - 90)
            const trail1 = polarToXY(cx, cy, 103, sweepAngle - 90 - 30)
            return (
              <>
                <line
                  x1={cx} y1={cy} x2={tip.x} y2={tip.y}
                  stroke="#22c55e"
                  strokeWidth="1"
                  opacity="0.6"
                  style={{ filter: 'drop-shadow(0 0 4px #22c55e)' }}
                />
                <path
                  d={`M ${cx} ${cy} L ${tip.x} ${tip.y} L ${trail1.x} ${trail1.y} Z`}
                  fill="#22c55e"
                  opacity="0.04"
                />
              </>
            )
          })()}

          {/* Signal dots + labels */}
          {points.map((p, i) => {
            const isHovered = hoveredSymbol === p.symbol
            const dotRadius = isHovered ? 8 : 6
            const glowIntensity = Math.max(0.4, p.confidence)
            const filterName = p.direction === 'BUY' ? 'glowBuy' : p.direction === 'SELL' ? 'glowSell' : ''

            return (
              <g
                key={p.symbol || i}
                onMouseEnter={() => handleMouseEnter(p.symbol)}
                onMouseLeave={handleMouseLeave}
                style={{ cursor: 'pointer' }}
              >
                {/* Dot */}
                <circle
                  cx={p.x} cy={p.y}
                  r={dotRadius}
                  fill={p.color}
                  opacity={glowIntensity}
                  filter={filterName ? `url(#${filterName})` : undefined}
                >
                  {!isHovered && (
                    <animate
                      attributeName="r"
                      values="5;7;5"
                      dur="2.5s"
                      repeatCount="indefinite"
                    />
                  )}
                </circle>

                {/* Symbol label — dark outline for contrast, then bright fill */}
                <text
                  x={p.labelX}
                  y={p.labelY}
                  textAnchor="middle"
                  dominantBaseline="central"
                  stroke="#0f172a"
                  strokeWidth="3"
                  paintOrder="stroke"
                  fill={isHovered ? '#f1f5f9' : '#cbd5e1'}
                  style={{
                    fontSize: isHovered ? '13px' : '11px',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: isHovered ? 700 : 600,
                  }}
                >
                  {p.symbol || ''}
                </text>
              </g>
            )
          })}

          {/* Center glow */}
          <circle cx={cx} cy={cy} r="4" fill="#22c55e" opacity="0.8" style={{ filter: 'drop-shadow(0 0 8px #22c55e)' }} />
        </svg>

        {/* Tooltip */}
        {hoveredPoint && (
          <div
            className="absolute z-50 pointer-events-none rounded-lg border border-gray-700 bg-gray-900/95 px-3 py-2 shadow-lg"
            style={{
              top: '8px',
              right: '8px',
              minWidth: '140px',
            }}
          >
            <div className="text-sm font-bold" style={{ color: hoveredPoint.color }}>
              {hoveredPoint.symbol}
            </div>
            <div className="mt-1 space-y-0.5 text-xs text-gray-300">
              <div>Signal: <span className="font-semibold" style={{ color: hoveredPoint.color }}>{hoveredPoint.direction}</span></div>
              <div>Confidence: <span className="font-mono">{(hoveredPoint.confidence * 100).toFixed(0)}%</span></div>
              {hoveredPoint.expected_return != null && (
                <div>Exp. Return: <span className="font-mono">{(hoveredPoint.expected_return * 10000).toFixed(1)} pips</span></div>
              )}
              {hoveredPoint.n_models != null && (
                <div>Models: <span className="font-mono">{hoveredPoint.n_models}</span></div>
              )}
              <div className="text-gray-500 text-[10px] mt-1">Source: Ensemble</div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-2 flex justify-center gap-4">
        {[
          { label: 'BUY', color: SIGNAL_COLORS.BUY },
          { label: 'SELL', color: SIGNAL_COLORS.SELL },
          { label: 'HOLD', color: SIGNAL_COLORS.HOLD },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }} />
            <span className="text-xs text-gray-500">{label}</span>
          </div>
        ))}
      </div>

      {/* Signal breakdown */}
      <div className="mt-1 text-center text-xs text-gray-500">
        <span className="text-gray-400 font-medium">{total} symbols tracked</span>
        {total > 0 && (
          <span className="ml-2 text-[10px]">
            <span style={{ color: SIGNAL_COLORS.BUY }}>{breakdown.BUY} BUY</span>
            {' | '}
            <span style={{ color: SIGNAL_COLORS.SELL }}>{breakdown.SELL} SELL</span>
            {' | '}
            <span style={{ color: SIGNAL_COLORS.HOLD }}>{breakdown.HOLD} HOLD</span>
          </span>
        )}
      </div>
    </div>
  )
}
