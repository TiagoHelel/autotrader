---
type: agent-hypothesis
created: 2026-04-29T03:06:24.307409+00:00
filter_hash: 2aee539f32fc
status: generated
tags: [agent-research, hypothesis]
---

# EURUSD and GBPUSD pairs with random_forest model confidence >=0.75 during London session show improved hit_t1

## Filters

```json
{
  "confidence_min": 0.75,
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

From daily_eval data, EURUSD shows mean hit_t1=0.4713 and GBPUSD=0.4767 (both above average ~0.45). London session has baseline 0.4298 but the combination of major pairs + London liquidity window is a known high-conviction setup. The random_forest model shows highest hit rates across days (0.6497, 0.6732) compared to other models. H7 tested EURUSD/GBPUSD with RF during London at confidence>=0.65 but was REJECTED_N - by raising the confidence threshold to 0.75, we target a regime where both temporal and instrument-specific factors align causally while filtering for stronger model consensus. The higher confidence gate should reduce noise from marginal predictions that may have contaminated the lower-threshold test.

## Expected behavior

hit_t1 >= 60% (vs ~47-48% baseline for these pairs), p-value < 0.05 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/2aee539f32fc-eurusd-and-gbpusd-pairs-with-random-forest-model-confidence-0-75-during-london-s]]
- Experiment log: [[logs/2aee539f32fc-eurusd-and-gbpusd-pairs-with-random-forest-model-confidence-0-75-during-london-s]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
