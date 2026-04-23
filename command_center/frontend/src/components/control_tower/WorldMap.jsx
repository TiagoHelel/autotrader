import { useRef, useEffect, useMemo, useState, useCallback, lazy, Suspense } from 'react'
import useApi from '../../hooks/useApi'
import { api } from '../../services/api'
import { useTheme } from '../../theme/ThemeProvider'
import LoadingSpinner from '../common/LoadingSpinner'

const SIGNALS_REFRESH_INTERVAL = 60_000

const Globe = lazy(() => import('react-globe.gl'))

// Currency centers (lat, lng)
const CURRENCY_LOCATIONS = {
  USD: { lat: 38.9, lng: -77.0, label: 'USD', city: 'New York' },
  EUR: { lat: 50.1, lng: 8.68, label: 'EUR', city: 'Frankfurt' },
  GBP: { lat: 51.5, lng: -0.12, label: 'GBP', city: 'London' },
  JPY: { lat: 35.7, lng: 139.7, label: 'JPY', city: 'Tokyo' },
  AUD: { lat: -33.9, lng: 151.2, label: 'AUD', city: 'Sydney' },
  CAD: { lat: 45.4, lng: -75.7, label: 'CAD', city: 'Ottawa' },
  CHF: { lat: 46.9, lng: 7.45, label: 'CHF', city: 'Bern' },
  NZD: { lat: -41.3, lng: 174.8, label: 'NZD', city: 'Wellington' },
  XAU: { lat: 51.5, lng: -0.12, label: 'XAU', city: 'London' },
}

// Parse symbol like "EURUSD" into base/quote currencies
function parseSymbol(symbol) {
  const s = symbol.replace(/[^A-Z]/g, '')
  // Handle XAU
  if (s.startsWith('XAU')) return { base: 'XAU', quote: s.slice(3) }
  if (s.endsWith('XAU')) return { base: s.slice(0, -3), quote: 'XAU' }
  return { base: s.slice(0, 3), quote: s.slice(3, 6) }
}

const COUNTRIES_GEOJSON_URL = 'https://unpkg.com/world-atlas@2/countries-110m.json'

// Matrix Rain background canvas
function MatrixRain({ width, height }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const fontSize = 14
    const columns = Math.floor(width / fontSize)
    const drops = new Array(columns).fill(1)
    const chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789ABCDEF'

    function draw() {
      // Trail mais longo (fade menor) para compensar frame rate baixo
      ctx.fillStyle = 'rgba(0, 0, 0, 0.08)'
      ctx.fillRect(0, 0, width, height)
      ctx.fillStyle = 'rgba(0, 255, 65, 0.45)'
      ctx.font = `${fontSize}px monospace`

      for (let i = 0; i < drops.length; i++) {
        const text = chars[Math.floor(Math.random() * chars.length)]
        ctx.fillText(text, i * fontSize, drops[i] * fontSize)

        if (drops[i] * fontSize > height && Math.random() > 0.985) {
          drops[i] = 0
        }
        drops[i]++
      }
    }

    // ~8fps — rain lento e ambiente, nao chamativo
    const interval = setInterval(draw, 125)

    return () => {
      clearInterval(interval)
    }
  }, [width, height])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        zIndex: 0,
        pointerEvents: 'none',
        opacity: 0.7,
      }}
    />
  )
}

