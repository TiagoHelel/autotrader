# Graph Report - src + tests  (2026-04-28)

## Corpus Check
- 164 files · ~82,757 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1938 nodes · 3696 edges · 33 communities detected
- Extraction: 61% EXTRACTED · 39% INFERRED · 0% AMBIGUOUS · INFERRED: 1427 edges (avg confidence: 0.71)
- Token cost: 50,200 input · 5,300 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Agent Researcher & Drift Monitor|Agent Researcher & Drift Monitor]]
- [[_COMMUNITY_Core Engine & ML Models|Core Engine & ML Models]]
- [[_COMMUNITY_Backtest & Experiment Tests|Backtest & Experiment Tests]]
- [[_COMMUNITY_Backtest & Model Selection API|Backtest & Model Selection API]]
- [[_COMMUNITY_Data Collection & Raw Features|Data Collection & Raw Features]]
- [[_COMMUNITY_News Sentiment & LLM|News Sentiment & LLM]]
- [[_COMMUNITY_Session Intelligence|Session Intelligence]]
- [[_COMMUNITY_Signal Generation|Signal Generation]]
- [[_COMMUNITY_Backtest Engine|Backtest Engine]]
- [[_COMMUNITY_HPO Context & Search Space|HPO Context & Search Space]]
- [[_COMMUNITY_Research Concepts & Hypotheses|Research Concepts & Hypotheses]]
- [[_COMMUNITY_Conditional Analysis|Conditional Analysis]]
- [[_COMMUNITY_News & LLM Tests|News & LLM Tests]]
- [[_COMMUNITY_Feature Experiments|Feature Experiments]]
- [[_COMMUNITY_News & Regime API|News & Regime API]]
- [[_COMMUNITY_Feature Engineering|Feature Engineering]]
- [[_COMMUNITY_Model Selector|Model Selector]]
- [[_COMMUNITY_Signal Tests & Logging|Signal Tests & Logging]]
- [[_COMMUNITY_CPCV Validation|CPCV Validation]]
- [[_COMMUNITY_Overfitting Detection & API|Overfitting Detection & API]]
- [[_COMMUNITY_HPO Objective & Promoter|HPO Objective & Promoter]]
- [[_COMMUNITY_Execution Loop|Execution Loop]]
- [[_COMMUNITY_Temporal Conviction|Temporal Conviction]]
- [[_COMMUNITY_Daily Evaluation|Daily Evaluation]]
- [[_COMMUNITY_Feature Importance|Feature Importance]]
- [[_COMMUNITY_API Test Fixtures|API Test Fixtures]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]
- [[_COMMUNITY_Module Init|Module Init]]

## God Nodes (most connected - your core abstractions)
1. `PredictionEngine` - 64 edges
2. `ModelRegistry` - 56 edges
3. `MT5Connection` - 55 edges
4. `StateManager` - 52 edges
5. `Hypothesis` - 42 edges
6. `LinearPredictor` - 37 edges
7. `RandomForestPredictor` - 37 edges
8. `XGBoostPredictor` - 37 edges
9. `OpenCodeClient` - 32 edges
10. `BasePredictor` - 30 edges

## Surprising Connections (you probably didn't know these)
- `Ex-post (sentiment/LLM) NAO deve aparecer dentro da janela de embargo.     Ex-an` --uses--> `InvestingCalendarAPI`  [INFERRED]
  tests\test_collector_and_news.py → src\data\news\investing.py
- `Tracking de experimentos. Registra modelos, parametros, features e performance h` --uses--> `BasePredictor`  [INFERRED]
  src\evaluation\tracker.py → src\models\base.py
- `Retorna historico de experimentos com filtros opcionais.` --uses--> `BasePredictor`  [INFERRED]
  src\evaluation\tracker.py → src\models\base.py
- `Retorna resumo de todos os modelos testados.` --uses--> `BasePredictor`  [INFERRED]
  src\evaluation\tracker.py → src\models\base.py
- `Loop continuo de previsao. Sincroniza com fechamento de candles M5 e roda 24/7.` --uses--> `PredictionEngine`  [INFERRED]
  src\execution\loop.py → src\execution\engine.py

## Communities

### Community 0 - "Agent Researcher & Drift Monitor"
Cohesion: 0.02
Nodes (151): apply_daily_eval_filters(), DriftMonitor, latest_eval_path(), Monitor active strategies against daily_eval outputs., Apply conditional_analysis-like filters to daily_eval schema., Detect hit-rate degradation for active strategies., Check every active strategy and update/reject when needed., Return latest daily_eval output by file name. (+143 more)

