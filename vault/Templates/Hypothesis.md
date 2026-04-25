---
type: hypothesis
created: {{date}} {{time}}
status: draft
tags: [hipotese]
filter_hash: 
verdict: 
# filters: dict opcional. Se presente, daily_eval roda automaticamente em todo
# eval e adiciona linha em "## Daily eval log (auto)" no fim da nota.
# Suportado: confidence_min, symbol, model, signal, regime_trend, regime_vol,
# regime_range, session (qualquer coluna do eval_{date}.parquet).
# filters:
#   confidence_min: 0.85
#   symbol: XAUUSD
---

# {{title}}

## Hipotese

> **Uma frase clara, falsificavel.** Ex: "XAUUSD em London-NY overlap (14-15 UTC) com xgb.confidence > 0.8 tem winrate > 55%."

## Por que faz sentido (pre-teste)

- Mecanismo de mercado:
- Evidencia anterior (research, leituras, observacao):
- Diferenca para coin flip:

## Filtro proposto (formato `evaluate_filter`)

```python
filters = {
    "symbol": "XAUUSD",
    "model": "xgboost",
    "hour_utc": (14, 15),
    "session": "london_ny_overlap",
    "confidence_min": 0.80,
}
```

## Plano

- Dataset: `data/research/predictions_xgboost_<timestamp>.parquet`
- Split: `holdout_pct=0.20, method="temporal"`
- N esperado apos filtro: **(estime ANTES de rodar)**
- Criterio de sucesso: WR > 52%, p < 0.05, N >= 100

---

## Resultado (preencher APOS rodar)

- `filter_hash`: 
- N: 
- WR: 
- CI95: 
- p-value: 
- Bonferroni ajustado: 
- Verdict: 

## Validacao no holdout

- Data: 
- N holdout: 
- WR holdout: 
- Decisao: 

## Conclusao / proximos passos

- 

## Links

- Research base: [[]]
- Backtest derivado: [[]]
- Postmortem (se aplicavel): [[]]
