import { useState, useEffect, useRef, useCallback } from 'react'
import { WS_URL } from '../services/api'

const WS_RECONNECT_INTERVAL = 10_000

export default function useWebSocket() {
  const [ticks, setTicks] = useState({})
  const [logs, setLogs] = useState([])
  const [kpis, setKpis] = useState(null)
  const [predictions, setPredictions] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case 'tick':
            setTicks((prev) => ({ ...prev, [msg.data.symbol]: msg.data }))
            break
          case 'log':
            setLogs((prev) => [...prev.slice(-199), msg.data])
            break
          case 'kpi':
            setKpis(msg.data)
            break
          case 'prediction':
            setPredictions((prev) => [msg.data, ...prev.slice(0, 49)])
            break
        }
      } catch (e) {
        console.error('WebSocket parse error:', e)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, WS_RECONNECT_INTERVAL)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  return { ticks, logs, kpis, predictions, connected }
}
