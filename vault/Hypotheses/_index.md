---
type: index
tags: [index]
---

# Hypotheses Index

Lista de todas as hipoteses, status e verdict. Mantenha atualizado.

## Convencao de nome de arquivo

`YYYY-MM-DD-{simbolo}-{ideia-curta}.md`

Ex: `2026-04-23-XAUUSD-london-ny-confidence80.md`

## Status possiveis

- `draft` — escrita, ainda nao testada
- `tested` — rodou no research dataset
- `validated` — passou no holdout
- `rejected` — falhou em algum gate
- `production` — virou regra do signal engine

## Lista (manual ou via Dataview)

```dataview
TABLE
  status,
  verdict,
  filter_hash
FROM "Hypotheses"
WHERE type = "hypothesis"
SORT created DESC
```

> Se nao tem o plugin Dataview instalado, esta tabela aparece como bloco de
> codigo. Instale via Settings > Community plugins > Browse > "Dataview".
