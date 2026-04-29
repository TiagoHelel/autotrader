---
type: agent-hypothesis
created: 2026-04-26T03:20:02.270013+00:00
filter_hash: ed954f14251a
status: generated
tags: [agent-research, hypothesis]
---

# H10 - XAUUSD with any model confidence >=0.5 during Tokyo session shows improved hit_t1

## Filters

```json
{
  "confidence_min": 0.5,
  "session": [
    "tokyo"
  ],
  "signal": 1,
  "symbol": [
    "XAUUSD"
  ]
}
```

## Causal reasoning

From daily_eval data, XAUUSD (gold) shows mean hit_t1=0.3631-0.3831 across days, which is the lowest among all pairs (~0.45 average). However, Tokyo sessions show highest baseline hit rates (tokyo=0.50) compared to London/New York overlap (~0.39-0.43). Gold often has clearer momentum establishment during Asian session when institutional flows begin positioning for NY open. By filtering specifically for XAUUSD during Tokyo with a moderate confidence threshold (>=0.5), we target the intersection where temporal predictability + commodity-specific factors align causally, potentially capturing gold's unique liquidity and regime characteristics that differ from fiat pairs.

## Expected behavior

hit_t1 >= 48% (vs ~37-38% baseline for XAUUSD), p-value < 0.05 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/ed954f14251a-h10-xauusd-with-any-model-confidence-0-5-during-tokyo-session-shows-improved-hit]]
- Experiment log: [[logs/ed954f14251a-h10-xauusd-with-any-model-confidence-0-5-during-tokyo-session-shows-improved-hit]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
