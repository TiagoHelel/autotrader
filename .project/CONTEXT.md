# Project Context

> **This is the most important file for AI assistants. Keep it current.**
> Update this at the start or end of every session.

_Last updated: 2026-04-26 (mt5_api pull bridge — passo 1 do desacoplamento)_

---

## Current Phase

**Fase 0 do faseamento bot/research** (decisao [017]): acumulando dados com schema
enriquecido, rodando avaliador batch diario, formulando hipoteses formais em
`vault/Hypotheses/`. Bot de execucao **nao deve ser construido** ate H1 (ou
equivalente) validar em holdout 30d.

## What's happening right now

- **MT5 HTTP pull bridge (2026-04-26) — desacoplamento completo (read-only):**
  - Servidor `mt5_api/` (FastAPI) expondo `MT5Connection` via pull HTTP
    (porta default 8002). Endpoints: `/health`, `/account`, `/terminal`,
    `/symbols`, `/symbols/{s}`, `/symbols/{s}/tick`, `/candles/{s}`
    (count ou date_from/date_to). Lifespan + `threading.Lock` (lib MT5
    nao eh thread-safe). Auth opcional `MT5_API_TOKEN`.
  - Cliente `src/mt5/remote_client.py:MT5RemoteClient` com a mesma
    interface do `MT5Connection`. Usa `httpx.Client` com base_url +
    Bearer; `/health` validado no `connect()`.
  - Factory `src/mt5/__init__.py:get_mt5_connection()` escolhe local
    ou remote por `settings.mt5.backend` (env `MT5_BACKEND`).
  - `src/execution/loop.py` agora usa a factory. Default `local`
    mantem comportamento identico ao anterior.
  - **Validado E2E** com API real em `localhost:8002`: account, symbols,
    candles e tick retornam dados corretos do terminal. `tests/mt5/`
    25/25 verde.
  - Para portar pra Linux: setar no `.env` `MT5_BACKEND=remote` +
    `MT5_API_URL=http://<ip-windows>:8002` + token opcional.
  - **Sem execucao de ordens** ainda (read-only). Quando vier, sera
    `POST /order` com `client_id` para idempotencia.
- **Weekend gate + UI banner (2026-04-25):**
  - `src/features/session.py` ganhou `is_market_open(timestamp)`. Forex fecha
    sex 22:00 UTC e reabre dom 22:00 UTC. `compute_session_features` zera todas
    as features quando o mercado esta fechado (forca HOLD via `session_score=0`).
  - `src/execution/engine.run_cycle` skipa o ciclo retornando
    `{"skipped": "market_closed"}` quando esta fora do horario; sem predicao,
    sem signal, sem log.
  - `src/evaluation/daily_eval.run_for_date` filtra predicoes feitas com mercado
    fechado antes de cruzar com candles. Evita `hit_t1` ruidoso na estatistica
    que decide se H1 vai pra holdout.
  - `src/agent_researcher/hypothesis_generator.load_daily_eval_summary` aplica
    o mesmo filtro ao alimentar contexto pro LLM.
  - **API `/api/predict/signals/radar`** agora retorna
    `{"market_closed": true, "signals": [], "total": 0, ...}` quando fechado,
    em vez de devolver sinais stale.
  - **Frontend:** novo `MarketStatusBanner` no topo do Control Tower; SignalBoard
    mostra "MARKET CLOSED" no corpo. Cobertura via Vitest (245 verde).
  - Suite Python: **522 passed**. 12 testes novos cobrindo o gate.
  - Bot real ainda nao existe (decisao [017]); quando vier, tera mais um gate
    `is_market_open` antes de qualquer ordem (defesa em profundidade).
- **Agent researcher: artefatos runtime ignorados em git, snapshot diario em S3 (2026-04-25):**
  - `.gitignore` agora cobre `src/agent_researcher/state.json`,
    `src/agent_researcher/strategies/{active,rejected}/*.json` e
    `src/agent_researcher/tmp/`. Fonte de verdade fica no S3.
  - `scripts/upload_to_s3.py` ganhou `upload_agent_researcher`:
    `agent_researcher/state/state-YYYY-MM-DD.json` (snapshot diario, sem
    overwrite — preserva tracking de holdout), `agent_researcher/strategies/{active,rejected}/<id>.json`,
    e `agent_researcher/prompts/date=YYYY-MM-DD/<arquivo>` (audit trail completo).
  - Tambem removemos `command_center/backend/autotrader_cc.db` do git
    (regenerado pelo `init_db()` via `CREATE TABLE IF NOT EXISTS`).
