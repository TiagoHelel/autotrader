---
type: agent-hypothesis
created: 2026-04-25T21:35:31.400173+00:00
filter_hash: e84fbf339819
status: generated
tags: [agent-research, hypothesis]
---

# H5 - Confidence >= 0.75 combined with Tokyo session (tokyo, tokyo,london) and signal=1 improves hit_t1 to >62% with positive PnL

## Filters

```json
{
  "confidence_min": 0.75,
  "session": [
    "tokyo",
    "tokyo,london"
  ],
  "signal": 1
}
```

## Causal reasoning

From daily_eval data: Tokyo sessions show highest baseline hit rates (tokyo=0.50, tokyo,london=0.5182) compared to London/New York overlap (~0.39-0.43). Confidence gradient shows strong monotonic improvement (<0.3: 46.8%, 0.7-0.85: 53.5%, 0.85+: 64.5%). Combining Tokyo session (known higher predictability) with moderate-high confidence (>=0.75, not too restrictive like 0.85 which only has ~4910 samples/day) should capture the intersection where both temporal and model-consensus factors align. This is causal: Tokyo opens often have clearer momentum establishment after Asian session consolidation, and higher confidence indicates multi-model agreement on that directional signal.

## Expected behavior

hit_t1 >= 62% (vs ~50-53% baseline), p-value < 0.01 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs
