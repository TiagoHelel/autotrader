import { useState, useEffect, useMemo } from 'react'
import { useTheme } from '../../theme/ThemeProvider'

// Sessions in UTC-3 (Brazil) — synced with src/features/session.py (UTC)
// session.py UTC → UTC-3: subtract 3 hours
const SESSIONS = [
  { name: 'Sydney',   color: '#a78bfa', start: 19, end: 4,  days: [0, 1, 2, 3, 4, 5] }, // 22:00-07:00 UTC
  { name: 'Tokyo',    color: '#f472b6', start: 21, end: 6,  days: [0, 1, 2, 3, 4, 5] }, // 00:00-09:00 UTC
  { name: 'London',   color: '#60a5fa', start: 5,  end: 14, days: [1, 2, 3, 4, 5] },    // 08:00-17:00 UTC
  { name: 'New York', color: '#34d399', start: 10, end: 19, days: [1, 2, 3, 4, 5] },    // 13:00-22:00 UTC
]

// Overlaps (UTC-3) — synced with session.py
const OVERLAPS = [
  { name: 'Tokyo + London', sessions: ['Tokyo', 'London'], start: 5, end: 6 },   // 08:00-09:00 UTC
  { name: 'London + NY',    sessions: ['London', 'New York'], start: 10, end: 14 }, // 13:00-17:00 UTC
]

// Get current time in UTC-3
function getBrazilTime(now) {
  // Create UTC-3 offset
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000
  const brDate = new Date(utcMs - 3 * 3600000)
  return {
    hour: brDate.getHours(),
    minute: brDate.getMinutes(),
    second: brDate.getSeconds(),
    // weekday: 0=Sun, 1=Mon ... 6=Sat
    weekday: brDate.getDay(),
    date: brDate,
  }
}

function isMarketOpen(weekday, hour) {
  // Forex: Sunday 18:00 (UTC-3) → Friday 18:00 (UTC-3)
  if (weekday === 6) return false // Saturday: CLOSED
  if (weekday === 0 && hour < 18) return false // Sunday before 18:00: CLOSED
  if (weekday === 5 && hour >= 18) return false // Friday after 18:00: CLOSED
  return true
}

function isSessionActive(session, weekday, hour) {
  // Check if day is valid for this session
  // Special: sessions that start on one day and end on next
  if (session.start > session.end) {
    // Crosses midnight (e.g. Sydney 18:00-03:00)
    if (hour >= session.start) {
      // Evening part — check if current weekday allows start
      return session.days.includes(weekday)
    }
    if (hour < session.end) {
      // Morning part — the session started the day before
      const prevDay = weekday === 0 ? 6 : weekday - 1
      return session.days.includes(prevDay)
    }
    return false
  }
  // Normal range (e.g. London 04:00-13:00)
  if (hour >= session.start && hour < session.end) {
    return session.days.includes(weekday)
  }
  return false
}

function getSessionProgress(session, hour, minute) {
  const currentMinutes = hour * 60 + minute
  const startMinutes = session.start * 60
  const duration = session.start < session.end
    ? (session.end - session.start) * 60
    : (24 - session.start + session.end) * 60

  let elapsed
  if (session.start < session.end) {
    elapsed = currentMinutes - startMinutes
  } else {
    elapsed = currentMinutes >= startMinutes
      ? currentMinutes - startMinutes
      : currentMinutes + (24 * 60 - startMinutes)
  }
  return Math.max(0, Math.min(1, elapsed / duration))
}

function getActiveOverlaps(weekday, hour) {
  return OVERLAPS.filter((o) => {
    if (hour >= o.start && hour < o.end) {
      // Check both sessions are active
      return o.sessions.every((name) => {
        const s = SESSIONS.find((s) => s.name === name)
        return s && isSessionActive(s, weekday, hour)
      })
    }
    return false
  })
}

