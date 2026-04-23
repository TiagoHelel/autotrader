import { useEffect, useRef, useState, useMemo, useCallback, memo } from 'react'
import {
  createChart,
  CrosshairMode,
  CandlestickSeries,
  createSeriesMarkers,
} from 'lightweight-charts'
import { useTheme } from '../../theme/ThemeProvider'
import { api } from '../../services/api'

/**
 * Live Price + Model Prediction view.
 *
 * - Reads candles from /api/predict/candles?symbol=X (last 10)
 * - Reads ensemble prediction from /api/predict/predictions/latest?symbol=X
 * - Builds 3 forecast pseudo-candles (open=prev close, close=ensemble_tN)
 * - Renders real candles + ghost predicted candles using lightweight-charts
 *
 * Symbol is controlled by parent (Session Intelligence selection).
 */
function LivePredictionChart({ symbol = 'EURUSD' }) {
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const realSeriesRef = useRef(null)
  const predSeriesRef = useRef(null)
  const markersRef = useRef(null)

  const [candles, setCandles] = useState([])
  const [latestPred, setLatestPred] = useState(null)
  const [hover, setHover] = useState(null)
  const [error, setError] = useState(null)
  // Bump to force chart re-init when data arrives but chart was missing
  const [dataVersion, setDataVersion] = useState(0)

  // ---- Fetch (30s polling — catches new M5 candles promptly) ----
  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [c, p] = await Promise.all([
          api.getCandles(symbol, 10),
          api.getLatestPrediction(symbol).catch(() => null),
        ])
        if (cancelled) return
        setCandles(c?.candles || [])
        setLatestPred(p && p.ensemble ? p : null)
        setError(null)
        setDataVersion((v) => v + 1)
      } catch (e) {
        if (!cancelled) setError(e.message || 'load error')
      }
    }

    load()
    const id = setInterval(load, 30_000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [symbol])

  // ---- Build chart data (memoized) ----
  const { realData, predData } = useMemo(() => {
    const real = (candles || [])
      .map((row) => {
        const t = Math.floor(new Date(row.time).getTime() / 1000)
        return {
          time: t,
          open: Number(row.open),
          high: Number(row.high),
          low: Number(row.low),
          close: Number(row.close),
        }
      })
      .filter((c) => Number.isFinite(c.open) && Number.isFinite(c.close))
      .sort((a, b) => a.time - b.time)

    if (!real.length || !latestPred?.ensemble) {
      return { realData: real, predData: [] }
    }

    const lastReal = real[real.length - 1]
    const STEP = 5 * 60 // M5
    const ens = latestPred.ensemble

    const horizons = [ens.pred_t1, ens.pred_t2, ens.pred_t3].filter(
      (v) => v != null && Number.isFinite(Number(v)),
    )
    const pred = []
    let prevClose = lastReal.close
    let t = lastReal.time
    for (const v of horizons) {
      t += STEP
      const close = Number(v)
      pred.push({
        time: t,
        open: prevClose,
        close,
        high: Math.max(prevClose, close),
        low: Math.min(prevClose, close),
      })
      prevClose = close
    }

    return { realData: real, predData: pred }
  }, [candles, latestPred])

  // ---- Create / recreate chart when symbol or theme changes ----
  useEffect(() => {
    if (!containerRef.current) return

    // Cleanup previous chart if any
    if (chartRef.current) {
      try { chartRef.current.remove() } catch {}
      chartRef.current = null
      realSeriesRef.current = null
      predSeriesRef.current = null
      markersRef.current = null
    }

    const mGreen = '#00ff41'
    const mGreenDark = '#006622'
    const mGreenGrid = 'rgba(0,255,65,0.1)'
    const mGreenPred = 'rgba(0,255,65,0.4)'
    const mFont = "'JetBrains Mono', 'Fira Code', monospace"

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: isMatrix ? '#000000' : 'transparent' },
        textColor: isMatrix ? mGreen : '#94a3b8',
        fontFamily: isMatrix ? mFont : 'ui-monospace, SFMono-Regular, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: isMatrix ? mGreenGrid : 'rgba(30,41,59,0.6)' },
        horzLines: { color: isMatrix ? mGreenGrid : 'rgba(30,41,59,0.6)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        ...(isMatrix && {
          vertLine: { color: 'rgba(0,255,65,0.3)', labelBackgroundColor: '#001a00' },
          horzLine: { color: 'rgba(0,255,65,0.3)', labelBackgroundColor: '#001a00' },
        }),
      },
      rightPriceScale: { borderColor: isMatrix ? 'rgba(0,255,65,0.2)' : '#334155' },
      timeScale: { borderColor: isMatrix ? 'rgba(0,255,65,0.2)' : '#334155', timeVisible: true, secondsVisible: false },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    const realSeries = chart.addSeries(CandlestickSeries, isMatrix
      ? {
          upColor: mGreen,
          downColor: mGreenDark,
          borderUpColor: mGreen,
          borderDownColor: mGreenDark,
          wickUpColor: mGreen,
          wickDownColor: mGreenDark,
        }
      : {
          upColor: '#22c55e',
          downColor: '#ef4444',
          borderUpColor: '#22c55e',
          borderDownColor: '#ef4444',
          wickUpColor: '#22c55e',
          wickDownColor: '#ef4444',
        }
    )

    const predSeries = chart.addSeries(CandlestickSeries, isMatrix
      ? {
          upColor: mGreenPred,
          downColor: 'rgba(0,102,34,0.4)',
          borderUpColor: mGreen,
          borderDownColor: mGreenDark,
          wickUpColor: mGreenPred,
          wickDownColor: 'rgba(0,102,34,0.4)',
        }
      : {
          upColor: 'rgba(139,92,246,0.55)',
          downColor: 'rgba(96,165,250,0.55)',
          borderUpColor: '#a78bfa',
          borderDownColor: '#60a5fa',
          wickUpColor: '#a78bfa',
          wickDownColor: '#60a5fa',
        }
    )

    chartRef.current = chart
    realSeriesRef.current = realSeries
    predSeriesRef.current = predSeries
    markersRef.current = null

    // Crosshair for tooltip
    chart.subscribeCrosshairMove((param) => {
      if (!param?.time || !param.seriesData) {
        setHover(null)
        return
      }
      const r = param.seriesData.get(realSeries)
      const p = param.seriesData.get(predSeries)
      setHover({ time: param.time, real: r, pred: p })
    })

    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        chart.applyOptions({ width: e.contentRect.width, height: e.contentRect.height })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      try { chart.remove() } catch {}
      chartRef.current = null
      realSeriesRef.current = null
      predSeriesRef.current = null
      markersRef.current = null
    }
  }, [symbol, isMatrix])

  // ---- Push data updates to chart ----
  useEffect(() => {
    if (!realSeriesRef.current || !predSeriesRef.current) return

    realSeriesRef.current.setData(realData)
    predSeriesRef.current.setData(predData)

    // "NOW" marker on last real candle
    if (realData.length) {
      const last = realData[realData.length - 1]
      const marker = {
        time: last.time,
        position: 'aboveBar',
        color: isMatrix ? '#00ff41' : '#facc15',
        shape: 'arrowDown',
        text: isMatrix ? '> NOW' : 'NOW',
      }
      try {
        if (!markersRef.current) {
          markersRef.current = createSeriesMarkers(realSeriesRef.current, [marker])
        } else {
          markersRef.current.setMarkers([marker])
        }
      } catch {
        // marker plugin may be unavailable in some builds
      }
    }

    chartRef.current?.timeScale().fitContent()
  }, [realData, predData, dataVersion])

  // ---- UI overlays ----
  const mGreen = '#00ff41'
  const mGreenDim = 'rgba(0,255,65,0.2)'
  const mGreenMuted = '#008f2a'
  const mFont = "'JetBrains Mono', 'Fira Code', monospace"

  const confidence = latestPred?.confidence
  const confColor = isMatrix
    ? mGreen
    : confidence == null
    ? '#64748b'
    : confidence >= 0.7
    ? '#22c55e'
    : confidence >= 0.4
    ? '#f59e0b'
    : '#ef4444'

  const empty = !realData.length

  return (
    <div className={`themed-card ${isMatrix ? 'rounded-sm' : 'rounded-xl'} p-4 h-full flex flex-col relative`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2 shrink-0">
        <div>
          <h3
            className="text-xs font-semibold uppercase tracking-wider"
            style={isMatrix ? { color: mGreen, fontFamily: mFont } : { color: '#9ca3af' }}
          >
            {isMatrix ? '> Live Price + Prediction' : 'Live Price + Model Prediction'}
          </h3>
          <p className="text-[10px] font-mono" style={{ color: isMatrix ? mGreenMuted : '#4b5563', fontFamily: isMatrix ? mFont : undefined }}>
            {symbol} · M5 · ensemble
          </p>
        </div>
        {latestPred && (
          <div className="flex items-center gap-2 text-[10px]">
            <span style={{ color: isMatrix ? mGreenMuted : '#6b7280' }}>
              {isMatrix ? 'conf' : 'Confidence'}
            </span>
            <div className="h-1.5 w-16 bg-gray-800 overflow-hidden" style={{ borderRadius: isMatrix ? '0' : '9999px' }}>
              <div
                className="h-full transition-all"
                style={{
                  width: `${(confidence ?? 0) * 100}%`,
                  borderRadius: isMatrix ? '0' : '9999px',
                  background: confColor,
                  boxShadow: isMatrix ? 'none' : `0 0 6px ${confColor}80`,
                }}
              />
            </div>
            <span className="font-mono font-bold" style={{ color: confColor, fontFamily: isMatrix ? mFont : undefined }}>
              {confidence == null ? '—' : `${(confidence * 100).toFixed(0)}%`}
            </span>
          </div>
        )}
      </div>

      {/* Chart container */}
      <div ref={containerRef} className="flex-1 min-h-0 relative">
        {empty && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs animate-pulse" style={{ color: isMatrix ? mGreenMuted : '#6b7280', fontFamily: isMatrix ? mFont : undefined }}>
              {error
                ? (isMatrix ? `> err: ${error}` : `Error: ${error}`)
                : (isMatrix ? '> loading candles...' : 'Loading candles...')
              }
            </span>
          </div>
        )}
        {!empty && !latestPred && (
          <div
            className="pointer-events-none absolute top-2 right-2 px-2 py-1 text-[10px]"
            style={isMatrix
              ? { color: mGreen, border: `1px solid ${mGreenDim}`, borderRadius: '2px', background: '#000', fontFamily: mFont }
              : { color: '#facc15', border: '1px solid rgba(161,98,7,0.4)', borderRadius: '0.375rem', background: 'rgba(17,24,39,0.7)' }
            }
          >
            {isMatrix ? '> awaiting predictions...' : 'Waiting for predictions\u2026'}
          </div>
        )}
      </div>

      {/* Tooltip */}
      {hover && (hover.real || hover.pred) && (
        <div
          className="absolute top-12 left-4 z-10 px-3 py-2 text-[10px] font-mono shadow-xl pointer-events-none"
          style={isMatrix
            ? { color: mGreen, background: '#000', border: `1px solid ${mGreenDim}`, borderRadius: '2px', fontFamily: mFont }
            : { color: '#e2e8f0', background: 'rgba(17,24,39,0.9)', border: '1px solid #374151', borderRadius: '0.375rem' }
          }
        >
          {hover.real && (
            <div className="mb-1">
              <div style={{ color: isMatrix ? mGreenMuted : '#6b7280' }}>{isMatrix ? '> real' : 'Real Candle'}</div>
              <div>O: {hover.real.open?.toFixed(5)}</div>
              <div>H: {hover.real.high?.toFixed(5)}</div>
              <div>L: {hover.real.low?.toFixed(5)}</div>
              <div>C: {hover.real.close?.toFixed(5)}</div>
            </div>
          )}
          {hover.pred && (
            <div>
              <div style={{ color: isMatrix ? mGreenMuted : '#a78bfa' }}>{isMatrix ? '> predicted' : 'Predicted Candle'}</div>
              <div>O: {hover.pred.open?.toFixed(5)}</div>
              <div>C: {hover.pred.close?.toFixed(5)}</div>
              <div style={{ color: isMatrix ? mGreenMuted : '#6b7280' }}>Model: Ensemble</div>
              <div style={{ color: isMatrix ? mGreenMuted : '#6b7280' }}>
                Conf: {confidence == null ? '—' : `${(confidence * 100).toFixed(0)}%`}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default memo(LivePredictionChart)
