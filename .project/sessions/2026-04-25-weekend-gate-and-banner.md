# 2026-04-25 — Weekend gate + Market Closed banner

## Goal

Parar de gerar/exibir sinais quando o Forex esta fechado (sex 22:00 UTC ->
dom 22:00 UTC) e impedir que predicoes de fim de semana contaminem a
estatistica de avaliacao e o contexto do agent_researcher.

## What was missing

- `src/features/session.py` so classificava janelas Sydney/Tokyo/London/NY.
  Sabado 21h UTC, por exemplo, ele flagava "Sydney abrindo" mesmo com
  mercado fechado. Por isso o Signal Board mostrava sinais de venda no
  fim de semana.
- `daily_eval.py` cruzava qualquer predicao com candles, gerando `hit_t1`
  com base em "proxima vela" inexistente.
- `agent_researcher` lia esses eval files e podia formular hipoteses em
  cima do ruido.
- API `/signals/radar` devolvia sinais cacheados/stale para o frontend.

## Solution

Defesa em camadas:

1. **`is_market_open(timestamp)` em `src/features/session.py`**
   - Fechado sex 22:00 UTC -> dom 22:00 UTC.
   - `compute_session_features` zera todas as features quando fechado;
     `session_score=0` aciona o `HOLD forcado` ja existente.
2. **`PredictionEngine.run_cycle`** skipa quando fechado, retornando
   `{"skipped": "market_closed", "symbols": {}}`. Nao gera predicao, nao
   loga signal, nao toca `signals.csv`.
3. **`daily_eval.run_for_date`** filtra `pred[pred["timestamp"].apply(is_market_open)]`
   antes de cruzar com candles.
4. **`agent_researcher.hypothesis_generator.load_daily_eval_summary`**
   aplica o mesmo filtro nos parquets que viram contexto pro LLM.
5. **`/api/predict/signals/radar`** agora retorna
   `{"market_closed": true, "signals": [], "total": 0, "breakdown": {...}}`
   quando fora do horario. Resposta vem ANTES da consulta ao cache para
   nao devolver payload stale.
6. **Frontend:**
   - Novo `command_center/frontend/src/components/common/MarketStatusBanner.jsx`
     no topo do Control Tower (visivel em todas as cores do tema).
   - `SignalBoard` mostra "MARKET CLOSED" no corpo quando o radar reporta
     `market_closed: true`.

## Tests

- 9 novos em `tests/features/test_session.py::TestIsMarketOpen` (weekday,
  sex 21:59 UTC, sex 22:00 UTC, sabado, dom 21:59 UTC, dom 22:00 UTC,
  segunda, NaT, feature zeroing).
- `tests/execution/test_engine.py::TestRunCycle::test_run_cycle_skips_when_market_closed`
  trava o contrato do skip.
- `tests/api/test_signals.py::test_radar_returns_market_closed_when_forex_shut`
  cobre o short-circuit do endpoint.
- Fixture `_force_market_open` adicionada em
  `tests/api/test_signals.py`, `tests/api/test_data_integrity.py` e
  `tests/api/test_predictions_comprehensive.py::TestRadarSignals` para que
  testes de logica do radar nao dependam do dia da semana real.
- Vitest: 245 testes verdes (nao tive que mexer porque o
  `MarketStatusBanner` so aparece quando `data?.market_closed === true`,
  estado nao ativado pelos handlers MSW atuais).

## What I learned

- Janela Forex padrao: fecha sex 22:00 UTC, abre dom 22:00 UTC. Algumas
  corretoras usam 21:00 em verao do norte; assumimos a janela conservadora
  (mais predicoes filtradas, melhor para honestidade estatistica).
- `_force_market_open` e necessario em todo modulo que exercita
  `/signals/radar` ou `daily_eval` sem mockar o gate. Senao a suite vira
  flaky por dia da semana.

## Next session should

- Adicionar `is_market_open()` na rota `/api/predict/predictions/latest`
  (hoje so o radar foi blindado).
- Estender o banner pra outras paginas (Symbols, Backtest) se virarem
  superficie de exposicao de sinal.
- Quando o bot real existir (decisao [017]), `is_market_open` vira hard
  gate antes de qualquer ordem; broker rejeita por sua vez (defesa em
  profundidade).
