import { http, HttpResponse } from 'msw'

// MSW handlers — match the real backend endpoints used by the frontend.
// Base URL is dynamic (http://<hostname>:8000) so we wildcard the origin.
const match = (path) => new RegExp(`^https?://[^/]+${path}$`)

export const handlers = [
  http.get(match('/api/predict/signals/radar'), () =>
    HttpResponse.json({
      signals: [
        { symbol: 'EURUSD', signal: 'BUY', confidence: 0.82 },
        { symbol: 'GBPUSD', signal: 'SELL', confidence: 0.64 },
        { symbol: 'USDJPY', signal: 'HOLD', confidence: 0.31 },
      ],
      breakdown: { BUY: 1, SELL: 1, HOLD: 1 },
      total: 3,
    }),
  ),

  http.get(match('/api/predict/candles'), () =>
    HttpResponse.json({
      candles: [
        { time: 1700000000, open: 1.10, high: 1.11, low: 1.09, close: 1.105 },
        { time: 1700000060, open: 1.105, high: 1.112, low: 1.102, close: 1.108 },
      ],
    }),
  ),

  http.get(match('/api/predict/predictions/latest'), () =>
    HttpResponse.json({
      ensemble: { t1: 1.109, t2: 1.110, t3: 1.111 },
    }),
  ),

  // Fallback for other endpoints used ambiently
  http.get(match('/api/.*'), () => HttpResponse.json({})),
]
