# Vault - AutoTrader Research & Journal

Vault Obsidian versionado junto com o codigo. Cerebro estendido do trader/dev:
hipoteses, estudos, resultados de backtest e testes em conta demo, post-mortems
de modelo, e ideias de melhorias.

> **Diferente de `.project/`:** aquela pasta documenta o **codigo** (otimizada
> para AI assistant carregar contexto). Esta aqui documenta o **raciocinio**.

---

## Estrutura

| Pasta | Para que serve |
|---|---|
| `00-Inbox/` | Captura rapida. Tudo que voce escreve sem saber onde categorizar entra aqui. Revise semanalmente e reclassifique. |
| `Hypotheses/` | Hipoteses **antes** de virar teste. Regra de ouro do `conditional_analysis`: hipotese antes do teste protege contra HARKing. |
| `Research/` | Estudos, leituras, papers (Marcos Lopez de Prado, threads), notas tecnicas que nao sao hipotese ainda. |
| `Backtests/` | Apenas resultados consolidados — uma nota por backtest interessante. PnL, Sharpe, DD, regime, e racional do que voce aprendeu. Linka pra hipotese de origem. |
| `Demo-Trading/` | Sessoes em conta demo. Trades executados, observacoes psicologicas, slippage real, comportamento do broker. |
| `Postmortems/` | Quando algo regrediu (modelo, estrategia, sistema). O que aconteceu, por que, o que mudar. |
| `Ideas/` | Backlog de ideias soltas. Vira hipotese ou research quando amadurece. |
| `Templates/` | Templates do Obsidian. Configure em Settings > Templates > Template folder location = `Templates`. |
| `AgentResearch/` | Notas geradas pelo agente autonomo (`src/agent_researcher`): hipoteses, logs e learnings. |

---

## Fluxo recomendado

```
Ideia solta
  -> Ideas/  (rascunho)
  -> Research/  (estudou, virou conhecimento)
  -> Hypotheses/  (formulou hipotese testavel ANTES de rodar)
  -> conditional_analysis evaluate_filter()
  -> Backtests/  (se PROMISING/STRONG)
  -> Demo-Trading/  (validacao real)
  -> producao
```

Se algo deu errado em qualquer etapa: `Postmortems/`.

---

## Regras de higiene

1. **Hipotese ANTES do teste.** Escreva a hipotese, salve com data, **depois** rode o filtro. HARKing (escrever hipotese depois de ver resultado) anula tudo.
2. **Linka.** Backtest aponta pra hipotese, hipotese aponta pra research. Use `[[wikilinks]]`. O graph view do Obsidian fica util quando ha conexoes.
3. **Tags consistentes.** Sugestao: `#hipotese`, `#regime/bull`, `#session/london-ny`, `#symbol/XAUUSD`, `#status/promising`, `#status/rejected`.
4. **Nada de valores reais da conta no git.** Se quiser journal emocional ou tracking de PnL real, use vault separado fora do repo. Aqui e research.

---

## Setup do Obsidian

1. Abrir Obsidian -> Open folder as vault -> selecionar esta pasta (`vault/`).
2. Settings > Templates > Template folder = `Templates`. Hotkey: `Ctrl+T` para inserir template.
3. Plugins recomendados (community):
   - **Templater** (templates dinamicos com variaveis)
   - **Dataview** (queries em notas, ex: tabela de hipoteses por status)
   - **Tag Wrangler** (gestao de tags)
4. Theme: a gosto. Recomendado um monoespacado pra blocos de codigo se voce vai colar JSON de filtro.

---

## Conectando com o codigo

Quando uma hipotese vira teste no `conditional_analysis`, a nota deve registrar:
- O dict de filtros exato (mesmo formato que vai pro `evaluate_filter`)
- O `filter_hash` retornado (anota depois de rodar)
- Caminho do dataset usado (`data/research/predictions_*.parquet`)
- Verdict resultante (REJECTED_N / UNDERPOWERED / WEAK / PROMISING / STRONG)

Assim a nota Obsidian e o `filter_log.parquet` ficam linkados — graph teorico + log empirico.

## Agent Researcher

O agente autonomo de pesquisa escreve apenas em `vault/AgentResearch/**`.
Ele pode ler `vault/Hypotheses/` e os learnings anteriores para melhorar novas
hipoteses, mas nao altera notas fora da area dele em runtime.
