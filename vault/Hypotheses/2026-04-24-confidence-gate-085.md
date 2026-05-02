---
type: hypothesis
created: 2026-04-24
status: draft
tags: [hipotese, confidence-gate, edge-discovery]
filter_hash: 
verdict: 
filters:
  confidence_min: 0.85
---

# H1 - Confidence >= 0.85 como gate universal de qualidade

## Hipotese

> Predicoes com `confidence >= 0.85` (qualquer modelo, qualquer simbolo)
> tem `hit_t1 >= 58%` em janela 30 dias, com delta vs coinflip > 5pp e
> p-value < 0.01 apos correcao Bonferroni.

## Por que faz sentido (pre-teste)

- **Mecanismo:** confidence no signal engine eh derivada de magnitude do
  expected return + concordancia entre modelos. Alto confidence implica
  predicoes consistentes entre random_forest, xgboost e linear — logo o
  sinal tem mais chance de refletir estrutura real do mercado, nao ruido.
- **Evidencia preliminar (2026-04-24):** gradiente forte e monotono nos
  bins de confidence:
  - <0.3: 46.8% (n=1343)
  - 0.5-0.7: 45.8% (n=2430)
  - 0.7-0.85: 53.5% (n=2930)
  - **0.85+: 64.5% (n=4910)**
  Delta de **17.7pp** entre o bin mais baixo e o mais alto.
- **Diferenca para coin flip:** se sustentar, eh edge agnostico a sym/sessao —
  vira gate plug-and-play em qualquer estrategia downstream.

## Filtro proposto

```python
filters = {
    "confidence_min": 0.85,
}
```

Sem outras restricoes. Quero testar se o gate sozinho carrega edge.

## Plano

- **Dataset:** `data/research/predictions_*.parquet` cobrindo >= 30 dias
  com schema enriquecido. **Nao temos isso ainda** — schema `confidence` so
  comecou a ser gravado em 2026-04-23. Plano: aguardar 30 dias de coleta OU
  reconstruir confidence retroativamente a partir das predicoes antigas
  (recalcular dispersao entre modelos no momento da predicao).
- **Split:** `holdout_pct=0.20, method="temporal"` (ultimos 20% do dataset).
- **N esperado:** ~30k+ amostras com `confidence >= 0.85` (extrapolando hoje).
- **Criterio de sucesso:**
  - hit_t1 >= 58% (vs ~50% coinflip, vs ~46% baseline confidence baixo)
  - p-value binomial < 0.01
  - p-value Bonferroni < 0.05 (estimar quantos testes serao feitos no log)
  - PnL liquido positivo apos custo de spread (~1-2 bps por par)

## Riscos / falsificadores

- **Confidence pode ser overfit ao regime atual.** Se 30d de dados nao gerar
  o mesmo gradiente, a metrica eh ruido.
- **Spread pode comer todo o edge.** 64% hit em direcao M5 pode virar 50%
  PnL apos spread de 1.5 bps em pares menores.
- **Selection bias.** Confidence alto talvez correlacione com horarios de
  baixa volatilidade onde direcao eh mais previsivel mas movimento pequeno
  — gate filtra movimento > custo.

---

## Resultado (preencher APOS rodar)

- `filter_hash`:
- N:
- hit_t1:
- CI95:
- p-value:
- Bonferroni ajustado:
- PnL bruto (bps):
- PnL liquido apos spread:
- Verdict:

## Validacao no holdout

- Data:
- N holdout:
- hit_t1 holdout:
- Decisao:

## Conclusao / proximos passos

-

## Links

- Research base: [[../Research/2026-04-24-eval-diaria-baseline]]
- Modulo: [[../../src/research/conditional_analysis]] (mencionado em CHANGELOG.md)

## Daily eval log (auto)

- 2026-05-01: n=6110 | hit_t1=0.5352 | CI95=[0.5227, 0.5477] | verdict=PROMISING

- 2026-04-30: n=6915 | hit_t1=0.6668 | CI95=[0.6556, 0.6778] | verdict=PROMISING

- 2026-04-29: n=4670 | hit_t1=0.7096 | CI95=[0.6964, 0.7225] | verdict=PROMISING

- 2026-04-28: n=3459 | hit_t1=0.7132 | CI95=[0.6979, 0.728] | verdict=PROMISING

- 2026-04-27: n=4565 | hit_t1=0.5689 | CI95=[0.5545, 0.5832] | verdict=PROMISING

- 2026-04-24: n=3946 | hit_t1=0.6358 | CI95=[0.6207, 0.6507] | verdict=PROMISING
