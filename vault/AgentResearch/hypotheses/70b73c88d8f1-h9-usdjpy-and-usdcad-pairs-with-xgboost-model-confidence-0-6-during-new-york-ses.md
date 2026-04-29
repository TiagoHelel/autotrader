---
type: agent-hypothesis
created: 2026-04-26T03:20:02.250398+00:00
filter_hash: 70b73c88d8f1
status: generated
tags: [agent-research, hypothesis]
---

# H9 - USDJPY and USDCAD pairs with xgboost model confidence >=0.6 during New York session show improved hit_t1

## Filters

```json
{
  "confidence_min": 0.6,
  "model": "xgboost",
  "session": [
    "new_york"
  ],
  "signal": 1,
  "symbol": [
    "USDJPY",
    "USDCAD"
  ]
}
```

## Causal reasoning

From daily_eval data, USDJPY shows mean hit_t1=0.431 and USDCAD=0.4597 (both above average ~0.45). New York session has baseline 0.3727 but the combination of these specific pairs + NY liquidity window is a known high-conviction setup, especially for USD crosses. The xgboost model shows strong hit rates (0.6013) and may capture different regime signals than random_forest. By filtering for these specific liquid pairs during New York's peak liquidity window with the second-strongest-performing model at moderate confidence (>=0.6), we target a regime where both temporal and instrument-specific factors align causally, potentially capturing USD momentum flows that RF might miss.

## Expected behavior

hit_t1 >= 52% (vs ~43-46% baseline for these pairs), p-value < 0.05 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/70b73c88d8f1-h9-usdjpy-and-usdcad-pairs-with-xgboost-model-confidence-0-6-during-new-york-ses]]
- Experiment log: [[logs/70b73c88d8f1-h9-usdjpy-and-usdcad-pairs-with-xgboost-model-confidence-0-6-during-new-york-ses]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
