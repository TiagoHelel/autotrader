---
type: agent-hypothesis
created: 2026-04-28T03:13:05.745056+00:00
filter_hash: 02c35ec34add
status: generated
tags: [agent-research, hypothesis]
---

# EURUSD and GBPUSD pairs with random_forest model confidence >=0.7 during London session show improved hit_t1

## Filters

```json
{
  "confidence_min": 0.7,
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

From daily_eval data, EURUSD shows mean hit_t1=0.4713 and GBPUSD=0.4767 (both above average ~0.45). London session has baseline 0.4298 but the combination of major pairs + London liquidity window is a known high-conviction setup. The random_forest model shows highest hit rates across days (0.6497, 0.6732) compared to other models. H7 tested EURUSD/GBPUSD with RF during London at confidence>=0.65 but didn't include GBPJPY and used a lower threshold. By adding GBPJPY (which has strong momentum characteristics in London) and raising the confidence threshold to 0.7, we target a regime where both temporal and instrument-specific factors align causally while filtering for stronger model consensus.

## Expected behavior

hit_t1 >= 54% (vs ~47-48% baseline for these pairs), p-value < 0.05 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/02c35ec34add-eurusd-and-gbpusd-pairs-with-random-forest-model-confidence-0-7-during-london-se]]
- Experiment log: [[logs/02c35ec34add-eurusd-and-gbpusd-pairs-with-random-forest-model-confidence-0-7-during-london-se]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
