import { Bot, Clock, Layers, Cpu } from 'lucide-react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import Badge from '../common/Badge'
import LoadingSpinner from '../common/LoadingSpinner'

const BOT_STATUS_INTERVAL = 10_000

export default function BotStatus() {
  const { data, loading } = useApi(() => api.getBotStatus(), [], { interval: BOT_STATUS_INTERVAL })

  if (loading) return <LoadingSpinner text="Loading bot status..." />
  if (!data) return null

  const isRunning = data.status === 'running'

  return (
    <div className="glass-card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">Bot Status</h3>
        <Badge variant={isRunning ? 'running' : 'stopped'}>
          {data.status?.toUpperCase() || 'UNKNOWN'}
        </Badge>
      </div>

      <div className="space-y-3">
        <StatusRow icon={Bot} label="Current Symbol" value={data.current_symbol || '-'} />
        <StatusRow icon={Clock} label="Timeframe" value={data.timeframe || '-'} />
        <StatusRow icon={Layers} label="Active Symbols" value={data.symbols_active ?? '-'} />
        <StatusRow icon={Cpu} label="Active Models" value={data.models_active ?? '-'} />
        <StatusRow icon={Clock} label="Uptime" value={formatUptime(data.uptime_seconds)} />
      </div>

      {isRunning && (
        <div className="mt-4 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse-dot" />
          <span className="text-xs text-green-400">System operational</span>
        </div>
      )}
    </div>
  )
}

function StatusRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-gray-900/50 px-3 py-2">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <span className="font-mono text-xs font-medium text-gray-300">{value}</span>
    </div>
  )
}

function formatUptime(seconds) {
  if (!seconds && seconds !== 0) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}