export default function WorldMap() {
  const globeRef = useRef()
  const containerRef = useRef()
  const [dimensions, setDimensions] = useState({ width: 500, height: 400 })
  const [countries, setCountries] = useState([])
  const { theme } = useTheme()
  const isMatrix = theme === 'matrix'

  const { data: predictions } = useApi(() => api.getLatestSignals(null, 30), [], { interval: SIGNALS_REFRESH_INTERVAL })
  const { data: newsAnalytics } = useApi(() => api.getNewsAnalytics(), [], { interval: 30000 })
  const { data: sessionData } = useApi(() => api.getSessionCurrent('EURUSD'), [], { interval: 15000 })

  // Fetch countries GeoJSON for hex polygons (matrix theme)
  useEffect(() => {
    if (!isMatrix) return
    fetch(COUNTRIES_GEOJSON_URL)
      .then((r) => r.json())
      .then((topoData) => {
        // Convert TopoJSON to GeoJSON features
        if (topoData.type === 'Topology') {
          const key = Object.keys(topoData.objects)[0]
          import('topojson-client').then(({ feature }) => {
            const geo = feature(topoData, topoData.objects[key])
            setCountries(geo.features)
          }).catch(() => {
            // Fallback: try loading GeoJSON directly
            fetch('https://unpkg.com/world-atlas@2/countries-50m.json')
              .then((r) => r.json())
              .then(() => setCountries([]))
          })
        } else if (topoData.features) {
          setCountries(topoData.features)
        }
      })
      .catch(() => {})
  }, [isMatrix])

  // Responsive sizing
  useEffect(() => {
    if (!containerRef.current) return
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      setDimensions({ width, height: Math.max(height, 350) })
    })
    obs.observe(containerRef.current)
    return () => obs.disconnect()
  }, [])

  // Auto-rotate
  useEffect(() => {
    if (globeRef.current) {
      globeRef.current.controls().autoRotate = true
      globeRef.current.controls().autoRotateSpeed = isMatrix ? 0.3 : 0.4
      globeRef.current.controls().enableZoom = true
      globeRef.current.pointOfView({ lat: 30, lng: 10, altitude: 2.2 })
    }
  }, [isMatrix])

  // Compute currency strength from news analytics (by_currency sentiment)
  const currencyStrength = useMemo(() => {
    const strength = {}
    const byCurrency = newsAnalytics?.analytics?.by_currency || {}
    Object.entries(byCurrency).forEach(([cur, stats]) => {
      // Prefer LLM sentiment, fallback to basic
      const score = stats.sentiment_llm_avg ?? stats.sentiment_basic_avg ?? 0
      strength[cur] = typeof score === 'number' ? score : parseFloat(score) || 0
    })
    return strength
  }, [newsAnalytics])

  // Build arcs from predictions (signal flows between currency pairs)
  const arcsData = useMemo(() => {
    const predList = Array.isArray(predictions) ? predictions : predictions?.signals || []
    if (!predList.length) return []
    const arcs = []
    const seen = new Set()

    predList.forEach((sig) => {
      const sym = sig.symbol || ''
      const { base, quote } = parseSymbol(sym)
      const from = CURRENCY_LOCATIONS[base]
      const to = CURRENCY_LOCATIONS[quote]
      if (!from || !to) return
      const key = `${base}-${quote}`
      if (seen.has(key)) return
      seen.add(key)

      const direction = (sig.direction || sig.signal || 'HOLD').toUpperCase()
      const confidence = sig.confidence ?? sig.probability ?? 0.5

      let color
      if (isMatrix) {
        // Matrix: green for BUY, red for SELL, dim green for HOLD
        if (direction === 'BUY' || direction === 'LONG') {
          color = ['rgba(0, 255, 65, 0.8)', 'rgba(0, 255, 65, 0.15)']
        } else if (direction === 'SELL' || direction === 'SHORT') {
          color = ['rgba(255, 0, 51, 0.8)', 'rgba(255, 0, 51, 0.15)']
        } else {
          color = ['rgba(0, 255, 65, 0.3)', 'rgba(0, 255, 65, 0.05)']
        }
      } else {
        if (direction === 'BUY' || direction === 'LONG') {
          color = ['rgba(34, 197, 94, 0.6)', 'rgba(34, 197, 94, 0.1)']
        } else if (direction === 'SELL' || direction === 'SHORT') {
          color = ['rgba(239, 68, 68, 0.6)', 'rgba(239, 68, 68, 0.1)']
        } else {
          color = ['rgba(107, 114, 128, 0.4)', 'rgba(107, 114, 128, 0.1)']
        }
      }

      arcs.push({
        startLat: from.lat,
        startLng: from.lng,
        endLat: to.lat,
        endLng: to.lng,
        color,
        stroke: isMatrix ? 0.5 + confidence * 1.5 : 0.5 + confidence * 2,
        label: `${sym}: ${direction}`,
        confidence,
      })
    })
    return arcs
  }, [predictions, isMatrix])

  // Points for currency centers
  const pointsData = useMemo(() => {
    return Object.entries(CURRENCY_LOCATIONS).map(([cur, loc]) => {
      const strength = currencyStrength[cur] ?? 0
      let color
      if (isMatrix) {
        // Matrix: all green, intensity varies
        if (strength > 0.2) color = '#00ff41'
        else if (strength < -0.2) color = '#ff0033'
        else color = '#008f2a'
      } else {
        if (strength > 0.2) color = '#22c55e'
        else if (strength < -0.2) color = '#ef4444'
        else color = '#3b82f6'
      }
      return {
        lat: loc.lat,
        lng: loc.lng,
        label: cur,
        city: loc.city,
        color,
        size: 0.4 + Math.abs(strength) * 0.6,
        strength,
      }
    })
  }, [currencyStrength, isMatrix])

  // Labels
  const labelsData = useMemo(() => {
    return pointsData.map((p) => ({
      lat: p.lat,
      lng: p.lng,
      text: p.label,
      color: isMatrix ? '#00ff41' : p.color,
      size: isMatrix ? 1.2 : 0.8,
    }))
  }, [pointsData, isMatrix])

  // Sentiment label for tooltip
  const getSentimentLabel = useCallback((strength) => {
    if (strength > 0.2) return 'Strong'
    if (strength < -0.2) return 'Weak'
    return 'Neutral'
  }, [])

  const getFlowLabel = useCallback((strength) => {
    const abs = Math.abs(strength)
    if (abs > 0.4) return 'High'
    if (abs > 0.15) return 'Medium'
    return 'Low'
  }, [])

  // Legend colors
  const legendItems = useMemo(() => {
    if (isMatrix) {
      return [
        { label: 'Strong', color: '#00ff41' },
        { label: 'Neutral', color: '#008f2a' },
        { label: 'Weak', color: '#ff0033' },
      ]
    }
    return [
      { label: 'Strong', color: '#22c55e' },
      { label: 'Neutral', color: '#3b82f6' },
      { label: 'Weak', color: '#ef4444' },
    ]
  }, [isMatrix])

  // Globe material for matrix
  const globeMaterial = useMemo(() => {
    if (!isMatrix) return undefined
    // We'll apply this via onGlobeReady
    return null
  }, [isMatrix])

  // Apply custom material when globe is ready
  const onGlobeReady = useCallback(() => {
    if (!globeRef.current) return
    const controls = globeRef.current.controls()
    controls.autoRotate = true
    controls.autoRotateSpeed = isMatrix ? 0.3 : 0.4
    controls.enableZoom = true

    if (isMatrix) {
      // Access the globe mesh and set material
      const scene = globeRef.current.scene()
      scene.traverse((obj) => {
        if (obj.type === 'Mesh' && obj.geometry?.type === 'SphereGeometry') {
          obj.material.color.setHex(0x003d00)
          obj.material.emissive.setHex(0x00ff41)
          obj.material.emissiveIntensity = 0.25
          obj.material.shininess = 0.05
          obj.material.needsUpdate = true
        }
      })
    }
  }, [isMatrix])

  const containerStyle = useMemo(() => {
    if (!isMatrix) return {}
    return {
      background: 'radial-gradient(circle, #0a2f0a 0%, #001a00 100%)',
      borderRadius: '0.75rem',
    }
  }, [isMatrix])

  return (
    <div className="themed-card rounded-xl p-4 flex flex-col h-full" style={containerStyle}>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider"
        style={{ color: isMatrix ? '#00ff41' : '#9ca3af' }}
      >
        Global Currency Flow
      </h3>
      <div ref={containerRef} className="relative flex-1 min-h-0">
        {isMatrix && <MatrixRain width={dimensions.width} height={dimensions.height} />}
        <Suspense fallback={<LoadingSpinner text="Loading globe..." />}>
          <Globe
            ref={globeRef}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor="rgba(0,0,0,0)"
            onGlobeReady={onGlobeReady}

            // Globe surface
            {...(isMatrix
              ? { globeImageUrl: undefined }
              : { globeImageUrl: '//unpkg.com/three-globe/example/img/earth-night.jpg' }
            )}

            // Atmosphere
            atmosphereColor={isMatrix ? '#00ff41' : '#3b82f6'}
            atmosphereAltitude={isMatrix ? 0.25 : 0.15}

            // Hex polygons (matrix only — country outlines as dots)
            hexPolygonsData={isMatrix ? countries : []}
            hexPolygonResolution={3}
            hexPolygonMargin={0.6}
            hexPolygonColor={() => 'rgba(0,255,65,0.6)'}

            // Arcs
            arcsData={arcsData}
            arcColor="color"
            arcStroke="stroke"
            arcDashLength={0.4}
            arcDashGap={0.2}
            arcDashAnimateTime={isMatrix
              ? (d) => 2000 / Math.max(d.confidence || 0.2, 0.2)
              : 2000
            }
            arcLabel="label"

            // Points
            pointsData={pointsData}
            pointColor="color"
            pointAltitude={0.01}
            pointRadius="size"
            pointLabel={(d) =>
              isMatrix
                ? `${d.label}\nSentiment: ${getSentimentLabel(d.strength)}\nFlow: ${getFlowLabel(d.strength)}`
                : `${d.label} (${d.city}) — ${d.strength > 0 ? '+' : ''}${d.strength.toFixed(2)}`
            }

            // Labels
            labelsData={labelsData}
            labelText="text"
            labelColor="color"
            labelSize="size"
            labelDotRadius={0.3}
            labelAltitude={0.02}
          />
        </Suspense>

        {/* Overlay legend */}
        <div
          className="absolute bottom-2 left-2 flex gap-3 rounded-lg px-3 py-1.5 backdrop-blur-sm"
          style={{
            backgroundColor: isMatrix ? 'rgba(0, 10, 0, 0.85)' : 'rgba(3, 7, 18, 0.8)',
            border: isMatrix ? '1px solid rgba(0, 255, 65, 0.2)' : 'none',
          }}
        >
          {legendItems.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-xs" style={{ color: isMatrix ? '#008f2a' : '#6b7280' }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
