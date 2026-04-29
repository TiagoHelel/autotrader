# Changelog

## [2026-04-28] - Temporal Conviction + Trajectory Filter

**What changed:**

- `src/decision/conviction.py` (novo) — `compute_temporal_conviction(symbol, model, pred_dir)`
  le as ultimas 3 linhas do parquet para o model em questao e checa se T-2's `pred_t3`,
  T-1's `pred_t2` e T's `pred_t1` apontam a mesma direcao para o candle T+1. Retorna
  `"high"` (todas concordam e nao-zero), `"low"` (pelo menos uma discorda) ou `"unknown"`
  (historico insuficiente ou arquivo ausente). `compute_all_convictions()` retorna
  `{model: conviction}` para todos os modelos de uma vez.
- `src/decision/signal.py` — `generate_signal()` ganha dois novos campos no dict de saida:
  `trajectory_ok` (bool) e `temporal_conviction` (str|None). Novo param
  `trajectory_filter=False`: quando True forca HOLD se trajetoria nao for monotonica
  (pred_t1→pred_t2→pred_t3 nao crescente/decrescente na direcao do sinal). Ambos os
  filtros sao **off by default** para nao alterar comportamento existente.
  `generate_signals_for_models()` ganha `trajectory_filter` e `convictions` params.
- `src/execution/engine.py` — `compute_all_convictions()` chamado antes de
  `_save_predictions()` (importante: parquet da rodada atual nao esta escrito ainda).
  `convictions` passado para `generate_signals_for_models`.
- `tests/decision/test_conviction.py` (novo) — 13 testes cobrindo todos os casos:
  sem arquivo, historico insuficiente, concordancia up/down, discordancia, flat,
  filtro por model, janela dos ultimos 3 rows.
- `tests/decision/test_signal.py` — 8 novos testes para trajectory_ok, trajectory_filter
  e temporal_conviction. Schema test atualizado com novos campos.
- `tests/execution/test_engine.py` — mock de `generate_signals_for_models` atualizado
  para aceitar `**kwargs` (estava quebrando com o novo param `convictions`).

**Why:**
- A mesma previsao de preco para o candle T+1 e feita 3 vezes ao longo do tempo
  (pred_t3 em T-2, pred_t2 em T-1, pred_t1 em T). Quando as 3 revisoes convergem
  para a mesma direcao, o modelo mostrou consistencia — isso e "temporal conviction".
  Trajectory filter garante que as 3 previsoes formem um caminho coerente (nao so
  que concordem na direcao, mas que a magnitude seja monotonica). Ambos ficam como
  campos informativos no parquet para o agent researcher validar antes de ativar
  como gate real de sinal.

---

## [2026-04-27] - HPO Pipeline + LLM Search Space Advisor

**What changed:**

- `src/training/hpo_objective.py` — objetivo Optuna com CPCV, penaliza overfit gap > 10%.
  `DEFAULT_SPACES` para xgboost, random_forest, linear. `build_objective()` retorna closure.
- `src/training/hpo_store.py` — SQLite via Optuna + JSON por champion. `SYMBOL_GROUPS`
  (4 grupos), `HPO_MODELS`, `get_best_params_for_symbol(model, symbol)`.
- `src/training/hpo_runner.py` — round-robin `model × group`, carrega features de parquet
  cacheado (sem MT5). `run_nightly_hpo()` e entry point do scheduler.
- `src/training/promoter.py` — champion/challenger: `MIN_IMPROVEMENT=0.005`,
  `MAX_CHAMPION_DAYS=60`, `MIN_TRIALS_FOR_PROMOTION=20`. `run_promotion_cycle()`.
- `src/agent_researcher/hpo_context.py` — `load_hpo_summary()` retorna champions +
  top_trials_by_study + param_patterns para o LLM.
- `src/agent_researcher/search_space_advisor.py` — LLM estreita bounds do Optuna.
  `_validate_param_spec` impede widen. `SearchSpaceAdvisor.advise()` salva em
  `data/hpo/search_spaces/`.
- `src/agent_researcher/llm_interface.py` — extraido `call(prompt)` reutilizavel.
- `src/agent_researcher/hypothesis_generator.py` — `hpo_summary` incluido no contexto LLM.
- `src/agent_researcher/orchestrator.py` — `_run_search_space_advisor()` apos cada ciclo.
- `src/models/registry.py` — `create_all_models(symbol=None)` le champion params lazily.
- `scripts/run_hpo.py` — CLI manual HPO. `scripts/scheduler.py` — job `hpo` 04:00 UTC.
- **47 testes novos** em `tests/training/` (novo package) e updates em
  `tests/agent_researcher/`, `tests/models/`. Suite: **~543 passed**.

**Why:**
- Modelos usavam hiperparametros hardcoded desde sempre. HPO automatico com CPCV garante
  que os params sejam otimizados com validacao rigorosa (sem leakage). LLM como
  estrategista (ajuste de bounds) + Optuna como executor (busca) e a divisao correta:
  LLM interpreta padroes, Optuna amostra eficientemente dentro do espaco.

---

## [2026-04-26] - MT5 HTTP pull bridge (passo 1 do desacoplamento)

**What changed:**

- Nova pasta `mt5_api/` na raiz com FastAPI fino que expoe `MT5Connection`
  via pull HTTP. Endpoints: `/health`, `/account`, `/terminal`, `/symbols`,
  `/symbols/{s}`, `/symbols/{s}/tick`, `/candles/{s}` (suporta `count` ou
  `date_from`/`date_to`).
- Lifespan abre/fecha conexao MT5; `threading.Lock` global protege a lib
  `MetaTrader5` (nao eh thread-safe).
- Auth opcional via env `MT5_API_TOKEN` (Bearer). Porta default `8002`
  (`MT5_API_PORT`), host `0.0.0.0`.
- `startup.bat` agora sobe `python -m mt5_api.main` ao lado dos demais
  servicos.

**Why:**
- Primeiro passo para mover o stack principal pra Linux. Hoje qualquer
  consumidor de candles/tick precisa importar `MetaTrader5`
  (Windows-only). Servidor fica na maquina com terminal MT5; resto do
  sistema (ML, LLM, news, command_center) vai poder rodar Linux
  consumindo HTTP. Pull (nao webhook) porque backtest/research precisam
  de range historico arbitrario e recovery pos-queda fica trivial.

**Update (mesma data) — passo 2 fechado:**
- `src/mt5/remote_client.py:MT5RemoteClient` (httpx, mesma interface do
  `MT5Connection`).
- `src/mt5/__init__.py` ganhou factory `get_mt5_connection()` chaveada
  por `settings.mt5.backend` ("local"/"remote"). `config/settings.py`
  ganhou `MT5Config.backend/api_url/api_token` com defaults sensatos.
- `src/execution/loop.py` agora usa a factory. Default "local"
  preserva o comportamento anterior bit-a-bit.
- E2E validado contra a API rodando em `localhost:8002`: account,
  symbols, candles e tick OK. Suite `tests/mt5/` 25/25 verde.

---

## [2026-04-25] - Weekend gate + market-closed banner

**What changed:**

- `src/features/session.py`: nova funcao publica `is_market_open(ts)`. Forex
  fechado sex 22:00 UTC -> dom 22:00 UTC. `compute_session_features` zera
  features quando fechado.
- `src/execution/engine.run_cycle`: skip imediato quando fechado, retorna
  `{"skipped": "market_closed", "symbols": {}}`.
- `src/evaluation/daily_eval.run_for_date`: filtra predicoes feitas com
  mercado fechado antes de cruzar com candles.
- `src/agent_researcher/hypothesis_generator.load_daily_eval_summary`: mesmo
  filtro aplicado ao alimentar contexto pro LLM.
- API `/api/predict/signals/radar` retorna
  `{"market_closed": true, "signals": [], "total": 0, ...}` antes do cache.
- Frontend: novo `MarketStatusBanner` no Control Tower; `SignalBoard` mostra
  "MARKET CLOSED" no corpo.

**Why:**
- Sabado o Signal Board estava mostrando sinais de venda em mercado fechado.
  Isso ainda nao virava ordem real (nao existe bot ainda — decisao [017]),
  mas contaminava `daily_eval` e o contexto do `agent_researcher`. Defesa em
  camadas para cortar a contaminacao na origem.

**Tests:**
- 12 testes novos cobrindo o gate (`TestIsMarketOpen`, skip do engine,
  short-circuit do endpoint).
- Fixture `_force_market_open` em `tests/api/test_signals.py`,
  `test_data_integrity.py` e `test_predictions_comprehensive.py::TestRadarSignals`.
- `pytest -q`: **522 passed**. Vitest: **245 passed**.

---

## [2026-04-25] - Stop tracking runtime artifacts; agent_researcher backups to S3

**What changed:**

- `.gitignore`:
  - `command_center/backend/*.db` (e variantes `-journal`/`-wal`/`-shm`).
  - `src/agent_researcher/state.json`,
    `src/agent_researcher/strategies/{active,rejected}/*.json`,
    `src/agent_researcher/tmp/`.
- `git rm --cached command_center/backend/autotrader_cc.db` — backend recria
  schema com `CREATE TABLE IF NOT EXISTS`.
- `scripts/upload_to_s3.py`: nova `upload_agent_researcher`. Layout:
  - `agent_researcher/state/state-YYYY-MM-DD.json` (snapshot diario, sem
    overwrite — se perder a maquina, restaura ate o dia anterior; sem ele
    o anti-snooping de holdout / Bonferroni cai).
  - `agent_researcher/strategies/{active,rejected}/<id>.json`.
  - `agent_researcher/prompts/date=YYYY-MM-DD/<file>` (audit trail completo
    dos prompts e raw outputs do LLM).

**Why:**
- O `.db` produzia churn em `git status` toda execucao. O `state.json` do
  agente nao tinha gitignore — era acidente esperando para virar PR. As
  estrategias e prompts sao runtime, mas precisam de backup forense:
  S3 e a fonte de verdade.

---

## [2026-04-25] - Agent researcher: integracao OpenCode end-to-end

**What changed:**

- `src/agent_researcher/llm_interface.py` reescrito para o opencode CLI atual:
  - `opencode chat --input` (inexistente) -> `opencode run --agent autotrader-researcher --model <m>` com prompt via stdin.
  - No Windows, invoca `node <opencode-bin>` direto e pula o shim `.CMD` que mutilava `--model qwen/qwen/qwen3.5:9b`.
  - `timeout_seconds` default `None` — qwen 9B no Mac mini precisa de minutos.
  - `_dump_raw` salva stdout/stderr crus em `src/agent_researcher/tmp/prompts/raw_output_*.log` quando subprocess falha ou parse de JSON nao acha array.
  - Encoding `utf-8` com `errors="replace"`.
  - Novos env vars: `AGENT_RESEARCH_OPENCODE_AGENT`, `AGENT_RESEARCH_NODE_EXE`, `AGENT_RESEARCH_OPENCODE_SCRIPT`.
- Agente OpenCode `autotrader-researcher` registrado em `~/.config/opencode/opencode.jsonc`:
  - Tools allow: `read`, `list`, `glob`, `grep`, `webfetch`, `websearch`.
  - Tools deny: `write`, `edit`, `patch`, `bash`, `todowrite`, `todoread`.
  - System prompt obriga emissao de JSON puro como resposta final.
