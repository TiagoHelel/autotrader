---
type: research
created: 2026-04-24
source: data/research/eval_today_2026-04-24.parquet
tags: [research, baseline, eval-diaria, edge-discovery]
---

# Eval diaria - 24/abril/2026 (baseline pre-avaliador automatico)

## Contexto

Primeira avaliacao end-to-end pred vs real apos o restart com schema enriquecido.
Objetivo: criar baseline numerico das predicoes de hoje pra alimentar a construcao
do avaliador automatico de estrategias.

**Janela:** 2026-04-24 00:00 UTC -> 23:55 UTC (24h, mercado aberto sex inteira).
**Total amostras:** 15.245 predicoes (todas as 5 modelos x 11 simbolos x ~282 ciclos M5)
com candle real disponivel em t+1, t+2, t+3 (5/10/15 min a frente).

## Metodo

```
para cada predicao:
    target_time = ceil(timestamp + h_min, "5min")
    actual = close do candle M5 fechado mais proximo a target_time
    hit = sign(pred - current_price) == sign(actual - current_price)
```

Dataset salvo em `data/research/eval_today_2026-04-24.parquet` (todas as colunas
de contexto preservadas: `regime_trend`, `regime_vol`, `regime_range`, `session`,
`session_score`, `signal`, `confidence`, `model_version`, `features_hash`).

## Resultados

### Hit rate global por modelo (t+1)

| Modelo | Hit rate | n |
|---|---:|---:|
| random_forest | **65.4%** | 3032 |
| xgboost | 60.2% | 3032 |
| linear_regression | 54.9% | 3032 |
| ema_heuristic | 40.6% | 3032 |
| naive | 0.0% (degenerado) | 3032 |

**Observacao naive:** naive prediz `current_price` -> `sign(pred - current_price) = 0`
sempre, e excluimos `actual_movement = 0` do denominador, entao 0% e o esperado. Naive
nao e modelo direcional, e baseline de "no-information".

### Hit rate por horizonte

Random Forest sobe com o horizonte (t+1 65% -> t+3 70%). Provavelmente artefato:
em horizonte mais longo, o componente "trend" do dia ganha peso vs ruido M5.

### Por sessao (todos modelos, t+1)

| Sessao | Hit | n |
|---|---:|---:|
| tokyo,london (overlap) | 51.8% | 660 |
| tokyo | 50.8% | 650 |
| sydney | 47.0% | 1090 |
| sydney,tokyo | 46.8% | 4435 |
| london | 43.0% | 2585 |
| new_york | 41.6% | 3175 |
| london,new_york | 39.6% | 2565 |

**Contraintuitivo:** London-NY overlap, normalmente a sessao mais liquida e
considerada "boa pra direcao", saiu **pior** que sessoes asiaticas hoje. Tres
hipoteses concorrentes:
1. Hoje teve algum evento NY que pegou os modelos no contrape (sexta = NFP nao,
   mas pode ter tido data point).
2. Modelos foram treinados em janela dominada por sessao asiatica.
3. **Apenas ruido de 1 dia.**

### Por confidence bin (t+1)

| Confidence | Hit | n |
|---|---:|---:|
| <0.3 | 46.8% | 1343 |
| 0.3-0.5 | 44.5% | 515 |
| 0.5-0.7 | 45.8% | 2430 |
| 0.7-0.85 | 53.5% | 2930 |
| **0.85+** | **64.5%** | 4910 |

**Forte sinal de calibragem:** confidence e monotonicamente correlacionado com
acerto nos bins altos. Bin <0.3 ainda > 0.45 — esperado pra coin flip ajustado.
**Threshold 0.85 separa 64.5% vs 47% (delta ~17pp)** — esse e o achado mais
robusto do dia.

### Por signal engine

| Signal | Hit | n |
|---|---:|---:|
| BUY | 55.4% | 1012 |
| SELL | **66.9%** | 1130 |
| HOLD | 41.4% | 13018 |

Signal SELL > BUY hoje. **Suspeito**: dia bear-leve (regime_trend=bear pegou 6915
das 15160 amostras). Modelos provavelmente capturaram tendencia geral.

### Por regime

- `regime_trend`: bear 46.5% > bull 42.3% (tras reforca: dia bear-favoravel)
- `regime_vol`: low 45.3% > medium 44.3% > high 42.5% (modelos sofrem em vol alta)
- `regime_range`: trending 44.9% > ranging 41.1% (consistente)

### PnL real (apenas BUY/SELL, sem custo de spread)

| Modelo | n | PnL medio (bps) | Winrate |
|---|---:|---:|---:|
| random_forest | 493 | **+6.14** | 79.7% |
| xgboost | 874 | +1.04 | 57.6% |
| linear_regression | 675 | -0.89 | 56.3% |
| ema_heuristic | 100 | -15.71 | 40.0% |

**ema_heuristic tem PnL negativo + winrate < 50%** — vale considerar remover do
ensemble ou auditar. Ele esta atrapalhando.

### Top combos (symbol + model + session, n >= 20)