- **Agent researcher autonomo — integracao OpenCode end-to-end (2026-04-25):**
  - Modulo `src/agent_researcher/` agora roda end-to-end no Windows contra
    LM Studio + qwen3.5:9b hospedado em Mac mini (192.168.100.191:3032 via
    OpenAI-compat). Primeira hipotese real gerada e avaliada (verdict
    REJECTED_N porque dataset ainda nao tem amostras suficientes).
  - **Agente OpenCode customizado** `autotrader-researcher` registrado em
    `~/.config/opencode/opencode.jsonc` com tools so de leitura e web
    (`read`, `list`, `glob`, `grep`, `webfetch`, `websearch`); `write`,
    `edit`, `patch`, `bash` desligados. Mantemos a capacidade de pesquisar
    web/vault sem risco do agente editar codigo do projeto.
  - **Bypass do shim Windows:** `OpenCodeClient` chama `node` direto com
    `node_modules/opencode-ai/bin/opencode` em vez do `.CMD` shim, porque o
    shim mutila `--model qwen/qwen/qwen3.5:9b` (chega no yargs como `qwen/`).
    Prompt entregue via stdin (foge do limite de 8 KB de linha de comando).
  - **`timeout_seconds` agora `None`** porque qwen 9B no Mac mini pode levar
    varios minutos por chamada. Sem subprocess timeout.
  - **Fronteira de escrita preservada:** orchestrator Python continua sendo o
    unico caminho de escrita no vault/strategies. O agente OpenCode nao recebe
    nenhum tool de Write/Edit/Bash, entao nao pode burlar mesmo querendo.
  - Bumps de contexto (vault 20->50 arquivos x 4k->8k chars, daily_eval 5->15,
    filter_log 50->200, breakdowns extra por symbol/trend/volatility/hour) —
    prompt atual ~2.6k tokens, espaço sobrando na janela de 100k.
  - Wrapper agendavel: `scripts/run_agent_researcher.py`. Scheduler:
    upload 01:00 UTC, daily_eval 02:00 UTC, agent 03:00 UTC.
  - Suite completa pos-mudancas: **511 passed**.
- **Lint/PEP 8 cleanup + overfit warning operacional (2026-04-25):**
  - `pyproject.toml` agora tem **`[tool.ruff]`** com `line-length = 88` e
    `per-file-ignores` pontual para `command_center/backend/main.py` (`E402`,
    necessario porque o arquivo injeta `PROJECT_ROOT` no `sys.path` antes dos imports).
  - Cleanup de lint concluido: imports mortos removidos, `src/api/predictions.py`
    reorganizado, `tests/execution/test_engine.py` sem `;` inline, `tests/execution/test_loop.py`
    com imports no topo.
  - **`src/execution/engine.py` agora transforma overfit gap em sinal operacional:**
    `_run_cpcv_validation()` calcula `avg_overfit_gap` por modelo a partir de
    `fold_details`, anexa `overfit_warning` ao resultado da CPCV e registra
    `log_decision("overfit_warning_<model>")` quando a media passa de `OVERFIT_THRESHOLD`.
    Nao bloqueia treino nem selecao ainda; apenas observabilidade/telemetria.
  - Validacao feita: `ruff check .` OK e subset de testes OK
    (`tests/execution/test_engine.py`, `test_loop.py`, `tests/evaluation/test_overfitting.py`,
    `test_cpcv.py`) â€” **78 passed**.
- **Avaliador batch diario implementado (2026-04-24):** `src/evaluation/daily_eval.py`
  cruza pred vs real, segmenta por contexto, detecta drift, auto-executa hipoteses
  com `filters` no frontmatter, gera relatorio em `vault/Research/eval-daily/{date}.md`.
  Idempotente. Rodar diariamente (`python -m src.evaluation.daily_eval`).
  - **Primeira execucao (2026-04-24):** 12.550 predicoes; H1 (confidence>=0.85) deu
    PROMISING com hit_t1=63.6%, CI95 [62.1%, 65.1%]. **NAO eh edge confirmado** (1 dia).
- **Vault Obsidian (`vault/`)** versionada no repo: research, hypotheses, backtests,
  demo trading, postmortems, ideas + 6 templates. Co-locada com codigo, alimenta
  contexto da AI assistant.
