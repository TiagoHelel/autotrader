import { Trophy, TrendingUp, TrendingDown } from 'lucide-react'
import useWebSocket from '../hooks/useWebSocket'
import useApi from '../hooks/useApi'
import { api } from '../services/api'
import KPICards from '../components/dashboard/KPICards'
import EquityChart from '../components/dashboard/EquityChart'
import BotStatus from '../components/dashboard/BotStatus'
import ModelDecision from '../components/dashboard/ModelDecision'

export default function Dashboard() {
  const { kpis, predictions } = useWebSocket()

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h2 className="text-xl font-bold" style={{ color: 'var(--theme-text)' }}>Dashboard</h2>
        <p className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>Real-time trading overview</p>
      </div>

      {/* KPI Cards */}
      <KPICards wsKpis={kpis} />

      {/* Best Model Card */}
      <BestModelCard />

      {/* Charts + Status Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <EquityChart />
        </div>
        <div className="space-y-6">
          <BotStatus />
          <ModelDecision wsPredictions={predictions} />
        </div>
      </div>
    </div>
  )
}

function BestModelCard() {
  const { data } = useApi(() => api.getBestModel(), [], { interval: 30000 })
  const best = data?.model

  if (!best || !best.model) return null

  const pnl = best.pnl || best.pnl_total || 0
  const sharpe = best.sharpe || best.avg_sharpe || 0
  const drawdown = best.drawdown || best.max_drawdown || 0

  return (
    <div className="glass-card rounded-xl p-5 ring-1 ring-yellow-500/20">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-500/10">
          <Trophy className="h-5 w-5 text-yellow-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white">Best Model</h3>
            <span className="rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs font-medium text-yellow-400">
              {best.model}
            </span>
            {best.feature_set && (
              <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">
                {best.feature_set}
              </span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-6 text-xs">
            <span className="flex items-center gap-1">
              <span className="text-gray-500">PnL:</span>
              <span className={`font-mono font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {pnl >= 0 ? <TrendingUp className="inline h-3 w-3" /> : <TrendingDown className="inline h-3 w-3" />}
                {' '}{Number(pnl).toFixed(1)} pips
              </span>
            </span>
            <span className="flex items-center gap-1">
              <span className="text-gray-500">Sharpe:</span>
              <span className="font-mono text-gray-300">{Number(sharpe).toFixed(2)}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="text-gray-500">Drawdown:</span>
              <span className="font-mono text-red-400">{Number(drawdown).toFixed(1)}</span>
            </span>
            {best.accuracy != null && (
              <span className="flex items-center gap-1">
                <span className="text-gray-500">Accuracy:</span>
                <span className="font-mono text-gray-300">{Number(best.accuracy).toFixed(1)}%</span>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
