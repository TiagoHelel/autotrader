import { describe, test, expect } from 'vitest'

/**
 * Data contract tests — guardrails for what the UI expects from the backend.
 * These are fast, pure assertions: no rendering, no network.
 */

const SIGNAL_VALUES = ['BUY', 'SELL', 'HOLD']

function isValidSignal(s) {
  return (
    s &&
    typeof s.symbol === 'string' &&
    SIGNAL_VALUES.includes(String(s.signal).toUpperCase()) &&
    typeof s.confidence === 'number' &&
    s.confidence >= 0 &&
    s.confidence <= 1
  )
}

describe('Signal data consistency', () => {
  test('confidence is a number in [0, 1]', () => {
    const sample = [
      { symbol: 'EURUSD', signal: 'BUY', confidence: 0.8 },
      { symbol: 'GBPUSD', signal: 'SELL', confidence: 0.42 },
      { symbol: 'USDJPY', signal: 'HOLD', confidence: 0.0 },
      { symbol: 'XAUUSD', signal: 'BUY', confidence: 1.0 },
    ]
    sample.forEach((s) => {
      expect(s.confidence).toBeGreaterThanOrEqual(0)
      expect(s.confidence).toBeLessThanOrEqual(1)
      expect(isValidSignal(s)).toBe(true)
    })
  })

  test('signal is one of BUY/SELL/HOLD', () => {
    SIGNAL_VALUES.forEach((v) => {
      expect(isValidSignal({ symbol: 'X', signal: v, confidence: 0.5 })).toBe(true)
    })
    expect(isValidSignal({ symbol: 'X', signal: 'LONG', confidence: 0.5 })).toBe(false)
    expect(isValidSignal({ symbol: 'X', signal: null, confidence: 0.5 })).toBe(false)
  })

  test('rejects invalid confidence values', () => {
    expect(isValidSignal({ symbol: 'X', signal: 'BUY', confidence: 1.5 })).toBe(false)
    expect(isValidSignal({ symbol: 'X', signal: 'BUY', confidence: -0.1 })).toBe(false)
    expect(isValidSignal({ symbol: 'X', signal: 'BUY', confidence: 'high' })).toBe(false)
  })
})

describe('Candle data consistency', () => {
  const candle = { time: 1700000000, open: 1.10, high: 1.12, low: 1.09, close: 1.11 }

  test('OHLC obeys high >= max(open,close) and low <= min(open,close)', () => {
    expect(candle.high).toBeGreaterThanOrEqual(Math.max(candle.open, candle.close))
    expect(candle.low).toBeLessThanOrEqual(Math.min(candle.open, candle.close))
  })

  test('time is a positive number', () => {
    expect(typeof candle.time).toBe('number')
    expect(candle.time).toBeGreaterThan(0)
  })
})