function getSessionStrength(activeSessions, activeOverlaps) {
  if (activeSessions.length === 0) return 0
  let strength = activeSessions.length * 20 // base: 20 per session
  // Bonus for London or NY
  if (activeSessions.some((s) => s.name === 'London')) strength += 15
  if (activeSessions.some((s) => s.name === 'New York')) strength += 15
  // Bonus for overlaps
  strength += activeOverlaps.length * 15
  // London+NY overlap = peak
  if (activeOverlaps.some((o) => o.name === 'London + NY')) strength += 15
  return Math.min(100, strength)
}


function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

export default function ControlTowerClock() {
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const br = useMemo(() => getBrazilTime(now), [now])
  const marketOpen = isMarketOpen(br.weekday, br.hour)

  const activeSessions = useMemo(
    () => SESSIONS.filter((s) => marketOpen && isSessionActive(s, br.weekday, br.hour)),
    [br.weekday, br.hour, marketOpen]
  )

  const activeOverlaps = useMemo(
    () => marketOpen ? getActiveOverlaps(br.weekday, br.hour) : [],
    [br.weekday, br.hour, marketOpen]
  )

  const strength = useMemo(
    () => getSessionStrength(activeSessions, activeOverlaps),
    [activeSessions, activeOverlaps]
  )

  // Clock hands (local browser time for analog display)
  const hourLocal = now.getHours()
  const minuteLocal = now.getMinutes()
  const secondLocal = now.getSeconds()
  const hour12 = hourLocal % 12
  const handAngle = ((hour12 + minuteLocal / 60) / 12) * 360 - 90
  const minuteAngle = (minuteLocal / 60) * 360 - 90

  const cx = 100, cy = 100

  const strengthColor = isMatrix
    ? '#00ff41'
    : strength >= 70 ? '#22c55e' : strength >= 40 ? '#f59e0b' : '#64748b'

  // Matrix: all green neon | Default/Cyberpunk: original colors
  const mGreen = '#00ff41'
  const mGreenDim = 'rgba(0,255,65,0.2)'
  const mGreenMid = 'rgba(0,255,65,0.5)'
  const mFont = "'JetBrains Mono', 'Fira Code', monospace"

  return (
    <div className={`themed-card ${isMatrix ? 'rounded-sm' : 'rounded-xl'} p-4 h-full flex flex-col ${!marketOpen ? 'opacity-60' : ''}`}>
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h3
          className="text-xs font-semibold uppercase tracking-wider"
          style={isMatrix ? { color: mGreen, fontFamily: mFont } : { color: '#9ca3af' }}
        >
          {isMatrix ? '> Forex Sessions' : 'Forex Sessions'}
        </h3>
        {!marketOpen && (
          <span
            className="px-2 py-0.5 text-xs font-bold"
            style={isMatrix
              ? { color: mGreen, border: `1px solid ${mGreenDim}`, borderRadius: '2px', background: '#000' }
              : { color: '#f87171', background: 'rgba(239,68,68,0.1)', borderRadius: '9999px' }
            }
          >
            CLOSED
          </span>
        )}
        {marketOpen && activeOverlaps.length > 0 && (
          <span
            className="px-2 py-0.5 text-xs font-bold"
            style={isMatrix
              ? { color: mGreen, border: `1px solid ${mGreenDim}`, borderRadius: '2px', background: '#000' }
              : { color: '#facc15', background: 'rgba(234,179,8,0.1)', borderRadius: '9999px' }
            }
          >
            OVERLAP
          </span>
        )}
      </div>

      {/* Analog clock */}
      <div className="flex items-center justify-center shrink-0">
        <svg viewBox="0 0 200 200" className="h-36 w-36">
          {/* Outer ring */}
          <circle cx={cx} cy={cy} r="88" fill="none" stroke={isMatrix ? mGreenDim : '#1e293b'} strokeWidth="1" />

          {/* Hour ticks (12h) */}
          {Array.from({ length: 12 }, (_, i) => {
            const angle = (i / 12) * 360 - 90
            const p1 = polarToCartesian(cx, cy, 85, angle)
            const p2 = polarToCartesian(cx, cy, i % 3 === 0 ? 76 : 80, angle)
            return (
              <line
                key={i}
                x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                stroke={isMatrix
                  ? (i % 3 === 0 ? mGreen : mGreenDim)
                  : (i % 3 === 0 ? '#64748b' : '#334155')
                }
                strokeWidth={i % 3 === 0 ? 1.5 : 0.8}
              />
            )
          })}

          {/* Hour labels */}
          {[12, 3, 6, 9].map((h) => {
            const angle = ((h % 12) / 12) * 360 - 90
            const p = polarToCartesian(cx, cy, 68, angle)
            return (
              <text
                key={h}
                x={p.x} y={p.y}
                textAnchor="middle"
                dominantBaseline="central"
                fill={isMatrix ? mGreen : '#6b7280'}
                style={{ fontSize: '8px', fontFamily: isMatrix ? mFont : 'var(--font-mono)' }}
              >
                {h}
              </text>
            )
          })}

          {/* Minute hand */}
          {(() => {
            const tip = polarToCartesian(cx, cy, 52, minuteAngle)
            return (
              <line
                x1={cx} y1={cy} x2={tip.x} y2={tip.y}
                stroke={isMatrix ? mGreenMid : '#475569'}
                strokeWidth="1"
                strokeLinecap="round"
              />
            )
          })()}

          {/* Hour hand */}
          {(() => {
            const tip = polarToCartesian(cx, cy, 40, handAngle)
            const handColor = isMatrix ? mGreen : (marketOpen ? '#22c55e' : '#64748b')
            return (
              <line
                x1={cx} y1={cy} x2={tip.x} y2={tip.y}
                stroke={handColor}
                strokeWidth="2"
                strokeLinecap="round"
                style={marketOpen ? { filter: `drop-shadow(0 0 4px ${handColor})` } : undefined}
              />
            )
          })()}

          {/* Center dot */}
          <circle
            cx={cx} cy={cy} r="3"
            fill={isMatrix ? mGreen : (marketOpen ? '#22c55e' : '#64748b')}
            style={marketOpen ? { filter: `drop-shadow(0 0 6px ${isMatrix ? mGreen : '#22c55e'})` } : undefined}
          />
        </svg>
      </div>

      {/* Digital time */}
      <div className="text-center shrink-0">
        <p
          className="font-mono text-base font-bold"
          style={isMatrix
            ? { color: mGreen, fontFamily: mFont, textShadow: marketOpen ? `0 0 8px ${mGreenDim}` : 'none' }
            : { color: '#fff', textShadow: marketOpen ? '0 0 8px rgba(34,197,94,0.5)' : 'none' }
          }
        >
          {String(hourLocal).padStart(2, '0')}:{String(minuteLocal).padStart(2, '0')}:{String(secondLocal).padStart(2, '0')}
          <span className="ml-1.5 text-xs" style={{ color: isMatrix ? '#008f2a' : '#6b7280' }}>LOCAL</span>
        </p>
        <p className="mt-0.5 font-mono text-xs" style={{ color: isMatrix ? '#008f2a' : '#4b5563', fontFamily: isMatrix ? mFont : undefined }}>
          {String(br.hour).padStart(2, '0')}:{String(br.minute).padStart(2, '0')} UTC-3
        </p>
      </div>

      {/* Session strength bar */}
      {marketOpen && (
        <div className="mt-2 shrink-0">
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-xs" style={{ color: isMatrix ? '#008f2a' : '#6b7280', fontFamily: isMatrix ? mFont : undefined }}>
              {isMatrix ? '> liquidity' : 'Liquidity'}
            </span>
            <span className="font-mono text-xs" style={{ color: strengthColor }}>{strength}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden bg-gray-800" style={{ borderRadius: isMatrix ? '0' : '9999px' }}>
            <div
              className="h-full transition-all"
              style={{
                width: `${strength}%`,
                borderRadius: isMatrix ? '0' : '9999px',
                background: isMatrix ? mGreenDim : `linear-gradient(90deg, #3b82f6, ${strengthColor})`,
                boxShadow: isMatrix ? 'none' : `0 0 8px ${strengthColor}40`,
              }}
            />
          </div>
        </div>
      )}

      {/* Session bars */}
      <div className="mt-2 flex-1 space-y-1.5">
        {SESSIONS.map((s) => {
          const active = activeSessions.includes(s)
          const progress = active ? getSessionProgress(s, br.hour, br.minute) : 0
          const hoursTotal = s.start < s.end ? s.end - s.start : 24 - s.start + s.end
          const hoursLeft = active ? Math.max(0, Math.round(hoursTotal * (1 - progress))) : 0
          const inOverlap = activeOverlaps.some((o) => o.sessions.includes(s.name))

          // Matrix: monochrome green | Default: original session colors
          const dotColor = isMatrix ? mGreen : s.color
          const barColor = isMatrix
            ? (active ? mGreenDim : 'transparent')
            : (inOverlap ? '#f59e0b' : s.color)

          return (
            <div
              key={s.name}
              style={isMatrix && active ? { borderLeft: `2px solid ${mGreen}`, paddingLeft: '6px' } : undefined}
            >
              <div className="flex items-center justify-between mb-0.5">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`inline-block h-2 w-2 ${isMatrix ? 'rounded-none' : 'rounded-full'} ${active ? 'animate-dot-pulse' : ''}`}
                    style={{
                      backgroundColor: dotColor,
                      opacity: active ? 1 : 0.3,
                      boxShadow: active && !isMatrix ? `0 0 6px ${s.color}` : 'none',
                    }}
                  />
                  <span
                    className="text-xs"
                    style={isMatrix
                      ? { color: active ? mGreen : '#008f2a', fontFamily: mFont }
                      : { color: active ? '#fff' : '#4b5563', fontWeight: active ? 500 : 400 }
                    }
                  >
                    {s.name}
                  </span>
                  {inOverlap && (
                    <span className="text-xs" style={{ color: isMatrix ? mGreen : '#facc15' }}>*</span>
                  )}
                </div>
                <span className="font-mono text-xs" style={{ color: isMatrix ? '#008f2a' : '#4b5563', fontFamily: isMatrix ? mFont : undefined }}>
                  {active ? `${hoursLeft}h left` : `${String(s.start).padStart(2, '0')}:00`}
                </span>
              </div>
              <div className="h-1 w-full overflow-hidden bg-gray-800" style={{ borderRadius: isMatrix ? '0' : '9999px' }}>
                <div
                  className="h-full transition-all"
                  style={{
                    width: active ? `${progress * 100}%` : '0%',
                    borderRadius: isMatrix ? '0' : '9999px',
                    backgroundColor: barColor,
                    boxShadow: active && !isMatrix ? `0 0 6px ${inOverlap ? '#f59e0b' : s.color}` : 'none',
                  }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Overlap indicator */}
      {activeOverlaps.length > 0 && (
        <div
          className="mt-2 shrink-0 px-2 py-1 text-center"
          style={isMatrix
            ? { border: `1px solid ${mGreenDim}`, borderRadius: '2px', background: '#000' }
            : { borderRadius: '0.375rem', background: 'rgba(234,179,8,0.05)' }
          }
        >
          <span className="text-xs" style={{ color: isMatrix ? mGreen : '#facc15', fontFamily: isMatrix ? mFont : undefined }}>
            {isMatrix ? `> ${activeOverlaps.map((o) => o.name).join(' | ')}` : activeOverlaps.map((o) => o.name).join(' | ')}
          </span>
        </div>
      )}
    </div>
  )
}
