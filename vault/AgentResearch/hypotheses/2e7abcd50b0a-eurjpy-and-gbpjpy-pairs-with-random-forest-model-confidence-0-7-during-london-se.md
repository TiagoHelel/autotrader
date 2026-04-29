---
type: agent-hypothesis
created: 2026-04-27T03:03:33.701505+00:00
filter_hash: 2e7abcd50b0a
status: generated
tags: [agent-research, hypothesis]
---

# EURJPY and GBPJPY pairs with random_forest model confidence >=0.7 during London session show improved hit_t1

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
    "EURJPY",
    "GBPJPY"
  ]
}
```

## Causal reasoning

From daily_eval data: EURJPY shows mean hit_t1=0.4105 and GBPJPY=0.4318 (both above average ~0.45). London session has baseline 0.4298 but the combination of JPY crosses + London liquidity window is a known high-conviction setup, especially for pairs with strong momentum characteristics. The random_forest model shows highest hit rates across days (0.6497, 0.6732) compared to other models. H8 tested EURUSD/GBPJPY with RF during London at confidence>=0.7 but only included EURUSD and GBPJPY - by focusing specifically on the JPY crosses (EURJPY, GBPJPY) which have stronger momentum characteristics in London sessions, we target a regime where both temporal and instrument-specific factors align causally while filtering for stronger model consensus.

## Expected behavior

hit_t1 >= 54% (vs ~41-43% baseline for these pairs), p-value < 0.05 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/2e7abcd50b0a-eurjpy-and-gbpjpy-pairs-with-random-forest-model-confidence-0-7-during-london-se]]
- Experiment log: [[logs/2e7abcd50b0a-eurjpy-and-gbpjpy-pairs-with-random-forest-model-confidence-0-7-during-london-se]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
