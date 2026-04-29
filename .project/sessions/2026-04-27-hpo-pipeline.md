# Session: 2026-04-27 — HPO Pipeline + LLM Search Space Advisor

## What we built

Full 24/7 hyperparameter optimisation pipeline with LLM-driven search space adjustment.

### Problem

Models used hardcoded hyperparameters in `engine.py` (max_depth=4, etc.) and never
improved them automatically. Agent researcher generated hypotheses about *when* to use
signals but knew nothing about *how* the models were configured.

### Solution: two-loop architecture

**Loop rápido (Optuna, scheduler 04:00 UTC):**
- `src/training/hpo_objective.py` — CPCV-based objective, penalises overfit gap above 10%
- `src/training/hpo_store.py` — SQLite via Optuna + champion JSON files per (model, group)
- `src/training/hpo_runner.py` — round-robin over (model × symbol_group), loads cached features
- `src/training/promoter.py` — champion/challenger logic (MIN_IMPROVEMENT=0.5pp, MAX_CHAMPION_DAYS=60)

**Loop lento (LLM, scheduler 03:00 UTC — within agent researcher):**
- `src/agent_researcher/hpo_context.py` — loads champions + top trials + param patterns
- `src/agent_researcher/search_space_advisor.py` — LLM narrows Optuna search ranges
- `src/agent_researcher/llm_interface.py` — added `call()` reusable method

**Integration:**
- `hypothesis_generator.py` now includes `hpo_summary` in LLM context
- `orchestrator.py` calls `SearchSpaceAdvisor.advise()` after each cycle
- `registry.py:create_all_models(symbol)` reads champion params when available (falls back to defaults)
- `scripts/run_hpo.py` + scheduler job at 04:00 UTC (2h timeout)

### Key design decisions

- LLM never drives Optuna trial-by-trial — only adjusts search *bounds* nightly
- `_validate_param_spec` enforces that LLM can only narrow ranges, never widen them
- `SYMBOL_TO_GROUP` maps each of 11 symbols to one of 4 groups (yen_crosses, dollar_majors, crosses, commodities)
- Champion stored as JSON; `registry.py` reads it lazily at model instantiation time

### Tests added

- `tests/training/` (new package): 30 tests covering hpo_store, hpo_objective, promoter
- `tests/agent_researcher/test_search_space_advisor.py`: 13 tests
- `tests/models/test_registry.py`: 2 new tests for champion params
- `tests/agent_researcher/test_llm_interface.py`: 2 new tests for `call()`
- Total new: ~47 tests. Suite: 498+ passed, 0 failures.

### Code quality issues found and fixed

- Removed dead code: `_PARAM_SUGGESTERS` dict in `hpo_objective.py`
- Removed duplicate import of `SYMBOL_GROUPS` inside `_load_xy_for_group`

## What to do next

- First nightly run will have no champion data (expected) — models use defaults
- After ~20 trials per study, promoter starts evaluating candidates
- Monitor `data/hpo/studies.db` and `data/hpo/champions/` after first run
- If symbol group has no cached features parquet, study is skipped gracefully — check logs
