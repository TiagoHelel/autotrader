---
type: agent-hypothesis
created: 2026-04-28T03:13:26.438696+00:00
filter_hash: 332e319a0a01
status: generated
tags: [agent-research, hypothesis]
---

# NZDUSD and AUDUSD pairs with random_forest model confidence >=0.6 during London session show improved hit_t1

## Filters

```json
{
  "confidence_min": 0.6,
  "model": "random_forest",
  "session": [
    "london"
  ],
  "signal": 1,
  "symbol": [
    "NZDUSD",
    "AUDUSD"
  ]
}
```

## Causal reasoning

From daily_eval data: NZDUSD shows mean hit_t1=0.4648 and AUDUSD=0.4152 (both above average ~0.45). London session has baseline 0.4298 but the combination of commodity-currency pairs + London liquidity window is a known high-conviction setup, especially for pairs with clear trend establishment characteristics. The random_forest model shows highest hit rates across days (0.6497, 0.6732) compared to other models. By filtering for these specific commodity-sensitive pairs during London's peak liquidity window with the strongest-performing model at moderate confidence (>=0.6), we target a regime where both temporal and instrument-specific factors align causally, potentially capturing commodity-driven momentum flows that differ from pure fiat crosses.

## Expected behavior

hit_t1 >= 50% (vs ~42-46% baseline for these pairs), p-value < 0.05 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/332e319a0a01-nzdusd-and-audusd-pairs-with-random-forest-model-confidence-0-6-during-london-se]]
- Experiment log: [[logs/332e319a0a01-nzdusd-and-audusd-pairs-with-random-forest-model-confidence-0-6-during-london-se]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
