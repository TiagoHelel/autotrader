import { lazy, Suspense, memo, useState, useCallback } from 'react'
import useWebSocket from '../hooks/useWebSocket'
import KPICards from '../components/dashboard/KPICards'
import LoadingSpinner from '../components/common/LoadingSpinner'
import MarketStatusBanner from '../components/common/MarketStatusBanner'
import { useTheme } from '../theme/ThemeProvider'

// Lazy load heavy components
const ControlTowerClock = lazy(() => import('../components/control_tower/ControlTowerClock'))
const SignalBoard = lazy(() => import('../components/control_tower/SignalBoard'))
const AICorePanel = lazy(() => import('../components/control_tower/AICorePanel'))
const WorldMap = lazy(() => import('../components/control_tower/WorldMap'))
const LivePredictionChart = lazy(() => import('../components/control_tower/LivePredictionChart'))
const DataStream = lazy(() => import('../components/control_tower/DataStream'))
const SessionPanel = lazy(() => import('../components/control_tower/SessionPanel'))

const MemoKPICards = memo(KPICards)

function LazyWrap({ children, className = '' }) {
  return (
    <Suspense fallback={<LoadingSpinner text="Loading..." />}>
      <div className={`h-full ${className}`}>{children}</div>
    </Suspense>
  )
}

export default function ControlTower() {
  const { kpis } = useWebSocket()
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'

  // Lifted: shared between Session Intelligence and LivePredictionChart
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD')
  const handleSymbolChange = useCallback((s) => setSelectedSymbol(s), [])

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div>
        {isMatrix ? (
          <>
            <h2 className="font-mono text-xl font-bold uppercase tracking-[0.22em]" style={{ color: 'var(--theme-text)' }}>
              CONTROL NODE
            </h2>
            <p className="font-mono text-xs uppercase tracking-[0.18em]" style={{ color: 'var(--theme-text-muted)' }}>
              REAL-TIME MARKET CONSOLE / LIVE SYSTEM FEED
            </p>
          </>
        ) : (
          <>
            <h2 className="text-xl font-bold" style={{ color: 'var(--theme-text)', textShadow: `0 0 12px var(--theme-accent-glow)` }}>
              Control Tower
            </h2>
            <p className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>Real-time market intelligence hub</p>
          </>
        )}
      </div>

      <MarketStatusBanner />

      {/* KPI Strip (now 7 cards incl. 30D Trend sparkline) */}
      <MemoKPICards wsKpis={kpis} />

      {/* Row: Clock | Session Intel | Radar | AI Core */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        <LazyWrap><ControlTowerClock /></LazyWrap>
        <LazyWrap>
          <SessionPanel selectedSymbol={selectedSymbol} onSymbolChange={handleSymbolChange} />
        </LazyWrap>
        <LazyWrap><SignalBoard /></LazyWrap>
        <LazyWrap><AICorePanel /></LazyWrap>
      </div>

      {/* Row: World Map | Live Prediction Chart | Data Stream */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3" style={{ gridAutoRows: '400px' }}>
        <LazyWrap><WorldMap /></LazyWrap>
        <LazyWrap><LivePredictionChart symbol={selectedSymbol} /></LazyWrap>
        <LazyWrap><DataStream /></LazyWrap>
      </div>
    </div>
  )
}