- **2 hipoteses ativas em `vault/Hypotheses/`:** H1 confidence-gate (auto-rodando),
  H4 remover ema_heuristic (manual ainda).
- **Decisao [017] - Bot/research separados:** quando vier execucao real, ficara em
  repo separado (`trading-bot/`), pequeno (<1500 LOC), com faseamento obrigatorio
  paper -> demo -> mini-real. Placeholder em `vault/Ideas/2026-04-24-trading-bot-architecture.md`.
- **Decisao [018] - Eval batch (nao streaming):** edge discovery e estatisticamente
  lento, batch end-of-day eh tamanho certo. LLM priorization (camada 2) fica para
  depois.
- **Schema enriquecido de predicoes + pipeline S3 (2026-04-23):**
  - `data/predictions/{SYMBOL}.parquet` agora grava `model_version`, `features_hash`, `confidence`, `signal`, `expected_return`, `regime_trend/vol/range`, `session`, `session_score`, `input_window`, `output_horizon` junto de cada row. `_save_predictions` roda depois de signals/session em `src/execution/engine.py`.
  - Novos scripts: `scripts/migrate_predictions_schema.py` (backfill de colunas novas como NA nos historicos, idempotente) e `scripts/upload_to_s3.py` (Hive-partitioned, incremental via md5 vs ETag).
  - S3 layout: `predictions/symbol=X/date=Y/`, `candles/symbol=X/date=Y/`, `news/date=Y/`, `experiments/date=Y/`. `features/`, `backtest/`, `metrics/`, `logs/` nao sobem (regeneraveis).
  - `boto3==1.42.94` adicionado.
  - README reorganizado: secao "Atualizacoes de Hoje" (~200 linhas) movida para `.project/CHANGELOG_LEGACY.md`; README aponta pra CHANGELOG + CHANGELOG_LEGACY + DECISIONS.
  - **Proximos:** (1) restart do preditor + rodar migrate + primeiro upload; (2) construir avaliador de estrategias em 2 camadas (deterministica com CPCV + LLM pra priorizar hipoteses).
- **Coverage + quality gate (2026-04-17):** tiered coverage + property tests + mutation testing setup.
  - `src/execution/engine.py` 45%→**99.5%**, `execution/loop.py` 58%→**100%**, `features/session.py` 65%→**100%**, `features/engineering.py` 78%→**98%**.
  - **Tiered CI gate** em `scripts/check_coverage_tiers.py`: CRITICAL (execution/decision/backtest/mt5/cpcv) **96.6%** ≥ 90%, ML (models/features/evaluation/research) **80.3%** ≥ 80%, OVERALL **85.1%** ≥ 75%. Todos passam.
  - **17 property tests** (hypothesis) em `tests/property/` cobrem invariantes de signal generation (simetria BUY↔SELL, session filter, flat preds → HOLD) e metricas de backtest (winrate ∈ [0,100], drawdown ≤ 0, pnl_total = Σpips).
  - **Mutmut configurado** em `pyproject.toml` pros 5 modulos financeiros criticos (signal, ensemble, execution/engine, backtest/engine, cpcv). Meta survival < 15% por modulo. Rodar pre-release.
  - **501 testes Python + 245 frontend** passando. README/.project atualizados com passo-a-passo.
- **Coverage campaign (2026-04-15):** todos os P0 Python do plano fechados.
  - Cobertura medida: Python **51%** linhas, frontend **15.5%**.
  - Novos test suites (82 testes no total, ~45s):
    - `tests/evaluation/test_cpcv.py` (16 testes) — CPCV 0% → **96%**. Decisao [001] travada.
    - `tests/decision/test_model_selector.py` (17 testes) — 0% → **84%**. 4-tier fallback + regime/session.
    - `tests/decision/test_signal.py` (25 testes) — 40% → **99%**. Expos/corrigiu bug em `generate_signals_for_models`.
    - `tests/backtest/test_engine.py` (24 testes) — 12% → **99%**. Spread, PnL direcional, metricas (Sharpe/PF/DD), persistencia parquet.
  - 170 testes Python passando. Proximos alvos sao P1 (api/backtest_experiments 22%, evaluation/evaluator 22%) ou frontend pages (0%).
