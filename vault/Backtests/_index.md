---
type: index
tags: [index]
---

# Backtests Index

Resultados consolidados. Uma nota por backtest interessante (nao todos — so os
que ensinam algo ou viram candidato a demo).

## Convencao de nome

`YYYY-MM-DD-{simbolo}-{modelo}-{filtro-curto}.md`

## Lista

```dataview
TABLE
  symbol,
  model,
  status,
  period
FROM "Backtests"
WHERE type = "backtest"
SORT created DESC
```
