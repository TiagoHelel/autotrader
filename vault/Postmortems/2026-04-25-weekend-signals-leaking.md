---
date: 2026-04-25
severity: medium
area: features/session, evaluation/daily_eval, api/signals, frontend/SignalBoard
status: resolved
related_decisions: [021, 017]
---

# Weekend Signals Leaking — Sat 2026-04-25

## What happened

Sabado 2026-04-25 ~21:30 UTC. Usuario notou no Signal Board sinais de venda
sendo mostrados em multiplos pares enquanto o Forex estava fechado. Tres
sintomas:

1. UI exibindo sinais staleness em mercado fechado.
2. `data/predictions/*.parquet` ganhando linhas com `timestamp` em fim de
   semana (engine continuava rodando o ciclo).
3. `data/research/eval_*.parquet` (saida do `daily_eval`) iria, na proxima
   execucao, cruzar essas predicoes com "proxima vela" inexistente, gerando
   `hit_t1` ruidoso na estatistica que decide se H1 vai virar candidata a
   holdout.

## Root cause

`src/features/session.py` so classificava as janelas Sydney/Tokyo/London/NY
em UTC; nao tinha consciencia de fim de semana. Sabado 21h UTC, por exemplo,
ele flagava "Sydney abrindo" mesmo com mercado fechado, e o `session_score`
ficava maior que zero — o que destravava o threshold adaptativo (que so
forca HOLD em score < 0.3).

Bot real ainda nao existe (decisao [017]), entao nada virou ordem. Mas
contaminava research e exposicao na UI, ambos importantes para nao
auto-enganar.

## Fix

Defesa em camadas (decisao [021]):

1. `is_market_open(timestamp)` em `session.py` (sex 22:00 UTC -> dom 22:00 UTC).
   `compute_session_features` zera quando fechado.
2. `PredictionEngine.run_cycle` skipa quando fechado.
3. `daily_eval.run_for_date` filtra rows fora do mercado.
4. `agent_researcher.hypothesis_generator` aplica mesmo filtro no contexto LLM.
5. `/api/predict/signals/radar` retorna `market_closed: true` (curto-circuito
   antes do cache).
6. UI: `MarketStatusBanner` no Control Tower + estado "MARKET CLOSED" no
   `SignalBoard`.

## What I learned

- Gate de horario e responsabilidade da camada de features, nao so do bot
  (que ainda nao existe). Sem o gate na origem, todas as camadas downstream
  se contaminam.
- Quando o bot real existir, ainda assim vai ter o gate como hard stop antes
  de qualquer ordem (decisao [017] / [021]) — defesa em profundidade.
- Janela Forex padrao: fecha sex 22:00 UTC, reabre dom 22:00 UTC. Algumas
  corretoras reabrem dom 21:00 UTC no verao do hemisferio norte; a janela
  conservadora foi escolhida.

## Tests added

- `tests/features/test_session.py::TestIsMarketOpen` — 9 cenarios (weekday,
  borders sex 21:59/22:00 UTC, sabado, dom 21:59/22:00 UTC, segunda, NaT,
  feature zeroing).
- `tests/execution/test_engine.py::TestRunCycle::test_run_cycle_skips_when_market_closed`.
- `tests/api/test_signals.py::test_radar_returns_market_closed_when_forex_shut`.
- Fixture `_force_market_open` em arquivos de teste do radar para evitar
  flakiness por dia da semana.

## Open follow-ups

- `/api/predict/predictions/latest` ainda nao tem o gate. Caso seja usado
  em alguma pagina alem do Control Tower (Symbols, Backtest), mesma
  blindagem deve ser aplicada.
- Quando o agente OpenCode rodar por scheduler 03:00 UTC, vai ler eval files
  ja filtrados — confirmar que o filter_log historico nao tem ruido pre-fix.