- **Frontend Test Suite (2026-04-15):**
  - Nova suite `command_center/frontend/src/tests/` com **26 testes** em **7 arquivos** (Vitest + Testing Library + MSW) — todos verdes em ~5s.
  - Cobre: App mount, ControlTower render + KPIs, SignalBoard (dados, ordenacao, badges, estado vazio), LivePredictionChart, ThemeProvider (default/matrix/cyberpunk + persistencia), integracao real com MSW em `/api/predict/signals/radar`, contratos de dados (confidence ∈ [0,1], signal ∈ {BUY,SELL,HOLD}, OHLC).
  - `vite.config.js` ganhou bloco `test` (jsdom) e `package.json` script `npm test`.
  - `lightweight-charts`, `react-globe.gl` e hooks de WS sao stubados/mockados — jsdom nao suporta WebGL e nao queremos WebSocket real em teste.
  - Politica: se teste falhar, corrigir componente — nao silenciar o teste.
- **API Backend Test Suite (2026-04-15):**
  - Nova suite `tests/api/` com **35 testes** cobrindo endpoints FastAPI (predictions, signals/radar, models, news, session, system, data integrity) — todos verdes em ~5s.
  - `tests/api/conftest.py` monta FastAPI minimalista com os routers de producao (`src.api.predictions`, `news_regime`, `backtest_experiments`) + `SafeJSONResponse` (sanitiza NaN/Inf), **sem** lifespan (evita news loop/ws manager).
  - Testes gracefully-skip quando `data/predictions/*.parquet` ausente; sem dependencia de MT5, LLM ou rede externa.
  - Mudanca de contrato: `/api/predict/predictions/latest` agora retorna **404** se `symbol` nao estiver em `DESIRED_SYMBOLS ∪ FALLBACK_SYMBOLS` (antes retornava 200 com payload vazio).
  - Cobertura inclui integridade cross-endpoint: radar symbols == DESIRED_SYMBOLS, sem NaN/Inf no JSON, session_score estavel entre chamadas, confidence in [0,1].
  - Politica: se teste falhar, corrigir backend — nao forcar o teste a passar.
- **ML Models Test Suite (2026-04-15):**
  - Nova suite `tests/models/` com 32 testes cobrindo treino, predicao, registry, ensemble, anti-leakage e estabilidade — todos verdes em ~47s.
  - Novo modulo `src/models/ensemble.py` (`compute_ensemble`) extrai logica que estava inline em `src/api/predictions.py`; suporta media simples/ponderada, NaN-safe, formato 1D ou 2D.
  - Fixtures em `tests/conftest.py`: `sample_data` (500 barras sinteticas M5), `sample_features` (pipeline real), `sample_dataset` (X, y, times).
  - Teste de leakage usa regex generico (`^next_|^future_|_ahead$|_lookahead$|^minutes_to_next`) para bloquear look-ahead em novas features.
  - Politica: testes nao dependem de MT5/API/LLM; falha = corrigir pipeline, nao o teste.
- Sistema de predicao multi-modelo implementado (5 modelos, 11 simbolos incluindo XAUUSD)
- **Research: Conditional Analysis (2026-04-14):**
  - Novo modulo `src/research/conditional_analysis.py` para descoberta honesta de edges condicionais
  - 3 funcoes publicas: `build_prediction_dataset`, `split_holdout`, `evaluate_filter`
  - Protecoes anti-snooping: filter_log.parquet (todos os testes registrados), Bonferroni correction automatica, holdout usage tracking, Wilson CI95, binomial p-value
  - Verdicts: REJECTED_N / UNDERPOWERED / WEAK / PROMISING / STRONG / REJECTED_WR
  - CLI via `python -m src.research.conditional_analysis build|test`
  - 16 testes com dataset sintetico (edge 80% plantado em hour=14) — todos verdes
  - Fix colateral: `src/models/xgboost_model.py` nao passava `early_stopping_rounds` ao `XGBRegressor` — quebrava CPCV em XGBoost >= 2.0
  - Decisao [016]: defesas em camadas (holdout + Bonferroni + log) contra auto-enganacao por multiple testing
  - **Proximos:** usar em producao pra descobrir filtros uteis para o signal engine; possivel API endpoint e dashboard page `/research`