- `OpenCodeClient(model="qwen")` hardcoded em `orchestrator.py` removido — usa default `qwen/qwen/qwen3.5:9b`.
- Bumps moderados de contexto (cabem em 100k):
  - `vault_reader.load_context`: 20->50 arquivos por categoria, snippet 4 KB -> 8 KB.
  - `hypothesis_generator.load_daily_eval_summary`: 5->15 arquivos, breakdowns por symbol/trend/volatility_regime/hour_utc.
  - `hypothesis_generator.load_filter_log_summary`: 50->200 linhas.
- Prompt instrui explicitamente uso da janela de 100k e cross-reference de learnings/filter_log antes de propor.

**Why:**
- O codigo herdado nunca rodou end-to-end no host real. Tres problemas sobrepostos: API errada do CLI, shim Windows mutilando args, e default agent do opencode (build) tentando editar codigo via Edit/Bash. Node-direto + agente custom restrito resolve os tres sem afrouxar a fronteira de escrita do orchestrator Python.

**End-to-end run:**
- Hipotese gerada: confidence>=0.75 + Tokyo session + signal=1.
- Verdict research: REJECTED_N (n=0 — dataset insuficiente).
- Holdout NAO consumido (correto).
- `pytest -q`: **511 passed, 2 warnings** (warnings pre-existentes).

---

## [2026-04-25] - Agent researcher autonomo com OpenCode

**What changed:**

- Novo modulo `src/agent_researcher/`:
  - `orchestrator.py` coordena ciclo load context -> OpenCode -> research split
    -> holdout once -> strategy persistence -> vault learnings -> drift monitor.
  - `llm_interface.py` usa somente OpenCode CLI com modelo `qwen` e prompt file
    local ao agente.
  - `evaluator.py` reutiliza `src.research.conditional_analysis.evaluate_filter`
    com `log=False`, mantendo o agente sem escrita em `data/**`.
  - `state_manager.py` controla filtros testados, holdouts usados, estrategias
    ativas e historico de drift em `src/agent_researcher/state.json`.
  - `strategy_manager.py` persiste estrategias validadas em
    `src/agent_researcher/strategies/active/` e move estrategias mortas para
    `strategies/rejected/`.
  - `vault_reader.py`/`vault_writer.py` leem contexto e escrevem somente em
    `vault/AgentResearch/`.
- Novo wrapper `scripts/run_agent_researcher.py`.
- `scripts/scheduler.py` agora agenda o agente as **03:00 UTC**, apos upload
  (01:00 UTC) e daily_eval (02:00 UTC).
- Novo vault area: `vault/AgentResearch/`.
- Testes novos em `tests/agent_researcher/`.

**Why:**
- Automatizar a camada LLM de geracao de hipoteses sem quebrar disciplina de
  holdout, Bonferroni awareness e isolamento de escrita.

**Validation:**
- Testes focados adicionados para parsing do OpenCode, state/holdout, evaluator,
  strategy persistence e drift monitor.

---

## [2026-04-25] - Ruff config + lint cleanup + overfit warning operacional

**What changed:**

- **`pyproject.toml`** ganhou configuracao de `ruff`:
  - `[tool.ruff] line-length = 88`
  - `[tool.ruff.lint] per-file-ignores = { "command_center/backend/main.py" = ["E402"] }`
- **Lint cleanup concluido** nos pontos que ainda estavam pendentes:
  - imports mortos removidos em arquivos do `command_center`
  - imports reorganizados em `src/api/predictions.py`
  - mocks com `;` quebrados em `tests/execution/test_engine.py`
  - import tardio removido em `tests/execution/test_loop.py`
- **`src/execution/engine.py`** agora resume o overfitting por modelo no ciclo de CPCV:
  - calcula `avg_overfit_gap` a partir de `fold_details`
  - adiciona `overfit_warning` ao `cpcv_result`
  - emite `logger.warning(...)` e `log_decision("overfit_warning_<model>")` quando a media passa de `OVERFIT_THRESHOLD`
  - comportamento de treino/selecionador permanece igual; mudanca e de observabilidade
- **`tests/execution/test_engine.py`** expandido para cobrir:
  - resumo `avg_overfit_gap`
  - caso sem warning
  - caso com warning + `log_decision`

**Why:**
- O `gap` de overfitting ja era calculado e persistido, mas no engine servia so para log descartado.
- O projeto ja tinha limpeza de lint em andamento; faltava consolidar a configuracao do `ruff` no `pyproject.toml` e fechar os restos seguros.

**Validation:**
- `ruff check .` â€” OK
- `python -m pytest tests\\execution\\test_engine.py tests\\execution\\test_loop.py tests\\evaluation\\test_overfitting.py tests\\evaluation\\test_cpcv.py -q` â€” **78 passed**

**Files:**
- Modified: `pyproject.toml`, `src/execution/engine.py`, `src/api/predictions.py`, `command_center/backend/{database,main,ws_manager}.py`, `tests/execution/{test_engine,test_loop}.py`, `.project/{CONTEXT,CHANGELOG}.md`

---

## [2026-04-25] - Scheduler in-process + wrapper agendavel do daily_eval

**What changed:**

- **`scripts/run_daily_eval.py`** — wrapper magrissimo do avaliador. Logica continua em `src/evaluation/daily_eval.py`. Wrapper existe pra dar entry point estavel pra schedulers (Task Scheduler, cron, NSSM, scheduler.py).
- **`scripts/scheduler.py`** — scheduler in-process com lib `schedule`. Agenda **upload_to_s3.py @ 01:00 UTC** e **daily_eval @ 02:00 UTC** (gap de 1h pra archive de candles fechar antes do eval rodar). Converte UTC para horario local automaticamente (lib `schedule` opera em local time). Subprocess isolado por job — crash de 1 nao derruba o outro. Timeout de 30min por job. Flags `--dry-run` (mostra cronograma) e `--run-once {upload,eval}` (executa ad-hoc).
- **Limitacao documentada no header:** `schedule` eh in-process, nao sobrevive reboot. Producao real -> Windows Task Scheduler chamando os scripts diretamente, ou rodar scheduler.py via NSSM como servico.
- **Dependencia nova:** `schedule==1.2.2`.

**Why:**
- Centralizar entry points agendaveis em `scripts/` (convencao mental do usuario).
- Daily eval rodando manual eh fricao garantida — esquece, perde candles do buffer. Scheduler in-process resolve enquanto a maquina estiver ligada.
- Migrar para Task Scheduler depois eh trivial (3 linhas no GUI), mas comecar com `schedule` permite testar/iterar antes de gravar em pedra.

**Operacao:**
```bash
python scripts/scheduler.py --dry-run     # confere horarios convertidos
python scripts/scheduler.py --run-once eval  # roda 1x e sai (teste)
python scripts/scheduler.py               # foreground, fica rodando
```

**Files:**
- Created: `scripts/run_daily_eval.py`, `scripts/scheduler.py`
- Modified: `requirements.txt`, `.project/CHANGELOG.md`, `README.md`

---

## [2026-04-24] - Avaliador batch diario + vault Obsidian + decisao bot/research separados

**What changed:**

- **Vault Obsidian (`vault/`)** versionado com o codigo: research, hypotheses, backtests, demo trading, postmortems, ideas. README + 6 templates (Hypothesis, Backtest, DemoSession, ResearchNote, Postmortem, Idea). `.gitignore` filtra UI state e capturas em 00-Inbox.

- **Avaliador batch diario `src/evaluation/daily_eval.py`:**
  - Cruza predicoes (schema enriquecido) vs candles reais em t+5/10/15min.
  - Segmenta hit rate por model, symbol, session, regime, confidence bin, signal.
  - Computa PnL bruto por modelo (BUY/SELL).
  - **Archive local de candles** em `data/archive/candles/symbol=X/date=Y/` (UNION+dedup) — protege contra rotacao do buffer raw/.
  - **Drift detection:** compara hit rate por modelo hoje vs media rolling 30d. Flag > 10pp.
  - **Auto-execucao de hipoteses** declaradas em `vault/Hypotheses/*.md` com bloco `filters` no YAML frontmatter. Computa Wilson CI95, atribui verdict (UNDERPOWERED / REJECTED_WR / WEAK / PROMISING), append em "Daily eval log" no fim da nota.
  - Gera relatorio markdown em `vault/Research/eval-daily/{date}.md`.
  - Salva dataset em `data/research/eval_{date}.parquet`.
  - CLI: `python -m src.evaluation.daily_eval [--date YYYY-MM-DD] [--from --to]`.

- **Eval do dia 2026-04-24 (primeira execucao):** 12.550 predicoes, 11 simbolos, 5 modelos. **H1 (confidence_min=0.85)** retornou n=3946, hit_t1=63.6%, CI95 [62.1%, 65.1%], verdict=**PROMISING**. Sem drift flags. Ver `vault/Research/eval-daily/2026-04-24.md`.

- **Eval ad-hoc inicial salva em `vault/Research/2026-04-24-eval-diaria-baseline.md`** (analise manual com 5 sinais de alerta + 5 hipoteses derivadas).

- **2 hipoteses formalizadas em `vault/Hypotheses/`:**
  - `2026-04-24-confidence-gate-085.md` — H1, com `filters` no frontmatter (auto-roda a cada eval).
  - `2026-04-24-remover-ema-heuristic.md` — H4, counterfactual de ensemble.

- **Decisoes arquiteturais novas em `.project/DECISIONS.md`:**
  - **[017]** Bot de execucao e research em repos/processos separados, com faseamento 0-3 obrigatorio antes de dinheiro real (paper -> demo -> mini-real).
  - **[018]** Avaliador eh batch diario (nao streaming), com auto-execucao segura de hipoteses no campo "Daily eval log" (nao toca no bloco "Resultado" formal que segue manual via `evaluate_filter`).

- **Placeholder do bot em `vault/Ideas/2026-04-24-trading-bot-architecture.md`:** estrutura de repo separado, componentes criticos (risk gate, state machine, kill switch, reconciliation, idempotencia), comunicacao via file-drop, faseamento detalhado.

- **Dependencias novas:** `tabulate==0.10.0` (para `to_markdown()` no daily_eval).

**Why:**
- Eval manual ad-hoc dura 1h por dia. Insustentavel — precisa virar pipeline.
- Confidence calibration foi o achado mais robusto do baseline manual: gradiente monotonico claro nos bins de confidence, delta 18pp entre extremos. Vale auto-rodar diariamente para acompanhar.
- Bot sem edge confirmado eh motor sem combustivel. Faseamento 0-3 forca disciplina antes de risco real.
- Vault Obsidian co-localizada no repo da AI assistant contexto rico (research + codigo no mesmo lugar) sem misturar com `.project/` (que continua AI-optimized para navegar codigo).

**Operacao:**
```bash
# Roda eval para data especifica
python -m src.evaluation.daily_eval --date 2026-04-24

# Roda range (catch-up depois de dias sem rodar)
python -m src.evaluation.daily_eval --from 2026-04-24 --to 2026-04-30

# Default: ontem UTC
python -m src.evaluation.daily_eval
```

Cadencia recomendada: **diaria, end-of-day UTC** (ou imediatamente apos rodar `upload_to_s3.py`). Idempotente — pode rodar quantas vezes quiser na mesma data.

