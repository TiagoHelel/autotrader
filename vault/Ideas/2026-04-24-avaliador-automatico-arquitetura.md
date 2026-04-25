---
type: idea
created: 2026-04-24
tags: [idea, avaliador-automatico, lllm, edge-discovery]
status: raw
---

# Avaliador automatico de estrategias - arquitetura proposta

## Ideia (1-2 frases)

> Pipeline diario que cruza predicoes vs real, segmenta por contexto
> (regime/sessao/confidence), aplica gates estatisticos honestos (CPCV +
> Bonferroni) e usa LLM apenas para **priorizar hipoteses para investigacao
> humana** — nao para decidir trades.

## Motivacao

- Hoje (2026-04-24) fiz a primeira eval manual ad-hoc. 15k amostras, varios
  cortes, achei pelo menos 5 hipoteses candidatas em 1 hora.
- Esse trabalho **deveria ser diario e automatico**. Senao perdemos
  edges sazonais, regressoes silenciosas e oportunidades.
- O problema central: **multiple testing**. Se eu rodo 50 cortes por dia
  durante 30 dias, vou achar dezenas de "edges" que sao apenas ruido.
  Avaliador precisa **levar a serio o controle de erro tipo I**.

## Arquitetura em 2 camadas

### Camada 1 - Deterministica (Python, no repo)

```
Trigger: cron diario, end-of-day UTC.

Inputs:
  - data/predictions/*.parquet (schema enriquecido)
  - data/raw/*.parquet (candles)
  - data/news/llm_features.parquet (contexto)
  - vault/Hypotheses/*.md (hipoteses pendentes)

Pipeline:
  1. Build research dataset (reusa src/research/conditional_analysis.build_prediction_dataset)
     Janelas: rolling 1d, 7d, 30d.
  2. Para cada hipotese ativa em vault/Hypotheses/ com status=draft:
     - Extrai filtro do frontmatter / bloco de codigo
     - Chama evaluate_filter (CPCV + purge + Bonferroni)
     - Atualiza nota com resultado (filter_hash, p-value, verdict)
  3. Para combos descobertos automaticamente (sym x model x session x conf_bin):
     - Calcula metricas
     - Marca PROMISING/STRONG candidatos
     - **Nao escreve em Hypotheses/** (so humano formula hipotese)
     - Salva em data/research/auto_eval_YYYY-MM-DD.parquet
  4. Calcula regressoes vs media 30d:
     - Modelo X caiu Y pp -> red flag
     - Confidence calibration drift
     - Sessao perdeu hit rate
  5. Custo de execucao realista:
     - Spread tipico por par
     - Slippage estimado
     - PnL liquido pra todo combo

Output:
  - vault/Research/eval-daily/YYYY-MM-DD.md (markdown automatico)
  - data/research/auto_eval_YYYY-MM-DD.parquet (dataset agregado)
  - Atualizacoes nas notas Hypothesis (preenche bloco "Resultado")
  - Slack/email opcional pra red flags
```

### Camada 2 - LLM (Claude API ou Qwen local)

```
Trigger: apos camada 1 completar.

Inputs:
  - Markdown gerado pela camada 1
  - Janela 30d de auto_eval
  - vault/Hypotheses/_index com status atual

Pipeline (chamada unica ao LLM, sem agentes):
  - System prompt: "Voce eh analista de trading quantitativo. NAO decide
    trades. Sua funcao eh ler o relatorio e priorizar 3-5 areas de
    investigacao para o humano formular hipoteses formais."
  - User prompt: relatorio + contexto macro (news high-impact do dia)
  - Estrutura de saida (JSON):
    {
      "priority_investigations": [
        {
          "title": "...",
          "rationale": "...",
          "suggested_filter": {...},  // pra humano usar como base
          "novelty_score": 0-1,        // quanto isso ja foi visto
          "risk_flags": [...]          // overfitting, sample size, etc
        }
      ],
      "regressions_to_audit": [...],
      "macro_context_relevance": "..."
    }

Output:
  - Append na nota diaria com seccao "## LLM priorization"
  - Comentarios em hipoteses existentes ("possivel correlacao com H1, ver...")
```

### Por que LLM nao decide trade

- **Verificabilidade.** Numeros da camada 1 sao replicaveis. LLM nao eh.
- **HARKing.** LLM eh otimo em narrar padroes que talvez nao existem.
  Confiabilidade estatistica vem da camada 1.
- **Custo de erro.** Erro do LLM em prioriacao = humano perde 10min lendo.
  Erro do LLM em decisao = perde dinheiro.
- **Auditabilidade.** Hipotese vira nota + filter_hash + log. LLM-decision
  nao tem trilha clara.

## Como testar (MVP)

1. **Semana 1:** rodar eval diaria manual igual fiz hoje, salvar em
   `vault/Research/eval-daily/`. Sem LLM. So pra confirmar que da pra
   automatizar.
2. **Semana 2:** extrair script `src/evaluation/daily_eval.py` que faz
   tudo da camada 1. Cron local ou Windows Task Scheduler.
3. **Semana 3:** plugar LLM. Comecar com um chamada Claude API simples
   passando o markdown, ver se output eh util.
4. **Semana 4:** ajustar prompts, criar templates, integrar com Slack.

## Custo / valor estimado

- **Esforco:** medio (40h pra MVP, 80h pra polished). Camada 1 reusa muito
  do conditional_analysis existente.
- **Upside:** alto. Multiplica capacidade de descobrir e validar edges
  sem gastar dia inteiro em SQL/pandas.
- **Risco:** baixo. Pipeline nao toma decisoes de trade. Maximo de dano:
  gerar relatorio errado que humano ignora.

## Proximo passo

- [ ] Validar arquitetura com mais 1 dia de eval manual (segunda 28/04)
- [ ] Criar issue/decisao em [[../../.project/DECISIONS]] sobre topologia
- [ ] Virar [[Hypothesis]] formal pra cada combo PROMISING descoberto
- [ ] Comecar `src/evaluation/daily_eval.py` (extrair codigo do ad-hoc de hoje)

## Links

- Research que originou: [[../Research/2026-04-24-eval-diaria-baseline]]
- Hipoteses derivadas: [[2026-04-24-confidence-gate-085]] [[2026-04-24-remover-ema-heuristic]]
- Modulo existente que reusar: `src/research/conditional_analysis.py`
