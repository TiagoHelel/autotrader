import {
  Wallet,
  TrendingUp,
  BarChart3,
  DollarSign,
  ArrowDownCircle,
  Target,
  Activity,
} from 'lucide-react'
import KPICard from '../common/KPICard'
import TrendSparklineCard from './TrendSparklineCard'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import LoadingSpinner from '../common/LoadingSpinner'

export default function KPICards({ wsKpis }) {
  const { data: account, loading } = useApi(() => api.getAccount(), [], { interval: 10000 })

  const d = wsKpis || account

  if (loading && !d) return <LoadingSpinner text="Loading account..." />

  if (!d) return null

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-7">
      <KPICard
        label="Balance"
        value={d.balance}
        prefix="$"
        icon={Wallet}
      />
      <KPICard
        label="Equity"
        value={d.equity}
        prefix="$"
        icon={TrendingUp}
      />
      <KPICard
        label="PnL Daily"
        value={d.pnl_daily}
        prefix="$"
        change={d.pnl_daily ? ((d.pnl_daily / (d.balance || 1)) * 100) : null}
        icon={BarChart3}
      />
      <KPICard
        label="PnL Total"
        value={d.pnl_total}
        prefix="$"
        icon={DollarSign}
      />
      <KPICard
        label="Drawdown"
        value={d.drawdown}
        suffix="%"
        format="percent"
        icon={ArrowDownCircle}
      />
      <KPICard
        label="Win Rate"
        value={d.winrate}
        suffix="%"
        format="percent"
        icon={Target}
      />
      <TrendSparklineCard label="30D Trend" icon={Activity} />
    </div>
  )
}