**Files:**
- Created: `src/evaluation/daily_eval.py`, `vault/` (estrutura completa), `vault/Research/eval-daily/2026-04-24.md`, `data/research/eval_2026-04-24.parquet`, `data/archive/candles/symbol=*/date=2026-04-24/part.parquet` (11 simbolos)
- Modified: `.project/DECISIONS.md` (entries 017 e 018), `.project/CONTEXT.md`, `requirements.txt`, `vault/Hypotheses/2026-04-24-confidence-gate-085.md` (frontmatter `filters`), `vault/Templates/Hypothesis.md` (comentario sobre `filters`), `.gitignore` (regras Obsidian)

---

## [2026-04-23] - Enriquecimento do schema de predicoes + pipeline S3

**What changed:**

- **Schema enriquecido de `data/predictions/{SYMBOL}.parquet`** (`src/execution/engine.py`):
  - Novas colunas gravadas por ciclo: `model_version`, `input_window`, `output_horizon`, `features_hash`, `confidence`, `signal`, `expected_return`, `regime_trend`, `regime_vol`, `regime_range`, `session`, `session_score`.
  - `_save_predictions` passou a ser chamado **depois** de gerar signals/session para persistir contexto junto da predicao (antes gravava so `timestamp, model, pred_t1..t3, current_price`).
  - `model_version` = `sha1(name+params+train_size)[:8]_YYYYMMDD`, registrado em `self._model_versions` apos cada treino.
  - `features_hash` = sha1(X_infer)[:12] — permite deduplicar inputs identicos e auditar regressoes.
  - Compatibilidade: linhas antigas ficam com NaN nas colunas novas (nao quebra concat/leitura).

- **Script de migracao `scripts/migrate_predictions_schema.py`:**
  - Idempotente. Varre `data/predictions/*.parquet` e adiciona colunas novas como `pd.NA` quando faltam, reordena para forma canonica, reescreve.
  - Uso: `python scripts/migrate_predictions_schema.py --dry-run` e depois sem a flag.
  - Necessario rodar **antes** do primeiro upload ao S3 pra que dados historicos + novos tenham schema uniforme (evita precisar de `union_by_name=true` em toda query Athena/DuckDB).

