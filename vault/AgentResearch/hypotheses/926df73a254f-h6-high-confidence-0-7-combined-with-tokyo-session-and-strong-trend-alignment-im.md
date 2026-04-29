---
type: agent-hypothesis
created: 2026-04-26T03:02:38.995916+00:00
filter_hash: 926df73a254f
status: generated
tags: [agent-research, hypothesis]
---

# H6 - High confidence (>=0.7) combined with Tokyo session and strong trend alignment improves hit_t1 to >60% with positive PnL

## Filters

```json
{
  "confidence_min": 0.7,
  "session": [
    "tokyo"
  ],
  "signal": 1
}
```

## Causal reasoning

Tokyo sessions show highest baseline hit rates (tokyo=0.50) compared to London/New York overlap (~0.39-0.43). Confidence gradient shows strong monotonic improvement (<0.3: 46.8%, 0.7-0.85: 53.5%, 0.85+: 64.5%). The previous H5 test with confidence_min=0.75 and sessions [tokyo, tokyo,london] was REJECTED_N but had n=0 (insufficient samples). By narrowing to just 'tokyo' session (which has 0.50 baseline vs 0.5182 for tokyo+london) and lowering confidence threshold to 0.7 (vs 0.75), we capture more samples while maintaining the causal mechanism: Tokyo opens have clearer momentum establishment after Asian consolidation, and moderate-high confidence indicates multi-model agreement on directional signals. The intersection of temporal predictability + model consensus should create a stronger edge than the previous broader session filter.

## Expected behavior

hit_t1 >= 60% (vs ~50-53% baseline), p-value < 0.01 Bonferroni-adjusted, PnL > 1 bps/trade after spread costs

## Related

- Learning: [[learnings/926df73a254f-h6-high-confidence-0-7-combined-with-tokyo-session-and-strong-trend-alignment-im]]
- Experiment log: [[logs/926df73a254f-h6-high-confidence-0-7-combined-with-tokyo-session-and-strong-trend-alignment-im]]
- Folder: [[AgentResearch/hypotheses/_index|hypotheses]]
- Area: [[AgentResearch/README|AgentResearch]]