- **News Pipeline Anti Look-ahead (2026-04-14):**
  - Auditoria identificou vazamento em `signal` do Investing (greenFont/redFont so existe pos-release)
  - `build_news_features` agora usa **duas janelas**: ex-ante (`timestamp <= t`) para impact/schedule, ex-post (`timestamp + NEWS_POST_RELEASE_LAG_MIN <= t`, default 5 min) para sentiment/LLM/volatility
  - Nova config `settings.news_post_release_lag_min` (env `NEWS_POST_RELEASE_LAG_MIN`)
  - Teste novo `test_news_post_release_embargo_blocks_sentiment_before_lag` cobre 3 cenarios
  - Fix de assert base/quote invertido em `test_news_llm_merge_keeps_same_name_for_different_countries`
  - Decisao [015]: opcao C (duas janelas com lag fixo) escolhida sobre A (delay no scraper) e B (signal_known_at) por ser retroativa, simples e semanticamente simetrica treino/live
  - **Pendente:** re-treinar modelos; calibrar lag com dados reais; auditar prompt LLM quanto ao campo `actual`
- **ML Pipeline Robustecido (2026-04-13):**
  - **Look-ahead bias eliminado:** news features usam apenas dados passados (janela 3h atras), `minutes_to_next_news` removido completamente
  - **CPCV implementado:** Combinatorial Purged Cross-Validation com 5 folds + 2% embargo (Marcos Lopez de Prado)
  - **Early stopping:** XGBoost para treino quando val_loss estagna (20 rounds, split interno 85/15)
  - **Regularizacao:** XGBoost (subsample=0.7, colsample=0.7, reg_lambda=1.0, max_depth=4), RF (min_samples_leaf=10, max_depth=8)
  - **Overfitting detection:** warning automatico quando train-val gap > 10%
  - **Feature importance tracking:** gain (XGBoost) + impurity (RF) salvas em parquet
  - **Validation API:** GET /api/predict/models/validation com CPCV score, std, overfit_gap
  - **Frontend Models atualizado:** CPCV score, stability (std), overfit warning com icones
- **Decision Layer:** sinais automaticos BUY/SELL/HOLD por modelo + ensemble
- **Session Intelligence:** features de sessao Forex, threshold adaptativo, model selection por sessao
- **Backtest Engine:** simulacao PnL real com spread, equity curve, Sharpe, drawdown
- **Feature Experiments:** teste automatico de combinacoes de features
- **Model Ranking:** score composto (PnL - dd*0.5 + sharpe*0.3)
- **Model Selector:** auto-selecao por regime de mercado E sessao
- Regime de mercado integrado (trend, volatility, momentum, range)
- News ingestion via Investing.com economic calendar
- LLM sentiment analysis via endpoint local unico (Qwen 3.5 9B) com fallback heuristico
- 44 features totais (24 tecnicas/regime + 8 session + 12 news — sem look-ahead)
- Command Center com 12 paginas (Control Tower + Session Intelligence panel)
- 36+ API endpoints (session/current, session/weights, predict/predictions/latest, predict/signals/radar, models/validation, models/feature-importance)
- **Control Tower:** 7 KPIs (incluindo 30D Trend sparkline), Forex Session Clock, Session Intelligence Panel, **Signal Radar (ensemble-only, 11 simbolos, tooltips)**, AI Core Panel, World Map, **Live Prediction Chart (candles reais + 3 previstos via ensemble)**, Data Stream
- **Signal Board + Themes (2026-04-13):** Signal Radar substituido por Signal Board — painel ticker/order book com lista vertical ordenada por confidence DESC. 3 colunas: Symbol | Signal (badge colorido) | Confidence (barra + %). Flash animation em mudanca de sinal. Novo sistema de temas (Default/Matrix/Cyberpunk) via React Context + CSS vars. Toggle no header, persistencia localStorage. Tema afeta toda a UI (glass-card, neon-border, sidebar, headings).
- **Signal Radar Upgrade (2026-04-13):** Radar reescrito para usar exclusivamente ensemble signal via novo endpoint `/api/predict/signals/radar`. Exibe TODOS os 11 simbolos (antes ~4), labels maiores com glow, dots maiores com pulse, tooltip on hover, breakdown BUY/SELL/HOLD, confidence zones nos rings.
- **Matrix Theme Deep Upgrade (2026-04-13):** Tema Matrix agora e um modo terminal autentico, separado de Default/Cyberpunk. Tokens reforcados para preto puro + verde neon puro, sem blur/glass moderno. DataStream refeito em modo console com scanlines, cursor piscando, typewriter e auto-follow. Signal Board simplificado para labels `[BUY] [SELL] [HOLD]`, intensidade por confidence, sem cores modernas no Matrix. AI Core tambem foi convertido para diagnostico tecnico monocromatico. Header do layout/control tower ganhou estilo CLI (`AUTOTRADER v1.0 / SYSTEM: ONLINE`).
- **Matrix Theme Full Uniformization (2026-04-13):** Corrigidos 3 componentes que nao seguiam o padrao Matrix: ControlTowerClock (Forex Sessions), SessionPanel (Session Intelligence), LivePredictionChart (candles). Todos agora usam `useTheme()` + condicional `isMatrix`. Forex Sessions: relogio SVG com cores verdes, barras sem gradiente, borda-left em sessao ativa, labels CLI. Session Intelligence: dropdown terminal, barras solidas verdes, regime estilo CLI (`> bull | vol: low`), ScoreBadge sem cores modernas. LivePredictionChart: candles up=#00ff41/down=#006622, previstos em verde transparente, grid verde, marker NOW verde, tooltip verde. CSS global: scanline overlay em todos os themed-card/glass-card via ::after pseudo-element, tipografia h1-h6 forcada monospace. Decisao [012]. Default e Cyberpunk intactos.
- **Signal Board Polling (2026-04-13):** polling do endpoint `/api/predict/signals/radar` reduzido para 60s. Sinais sao baseados em candles M5 e nao precisam de refresh agressivo.
- **Signal polling cleanup (2026-04-13):** `AICorePanel` e `WorldMap` tambem tiveram polling de `/api/signals/latest` reduzido para 60s. Backend de `/api/predict/signals/radar` recebeu cache de 60s para amortecer multiplas abas/requests simultaneas.
- **WorldMap Matrix Upgrade (2026-04-13):** Globo 3D transformado para estilo Matrix: textura realista removida, material verde neon emissivo, hex polygons (paises como dots verdes), atmosfera verde, Matrix Rain canvas, arcos/labels/tooltips adaptados. Condicional a `theme === "matrix"`. Dados (arcsData, pointsData, labelsData) intactos. Nova dep: `topojson-client`.
- **Control Tower Upgrade (2026-04-10):** Layout reorganizado — KPI strip 7 cards (30D Trend sparkline substitui Equity Chart grande), centro vira LivePredictionChart com lightweight-charts (10 candles M5 + 3 previstos do ensemble), symbol selecionado no SessionPanel propaga para o chart via state lifted em ControlTower.jsx, novo endpoint backend `/api/predict/predictions/latest` com ensemble + confidence
- **Control Tower Fixes (2026-04-09):** healthcheck 10s (endpoint LLM local Qwen 3.5 9B), session clock UTC-3 sincronizado, radar/AI Core/globe data unwrapping, signals.csv como fonte primaria
- Frontend polling reduzido: bot status = 10s, WebSocket reconnect = 10s

