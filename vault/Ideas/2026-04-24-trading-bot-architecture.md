---
type: idea
created: 2026-04-24
tags: [idea, trading-bot, execution, architecture]
status: decided
related_decision: ".project/DECISIONS.md#017"
---

# Trading bot - arquitetura (repo separado)

## Decisao registrada

Ver `.project/DECISIONS.md` decisao **[017]**: bot de execucao e research sao
processos/repos separados, com faseamento 0-3 obrigatorio antes de dinheiro real.

Esta nota documenta a arquitetura do bot quando vier — **mas nao construir agora**.

## Hard gates obrigatorios (defesa em profundidade)

Quando o bot existir, **antes de qualquer ordem ser enviada** ele precisa
passar por TODOS os gates abaixo, em sequencia. Falha em qualquer um =
no-op silencioso, log de auditoria, sem retry agressivo.

1. **`is_market_open(now_utc)`** (definido em `src/features/session.py`).
   Forex fechado sex 22:00 UTC -> dom 22:00 UTC. Decisao [021]. Sem este
   gate, sabado o bot tentaria abrir posicao em mercado fechado, broker
   rejeitaria, mas sequer deve chegar la.
2. **`session_score >= threshold`** do par (`SESSION_WEIGHTS`). Score 0
   forca HOLD; threshold adaptativo ja existente em `decision/signal.py`.
3. **Hipotese ativa em estrategia validada** (state.json do agent_researcher
   ou hipotese formal `validated` em `vault/Hypotheses/`). Sem edge
   confirmado em holdout, nao opera.
4. **Drift monitor verde** (`drift_monitor.py` reporta `healthy` para a
   estrategia). Se `degrading` ou `dead`, pausa ordens daquela estrategia.
5. **Risk caps OK** (max drawdown intra-dia, posicoes simultaneas, exposicao
   total).
6. **Broker check** (saldo, margem, sessao do broker ativa). Redundante com
   (1) mas e o gate fisico.

Resumo: o bot **nao confia em uma camada so**. Cada gate cobre o anterior.

## Quando comecar a construir

Gate explicito: H1 (confidence-gate 0.85) ou alguma hipotese equivalente
**precisa estar `validated` em holdout 30d** via `conditional_analysis.evaluate_filter`
antes de qualquer linha de codigo de execucao.

Status atual: H1 marcada como `draft`. Daily eval rodando. Esperar 14d minimo.

## Estrutura proposta

```
trading-bot/                          (repo SEPARADO, nao dentro do autotrader)
   src/
      signal_consumer.py              # le sinais do autotrader
      risk_gate.py                    # aplica limites antes de enviar ordem
      order_router.py                 # MT5 place/modify/close + retry
      position_manager.py             # estado de posicoes, reconciliation
      state_machine.py                # signal -> pending -> sent -> filled
      kill_switch.py                  # arquivo/comando que para tudo
      audit_log.py                    # append-only, parquet diario
      health.py                       # heartbeat + watchdog
   config/
      limits.yaml                     # max_dd_daily, max_open_positions
      pairs_allowlist.yaml            # quais pares pode operar
   state/                             # gitignored
      positions.parquet
      orders.parquet
      heartbeat.txt
   tests/
      test_risk_gate.py               # CADA regra tem teste
      test_state_machine.py
      test_idempotency.py
   README.md
```

**LOC objetivo:** < 1500. Cada linha auditavel.

## Componentes criticos

### Risk gate

Checks ANTES de qualquer ordem (todos hard, nao soft):

- [ ] Total exposure <= max_exposure_usd
- [ ] Open positions count <= max_open
- [ ] Daily DD < max_daily_dd_pct (circuit breaker do dia)
- [ ] Loss streak < max_loss_streak (cooldown)
- [ ] Correlation guard: nao abrir EURUSD long se ja tem GBPUSD long
- [ ] News blackout: nao operar +/- 5min de high-impact news
- [ ] Symbol allowlist (so pares aprovados)
- [ ] Spread atual <= 1.5x spread medio (recusa em mercado anormal)
- [ ] Confidence >= threshold da estrategia ativa

### Order state machine

