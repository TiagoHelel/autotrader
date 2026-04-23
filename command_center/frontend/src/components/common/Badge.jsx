const variants = {
  buy: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  sell: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  hold: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  profit: 'bg-green-500/20 text-green-400 border-green-500/30',
  loss: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-red-500/20 text-red-400 border-red-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
  info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  running: 'bg-green-500/20 text-green-400 border-green-500/30',
  stopped: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
}

export default function Badge({ variant = 'info', children }) {
  const classes = variants[variant] || variants.info

  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}
    >
      {children}
    </span>
  )
}
