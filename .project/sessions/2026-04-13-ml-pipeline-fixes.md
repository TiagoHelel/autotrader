# Session — 2026-04-13 · ML Pipeline Critical Fixes (Look-ahead, CPCV, Regularization)

_Type: refactor_

---

## Problem

O pipeline de ML tinha 3 problemas criticos que invalidavam os resultados:
1. **Look-ahead bias:** janela de noticias usava dados futuros (`current_time + 3h`), feature `minutes_to_next_news` usava futuro
2. **Validacao incorreta:** split simples 80/20 sem purge/embargo, causando data leakage em series temporais
3. **Overfitting estrutural:** XGBoost sem early stopping, RF sem regularizacao, sem metricas de overfitting

---

## Context loaded

- CONTEXT.md: Sistema completo com 45 features, 5 modelos, CPCV como blocker pendente desde decisao [001]
- DECISIONS.md: Decisao [001] definia CPCV como obrigatorio mas ainda nao estava implementado
- Previous sessions: Signal Board + Matrix Theme (visual, nao ML)

---

## Approach

1. **Explorar codebase completo** — entender todos os arquivos envolvidos antes de mudar qualquer coisa
2. **Perguntar ao usuario** — 4 perguntas de clarificacao (CPCV config, API router, feature importance scope, future news handling)
3. **Corrigir look-ahead bias primeiro** — mais critico, invalida tudo downstream
4. **Implementar CPCV** — modulo separado, depois integrar no engine
5. **Regularizacao e early stopping** — parametros conservadores baseados em boas praticas
6. **Overfitting detection** — modulo separado com threshold e logging
7. **Feature importance** — tracking automatico para XGBoost e RF
8. **API + Frontend** — expor metricas de validacao e mostrar no Models page
9. **Atualizar docs** — README, CONTEXT, CHANGELOG, DECISIONS

---

## What didn't work and why

- N/A — implementacao seguiu o plano sem problemas tecnicos. O principal risco era quebrar o pipeline existente, mas as mudancas foram cirurgicas.

---

## Decision made

- [x] Yes -> added to `DECISIONS.md` as #013 (look-ahead bias elimination) and #014 (regularizacao obrigatoria)
- [x] Decision #001 status atualizado de "decided" para "implemented"

---

## Files changed

### Novos
- `src/evaluation/cpcv.py` — CPCV com purge + embargo (Marcos Lopez de Prado)
- `src/evaluation/overfitting.py` — deteccao de overfitting + persistencia de resultados de validacao
- `src/evaluation/feature_importance.py` — tracking de feature importance (gain/impurity)

### Modificados
- `src/features/news_features.py` — janela `[t-3h, t]` (era `[t-3h, t+3h]`), removido `minutes_to_next_news`
- `src/features/engineering.py` — NEWS_FEATURE_COLUMNS atualizado (13→12)
- `src/models/xgboost_model.py` — regularizacao (subsample, colsample, reg_lambda, max_depth 6→4) + early stopping (20 rounds)
- `src/models/random_forest.py` — regularizacao (min_samples_leaf=10, max_depth 10→8)
- `src/models/registry.py` — defaults atualizados para novos parametros
- `src/execution/engine.py` — CPCV integrado, feature importance, overfitting detection, treino com dados completos apos validacao
- `src/api/predictions.py` — 2 novos endpoints (models/validation, models/feature-importance)
- `command_center/frontend/src/pages/Models.jsx` — CPCV score, stability, overfit warning, tabela de validacao
- `command_center/frontend/src/services/api.js` — 2 novos metodos API
- `README.md` — features 45→44, modelos atualizados, secao de validacao
- `.project/CONTEXT.md` — estado atualizado
- `.project/CHANGELOG.md` — entrada detalhada
- `.project/DECISIONS.md` — decisoes #013, #014, update #001

---

## Result

**Completo.** Todas as 11 partes implementadas:
1. Look-ahead bias eliminado
2. CPCV modulo criado
3. CPCV integrado no pipeline
4. Early stopping ativo no XGBoost
5. Regularizacao aplicada (XGB + RF)
6. Feature importance tracking
7. Overfitting detection com warnings
8. Logging de CPCV/treino
9. API `/api/predict/models/validation` e `/models/feature-importance`
10. Frontend Models com CPCV score, overfit warnings, stability
11. Docs atualizados (README, .project)

---

## What the next session should know

- **Accuracy e PnL vao cair apos esta correcao** — isso e esperado e desejavel. O modelo antigo estava "trapaceando" com dados futuros.
- O CPCV usa direction accuracy entre horizontes consecutivos como metrica. Se necessario, pode ser refinado para usar current_price como referencia (requer mudanca no `run_cpcv`).
- Feature importance agora e trackada — verificar quais features dominam e considerar remover features de baixa importancia em sessao futura.
- Early stopping logs indicam quantos rounds o XGBoost realmente precisa — pode ajudar a calibrar `n_estimators`.