| Combo | Hit | n |
|---|---:|---:|
| XAUUSD + RF + london | 83.3% (PnL +25.4 bps) | 36 |
| GBPUSD + xgb + new_york | **100%** (PnL +10.1 bps) | 58 |
| USDCAD + xgb + new_york | 100% (PnL +9.4 bps) | 33 |
| GBPUSD + RF + new_york | 100% (PnL +9.6 bps) | 46 |
| AUDUSD + RF + sydney,tokyo | 88.7% (PnL +9.0 bps) | 62 |

## Sinais de alerta (NAO virar trade ainda)

1. **N=1 dia.** Tudo acima e **um unico ponto amostral**. Hit rates de 100% em
   n=58 sao quase certamente overfit ao trend do dia, nao edge real.

2. **Sem custo de spread/slippage.** PnL bps acima e **bruto**. Spread tipico
   M5 GBPUSD ~1-2 pips = ~1-2 bps. Aplicar custo pode zerar ganhos pequenos.

3. **Modelos retreinam a cada 50 ciclos.** Random Forest e XGBoost foram
   treinados com janela recente — se o regime de hoje e parecido com o de
   treino, hit alto e esperado e nao generaliza.

4. **Sessao London/NY pior que asiatica e contraintuitivo.** Pode estar
   refletindo que o treino foi dominado por dados de sessao asiatica e os
   modelos fitaram aquele padrao.

5. **Possivel autocorrelacao.** 282 ciclos M5 sequenciais nao sao independentes
   — overlapping prediction windows criam correlacao serial nas metricas. CI95
   normal subestima erro.

## Hipoteses derivadas (candidatas a virar [[Hypothesis]])

Cada uma destas merece nota propria em `Hypotheses/` ANTES de virar
`evaluate_filter` no `conditional_analysis`:

- **H1:** `confidence >= 0.85` em qualquer modelo/simbolo gera hit_t1 >= 60%
  (delta vs coinflip > 5pp) **em janela 30+ dias**.
- **H2:** `random_forest + new_york + GBPUSD/USDCAD/AUDUSD` (USD pairs em horario
  americano) tem winrate > 65% em janela 30+ dias.
- **H3:** Filtrar `signal=HOLD` quando `confidence < 0.5` reduz drag (HOLD com
  baixa confidence tem hit 41% — abaixo de coin flip por causa do filtro de
  baixa atividade).
- **H4:** `ema_heuristic` deveria ser removido do ensemble (PnL negativo + WR < 50%
  hoje — auditar 30 dias antes de remover).
- **H5:** XAUUSD + random_forest tem comportamento diferenciado vs FX puros
  (ouro responde a outros drivers — confirmar com analise especifica).

## Acoes para o avaliador automatico (proximo passo)

O avaliador precisa fazer essas perguntas todo dia, nao apenas hoje:

1. **Camada 1 (deterministica):**
   - Rodar este mesmo cruzamento pred-vs-real em janela rolante (1d, 7d, 30d)
   - Aplicar **CPCV com purge+embargo** pra cada combo (sym+model+session+conf_bin)
   - Filtrar combos com Bonferroni-corrected p < 0.01
   - Aplicar custo de spread realistico

2. **Camada 2 (LLM):**
   - Receber relatorio da camada 1 + contexto macro (news do dia, regime change)
   - Gerar hipoteses tipo "edge em XAUUSD-RF-london merece investigacao mais
     profunda — proximos 7 dias com news USD high impact"
   - **NAO decide trade** — so prioriza investigacoes pra eu (humano) escrever
     a hipotese formal em `Hypotheses/`.

3. **Output diario:**
   - Markdown automatico em `vault/Research/eval-daily/YYYY-MM-DD.md` com
     numeros + alertas de regressao (modelo X caiu 10pp vs media 30d -> red flag)
   - Slack/email opcional pros casos de promocao a candidato

## Arquivos relacionados

- Dataset: `data/research/eval_today_2026-04-24.parquet`
- Schema enriquecido (model_version, confidence, regime, session): ver
  [[../../.project/CHANGELOG.md]] entrada 2026-04-23
- Codigo de match pred-vs-real: ad-hoc neste eval — extrair pra
  `src/evaluation/daily_eval.py` quando virar pipeline

## Links

- Hipoteses derivadas: [[../Hypotheses/_index]] (criar uma nota por H1-H5)
- Decisao sobre estrutura do avaliador: [[../../.project/DECISIONS]] (a registrar)

## Verdict do dia

**Baseline OK, sem nenhum edge confirmado.** Os 100% winrate em combos pequenos
sao artefato de 1 dia. O unico achado generalizavel-em-tese e a calibragem da
**confidence (gradiente claro <0.3 -> 0.85+ de 47% -> 64%)**, e mesmo esse precisa
de janela maior pra confirmar.

Proximo passo concreto: rodar este mesmo eval em janela 7d e 30d quando tiver
dados acumulados (estamos com schema enriquecido apenas a partir de hoje — antes
falta `confidence`, `session`, etc).
