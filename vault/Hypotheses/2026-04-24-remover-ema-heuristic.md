---
type: hypothesis
created: 2026-04-24
status: draft
tags: [hipotese, ensemble, model-pruning]
filter_hash: 
verdict: 
---

# H4 - Remover ema_heuristic do ensemble melhora PnL

## Hipotese

> `ema_heuristic` tem PnL liquido < 0 e winrate < 50% em janela 30 dias
> quando age via signal engine. Remove-lo do ensemble (ou do voting) melhora
> PnL agregado da estrategia em pelo menos 2 bps por trade.

## Por que faz sentido (pre-teste)

- **Mecanismo:** ema_heuristic usa regra fixa (EMA50 vs EMA200 + momentum).
  Eh um modelo que **nao aprende** — diferente de RF/XGB que reagem a
  mudanca de regime. Em mercado moderno com noise alto e regime shifts,
  regras fixas tendem a degradar.
- **Evidencia preliminar (2026-04-24):**
  - hit_t1 = 40.6% (pior que coinflip)
  - PnL = **-15.7 bps**, winrate 40% em 100 trades BUY/SELL
  - Pior performer entre os 4 modelos direcionais
- **Por que esta no ensemble:** historico — era util como baseline interpretavel.
  Mas se contamina o ensemble com sinal contrario ao consenso de RF/XGB,
  pode estar puxando o ensemble pro errado em momentos onde os modelos
  fortes concordam.

## Falsificadores conscientes

- **1 dia de dados nao prova nada.** Ema_heuristic pode brilhar em regimes
  trending fortes que hoje nao apareceram.
- **Pode ter funcao de "diversificacao":** mesmo errando mais, talvez erre em
  momentos diferentes dos demais — entao remover aumenta correlacao do
  ensemble e piora variance.
- **O ensemble atual ja eh media simples** — verificar se o impacto e grande
  o suficiente pra justificar mudanca.

## Plano de teste

1. **Baseline:** rodar `evaluate_filter` com ensemble atual (5 modelos) em 30d.
2. **Counterfactual:** computar ensemble sem ema_heuristic (4 modelos) na
   mesma janela.
3. **Comparar:**
   - Hit rate ensemble com vs sem
   - PnL liquido com spread
   - Maximum drawdown
   - Sharpe ratio

```python
# Pseudocodigo
df_research = load_predictions_30d()
ensemble_5 = df_research.groupby("timestamp")["pred_t1"].mean()
ensemble_4 = df_research[df_research["model"] != "ema_heuristic"].groupby("timestamp")["pred_t1"].mean()
```

## Criterio de sucesso

- PnL ensemble_4 > PnL ensemble_5 em **pelo menos 2 bps/trade**
- Sharpe nao piora (proxy de variance nao explodiu)
- Drawdown nao piora

Se passar: PR removendo ema_heuristic do ensemble (mantendo no codigo pra
casos individuais ou regime trending forte).

---

## Resultado (preencher APOS rodar)

- `filter_hash`:
- PnL ensemble com 5 modelos:
- PnL ensemble sem ema_heuristic:
- Delta:
- Sharpe delta:
- DD delta:
- Verdict:

## Conclusao / proximos passos

-

## Links

- Research base: [[../Research/2026-04-24-eval-diaria-baseline]]
- Codigo do ensemble: `src/models/ensemble.py`