```
signal_received
   v
risk_check
   v
   PASS -> pending_submit
   FAIL -> rejected_by_risk (logado, nao envia)
   v
sent_to_broker (com client_order_id unico)
   v
   ack_received -> tracking
   timeout -> retry (max 3x) -> rejected_timeout
   v
fill_received -> open_position
partial_fill -> partial_open + cancel rest
reject_received -> rejected_by_broker
   v
exit_signal_or_stop_or_tp_or_kill
   v
close_sent -> closed -> archived
```

Toda transicao logada com timestamp + reason.

### Kill switch

3 mecanismos independentes:
1. **File watch:** existe `state/KILL` -> para imediatamente (fecha posicoes mercado)
2. **Heartbeat:** se bot nao escreve `heartbeat.txt` em 60s -> watchdog externo mata
3. **CLI command:** `python -m kill` -> envia close-all + para

### Reconciliation

A cada 30s: pega posicoes do broker via MT5 API, compara com `state/positions.parquet`.
Discrepancia -> alarme + parada. **Nunca confiar so no estado interno.**

### Idempotencia

Cada ordem tem `client_order_id = sha256(timestamp + symbol + signal_id)`. Reenvio
por timeout nao duplica trade. Broker valida unicidade.

## Comunicacao com AutoTrader (research)

3 opcoes, do mais simples ao mais robusto:

1. **File-drop (recomendado para MVP):**
   - AutoTrader escreve `data/signals_pending/{ts}_{symbol}.json`
   - Bot poll a cada 5s, atomicamente move para `signals_consumed/`
   - Vantagem: zero infra extra, audit trail trivial

2. **HTTP polling:**
   - Bot faz `GET /api/predict/signals/radar` cada 30s
   - Filtra confidence >= threshold
   - Vantagem: usa API que ja existe

3. **Message queue (Redis pub/sub):**
   - Over-engineering para solo trader
   - So se vier escala / multiplos consumers

## Faseamento detalhado

### Fase 0 (atual, semanas 1-2)

- Daily eval rodando todo dia
- Acumular >= 14 dias de dados com schema enriquecido
- Hipoteses formuladas em `vault/Hypotheses/`
- **Sem bot algum.**

Saida: `vault/Research/eval-daily/*.md` mostra tendencia, H1 ou alguma vira `tested`.

### Fase 1 (semanas 3-4): paper-trading

- Bot le sinais
- **NAO envia ordem ao broker**
- Simula execucao: aplica spread real, slippage estimado, registra trade simulado
- Compara com backtest puro (sem custos)
- Output: `data/paper_trades/{date}.parquet`

Gate pra Fase 2: PnL paper bate com backtest dentro de +/- 20%, sem catastrofe operacional.

### Fase 2 (semanas 5-8): demo account

- Mesmo bot, agora envia ordem real ao broker em **conta demo**
- Aparecem: slippage real, requote, off-quote, latencia, fill partial
- Bot precisa lidar com tudo isso sem crashar
- Risk gate em modo paranoid (limites apertados)

Gate pra Fase 3: 30 dias sem incidente operacional, PnL demo bate com paper +/- 30%.

### Fase 3 (semanas 9+): conta real, mini size

- $100 risk/trade maximo
- 30 dias rodando
- Daily eval continua monitorando
- Se PnL real bate com demo +/- 30%, sobe size 50% na proxima semana
- Se diverge muito: para, post-mortem

## NAO construir antes do tempo

Ainda nao existe edge confirmado. Construir bot agora seria:

1. Engenharia de qualidade investida em algo que talvez nao tenha PnL positivo
2. Risco psicologico de "ja construi, agora preciso usar"
3. Distracao do trabalho mais importante: validar hipoteses

## Quando os requisitos mudarem

Atualizar esta nota e a decisao [017]. Se a arquitetura mudar antes de implementar,
re-discutir tradeoffs.

## Links

- Decisao: [[../../.project/DECISIONS]] entry [017]
- Hipotese-gate: [[../Hypotheses/2026-04-24-confidence-gate-085]]
- Avaliador (camada 1): [[../../src/evaluation/daily_eval]]
- Research relacionada: [[../Research/2026-04-24-eval-diaria-baseline]]
