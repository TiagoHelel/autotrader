import OpenPositions from '../components/positions/OpenPositions'
import TradeHistory from '../components/positions/TradeHistory'

export default function Positions() {
  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Positions</h2>
        <p className="text-sm text-gray-500">Open positions and trade history</p>
      </div>

      <OpenPositions />
      <TradeHistory />
    </div>
  )
}
