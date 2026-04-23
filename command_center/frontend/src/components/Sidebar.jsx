import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  ArrowLeftRight,
  Brain,
  Newspaper,
  Terminal,
  Bot,
  TrendingUp,
  BarChart3,
  FlaskConical,
  LineChart,
  Activity,
  DollarSign,
  Radar,
} from 'lucide-react'
import useApi from '../hooks/useApi'
import { api } from '../services/api'

const BOT_STATUS_INTERVAL = 10_000

const navItems = [
  { to: '/control-tower', icon: Radar, label: 'Control Tower' },
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/overview', icon: TrendingUp, label: 'Overview' },
  { to: '/symbols', icon: LineChart, label: 'Symbols' },
  { to: '/models', icon: BarChart3, label: 'Models' },
  { to: '/backtest', icon: DollarSign, label: 'Backtest' },
  { to: '/positions', icon: ArrowLeftRight, label: 'Positions' },
  { to: '/ai', icon: Brain, label: 'AI / Model' },
  { to: '/experiments', icon: FlaskConical, label: 'Experiments' },
  { to: '/news', icon: Newspaper, label: 'News' },
  { to: '/news-analytics', icon: Activity, label: 'News Analytics' },
  { to: '/logs', icon: Terminal, label: 'Logs' },
]

export default function Sidebar() {
  const { data: botStatus } = useApi(() => api.getBotStatus(), [], { interval: BOT_STATUS_INTERVAL })
  const isRunning = botStatus?.status === 'running'

  return (
    <aside className="flex w-64 flex-col border-r" style={{ background: 'var(--theme-sidebar-bg)', borderColor: 'var(--theme-sidebar-border)' }}>
      {/* Logo */}
      <div className="flex items-center gap-3 border-b px-6 py-5" style={{ borderColor: 'var(--theme-sidebar-border)' }}>
        <div className="flex h-9 w-9 items-center justify-center rounded-lg" style={{ background: 'var(--theme-accent)' }}>
          <Bot className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-wide" style={{ color: 'var(--theme-text)' }}>AutoTrader</h1>
          <p className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>Command Center</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              background: isActive ? 'var(--theme-sidebar-active)' : undefined,
              color: isActive ? 'var(--theme-text)' : 'var(--theme-text-muted)',
            })}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
                isActive ? '' : 'sidebar-link-hover'
              }`
            }
          >
            <Icon className="h-4.5 w-4.5" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Bot Status */}
      <div className="border-t px-4 py-4" style={{ borderColor: 'var(--theme-sidebar-border)' }}>
        <div className="glass-card rounded-lg px-4 py-3">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                isRunning ? 'bg-green-500 animate-pulse-dot' : 'bg-gray-600'
              }`}
            />
            <span className="text-xs font-medium text-gray-300">
              {isRunning ? 'Bot Running' : 'Bot Offline'}
            </span>
          </div>
          {botStatus && (
            <div className="mt-2 space-y-1 text-xs text-gray-500">
              <div className="flex justify-between">
                <span>Symbols</span>
                <span className="text-gray-400">{botStatus.symbols_active ?? '-'}</span>
              </div>
              <div className="flex justify-between">
                <span>Models</span>
                <span className="text-gray-400">{botStatus.models_active ?? '-'}</span>
              </div>
              <div className="flex justify-between">
                <span>Uptime</span>
                <span className="text-gray-400">{formatUptime(botStatus.uptime_seconds)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}

function formatUptime(seconds) {
  if (!seconds && seconds !== 0) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
