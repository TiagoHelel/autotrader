---
type: index
tags: [index]
---

# Demo Trading Index

Sessoes em conta demo. Foco: comparar realidade (slippage, spread real, latencia)
com o backtest e detectar gap de execucao antes de levar pra real.

## Convencao de nome

`YYYY-MM-DD-{broker}-{estrategia}.md`

## Lista

```dataview
TABLE
  broker,
  strategy,
  created
FROM "Demo-Trading"
WHERE type = "demo-session"
SORT created DESC
```

## Regras

- Sempre linkar pro backtest e/ou hipotese de origem.
- Anote slippage e spread real — esses numeros vao calibrar o backtest engine.
- Se o gap demo vs backtest for grande, abre [[Postmortem]].