## Recent completions

- Step 1-11: Pipeline completo (MT5, data, features, 5 modelos, engine, eval, tracking, logging, API)
- Command Center v2: React + Vite + Tailwind + Recharts
- News & Regime Integration
- **Control Tower Consistency Fixes (2026-04-09):**
  - Healthcheck: 10s interval, endpoint LLM local (Qwen 3.5 9B), prediction engine status
  - ControlTowerClock: UTC-3 recalculado de session.py (Sydney 19-4, Tokyo 21-6, London 5-14, NY 10-19)
  - SignalRadar + AICorePanel: corrigido unwrapping de dados (API retorna objeto, componentes esperavam array)
  - WorldMap: corrigido caminho de sentiment (analytics.by_currency.sentiment_llm_avg)
  - Signals API: reescrito para ler signals.csv estruturado (era decisions.csv com parsing de texto)
  - WebSocket logs: expandido para incluir signals, session_metrics, backtest_trades
- **Control Tower (2026-04-09):**
  - Nova pagina principal: /control-tower — HUD futurista (cyberpunk trading desk)
  - ControlTowerClock: relogio circular SVG com sessoes Forex (Sydney/Tokyo/London/NY), glow neon, UTC real-time
  - SignalRadar: radar animado SVG com sweep line, sinais BUY/SELL/HOLD por confianca
  - AICorePanel: top model, confianca media, consenso entre modelos com divergencia
  - WorldMap: globo 3D (react-globe.gl/three.js) com arcos de fluxo de moedas, pontos de forca por sentimento de noticias
  - DataStream: terminal hacker-style com logs em tempo real (WebSocket + polling), classificacao por tipo
  - KPIs reutilizados do Dashboard com glow animations
  - EquityChart reutilizado com lazy loading
  - Novas animacoes CSS: neon-pulse, radar-sweep, glow-value, data-scroll, dot-pulse
  - Lazy loading de todos os componentes pesados (globo, radar)
  - Dependencias: three.js, react-globe.gl
  - Control Tower e agora primeiro item do menu (rota padrao)