### Community 1 - "Core Engine & ML Models"
Cohesion: 0.02
Nodes (129): ABC, BasePredictor, log_experiment(), Registra um experimento (treino de modelo).      Args:         model: instancia, _features_hash(), _model_version(), PredictionEngine, Engine de previsao. Orquestra coleta, features, modelos e avaliacao para cada c (+121 more)

### Community 2 - "Backtest & Experiment Tests"
Cohesion: 0.02
Nodes (115): Tests for src/api/backtest_experiments.py — all 12 endpoints.  Estratégia: moc, TestBacktestEquity, TestBacktestResults, TestBacktestRun, TestBacktestSummary, TestExperimentRanking, TestExperimentResults, TestExperimentsRun (+107 more)

### Community 3 - "Backtest & Model Selection API"
Cohesion: 0.02
Nodes (99): get_backtest_equity(), get_backtest_results(), get_backtest_summary(), get_best_model(), get_experiment_ranking(), get_experiment_results(), get_feature_set_ranking(), get_latest_signals() (+91 more)

### Community 4 - "Data Collection & Raw Features"
Cohesion: 0.03
Nodes (50): collect_initial(), collect_update(), load_raw(), Coleta de dados M5 do MetaTrader 5. Salva em /data/raw/{symbol}.parquet com appe, Carrega dados raw de um simbolo., Valida simbolos desejados contra o broker.     Completa com fallbacks ate cobrir, Coleta inicial de candles M5 (minimo 500 por simbolo).     Salva em /data/raw/{s, Atualiza dados existentes com novos candles (append incremental).     Retorna di (+42 more)

### Community 5 - "News Sentiment & LLM"
Cohesion: 0.05
Nodes (47): Executa refresh completo em background., _run_news_refresh_job(), _all_backends_in_cooldown(), _backend_in_cooldown(), _call_backend(), _call_llm_with_failover(), _clear_backend_cooldown(), _configured_backends() (+39 more)

### Community 6 - "Session Intelligence"
Cohesion: 0.05
Nodes (33): add_session_features(), _compute_score(), compute_session_features(), _compute_strength(), _get_active_sessions(), get_current_session_info(), _get_overlaps(), is_market_open() (+25 more)

### Community 7 - "Signal Generation"
Cohesion: 0.05
Nodes (32): generate_ensemble_signal(), generate_signal(), generate_signals_for_models(), log_signal(), Decision Layer - Geracao de sinais de trade. Converte previsoes de modelos ML e, Gera sinais para todos os modelos de um simbolo.      Args:         predictio, Gera sinal ensemble a partir dos sinais de todos os modelos.     Votacao ponder, Loga um sinal gerado. (+24 more)

### Community 8 - "Backtest Engine"
Cohesion: 0.05
Nodes (39): _compute_metrics(), _empty_result(), get_backtest_results(), get_backtest_summary(), Backtest Engine - Simulacao de PnL real. Simula trades baseados em sinais, calc, Roda backtest para todos os modelos de um simbolo usando dados salvos.      Re, Carrega resultados de backtest salvos., Retorna resumo de backtest por modelo/simbolo. (+31 more)

### Community 9 - "HPO Context & Search Space"
Cohesion: 0.06
Nodes (59): _extract_param_patterns(), load_hpo_summary(), Loads HPO results as context for the LLM hypothesis generator.  Exposes two view, Returns a structured summary of HPO state for the LLM context.      Structure:, Summarize hyperparameter tendencies across top trials.     Gives the LLM a compa, _load_xy_for_group(), Nightly HPO runner.  Iterates over (model_name x symbol_group) in round-robin, r, Main entry point for the scheduler.      Runs N trials for each (model_name x sy (+51 more)

### Community 10 - "Research Concepts & Hypotheses"
Cohesion: 0.07
Nodes (63): Agent Researcher System, AutoTrader Research System, Bonferroni Multiple Testing Correction, Conditional Analysis Filter System, Concept: Confidence Gate (signal quality filter), Prediction Confidence Score, Daily Evaluation Parquet Dataset, Model Ensemble Voting System (+55 more)

### Community 11 - "Conditional Analysis"
Cohesion: 0.05
Nodes (60): _apply_filters(), _binomial_test_two_sided(), build_prediction_dataset(), _check_holdout_reuse(), _cli(), _compute_context_frame(), _count_prior_tests(), _enrich_predictions() (+52 more)

### Community 12 - "News & LLM Tests"
Cohesion: 0.06
Nodes (48): client(), _post_to_backend(), Envia request para um backend em um modo especifico., fetch_news(), _get_daily_filepath(), InvestingCalendarAPI, load_news_raw(), News ingestion do Economic Calendar do Investing.com. Usa o endpoint AJAX do cal (+40 more)

### Community 13 - "Feature Experiments"
Cohesion: 0.06
Nodes (27): _direction_accuracy(), _experiment_id(), get_experiment_results(), _get_feature_columns(), _prepare_filtered_dataset(), _quick_backtest(), Feature Experiment Engine. Testa diferentes combinacoes de features automaticam, Roda experimentos para todos os simbolos. (+19 more)

### Community 14 - "News & Regime API"
Cohesion: 0.05
Nodes (49): get_news_analytics(), get_news_by_symbol(), get_news_features(), get_news_latest(), get_news_llm(), get_news_refresh_status(), get_regime_current(), get_session_current() (+41 more)

### Community 15 - "Feature Engineering"
Cohesion: 0.06
Nodes (36): _atr(), compute_features(), load_features(), prepare_dataset(), prepare_inference_input(), Feature engineering para previsao M5. Gera indicadores tecnicos, regime de merca, Prepara dataset para treino/inferencia.      Args:         df: DataFrame com fea, Gera todas as features a partir do DataFrame de candles raw.      Features gerad (+28 more)

### Community 16 - "Model Selector"
Cohesion: 0.08
Nodes (26): get_primary_session(), Auto-selecao de modelo baseada em regime de mercado. Seleciona o melhor modelo, Seleciona modelo com base em performance historica por regime., Seleciona o melhor modelo para um simbolo com base no regime e sessao atuais., Seleciona modelo com base em performance historica por sessao de mercado., Retorna a sessao principal ativa no momento (a mais relevante para o ativo)., Retorna o melhor modelo para cada regime de um simbolo.      Returns:, _select_by_regime() (+18 more)

### Community 17 - "Signal Tests & Logging"
Cohesion: 0.07
Nodes (23): TestLogSignal, CSVLogHandler, log_backtest_trade(), log_prediction(), log_session_metrics(), log_signal(), Sistema de logging persistente. Salva logs em CSV para analise posterior., Log de sinal gerado em CSV dedicado. (+15 more)

### Community 18 - "CPCV Validation"
Cohesion: 0.08
Nodes (16): purged_kfold_split(), Combinatorial Purged Cross-Validation (CPCV). Implementacao baseada em Marcos Lo, Gera indices de treino/teste com purge + embargo temporal.      Args:         X:, Executa CPCV completo para um modelo.      Args:         model_class: classe do, run_cpcv(), DummyModel, Tests for src/evaluation/cpcv.py — Combinatorial Purged Cross-Validation.  Decis, Modelo minimo com fit/predict. Retorna media de y_train sempre. (+8 more)

### Community 19 - "Overfitting Detection & API"
Cohesion: 0.09
Nodes (16): get_models_validation(), Resultados de validacao CPCV por modelo.      Retorna:     - cpcv_score: medi, get_latest_validation(), load_validation_results(), overfitting_score(), Overfitting detection e tracking de validacao. Compara train vs validation score, Carrega resultados de validacao., Retorna ultimo resultado de validacao por modelo. (+8 more)

### Community 20 - "HPO Objective & Promoter"
Cohesion: 0.1
Nodes (26): build_objective(), evaluate_params(), _get_model_class(), _get_space(), _load_advised_space(), _make_suggester(), HPO objective wrapper for Optuna.  Uso:     study = optuna.create_study(directio, Roda CPCV com os params dados e retorna métricas + score final.      Returns: (+18 more)

### Community 21 - "Execution Loop"
Cohesion: 0.09
Nodes (22): get_next_candle_time(), Loop continuo de previsao. Sincroniza com fechamento de candles M5 e roda 24/7., Calcula quando o proximo candle M5 vai fechar., Espera ate o proximo candle M5 fechar., Executa pipeline de noticias: scraping + normalizacao + LLM., _run_news_pipeline(), wait_for_next_candle(), Tests for src/execution/loop.py — loop contínuo e pipeline de notícias.  Estra (+14 more)

### Community 22 - "Temporal Conviction"
Cohesion: 0.15
Nodes (13): compute_all_convictions(), compute_temporal_conviction(), _direction(), Temporal conviction: are the model's last 3 "vintages" of prediction for the sam, Check if the last 3 prediction vintages agree on the T+1 candle direction., Returns {model_name: conviction_str} for each model in the list., _make_parquet(), Tests for src/decision/conviction.py — temporal conviction computation.  Convict (+5 more)

### Community 23 - "Daily Evaluation"
Cohesion: 0.14
Nodes (23): aggregate_metrics(), apply_filter(), archive_candles_for_date(), _coerce(), detect_drift(), evaluate_hypothesis_on_eval(), load_baseline_evals(), load_candles_for_dates() (+15 more)

### Community 24 - "Feature Importance"
Cohesion: 0.14
Nodes (12): load_feature_importance(), Feature importance tracking. Salva importancia de features para XGBoost (gain), Extrai e salva feature importance para um modelo.      Suporta:     - XGBoost, Carrega feature importance., save_feature_importance(), _fake_model(), featured_df(), Tests for src/evaluation/feature_importance.py. (+4 more)

### Community 25 - "API Test Fixtures"
Cohesion: 0.18
Nodes (8): app(), _build_test_app(), Fixtures da su\u00edte de API.  Monta uma app FastAPI leve contendo apenas os ro, Mesma sanitiza\u00e7\u00e3o usada em produ\u00e7\u00e3o (main.py) \u2014 NaN/Inf, FastAPI minimalista com os mesmos routers usados em produ\u00e7\u00e3o., SafeJSONResponse, _sanitize_json(), JSONResponse

### Community 27 - "Module Init"
Cohesion: 1.0
Nodes (1): Build from the existing conditional analysis result object.

### Community 37 - "Module Init"
Cohesion: 1.0
Nodes (1): Nome unico do modelo.

### Community 38 - "Module Init"
Cohesion: 1.0
Nodes (1): Parametros do modelo para tracking.

### Community 39 - "Module Init"
Cohesion: 1.0
Nodes (1): Lista de features usadas pelo modelo.

### Community 40 - "Module Init"
Cohesion: 1.0
Nodes (1): Gera previsoes.          Args:             X: input array (1, n_features) ou (n_

### Community 41 - "Module Init"
Cohesion: 1.0
Nodes (1): Retorna True se o modelo ja foi treinado.

### Community 50 - "Module Init"
Cohesion: 1.0
Nodes (1): Radar tests assume the Forex market is open.          Closed-state coverage li

## Ambiguous Edges - Review These
- `Hypothesis Prompt 2026-04-28T015541a (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T015541.642265Z0000.txt · relation: references
- `Hypothesis Prompt 2026-04-28T015541b (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T015541.661959Z0000.txt · relation: references
- `Hypothesis Prompt 2026-04-28T015611a (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T015611.005222Z0000.txt · relation: references
- `Hypothesis Prompt 2026-04-28T015611b (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T015611.029873Z0000.txt · relation: references
- `Hypothesis Prompt 2026-04-28T015629a (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T015629.474001Z0000.txt · relation: references
- `Hypothesis Prompt 2026-04-28T015629b (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T015629.495767Z0000.txt · relation: references
- `Hypothesis Prompt 2026-04-28T133915a (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T133915.994587Z0000.txt · relation: references
- `Hypothesis Prompt 2026-04-28T133916b (test prompt)` → `AutoTrader Research System`  [AMBIGUOUS]
  src/agent_researcher/tmp/prompts/hypothesis_2026-04-28T133916.025506Z0000.txt · relation: references

## Knowledge Gaps
- **391 isolated node(s):** `Loads HPO results as context for the LLM hypothesis generator.  Exposes two view`, `Returns a structured summary of HPO state for the LLM context.      Structure:`, `Summarize hyperparameter tendencies across top trials.     Gives the LLM a compa`, `Typed records used across the autonomous research agent.`, `Return an ISO timestamp in UTC.` (+386 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Module Init`** (1 nodes): `Build from the existing conditional analysis result object.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `Nome unico do modelo.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `Parametros do modelo para tracking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `Lista de features usadas pelo modelo.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `Gera previsoes.          Args:             X: input array (1, n_features) ou (n_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `Retorna True se o modelo ja foi treinado.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Init`** (1 nodes): `Radar tests assume the Forex market is open.          Closed-state coverage li`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Hypothesis Prompt 2026-04-28T015541a (test prompt)` and `AutoTrader Research System`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Hypothesis Prompt 2026-04-28T015541b (test prompt)` and `AutoTrader Research System`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Hypothesis Prompt 2026-04-28T015611a (test prompt)` and `AutoTrader Research System`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Hypothesis Prompt 2026-04-28T015611b (test prompt)` and `AutoTrader Research System`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Hypothesis Prompt 2026-04-28T015629a (test prompt)` and `AutoTrader Research System`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Hypothesis Prompt 2026-04-28T015629b (test prompt)` and `AutoTrader Research System`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Hypothesis Prompt 2026-04-28T133915a (test prompt)` and `AutoTrader Research System`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._