- **Uploader S3 incremental `scripts/upload_to_s3.py`:**
  - Particionamento Hive no bucket: `predictions/symbol=X/date=YYYY-MM-DD/part.parquet`, `candles/symbol=X/date=YYYY-MM-DD/part.parquet`, `news/date=YYYY-MM-DD/raw.parquet`, `news_llm/features.parquet`, `experiments/date=YYYY-MM-DD/runs.parquet`.
  - Incremental via comparacao **md5 local vs ETag S3** antes de cada put: dias passados sobem 1 vez (depois `skip`), dia corrente re-sobe a cada execucao (arquivo pequeno).
  - **Nao sobe:** `features/`, `backtest/`, `metrics/`, `logs/` (regeneravel a partir de `raw/` + codigo versionado).
  - Usa `config.settings.s3` (env: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`).
  - Flags: `--dry-run`, `--prefix <ambiente>`.

- **Dependencia nova:** `boto3==1.42.94` (+ `botocore`, `jmespath`, `s3transfer`, `urllib3`) em `requirements.txt`.

- **README.md reorganizado:** secao "Atualizacoes de Hoje" (~200 linhas) removida e movida para `.project/CHANGELOG_LEGACY.md`. README agora aponta para CHANGELOG.md / CHANGELOG_LEGACY.md / DECISIONS.md.

**Why:**
- Schema antigo (`timestamp, model, pred_t1..t3, current_price`) nao permitia segmentar edge por contexto — impossivel responder "o modelo tem edge em London overlap com confidence > 0.8?" sem juntar 3 arquivos diferentes.
- Avaliador automatico de estrategias (modelo + guardrails + regime) precisa das features de contexto gravadas **no mesmo row** da predicao, senao vira ETL retroativo caro.
- S3 Hive-partitioned permite queries predicate-pushdown em DuckDB/Athena direto sobre o bucket, sem baixar tudo localmente.
- Incremental por ETag evita re-upload desnecessario e mantem historico imutavel (MT5 pode revisar candles; nosso snapshot no S3 eh a fonte).

**Operacao:**
- Ordem de rollout: (1) restart do preditor pra ativar schema novo, (2) rodar `migrate_predictions_schema.py` uma vez, (3) rodar `upload_to_s3.py --dry-run`, (4) upload real. Cadencia sugerida em producao: a cada 1h ou end-of-day (fora do loop de predicao).

**Files:**
- Modified: `src/execution/engine.py`, `requirements.txt`, `README.md`
- Created: `scripts/migrate_predictions_schema.py`, `scripts/upload_to_s3.py`, `.project/CHANGELOG_LEGACY.md`

**Testes:** 501 Python passando apos o patch (smoke + imports do engine + syntax check).

---

## [2026-04-17] - Tiered coverage gates + property tests + mutation testing setup

**What changed:**
- **Coverage push nos criticos (45%-65% → 99%-100%):**
  - `src/execution/engine.py`: 45% → **99.5%** (+16 testes em `tests/execution/test_engine.py` cobrindo `_add_news_features` com news populado, `_save_feature_importance`, `_run_cpcv_validation` com overfit_score branch, `run_cycle` happy path + exception, `initial_setup`, `_process_symbol` com raw vazio / inference insuficiente)
  - `src/execution/loop.py`: 58% → **100%** (+4 testes cobrindo `run_forever` com KeyboardInterrupt, exception mid-cycle + sleep 30s, happy cycle + news refresh; `_run_news_pipeline` com LLM empty result)
  - `src/features/session.py`: 65% → **100%** (nova suite 27 testes em `tests/features/test_session.py` — `_is_session_active` cross-midnight, `_compute_score` weights zero, `add_session_features` vetorizado, `get_current_session_info` com London+NY overlap via `monkeypatch` em `datetime.datetime`)
  - `src/features/engineering.py`: 78% → **98%** (nova suite 11 testes cobrindo `compute_features` sem spread / time string, `prepare_dataset` insuficiente + fallback, `prepare_inference_input`, `save_features`/`load_features` roundtrip)

- **Tiered coverage gate (`scripts/check_coverage_tiers.py`):** le `coverage.xml` e enforce thresholds diferentes por tier de risco. CRITICAL (execution + decision + backtest + mt5 + cpcv) 90% / ML (models + features + evaluation + research) 80% / OVERALL 75%. Mostra breakdown por arquivo do tier critico. Exit code != 0 se qualquer tier regride.
  - Resultado atual: CRITICAL **96.6%** / ML **80.3%** / OVERALL **85.1%** — todos passam.
  - `.coveragerc` configurado com branch coverage e exclude de `if TYPE_CHECKING`, `if __name__ == "__main__"`, `pragma: no cover`.

- **Property-based tests (hypothesis) em `tests/property/`:**
  - `test_signal_properties.py` (10 props): signal sempre em {BUY, SELL, HOLD}, confidence em [0, 1], `expected_return` sign casa com direcao do signal, `session_score < 0.3` sempre forca HOLD, flat predictions sempre HOLD, simetria BUY↔SELL ao mirror preds em torno de `current_price`, ensemble unanime → ensemble concorda, `generate_signals_for_models` aceita list/dict e skipa malformado.
  - `test_backtest_metrics_properties.py` (7 props): `winrate` em [0, 100], `max_drawdown` nao-positivo, `pnl_total == sum(pnl_pips)`, total_trades = winning + losing, all-winners → profit_factor = inf, all-losers → profit_factor = 0, invariantes de ordem (pnl_total/winrate/total_trades).
  - 17 property tests passando em ~12s. Hypothesis roda 200 exemplos por propriedade por default; configuravel via `HYPOTHESIS_PROFILE`.

- **Mutation testing config em `pyproject.toml` (`[tool.mutmut]`):** escopo narrow nos 5 modulos financeiros criticos (`decision/signal.py`, `decision/ensemble.py`, `execution/engine.py`, `backtest/engine.py`, `evaluation/cpcv.py`). Runner customizado que so executa tests/decision + execution + backtest + evaluation + property (evita rodar suite inteira pra cada mutante). Meta: survival rate < 15% por modulo. Uso: `mutmut run` (30min-2h) → `mutmut results` → `mutmut show <id>` → escrever teste → repetir.

- **README atualizado:** secao "## Testes" reescrita com passo-a-passo claro ("Como rodar tudo", "Com coverage + gate tierado", "Subset por area", "Property-based tests", "Mutation testing"), tabela de tiered gates, arvore de `tests/` atualizada. Secao "## Frontend Tests" atualizada pra refletir 245 testes / 24 arquivos / 80.4% lines.

**Why:**
- Coverage % diz "linha executou", nao "teste pegaria uma regressao". Property tests e mutation testing complementam: property tests rodam milhares de casos random atras de contra-exemplos; mutation testing introduz bugs sinteticos e verifica se algum teste falha.
- Gate unico (80% global) trata igual `src/decision/signal.py` (roteia dinheiro) e `src/api/schemas.py` (DTOs). Tierar por risco = time certo de teste no lugar certo.
- Fechar buracos em `execution/engine.py` e critico: e o orquestrador do ciclo de predicao inteiro e estava em 45%.

**Dependencies added (`requirements.txt`):**
- `hypothesis==6.152.1` (property-based testing)
- `mutmut==3.5.0` + transitivas (`libcst`, `rich`, `textual`, `markdown-it-py`, `linkify-it-py`, `mdit-py-plugins`, `mdurl`, `uc-micro-py`, `platformdirs`, `setproctitle`, `sortedcontainers`, `toml`)

**New files:**
- `.coveragerc`
- `pyproject.toml` (sections: `[tool.pytest.ini_options]` e `[tool.mutmut]`)
- `scripts/check_coverage_tiers.py`
- `tests/features/__init__.py`, `tests/features/test_session.py`, `tests/features/test_engineering.py`
- `tests/property/__init__.py`, `tests/property/test_signal_properties.py`, `tests/property/test_backtest_metrics_properties.py`

**Modified files:**
- `tests/execution/test_engine.py` (+16 testes, total 32)
- `tests/execution/test_loop.py` (+4 testes, total 15)
- `requirements.txt` (hypothesis + mutmut + deps)
- `README.md` (secoes Testes + Frontend Tests reescritas)
- `.project/CONTEXT.md`, `.project/CHANGELOG.md`

**Run:**
```bash
source venv/Scripts/activate
pytest --cov=src --cov-report=xml --cov-config=.coveragerc
python scripts/check_coverage_tiers.py     # gate CI
pytest tests/property/ -q                  # property tests rapidos
mutmut run                                  # mutation testing (slow, pre-release)
```

**Estado final:** 501 testes Python + 245 frontend, CRITICAL 96.6% / ML 80.3% / OVERALL 85.1%, todos os 3 tiers acima do threshold.

---

## [2026-04-15] - Backtest engine test suite (P0 Python fechados)

**What changed:**
- **Nova suite `tests/backtest/test_engine.py`** — 24 testes cobrindo `run_backtest` (empty, threshold skip, BUY rising/SELL falling, spread reduz PnL, exit_horizon insuficiente, default spread, schema do trade), `_compute_metrics` (winrate, pnl_total, profit factor, max drawdown ≤0, equity curve = cumsum, all-losers → PF=0, all-winners → PF=inf, Sharpe=0 com 1 trade), `_empty_result`, `run_backtest_by_model` (persiste trades + metrics parquet por modelo), `get_backtest_results` (filtro symbol/model), `get_backtest_summary` (ordenado por pnl_total desc).
- **Fixture `fake_data_dir`:** redireciona `settings.project_root` para `tmp_path` e cria `data/raw/` + `data/predictions/` — exercita o pipeline completo read-parquet → backtest → write-parquet sem dados reais.
- **Impacto:** `src/backtest/engine.py` passou de **12% → 99%**, total Python **48% → 51%**. 170 testes Python passando.
- **Marco:** **todos os P0 Python do plano de cobertura estao fechados** (CPCV, model_selector, signal, backtest/engine). Proximos alvos sao P1 (api/backtest_experiments, evaluation/evaluator) ou frontend.

**Files:**
- `tests/backtest/__init__.py`, `tests/backtest/test_engine.py` (novo)
- `.project/COVERAGE_PLAN.md` (P0 fechado)

---

## [2026-04-15] - Signal generation test suite + bug fix

**What changed:**
- **Nova suite `tests/decision/test_signal.py`** — 25 testes cobrindo `generate_signal` (BUY/SELL/HOLD por threshold + confidence, session filter em score<0.3, multipliers high/medium, fallback sem preds, divisao por zero), `generate_signals_for_models` (lista + dict preds, skip malformado), `generate_ensemble_signal` (votacao ponderada, empate → HOLD, schema), e `log_signal`.
- **Bug corrigido em `src/decision/signal.py:143`** — branch `isinstance(preds, dict)` era inalcancavel porque `hasattr(preds, '__len__')` casava primeiro (dict tem `__len__`), fazendo `preds[0]` levantar `KeyError: 0`. Reordenado: dict check vem antes do list check.
- **Impacto:** `src/decision/signal.py` passou de **40% → 99%**, total Python **47% → 48%**. 146 testes Python passando.
- **Gap coberto:** decision layer agora tem contrato travado — qualquer mudanca nos multipliers de sessao (0.7 / 1.0 / 1.5), threshold default (3 pips) ou formula de confidence (0.6*agreement + 0.4*magnitude) quebra teste.

**Files:**
- `tests/decision/test_signal.py` (novo)
- `src/decision/signal.py` (fix)
- `.project/COVERAGE_PLAN.md` (progresso atualizado)

---

## [2026-04-15] - Model selector test suite

**What changed:**
- **Nova suite `tests/decision/test_model_selector.py`** — 17 testes cobrindo `select_model` (4-tier fallback: session+regime → session → regime → best-overall → default xgboost), `_select_by_regime`, `_select_by_session`, `select_models_by_regime` e `get_primary_session`.
- **Fixture `fake_project`:** monta `data/backtest/{symbol}_{model}.parquet` + `data/features/{symbol}.parquet` em `tmp_path` e monkeypatcha `settings.project_root`. Zero dependencia do filesystem real.
- **Impacto:** `src/decision/model_selector.py` passou de **0% → 84%**, total Python **44% → 47%**. 121 testes Python passando em ~45s.
- **Gap coberto:** auto-selecao de modelo por regime/sessao agora tem contrato travado — qualquer mudanca no fallback order ou minimo de trades (≥5 por sessao) quebra teste.

**Files:**
- `tests/decision/__init__.py`, `tests/decision/test_model_selector.py` (novo)
- `.project/COVERAGE_PLAN.md` (progresso atualizado)

---

## [2026-04-15] - Coverage baseline + CPCV test suite

**What changed:**
- **Cobertura medida pela primeira vez** em todas as camadas:
  - Python (src/): **42%** linhas (pytest-cov instalado, 88 testes).
  - Frontend (command_center/frontend/src/): **15.5%** linhas / 7.9% branches (@vitest/coverage-v8 instalado, 26 testes).
- **`.project/COVERAGE_PLAN.md`** criado com priorizacao P0/P1/P2 dos gaps por modulo (CPCV, model_selector, signal, backtest engine, paginas do frontend).
- **Novo pacote de testes `tests/evaluation/test_cpcv.py`** — 16 testes cobrindo `purged_kfold_split` (no-overlap train/test, embargo apos bloco de teste, blocos contiguos nao shuffled, indices validos, ValueError em dados pequenos) e `run_cpcv` (schema de retorno, fold sizes, overfit_gap = train - val, fallback 1D via MAE).
- **Impacto:** `src/evaluation/cpcv.py` passou de **0% → 96%**, total Python **42% → 44%**.
- Decisao arquitetural [001] (CPCV obrigatorio) agora tem cobertura direta impedindo regressao silenciosa.

**Gate policy:**
- Threshold de 80% NAO esta ativo. Meta eh subir modulo-a-modulo seguindo `.project/COVERAGE_PLAN.md`. Gate liga quando baseline global >= 80%.

**Scripts:**
```bash
# Python
source venv/Scripts/activate
pytest tests/ --cov=src --cov-report=html:coverage_html_python

# Frontend
cd command_center/frontend
npx vitest run --coverage
```

**Dependencias adicionadas:**
- `pytest-cov==7.1.0`, `coverage==7.13.5` (venv).
- `@vitest/coverage-v8@^4.1.4` (command_center/frontend devDependencies).

**Files:**
- `.project/COVERAGE_PLAN.md` (novo)
- `tests/evaluation/__init__.py`, `tests/evaluation/test_cpcv.py` (novo)
- `requirements.txt` (pytest-cov adicionado)

---

## [2026-04-15] - Frontend Test Suite (command_center/frontend/src/tests/)

**What changed:**
- **Nova suite de testes do frontend React** em `command_center/frontend/src/tests/` — **26 testes, ~5s, todos passando**.
- **7 arquivos de teste:**
  - `test_app.jsx` — App monta sem crash (MemoryRouter + ThemeProvider).
  - `test_control_tower.jsx` — `ControlTower` renderiza titulo e faixa de KPIs (Balance/Equity/PnL/Win Rate).
  - `test_signal_board.jsx` — `SignalBoard`: render, dados mockados, ordenacao por confidence desc, badges `[BUY]`/`[SELL]`/`[HOLD]`, estado "Waiting for signals...".
  - `test_live_chart.jsx` — `LivePredictionChart`: render default, prop `symbol`, dados de candles + predicao ensemble.
  - `test_theme.jsx` — `ThemeProvider`: default → matrix → cyberpunk, `data-theme` no `<html>`, CSS vars aplicadas, persistencia localStorage, tema invalido ignorado.
  - `test_api_integration.jsx` — Integracao **real via MSW** em `/api/predict/signals/radar`: contrato de confidence ∈ [0,1], tratamento de HTTP 500 sem quebrar UI.
  - `test_consistency.jsx` — Guardrails puros: confidence ∈ [0,1], signal ∈ {BUY,SELL,HOLD}, OHLC valido (high ≥ max(o,c), low ≤ min(o,c)).

**Infra:**
- `vite.config.js` ganhou bloco `test` (jsdom, `setupFiles: './src/tests/setupTests.js'`, `include: ['src/tests/**/test_*.{js,jsx}']`).
- `package.json` scripts: `npm test` (vitest run) e `npm run test:watch`.
- `setupTests.js` registra `@testing-library/jest-dom` e stubs de `matchMedia`, `ResizeObserver`, `IntersectionObserver` (jsdom nao implementa).
- `mocks/handlers.js` + `mocks/server.js` — MSW node server para integracao.

**Dependencias adicionadas (devDependencies):**
- `vitest@4.1.4`, `@testing-library/react@16`, `@testing-library/jest-dom@6`, `@testing-library/user-event@14`, `msw@2.13`, `jsdom@29`.

**Decisoes-chave:**
- **Componentes pesados stubados no import** (`WorldMap`, `LivePredictionChart` no teste de ControlTower; `lightweight-charts` no teste do chart): jsdom nao tem WebGL/canvas decentes e carregar esses libs matava tempo/confiabilidade.
- **API mock via `vi.mock('../services/api')`** em testes unitarios; **MSW apenas no arquivo de integracao** — mantem testes unitarios deterministicos e rapidos.
- **Proxy mock** para `api` no teste do ControlTower retorna `[]` para chamadas de historico (sparkline) e objeto-com-signals para o resto, cobrindo todos os consumers downstream sem listar um-a-um.

**Scripts:**
```bash
cd command_center/frontend
npm test
```

**Files:**
- `command_center/frontend/vite.config.js`, `package.json`
- `command_center/frontend/src/tests/setupTests.js`
- `command_center/frontend/src/tests/mocks/{handlers,server}.js`
- `command_center/frontend/src/tests/test_{app,control_tower,signal_board,live_chart,theme,api_integration,consistency}.jsx`

---

## [2026-04-15] - API Backend Test Suite (tests/api/)

**What changed:**
- **Nova suite de testes do backend FastAPI** em `tests/api/` — **35 testes, ~5s, todos passando**.
- **7 arquivos de teste:**
  - `test_predictions.py` — `/api/predict/symbols`, `/predictions`, `/predictions/latest` (ensemble dict com 3 horizontes pred_t1/t2/t3, confidence, models), **404 para symbol invalido**, **422 para query faltante**.
  - `test_signals.py` — `/api/predict/signals/radar` retorna exatamente 11 entries (DESIRED_SYMBOLS), todos em {BUY, SELL, HOLD}, confidence em [0, 1], breakdown BUY+SELL+HOLD == total.
  - `test_models.py` — `/models/performance` ({"ranking":[...]}), `/models/best` com e sem symbol, `/models/info`, `/feature-importance`.
  - `test_news.py` — `/news/latest` (events list), `/features` (feature dict contem `news_sentiment_base`), `/by-symbol` (base/quote currency corretos), `/analytics`.
  - `test_session.py` — `/session/current` (session_score in [0,1]), regime dict presente, `/session/weights`.
  - `test_system.py` — `/system/status`, `/logs/recent`, `/metrics`.
  - `test_data_integrity.py` — consistencia radar vs. predictions, sem NaN/Inf em JSON (smoke em 4 endpoints criticos), current_price > 0, radar symbols == set(DESIRED_SYMBOLS), session_score estavel entre chamadas consecutivas (tolerancia < 0.2).
- **Conftest de API (`tests/api/conftest.py`):** monta `FastAPI` minimalista com os 3 routers de producao (`src.api.predictions`, `news_regime`, `backtest_experiments`) + `SafeJSONResponse` (mesma sanitizacao NaN/Inf de `command_center/backend/main.py`). **Sem lifespan** — evita disparar news refresh loop + ws_manager em cada teste.
- **Fixtures:** `client` (TestClient), `has_predictions`/`has_features` (booleans usados para skip gracioso quando dados parquet ausentes).

**Backend contract change:**
- `src/api/predictions.py` — `GET /api/predict/predictions/latest` agora **valida symbol** contra `DESIRED_SYMBOLS ∪ FALLBACK_SYMBOLS` e retorna **HTTP 404** para simbolos desconhecidos. Antes retornava 200 com `{"ensemble": null, "models": []}`, o que mascarava erros de integracao.

**Why:**
- Garantir que o backend **nunca sirva dados errados**, **nunca quebre silenciosamente** e seja confiavel para trading real.
- Testes atuais cobrem endpoints, shape das respostas, sanidade numerica (NaN/Inf → None) e coerencia cross-endpoint.
- Sem dependencia de MT5, LLM ou rede externa — rodam em CI fresh ou dev bare.

**Policy:** se um teste falhar, **corrigir o backend** — nao forcar o teste a passar. Testes refletem o contrato real esperado pelo frontend e pela pipeline de ML.

**New files:**
- `tests/api/__init__.py`
- `tests/api/conftest.py`
- `tests/api/test_predictions.py`
- `tests/api/test_signals.py`
- `tests/api/test_models.py`
- `tests/api/test_news.py`
- `tests/api/test_session.py`
- `tests/api/test_system.py`
- `tests/api/test_data_integrity.py`

**Modified files:**
- `src/api/predictions.py` — validacao de symbol em `/predictions/latest` (HTTPException 404).
- `README.md` — nova secao "Suite de API Backend".
- `.project/CONTEXT.md` — entrada "API Backend Test Suite".

**Run:**
```bash
pytest tests/api/           # ~5s, 35 passed
```

---

## [2026-04-15] - ML Models Test Suite (tests/models/)

**What changed:**
- **Nova suite completa de testes** para os modelos de ML em `tests/models/` — 32 testes, ~47s, todos passando.
- **Novo modulo:** `src/models/ensemble.py` com `compute_ensemble(predictions, weights=None, skip_non_finite=True)`. Extrai logica de ensemble que estava inline em `src/api/predictions.py`, agora reutilizavel e test avel. Suporta media simples, ponderada, NaN-safe, e aceita tanto `dict[name, [t1,t2,t3]]` quanto `dict[name, array(n, 3)]`.
- **`tests/conftest.py` estendido** com 3 fixtures: `sample_data` (500 candles sinteticos M5 EURUSD-like, random walk + sazonalidade intradia), `sample_features` (pipeline real `compute_features`), `sample_dataset` (X, y, times via `prepare_dataset`).
- **6 arquivos de teste:**
  - `test_models_basic.py` — treino dos 5 modelos, isolamento de instancias por simbolo.
  - `test_models_predictions.py` — shape (n, 3), valores numericos, finitos, faixa plausivel.
  - `test_registry.py` — nomes esperados ({xgboost, random_forest, linear_regression, naive, ema_heuristic}), cache lazy por simbolo, get_model_info, predict_all nao quebra quando nao treinou.
  - `test_ensemble.py` — media correta ([1.5,2.5,3.5] para [1,2,3]+[2,3,4]), ponderada, NaN skip, validacao de input.
  - `test_no_leakage.py` — regex generico bloqueia `^next_`, `^future_`, `_ahead$`, `_lookahead$`, `^minutes_to_next`, `^target_`; valida target = `close[i+input_window+h]` (futuro real).
  - `test_training_stability.py` — sem NaN/Inf em batch, overfit gap < 1.5, determinismo (random_state=42), feature_importances_ em arvores, skip gracioso de `data/metrics/feature_importance.parquet` se ausente.

**Why:**
- Garantir confianca no pipeline de ML antes de escalar research/producao: modelos quebrados silenciosamente, overfitting invisivel e leakage sao os tres maiores riscos.
- Separar ensemble em modulo dedicado ajuda futuras variacoes (ponderado por confidence, por regime, etc.) e permite testar isoladamente.

**New files:**
- `src/models/ensemble.py`
- `tests/models/__init__.py`
- `tests/models/test_models_basic.py`
- `tests/models/test_models_predictions.py`
- `tests/models/test_registry.py`
- `tests/models/test_ensemble.py`
- `tests/models/test_no_leakage.py`
- `tests/models/test_training_stability.py`

**Modified files:**
- `tests/conftest.py` — fixtures `sample_data`, `sample_features`, `sample_dataset`.
- `README.md` — secao Testes + arvore de diretorios.

**Policy:**
- Testes usam dados sinteticos — zero dependencia de MT5, API externa ou LLM.
- Se um teste falhar: corrigir o pipeline, nao o teste.
- Adaptamos testes a API real (`train_all(symbol, X, y)`, nome `linear_regression`) em vez de mudar o pipeline.

---

## [2026-04-14] - Research: Conditional Analysis (Edge Discovery Framework)

**What changed:**
- **Novo modulo:** `src/research/conditional_analysis.py` — framework honesto para descobrir edges condicionais (ex: "XAU entre 14h-15h UTC com confidence > 0.85 tem edge?") em cima das predicoes ja geradas pelo pipeline.
- **Tambem corrigido:** bug em `src/models/xgboost_model.py` — `early_stopping_rounds` era armazenado em `params` mas nunca passado ao construtor do `XGBRegressor`, quebrando com `best_iteration is only defined when early stopping is used` em XGBoost >= 2.0.
- **3 funcoes publicas:**
  - `build_prediction_dataset(symbols, start, end, model)` — junta predictions + candles raw + contexto (session, regime, hora, confidence). Salva em `data/research/predictions_{model}_{timestamp}.parquet`. Reaproveita para todas as analises — nao re-treina nem re-preve.
  - `split_holdout(df, holdout_pct, method="temporal")` — split temporal (default) ou aleatorio. Holdout e os ultimos 20% do periodo.
  - `evaluate_filter(df, filters, hypothesis, holdout=False)` — aplica filtros (symbol, hour_utc, session, regime, confidence_min, etc.), retorna `FilterResult` com N, win_rate, Wilson CI95, PnL, Sharpe, max_drawdown, p-value binomial vs 0.5, verdict (REJECTED_N / UNDERPOWERED / WEAK / PROMISING / STRONG / REJECTED_WR).
- **Protecoes anti-snooping:**
  - `filter_log.parquet` registra TODO filtro testado — timestamp, filter_hash, hypothesis, metricas. Serve como memoria anti-autoenganacao.
  - **Bonferroni correction automatica:** se voce ja testou N filtros, o `bonferroni_adjusted_p` = `p * (N+1)`. Warning no sumario quando ajustado >= 0.05.
  - **Holdout usage tracking:** reuso do mesmo `filter_hash` no holdout dispara warning ("resultado e INVALIDO").
- **CLI:** `python -m src.research.conditional_analysis build --symbols XAUUSD,EURUSD --start 2025-01-01 --model xgboost` e `... test --dataset <path> --filter '{...}' --hypothesis "..."`.
- **Testes:** `tests/test_conditional_analysis.py` — 16 testes com dataset sintetico (edge de 80% plantado em hour=14). Valida deteccao correta, rejeicao de hours sem edge, UNDERPOWERED com N<30, Bonferroni, reuso de holdout, Wilson CI, binomial test.

**Why:**
- Modelo atual tem val_acc ~48.5% medio (coin flip). Edge real em FX M5 raramente existe em media — existe condicional a regime/hora/sessao. Precisavamos de framework para descobrir isso **sem auto-enganar** via data snooping.
- Multiple testing e overfit de segunda ordem sao os principais modos de falha: testar 100 combinacoes e 5 parecerao boas por acaso (p=0.05). Sem Bonferroni + holdout inviolado + log de tentativas, qualquer "edge" encontrado e suspeito.

**New files:**
- `src/research/conditional_analysis.py`
- `tests/test_conditional_analysis.py`

**Modified files:**
- `src/models/xgboost_model.py` — passa `early_stopping_rounds` ao `XGBRegressor` construtor

**Como usar (fluxo tipico):**
1. `build_prediction_dataset(["XAUUSD"], start="2025-01-01", model="xgboost")` — gera parquet (uma vez)
2. `df_r, df_h = split_holdout(df, 0.20)` — separa exploracao/validacao
3. Em `df_r`: teste varias hipoteses com `evaluate_filter` (cada uma com texto de `hypothesis` explicando o PORQUE)
4. Filtros PROMISING → valida **uma unica vez** no `df_h` com `holdout=True`
5. Passou no holdout → backtest engine atual (`src/backtest/engine.py`) com a estrategia combinada
6. Passou no backtest → paper trade forward 1-2 meses
7. Passou no paper trade → producao com tamanho pequeno

**Proximos passos possiveis (nao implementados ainda):**
- Gerador automatico de hipoteses ("grid" de session x hour x confidence com Bonferroni honesto)
- API endpoint `GET /api/research/filters/promising` lendo o filter_log
- Dashboard page `/research` pra UI interativa de teste de filtros
- Integracao signal engine: filtros aprovados viram config que o signal consome em producao

---

## [2026-04-14] - News Pipeline: Post-Release Embargo (Anti Look-ahead Bias)

**What changed:**
- **Embargo ex-post em features de noticias:** `build_news_features` agora aplica duas janelas distintas:
  - Ex-ante (impact, high_impact_flag, minutes_since_last_news): `timestamp <= current_time`
  - Ex-post (sentiment basic/LLM, volatility, sentiment_final): `timestamp + NEWS_POST_RELEASE_LAG_MIN <= current_time`
- **Nova config:** `settings.news_post_release_lag_min` (default 5 min, env `NEWS_POST_RELEASE_LAG_MIN`).
- **Novo parametro:** `build_news_features(..., post_release_lag_min=N)` para override (util em tests/calibracao).
- **Helper extraido:** `_filter_currency` centraliza logica de filtro por moeda (inclui caso XAU com currency vazia).
- **Teste novo:** `test_news_post_release_embargo_blocks_sentiment_before_lag` valida embargo em 3 cenarios (no t=release, apos lag, override zero).
- **Teste corrigido:** `test_news_llm_merge_keeps_same_name_for_different_countries` tinha asserts base/quote invertidos — USDCAD e base=USD/quote=CAD, nao o oposto.

**Why:**
- Auditoria identificou vazamento concreto em `src/data/news/investing.py:149-156`: `signal` e derivado de `greenFont/redFont` do HTML do Investing, que so e aplicado **apos** a release comparando `actual` vs `forecast`.
- Janela anterior usava `timestamp <= current_time` para TODAS as features. Como `timestamp` e o horario agendado da release (conhecido de antemao), qualquer feature derivada de `signal` ou do LLM processando `actual` entrava no dataset **no proprio instante agendado**, antes do mercado em geral ter acesso ao valor.
- Em backtest historico, o snapshot `raw_{date}.parquet` e salvo no fim do dia com `signal` preenchido para TODOS os eventos — contaminacao sistematica do treino.
- CPCV + purge/embargo nao protege contra esse vazamento: cada linha individual ja carregava o futuro codificado na feature.

**Modified files:**
- `src/features/news_features.py` — duas janelas (ex-ante/ex-post), novo helper `_filter_currency`
- `config/settings.py` — nova config `news_post_release_lag_min`
- `tests/test_collector_and_news.py` — novo teste de embargo, fix de assert invertido
- `README.md` — tabela de news features com coluna Tipo (ex-ante/ex-post), nota atualizada
- `.project/CONTEXT.md`, `.project/CHANGELOG.md`, `.project/DECISIONS.md` — documentacao

**Proximos passos recomendados:**
- Re-treinar modelos: esperado queda de `val_score` em janelas news-driven e reducao do `overfit_gap` localizado em candles proximos a releases. Se a queda for brutal, era vazamento dominante.
- Calibrar `NEWS_POST_RELEASE_LAG_MIN` com dados reais (tempo medio entre release agendada e aparecimento do greenFont/redFont no scraper — 5min e chute conservador, pode ser 2-3min).
- Auditar prompt do LLM (`src/llm/`): se nao recebe o campo `actual`, tecnicamente e ex-ante. Enquanto nao confirmado, manter ex-post por seguranca.

**Expectativa:** Metricas pos-fix devem cair em janelas de release e se manter em periodos sem noticias. Queda global moderada = sinal de que o modelo esta agora realista. Queda catastrofica = features de news eram o unico sinal util, e precisam ser repensadas.

---

## [2026-04-13] - ML Pipeline: Critical Fixes (Look-ahead Bias, CPCV, Regularization)

**What changed:**
- **Look-ahead bias eliminado:** `news_features.py` agora usa janela `[t-3h, t]` em vez de `[t-3h, t+3h]`. Feature `minutes_to_next_news` removida completamente do pipeline (usava informacao futura). Total features: 45 → 44.
- **CPCV implementado:** Novo modulo `src/evaluation/cpcv.py` com Combinatorial Purged Cross-Validation (Marcos Lopez de Prado). 5 folds temporais, 2% embargo apos cada bloco de teste. Substitui split simples 80/20 no `execution/engine.py`.
- **Early stopping (XGBoost):** Split interno 85/15 para monitorar val_loss. Para apos 20 rounds sem melhora. Logs: `[XGB] Horizon t+1: early stopping at round 83`.
- **Regularizacao reforçada:**
  - XGBoost: `max_depth` 6→4, `subsample=0.7`, `colsample_bytree=0.7`, `reg_lambda=1.0`
  - Random Forest: `max_depth` 10→8, `min_samples_leaf=10`
- **Overfitting detection:** Novo modulo `src/evaluation/overfitting.py`. Calcula gap train-val, emite warning quando >10%. Salva resultados em `data/metrics/validation_results.parquet`.
- **Feature importance tracking:** Novo modulo `src/evaluation/feature_importance.py`. Salva gain (XGBoost) e impurity (RF) agregados por feature base. Arquivo: `data/metrics/feature_importance.parquet`.
- **API endpoints novos:**
  - `GET /api/predict/models/validation` — CPCV score, std, overfit_gap, overfit_warning por modelo
  - `GET /api/predict/models/feature-importance` — importancia por feature/modelo
- **Frontend Models.jsx atualizado:** Cards mostram CPCV score, stability (std), overfit gap. Icones AlertTriangle (overfit) / ShieldCheck (OK). Tabela CPCV Validation Summary com todos os modelos.
- **Training pipeline refatorado:** CPCV roda para xgboost, random_forest e linear. Modelo final treinado com todos os dados apos validacao. Feature importance extraida automaticamente.

**Why:**
- `window_end = current_time + timedelta(hours=3)` usava dados do FUTURO → invalido para trading real
- Split 80/20 simples nao respeita estrutura temporal → data leakage
- Modelos sem regularizacao memorizavam noise → overfitting estrutural
- Sem metricas de validacao robustas → resultados enganosos

**New files:**
- `src/evaluation/cpcv.py`
- `src/evaluation/overfitting.py`
- `src/evaluation/feature_importance.py`

**Modified files:**
- `src/features/news_features.py` — look-ahead fix, remove minutes_to_next_news
- `src/features/engineering.py` — NEWS_FEATURE_COLUMNS updated (12 instead of 13)
- `src/models/xgboost_model.py` — regularization + early stopping
- `src/models/random_forest.py` — regularization (min_samples_leaf, max_depth)
- `src/models/registry.py` — updated defaults
- `src/execution/engine.py` — CPCV integration, feature importance, overfitting detection
- `src/api/predictions.py` — 2 new endpoints (validation, feature-importance)
- `command_center/frontend/src/pages/Models.jsx` — CPCV display, overfit warnings
- `command_center/frontend/src/services/api.js` — 2 new API methods
- `README.md` — updated features count, model params, validation section
- `.project/CONTEXT.md` — updated current state

**Expectativa:** Accuracy e PnL podem cair apos esta correcao. Isso e esperado e desejavel — significa que o modelo agora e realista e nao esta vazando informacao do futuro.

---

## [2026-04-13] - Matrix Theme: Full Visual Uniformization

**What changed:**
- ControlTowerClock.jsx (Forex Sessions): relogio SVG agora usa cores verdes (#00ff41) para ticks, labels, ponteiros e centro. Barras de liquidez e sessao sem gradiente — solidas com `rgba(0,255,65,0.2)`. Sessao ativa ganha `border-left: 2px solid #00ff41`. Labels CLI com prefixo `>`. Rounded removido (rounded-sm). Overlap badge estilo terminal.
- SessionPanel.jsx (Session Intelligence): dropdown estilo terminal (fundo preto, borda verde, fonte monospace). Score bar solida verde sem gradiente. Barras de peso por sessao solidas. Strength indicators sem glow. Regime info estilo CLI (`> bull | vol: low`). ScoreBadge adaptado para Matrix (sem cores modernas, borda verde fina).
- LivePredictionChart.jsx (candles): chart background preto. Grid lines verdes (`rgba(0,255,65,0.1)`). Candles reais: up=#00ff41, down=#006622. Candles previstos: verde transparente (`rgba(0,255,65,0.4)`). Crosshair verde. Price/time scale borders verdes. NOW marker verde com texto `> NOW`. Tooltip verde monospace. Confidence bar sem glow.
- index.css: scanline overlay via `::after` em `.themed-card` e `.glass-card` no Matrix. Headings h1-h6 com `font-family: var(--theme-font-data)` e `letter-spacing: 0.18em`.
- Todas as mudancas condicionais a `theme === "matrix"` — Default e Cyberpunk preservados sem alteracao.

**Why:**
- Forex Sessions, Session Intelligence e LivePredictionChart ainda usavam cores modernas (azul, vermelho, gradientes, rounded-full, glow) no modo Matrix, quebrando a identidade de terminal hacker
- Decisao [012]: uniformizacao visual completa — todo componente deve parecer terminal, nao dashboard web

**Modified files:**
- `command_center/frontend/src/components/control_tower/ControlTowerClock.jsx`
- `command_center/frontend/src/components/control_tower/SessionPanel.jsx`
- `command_center/frontend/src/components/control_tower/LivePredictionChart.jsx`
- `command_center/frontend/src/index.css`

---

## [2026-04-13] - WorldMap Globe 3D: Matrix theme visual upgrade

**What changed:**
- WorldMap.jsx transformado de globo realista (textura Terra) para estilo Matrix (wireframe/dots/neon verde) quando `theme === "matrix"`
- Textura realista (`globeImageUrl`) removida no modo Matrix
- Material do globo: fundo `#001a00` com emissive verde neon `#00ff41` aplicado via `onGlobeReady` (Three.js mesh traversal)
- Camada de hex polygons ativada: paises renderizados como dots verdes (`hexPolygonResolution=3`, `hexPolygonMargin=0.6`, cor `rgba(0,255,65,0.12)`)
- Atmosfera verde: `atmosphereColor="#00ff41"`, `atmosphereAltitude=0.25`
- Arcos visuais ajustados: verde neon para BUY, vermelho para SELL, verde dim para HOLD, stroke baseado em confidence
- Labels de moeda: cor `#00ff41`, tamanho 1.2
- Tooltips formatados: `USD\nSentiment: Strong\nFlow: High`
- Legenda adaptada para cores Matrix (verde/dim/vermelho)
- Fundo do container: `radial-gradient(circle, #001a00, #000000)`
- Matrix Rain canvas: caracteres japoneses + hex em baixa opacidade (0.3), ~15fps, pointer-events none
- Rotacao: `autoRotateSpeed=0.3` no Matrix
- Dados (arcsData, pointsData, labelsData, currencyStrength) intactos — apenas visual condicional por theme
- Nova dependencia: `topojson-client` (converte TopoJSON do world-atlas para GeoJSON)
- GeoJSON carregado sob demanda (fetch) apenas quando Matrix ativo
- Temas Default e Cyberpunk preservados sem alteracao

**Why:**
- O globo no Matrix ainda usava textura realista da Terra, quebrando a identidade de terminal digital do tema
- Decisao [010]: Matrix deve priorizar autenticidade de terminal sobre polish visual

**Modified files:**
- `command_center/frontend/src/components/control_tower/WorldMap.jsx`

**Dependencies added:**
- `topojson-client` (frontend)

**Build:** `npm run build` OK. WorldMap chunk: ~7.4KB (lazy).

---

## [2026-04-13] - Matrix theme deep upgrade

**What changed:**
- Tema Matrix reforcado para estilo terminal autentico:
  - preto puro (`#000000`)
  - verde neon real (`#00ff41`)
  - verde dim (`#008f2a`)
  - remocao de blur/glass/glow excessivo dentro do Matrix
- `ThemeProvider.jsx` atualizado com novos tokens do tema Matrix
- `index.css` atualizado com scanlines leves, grid terminal sutil, cursor blink e flicker minimo
- `DataStream.jsx` refeito em formato CLI real com typewriter, cursor `> _` e auto-follow
- `SignalBoard.jsx` adaptado no Matrix com labels `[BUY] [SELL] [HOLD]`
- `AICorePanel.jsx` adaptado no Matrix para remover azul/gradientes e adotar diagnostico terminal monocromatico
- `Layout.jsx` e `ControlTower.jsx` ganharam header em estilo CLI quando Matrix estiver ativo
- KPI cards / trend card ajustados para parecerem terminais no Matrix
- `SignalBoard.jsx` polling reduzido para 60s, alinhado ao ciclo M5
- `AICorePanel.jsx` e `WorldMap.jsx` polling de sinais reduzido para 60s
- `src/api/predictions.py` ganhou cache de 60s para `/api/predict/signals/radar`

**Why:**
- O Matrix anterior ainda parecia uma UI moderna verde
- O objetivo novo e parecer um terminal vivo, tecnico e minimalista

**Modified files:**
- `command_center/frontend/src/theme/ThemeProvider.jsx`
- `command_center/frontend/src/index.css`
- `command_center/frontend/src/components/control_tower/DataStream.jsx`
- `command_center/frontend/src/components/control_tower/SignalBoard.jsx`
- `command_center/frontend/src/components/control_tower/AICorePanel.jsx`
- `command_center/frontend/src/components/Layout.jsx`
- `command_center/frontend/src/pages/ControlTower.jsx`
- `command_center/frontend/src/components/common/KPICard.jsx`
- `command_center/frontend/src/components/dashboard/TrendSparklineCard.jsx`

---

## [2026-04-13] — Signal Board + Theme System

**What changed:**
- **Signal Radar → Signal Board:** Substituido o componente `SignalRadar.jsx` (radar circular SVG) por `SignalBoard.jsx` — painel tipo ticker/order book com lista vertical de sinais.
  - Layout: grid 3 colunas (Symbol | Signal | Confidence) ordenado por confidence DESC
  - Badge colorido por sinal (BUY=verde, SELL=vermelho, HOLD=cinza) com glow
  - Barra de progresso horizontal para confidence + valor numerico
  - Header com contagem: "Active Signals: 11" + breakdown BUY/SELL/HOLD
  - Flash animation quando sinal muda de direcao
  - Hover highlight nas linhas
  - Dados: mesmo endpoint `/api/predict/signals/radar` (ensemble-only)
  - Foco em clareza e leitura rapida vs estetica

- **Theme System (novo):** Sistema completo de temas visuais com React Context.
  - `src/theme/ThemeProvider.jsx`: ThemeProvider com 3 temas, CSS variables, localStorage persistence
  - **Default:** tema atual preservado exatamente como estava
  - **Matrix:** fundo preto, verde neon (#00ff41), estilo terminal hacker, fonte mono
  - **Cyberpunk:** neon azul (#00d4ff) + roxo (#7a00ff), gradientes, glow forte
  - Toggle no header: `[ Default | Matrix | Cyberpunk ]` — troca instantanea
  - Persistencia via `localStorage.setItem("theme", name)`
  - Aplicacao via CSS variables (`--theme-bg`, `--theme-accent`, `--theme-text`, etc.)
  - Tema afeta: Control Tower, Dashboard, Logs, DataStream, Sidebar, todos os glass-card/neon-border

- **CSS Updates:** `.glass-card`, `.neon-border`, `.glass-panel` agora usam CSS vars com fallback.
  - Nova classe `.themed-card` para componentes do Control Tower
  - `.theme-btn` para botoes do seletor de tema
  - `.sidebar-link-hover` para links da sidebar
  - `@keyframes signal-flash` para animacao de mudanca de sinal

- **Layout.jsx:** Adicionado top bar com theme toggle selector
- **Sidebar.jsx:** Cores e backgrounds agora usam CSS vars do tema
- **ControlTower.jsx:** SignalRadar → SignalBoard, headings com theme vars

**Why:**
- Signal Radar era visualmente bonito mas dificil de ler rapidamente para decisoes de trading
- Signal Board prioriza clareza: ordenado por forca do sinal, leitura tipo terminal
- Sistema de temas permite personalizacao visual sem afetar funcionalidade
- Matrix/Cyberpunk temas dão opcoes visuais para diferentes preferencias

**New files:**
- `command_center/frontend/src/theme/ThemeProvider.jsx`
- `command_center/frontend/src/components/control_tower/SignalBoard.jsx`

**Modified files:**
- `command_center/frontend/src/main.jsx` — ThemeProvider wrapping
- `command_center/frontend/src/components/Layout.jsx` — theme toggle header
- `command_center/frontend/src/components/Sidebar.jsx` — theme CSS vars
- `command_center/frontend/src/pages/ControlTower.jsx` — SignalBoard + theme vars
- `command_center/frontend/src/pages/Dashboard.jsx` — theme vars on headings
- `command_center/frontend/src/pages/Logs.jsx` — theme vars on headings
- `command_center/frontend/src/components/control_tower/DataStream.jsx` — themed-card
- `command_center/frontend/src/components/control_tower/AICorePanel.jsx` — themed-card
- `command_center/frontend/src/components/control_tower/SessionPanel.jsx` — themed-card
- `command_center/frontend/src/components/control_tower/WorldMap.jsx` — themed-card
- `command_center/frontend/src/components/control_tower/LivePredictionChart.jsx` — themed-card
- `command_center/frontend/src/components/control_tower/ControlTowerClock.jsx` — themed-card
- `command_center/frontend/src/index.css` — theme CSS vars, themed-card, signal-flash, sidebar hover

**Build:** `npm run build` OK. SignalBoard chunk: ~4KB (lazy).

---

## [2026-04-13] — Signal Radar: Ensemble-only + All 11 Symbols

**What changed:**
- **Backend — novo endpoint:** `GET /api/predict/signals/radar` em `src/api/predictions.py`. Para cada um dos 11 DESIRED_SYMBOLS: le previsoes mais recentes, calcula ensemble (media dos modelos), gera sinal BUY/SELL/HOLD via `generate_signal()`, retorna confidence e expected_return. Simbolos sem dados retornam HOLD/0. Inclui breakdown (count BUY/SELL/HOLD).
- **Frontend — SignalRadar.jsx reescrito:**
  - Data source: `/api/predict/signals/radar` (ensemble) em vez de `/api/signals/latest` (per-model signals.csv)
  - Exibe TODOS os 11 simbolos uniformemente distribuidos em circulo
  - Labels: fontSize 5px → 7.5px/9px (hover), fontWeight 600/700, glow filter, contraste melhorado
  - Dots: r=4 → r=6 (8 on hover), pulse animation, glow proporcional a confidence
  - Tooltip on hover: symbol, signal, confidence%, expected return em pips, n_models, source: Ensemble
  - Contador: "11 symbols tracked" + breakdown "5 BUY | 3 SELL | 3 HOLD"
  - SVG viewBox: 200 → 240, cx/cy: 100 → 120, maxRadius: 75 → 90
  - Confidence zone labels nos rings (0.25, 0.50, 0.75, 1.00)
  - Label positioning: deslocado 14px para fora do dot, evitando sobreposicao
- **api.js:** novo metodo `getRadarSignals()`.

**Why:**
- Radar mostrava apenas ~4 sinais (limitado pelo que estava em signals.csv) em vez dos 11 simbolos
- Sinais vinham de per-model logs, nao do ensemble — inconsistente com filosofia do sistema
- Labels eram ilegíveis (fontSize 5px no SVG)
- Sem tooltip para detalhes

**Modified files:**
- `src/api/predictions.py` — novo endpoint `/signals/radar`
- `command_center/frontend/src/services/api.js` — `getRadarSignals()`
- `command_center/frontend/src/components/control_tower/SignalRadar.jsx` — rewrite completo

---

## [2026-04-10] — Control Tower: KPI Reorg + Live Prediction Chart

**What changed:**
- **Backend — novo endpoint:** `GET /api/predict/predictions/latest?symbol=X` em `src/api/predictions.py`. Retorna a previsao mais recente do simbolo com **ensemble** (media dos modelos) para t+1, t+2, t+3, alem de `confidence` (1 - dispersao normalizada entre modelos).
- **Frontend — KPI Strip 7 cards:** grid `xl:grid-cols-7`. Adicionado 7o card **"30D Trend"** (`TrendSparklineCard.jsx`) — sparkline SVG do equity 30d com glow neon, cor por tendencia (verde/vermelho), variacao percentual.
- **Frontend — LivePredictionChart.jsx:** novo componente em `components/control_tower/`, usando **lightweight-charts** (TradingView). Mostra os ultimos 10 candles M5 reais + 3 candles previstos (ensemble) com cores diferenciadas (azul/roxo). Marker "NOW" no ultimo candle real. Tooltip custom mostrando OHLC real e ensemble + confidence. Barra de confidence no header. Atualiza a cada 60s. Symbol controlado via props.
- **Frontend — Symbol lifting:** `selectedSymbol` agora vive em `pages/ControlTower.jsx` e e compartilhado entre `SessionPanel` (que recebe `selectedSymbol` + `onSymbolChange` props) e `LivePredictionChart`. SessionPanel mantem fallback interno para compatibilidade.
- **Frontend — substituicao do EquityChart:** Equity Chart grande removido da row central da Control Tower (sua versao mini virou o 7o KPI). LivePredictionChart toma o lugar central.
- **api.js:** novo metodo `getLatestPrediction(symbol)`.

**Why:**
- Topo (KPIs) deve dar visao macro da conta, centro deve dar visao micro do mercado + previsoes do modelo
- Equity curve era so historia; agora o centro da Control Tower mostra acao do mercado em tempo real + o que o ensemble preve
- Ensemble (media) escolhido para UI limpa em vez de plotar 5 modelos sobrepostos

**Modified files:**
- `src/api/predictions.py` — novo endpoint `/predictions/latest` com ensemble + confidence
- `command_center/frontend/src/services/api.js` — `getLatestPrediction`
- `command_center/frontend/src/components/dashboard/KPICards.jsx` — grid 6→7, adiciona TrendSparklineCard
- `command_center/frontend/src/components/dashboard/TrendSparklineCard.jsx` — NOVO
- `command_center/frontend/src/components/control_tower/LivePredictionChart.jsx` — NOVO
- `command_center/frontend/src/components/control_tower/SessionPanel.jsx` — props selectedSymbol/onSymbolChange
- `command_center/frontend/src/pages/ControlTower.jsx` — lift state + replace EquityChart slot

**Dependencies:**
- `lightweight-charts` ^5.x (frontend)

**Build:** `npm run build` OK. LivePredictionChart chunk: 163 KB (lazy).

---

## [2026-04-09] — Control Tower Consistency Fixes (7 parts)

**What changed:**
- **Healthcheck (ws_manager.py):** Intervalo 3s→10s, verifica apenas LLM fallback_2 (Mac Mini), adiciona status do prediction engine (ultimo timestamp de predictions.csv)
- **Session Clock (ControlTowerClock.jsx):** Corrigido mapeamento UTC→UTC-3 para alinhar com session.py: Sydney 19-4, Tokyo 21-6, London 5-14, NY 10-19; overlaps Tokyo+London 5-6, London+NY 10-14
- **Signal Radar (SignalRadar.jsx):** Corrigido data unwrapping — API retorna `{signals:[...]}` mas componente esperava array direto. Adicionado: `Array.isArray(signals) ? signals : signals?.signals || []`
- **AI Core Panel (AICorePanel.jsx):** Mesma correcao de unwrapping para signals e performance. `performance?.ranking || (Array.isArray(performance) ? performance : [])` para ranking de modelos
- **World Map (WorldMap.jsx):** Corrigido caminho de dados para currency strength — API retorna `analytics.by_currency.{CUR}.sentiment_llm_avg`, nao `currency_scores`. Adicionado sessionData fetch
- **Signals API (backtest_experiments.py):** Reescrito `get_latest_signals()` para ler signals.csv (colunas estruturadas) como fonte primaria, com fallback para decisions.csv (parsing de texto)
- **Logs stream (ws_manager.py + predictions.py):** `get_recent_logs()` agora tambem le signals.csv, session_metrics.csv, backtest_trades.csv

**Why:**
- Todos os componentes do Control Tower mostravam dados zerados/neutros por causa de mismatches entre formato da API e expectativa do frontend
- Healthcheck consumia recurso desnecessario verificando LLMs que estao offline (RunPods)
- Session clock nao correspondia aos horarios reais do session.py

**Modified files:**
- `command_center/backend/ws_manager.py` — healthcheck simplificado + interval 10s
- `command_center/frontend/src/components/control_tower/ControlTowerClock.jsx` — UTC-3 corrigido
- `command_center/frontend/src/components/control_tower/SignalRadar.jsx` — data unwrapping
- `command_center/frontend/src/components/control_tower/AICorePanel.jsx` — data unwrapping
- `command_center/frontend/src/components/control_tower/WorldMap.jsx` — sentiment data path
- `src/api/backtest_experiments.py` — signals.csv como fonte primaria
- `src/api/predictions.py` — logs expandidos

---

## [2026-04-09] - Frontend polling reduced (health / reconnect)

**What changed:**
- Bot status polling no frontend alterado de 5s para 10s
- Reconexao automatica do WebSocket alterada de 3s para 10s
- Ajuste aplicado em:
  - `command_center/frontend/src/components/dashboard/BotStatus.jsx`
  - `command_center/frontend/src/components/Sidebar.jsx`
  - `command_center/frontend/src/hooks/useWebSocket.js`

**Why:**
- Reduzir spam de requests quando o backend esta parado ou reiniciando
- Evitar flood visual/logico de reconnect agressivo
- Tornar o comportamento do Command Center mais estavel durante restarts

**Consequences:**
- Status pode demorar ate 10s para refletir mudancas
- Reconexao WebSocket tambem passa a esperar 10s apos queda

---

> Dated log of meaningful changes. Most recent at the top.

---

## [2026-04-09] — Session Intelligence (Forex Market Sessions)

**What changed:**
- Novo modulo: `src/features/session.py` — Forex session feature engineering
  - 8 features: session_sydney/tokyo/london/new_york (0/1), overlap_london_ny, overlap_tokyo_london, session_strength (0-3), session_score (0-1)
  - Horarios em UTC: Sydney 22-07, Tokyo 00-09, London 08-17, New York 13-22
  - SESSION_WEIGHTS por ativo (11 pares): pesos refletem relevancia de cada sessao para cada par
  - Funcao vetorizada `add_session_features()` para DataFrames grandes
  - Funcao `get_current_session_info()` para API real-time
- Decision Layer atualizado: threshold adaptativo por sessao
  - score >= 0.6 → threshold * 0.7 (mais agressivo em alta liquidez)
  - 0.3 <= score < 0.6 → threshold normal
  - score < 0.3 → HOLD forcado (evita operar em baixa liquidez)
- Model Selector expandido: selecao por sessao + regime
  - Hierarquia: session+regime → session-only → regime-only → global fallback
  - `_select_by_session()` analisa performance historica por sessao (min 5 trades)
  - `get_primary_session()` retorna sessao mais relevante para o ativo
- Session tracking: `session_metrics.csv` com metricas por sessao/ativo
- API: GET `/api/session/current?symbol=EURUSD`, GET `/api/session/weights`
- Frontend: SessionPanel no Control Tower — score, strength, weights, regime, symbol selector
- Pipeline: session features integradas no execution engine (compute + save)
- Total features: 45 (24 tecnicas/regime + 8 session + 13 news)

**Why:**
- Sessoes Forex tem impacto direto na liquidez, volatilidade e spread
- Operar USDJPY em Tokyo tem resultado diferente de operar em Sydney
- Session score permite filtrar horarios de baixa liquidez automaticamente
- Model selection por sessao permite adaptar estrategia ao horario

**New files:**
- `src/features/session.py`
- `command_center/frontend/src/components/control_tower/SessionPanel.jsx`

**Modified files:**
- `src/features/engineering.py` — SESSION_FEATURE_COLUMNS_LIST, ALL_FEATURE_COLUMNS
- `src/execution/engine.py` — session features + session-aware signals + tracking
- `src/decision/signal.py` — session_score param, threshold adaptation, session_filtered
- `src/decision/model_selector.py` — _select_by_session(), get_primary_session()
- `src/utils/logging.py` — log_session_metrics()
- `src/api/news_regime.py` — /api/session/current, /api/session/weights
- `command_center/frontend/src/services/api.js` — getSessionCurrent, getSessionWeights
- `command_center/frontend/src/pages/ControlTower.jsx` — SessionPanel added

---

## [2026-04-09] — Control Tower (Cyberpunk HUD)

**What changed:**
- Nova pagina principal: `/control-tower` — interface futurista estilo trading desk HUD
- ControlTowerClock.jsx: relogio circular SVG com 4 sessoes Forex (Sydney/Tokyo/London/NY), ponteiro UTC, glow neon nas sessoes ativas
- SignalRadar.jsx: radar circular animado com sweep line, sinais BUY/SELL/HOLD posicionados por confianca, pulso nos pontos
- AICorePanel.jsx: top model, confianca media com barra animada, consenso entre modelos com detecao de divergencia (STRONG/MODERATE/WEAK)
- WorldMap.jsx: globo 3D via react-globe.gl com arcos de fluxo entre moedas, pontos de forca por sentimento de noticias, rotacao automatica
- DataStream.jsx: terminal hacker-style com scroll automatico, logs em tempo real via WebSocket + polling, classificacao por tipo (signal/news/error/trade)
- KPIs reutilizados do Dashboard
- EquityChart reutilizado com lazy loading
- CSS: neon-pulse, radar-sweep, glow-value, data-scroll, dot-pulse, glass-panel, neon-border
- Performance: lazy loading de todos os componentes pesados, memoization de KPIs
- Control Tower agora e primeiro item do sidebar e rota padrao (/)
- Dependencias adicionadas: three.js, react-globe.gl

**Why:**
- Criar interface de leitura rapida do mercado com visualizacao forte e dados reais
- Consolidar sinais, sessoes, performance e inteligencia AI em uma unica tela

**New files:**
- `command_center/frontend/src/pages/ControlTower.jsx`
- `command_center/frontend/src/components/control_tower/ControlTowerClock.jsx`
- `command_center/frontend/src/components/control_tower/SignalRadar.jsx`
- `command_center/frontend/src/components/control_tower/AICorePanel.jsx`
- `command_center/frontend/src/components/control_tower/WorldMap.jsx`
- `command_center/frontend/src/components/control_tower/DataStream.jsx`

**Modified files:**
- `command_center/frontend/src/App.jsx` — added Control Tower route, changed default redirect
- `command_center/frontend/src/components/Sidebar.jsx` — added Control Tower as first nav item
- `command_center/frontend/src/index.css` — added neon/glow animations and glass-panel styles
- `command_center/frontend/package.json` — added three, react-globe.gl dependencies

---

## [2026-04-08] — Decision Layer, Backtest Engine, Feature Experiments & Model Ranking

**What changed:**
- Novo modulo: Decision Layer (src/decision/signal.py) — geracao de sinais BUY/SELL/HOLD
  - Retorno esperado ponderado (t1*0.5 + t2*0.3 + t3*0.2)
  - Confianca baseada em concordancia entre horizontes + magnitude
  - Threshold configuravel + ensemble voting
- Novo modulo: Backtest Engine (src/backtest/engine.py) — simulacao PnL real
  - Entrada no fechamento, saida em t+1 ou t+3
  - Spread por simbolo (tabela realista)
  - Metricas: PnL acumulado, return%, drawdown, winrate, Sharpe ratio, profit factor
  - Equity curve + drawdown chart
  - Salvamento automatico em data/backtest/
- Novo modulo: Feature Experiments (src/research/feature_experiments.py)
  - 4 combinacoes: [technical], [technical+regime], [technical+news], [technical+regime+news]
  - Para cada: treina, preve, avalia, roda backtest
  - Cache de resultados em data/experiments/results.parquet
- Novo modulo: Model Ranking (src/research/model_ranking.py)
  - Score = pnl - (drawdown * 0.5) + (sharpe * 0.3)
  - Ranking global, por simbolo, por feature set
  - Salva em data/experiments/ranking.parquet
- Novo modulo: Model Selector (src/decision/model_selector.py)
  - Auto-selecao de modelo baseada em regime (trend, volatility, range)
  - Analisa trades historicos por regime para escolher melhor modelo
- Novo router API: src/api/backtest_experiments.py (12 endpoints)
  - /api/backtest/results, /summary, /run, /equity
  - /api/experiments/results, /ranking, /ranking/feature-sets, /run
  - /api/models/best, /by-regime, /select
  - /api/signals/latest
- Nova pagina frontend: Backtest (/backtest)
  - Equity curve por modelo, drawdown chart, tabela de trades simulados
  - Botao "Run Backtest", selector de simbolo
- Dashboard atualizado: Best Model card (PnL, Sharpe, Drawdown)
- Models atualizado: ranking por PnL score + ranking por feature set
- Experiments atualizado: feature experiments table + charts comparativos
- Symbols atualizado: melhor modelo por simbolo + melhor modelo por regime
- Pipeline integrado: sinais no ciclo de predicao, auto-backtest a cada 50 ciclos
- Logging expandido: signals.csv, backtest_trades.csv

**Why:**
- Evoluir de previsao pura para sistema completo de decisao + avaliacao financeira
- Permitir selecao automatica de modelos baseada em performance real (PnL)
- Testar automaticamente quais combinacoes de features produzem melhor resultado financeiro

**New files:**
- `src/decision/__init__.py`, `signal.py`, `model_selector.py`
- `src/backtest/__init__.py`, `engine.py`
- `src/research/__init__.py`, `feature_experiments.py`, `model_ranking.py`
- `src/api/backtest_experiments.py`
- `command_center/frontend/src/pages/Backtest.jsx`

**Modified files:**
- `src/execution/engine.py` — signal generation + auto-backtest integration
- `src/utils/logging.py` — log_signal(), log_backtest_trade()
- `command_center/backend/main.py` — mounted backtest_experiments router
- `command_center/frontend/src/App.jsx` — added Backtest route
- `command_center/frontend/src/components/Sidebar.jsx` — added Backtest nav
- `command_center/frontend/src/services/api.js` — 15+ new API methods
- `command_center/frontend/src/pages/Dashboard.jsx` — BestModelCard component
- `command_center/frontend/src/pages/Models.jsx` — PnlRanking component
- `command_center/frontend/src/pages/Experiments.jsx` — FeatureExperiments component
- `command_center/frontend/src/pages/Symbols.jsx` — BestModelForSymbol component
- `README.md` — full documentation update
- `.project/CONTEXT.md`, `.project/CHANGELOG.md`

---

## [2026-04-08] — Market Regime, News Ingestion & LLM Sentiment

**What changed:**
- XAUUSD promovido de fallback para simbolo principal (11 simbolos ativos)
- Novo modulo: regime de mercado (trend, volatility_regime, momentum, range_flag)
- Novo modulo: news ingestion via Investing.com economic calendar (scraping HTML)
- Novo modulo: normalizacao de noticias (country->currency, impact, sentiment_basic)
- Novo modulo: LLM sentiment analysis via HTTP (OpenAI-compatible, Qwen 3.5 9B)
- Sentimento hibrido: 0.7 * LLM + 0.3 * basic com fallback robusto
- Agregacao temporal: janela de 3h passado/futuro por moeda base/quote
- 37 features totais no pipeline (24 tecnicas/regime + 13 news)
- 6 novos endpoints FastAPI: /news/latest, /news/features, /news/llm, /news/by-symbol, /news/analytics, /regime/current
- Frontend: Symbols page com regime + news cards, Overview com sentiment por moeda, nova aba News Analytics
- Loop atualizado: scraping diario + processamento LLM
- Cache em memoria para LLM e news (evita chamadas repetidas)
- Novas deps: beautifulsoup4, arrow, httpx

**Why:**
- Adicionar contexto fundamental (noticias) e regime ao pipeline de predicao ML
- LLM local como feature avancada de sentimento sem dependencia externa

**New files:**
- `src/features/regime.py` — Market regime computation
- `src/data/news/investing.py` — Investing.com calendar scraper
- `src/features/news_features.py` — News normalization + aggregation
- `src/llm/news_sentiment.py` — LLM sentiment via HTTP + cache
- `src/api/news_regime.py` — FastAPI router for news/regime
- `command_center/frontend/src/pages/NewsAnalytics.jsx` — News analytics page

**Modified files:**
- `src/mt5/symbols.py` — XAUUSD moved to DESIRED, added COUNTRY_CURRENCY_MAP
- `src/features/engineering.py` — Added regime, NEWS_FEATURE_COLUMNS, ALL_FEATURE_COLUMNS
- `src/execution/engine.py` — Integrated news loading + regime logging
- `src/execution/loop.py` — Daily news pipeline
- `command_center/backend/main.py` — Mounted news_regime router
- Frontend: App.jsx, Sidebar.jsx, Symbols.jsx, Overview.jsx, News.jsx, api.js

---

## [2026-04-07] — Inicializacao do projeto

**What changed:**
- Criacao da estrutura .project/ com documentacao completa
- Configuracao do .gitignore
- Criacao do .env com credenciais MT5 demo
- Git init
- Definicao das decisoes arquiteturais iniciais (CPCV, Python+MT5, S3, LLM local)

**Why:**
- Setup inicial do projeto de trading algoritmico FOREX M1

**Session log:** `sessions/2026-04-07-project-init.md`

---