- **Decision & Evaluation System (2026-04-08):**
  - Decision Layer: src/decision/signal.py — sinais por modelo + ensemble
  - Backtest Engine: src/backtest/engine.py — simulacao PnL com spread
  - Feature Experiments: src/research/feature_experiments.py — 4 combinacoes automaticas
  - Model Ranking: src/research/model_ranking.py — score composto + ranking global
  - Model Selector: src/decision/model_selector.py — selecao por regime
  - API: src/api/backtest_experiments.py — 12 novos endpoints
  - Frontend: Backtest page, Dashboard (best model card), Models (PnL ranking), Experiments (feature comparison), Symbols (best model by regime)
  - Pipeline integration: signals no engine cycle, auto-backtest a cada 50 ciclos
  - Logging: signals.csv, backtest_trades.csv

- **Session Intelligence (2026-04-09):**
  - src/features/session.py: 8 features (4 sessoes + 2 overlaps + strength + score)
  - SESSION_WEIGHTS por ativo (11 pares com pesos por sessao)
  - Threshold adaptativo: score >= 0.6 → threshold -30%, score < 0.3 → HOLD forcado
  - Model selector com fallback: session+regime → session → regime → global
  - Session tracking metrics (session_metrics.csv)
  - API: GET /api/session/current, GET /api/session/weights
  - Frontend: SessionPanel no Control Tower (score, strength, weights por sessao, regime)

## Active blockers

- **Acumular >= 14 dias de daily_eval** antes de qualquer trabalho em bot. H1 precisa ficar PROMISING/STRONG em janela 14d para virar candidata a holdout formal.
- **Validar H1 em holdout temporal 30d** via `conditional_analysis.evaluate_filter` (cuidar do Bonferroni cumulativo). Holdout so pode ser usado UMA vez por filter_hash.
- Rodar `daily_eval` todo dia (idealmente cron noturno UTC). Sem isso, candles antigos saem do buffer raw/ antes de virem arquivados.
- Confirmar credenciais AWS no `.env` se for ativar S3 upload.

## Known issues / tech debt

- Command Center dados mock do SQLite ainda ativos (convivem com dados reais do /data/)
- Frontend bundle grande — globe chunk ~1.8MB (lazy loaded, mas ainda pesado)
- News scraping depende de HTML parsing (fragil se Investing mudar layout)
- Polling do frontend foi desacelerado para reduzir spam durante restarts do backend
- O tema Matrix deve priorizar leitura tecnica e atmosfera de terminal. Se um componente parecer bonito demais, simplificar antes de adicionar efeito.
- CPCV direction accuracy pode precisar de ajuste fino (proxy de current_price no contexto de CPCV)

## What NOT to touch right now

- SQLite mock data do command_center (ainda util para paginas existentes)

---

## Domain glossary

| Term | Meaning |
|---|---|
| M5 | Timeframe de 5 minutos (candle) |
| CPCV | Combinatorial Purged Cross-Validation — metodo de validacao cruzada robusto para series temporais financeiras |
| Purge | Remocao de amostras proximas ao ponto de corte train/test para evitar data leakage |
| Embargo | Periodo adicional apos o purge onde amostras tambem sao removidas |
| MT5 | MetaTrader 5 — plataforma de trading |
| Pip | Menor variacao de preco em FOREX (geralmente 4a casa decimal) |
| Spread | Diferenca entre preco de compra (ask) e venda (bid) |
| MAE | Mean Absolute Error — erro absoluto medio |
| MAPE | Mean Absolute Percentage Error — erro percentual medio |
| Marcos Lopez de Prado | Professor/pesquisador referencia em ML aplicado a financas, autor de "Advances in Financial Machine Learning" |
| Regime | Classificacao do estado do mercado: bull/bear, volatilidade, momentum, ranging/trending |
| LLM Sentiment | Analise de sentimento via Large Language Model local (Qwen 3.5 9B) |
| Economic Calendar | Calendario de eventos economicos (Investing.com) — noticias que movem mercado |
| Hybrid Sentiment | Combinacao ponderada: 0.7 * LLM + 0.3 * basic sentiment |
