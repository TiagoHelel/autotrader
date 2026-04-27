---
type: agent-hypothesis
created: 2026-04-26T03:02:53.180412+00:00
filter_hash: de816062e0ed
status: generated
tags: [agent-research, hypothesis]
---

# H7 - EURUSD and GBPUSD pairs with random_forest model confidence >=0.65 during London session show improved hit_t1

## Filters

```json
{
  "model": "random_forest",
  "session": [
    "london"
  ],
  "signal": 1,
  "symbol": [
    "EURUSD",
    "GBPUSD"
  ]
}
```

## Causal reasoning

From daily_eval data, EURUSD shows mean hit_t1=0.4713 and GBPUSD=0.4767 (both above average ~0.45). London session has baseline 0.4298 but the combination of major pairs + London liquidity window is a known high-conviction setup. The random_forest model shows highest hit rates across days (0.6497, 0.6732) compared to other models, suggesting it captures edge better than ema_heuristic or naive approaches. By filtering for these specific liquid pairs during London's peak liquidity window with the strongest-performing model at moderate confidence (>=0.65), we target a regime where both temporal and instrument-specific factors align causally.

## Expected behavior

hit_t1 >= 52% (vs ~47% baseline for these pairs), p-value < 0.05, PnL > 1 bps/trade after spread costs
