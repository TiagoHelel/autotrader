---
type: agent-hypothesis
created: 2026-04-27T03:03:44.024800+00:00
filter_hash: e5267b6a726d
status: generated
tags: [agent-research, hypothesis]
---

# USDJPY and EURJPY pairs with xgboost model confidence >=0.7 during Tokyo session show improved hit_t1

## Filters

```json
{
  "confidence_min": 0.7,
  "model": "xgboost",
  "session": [
    "tokyo"
  ],
  "signal": 1,
  "symbol": [
    "USDJPY",
    "EURJPY"
  ]
}
```

## Causal reasoning

From daily_eval data: USDJPY shows mean hit_t1=0.431 and EURJPY=0.4105 (both above average ~0.45). Tokyo session has baseline 0.50 which is the highest among all sessions, suggesting clearer momentum establishment after Asian consolidation. The xgboost model shows strong hit rates (0.6013) and may capture different regime signals than random_forest, particularly for JPY crosses which have unique liquidity characteristics during Tokyo hours. H6 tested high confidence with Tokyo session but didn't specify models or symbols - by narrowing to JPY crosses specifically with xgboost at moderate-high confidence (>=0.7), we target the intersection where temporal predictability + model consensus + instrument-specific factors align causally.

## Expected behavior

hit_t1 >= 56% (vs ~41-43% baseline for these pairs), p-value < 0.05 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/e5267b6a726d-usdjpy-and-eurjpy-pairs-with-xgboost-model-confidence-0-7-during-tokyo-session-s]]
- Experiment log: [[logs/e5267b6a726d-usdjpy-and-eurjpy-pairs-with-xgboost-model-confidence-0-7-during-tokyo-session-s]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
