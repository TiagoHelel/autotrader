# Coverage Plan — Meta 80%

> Baseline medido em **2026-04-15** com `pytest-cov` (Python) e `@vitest/coverage-v8` (frontend). Gate de 80% NAO esta ativo ainda — vira quando chegarmos la por modulo/global.

## Baseline

| Camada | Lines | Branches |
|---|---:|---:|
| Python (src/) | **42%** | — |
| Frontend (command_center/frontend/src/) | **15.5%** | 7.9% |

Relatorios HTML: `coverage_html_python/index.html`, `command_center/frontend/coverage/index.html`.

---

## Priorizacao (alta → baixa)

Criterio: **risco x facilidade**. Modulos que decidem trade ou validam modelo ganham prioridade.

### 🔴 P0 — Critico, sem teste direto

| Modulo | Cov | Porque importa | Esforco |
|---|---:|---|---|
| ~~`src/evaluation/cpcv.py`~~ | ~~**0%**~~ → **96%** ✅ (2026-04-15, 16 testes) | Decisao arquitetural [001]. Toda validacao de modelo depende disso. | DONE |
| ~~`src/decision/model_selector.py`~~ | ~~**0%**~~ → **84%** ✅ (2026-04-15, 17 testes) | Escolhe qual modelo dispara o trade. | DONE |
| ~~`src/decision/signal.py`~~ | ~~40%~~ → **99%** ✅ (2026-04-15, 25 testes, bug corrigido) | Converte predicao em BUY/SELL/HOLD. | DONE |
| ~~`src/backtest/engine.py`~~ | ~~12%~~ → **99%** ✅ (2026-04-15, 24 testes) | Simulacao de PnL, base do ranking. | DONE |

### 🟡 P1 — Gaps importantes

| Modulo | Cov | Esforco |
|---|---:|---|
| ~~`src/api/backtest_experiments.py`~~ | ~~22%~~ → **92%** ✅ (2026-04-16, 31 testes) | DONE |
| ~~`src/evaluation/evaluator.py`~~ | ~~22%~~ → **99%** ✅ (2026-04-15, 17 testes) | DONE |
| ~~`src/evaluation/overfitting.py`~~ | ~~19%~~ → **100%** ✅ (2026-04-15, 14 testes) | DONE |
| ~~`src/evaluation/feature_importance.py`~~ | ~~23%~~ → **97%** ✅ (2026-04-15, 9 testes) | DONE |
| ~~`src/research/feature_experiments.py`~~ | ~~0%~~ → **95%** ✅ (2026-04-16, 26 testes) | DONE |

### ⚫ P2 — Dependem de recursos externos (MT5, LLM)

| Modulo | Cov | Nota |
|---|---:|---|
| ~~`src/mt5/connection.py`~~ | ~~23%~~ → **99%** ✅ (2026-04-16, 25 testes) | DONE |
| ~~`src/llm/news_sentiment.py`~~ | ~~18%~~ → **71%** ✅ (2026-04-16, 32 testes) | DONE |
| ~~`src/execution/engine.py`~~ | ~~0%~~ → **45%** ✅ (2026-04-16, 16 testes) | DONE |
| ~~`src/execution/loop.py`~~ | ~~0%~~ → **58%** ✅ (2026-04-16, 11 testes) | DONE |

### Frontend — P0 (paginas de decisao)

| Arquivo | Cov | Nota |
|---|---:|---|
| ~~`pages/Positions.jsx`~~ | ~~0%~~ → **100%** ✅ (2026-04-16, 2 testes) | DONE |
| ~~`pages/AIModel.jsx`~~ | ~~0%~~ → **100%** ✅ (2026-04-16, 2 testes) | DONE (stub proxied, páginas compostas) |
| ~~`pages/Dashboard.jsx`~~ | ~~0%~~ → **100%** ✅ (2026-04-16, 8 testes) | DONE |
| ~~`pages/Backtest.jsx`~~ | ~~3%~~ → **50%** ✅ (2026-04-16, 8 testes) | DONE |
| ~~`hooks/useWebSocket.js`~~ | ~~0%~~ → **95%** ✅ (2026-04-16, 9 testes) | DONE |

### Frontend — P1 (widgets principais)

| Arquivo | Cov |
|---|---:|
| ~~`components/control_tower/SignalRadar.jsx`~~ | ~~0%~~ → **91%** ✅ | DONE |
| `components/control_tower/WorldMap.jsx` | 2% | |
| ~~`components/control_tower/AICorePanel.jsx`~~ | ~~1%~~ → **64%** ✅ | DONE |
| ~~`components/control_tower/SessionPanel.jsx`~~ | ~~6%~~ → **92%** ✅ | DONE |
| ~~`components/control_tower/DataStream.jsx`~~ | ~~1%~~ → **63%** ✅ | DONE |
| ~~`components/dashboard/EquityChart.jsx`~~ | ~~0%~~ → **57%** ✅ | DONE |
| ~~`components/dashboard/ModelDecision.jsx`~~ | ~~4%~~ → **85%** ✅ | DONE |
| ~~`components/news/*`~~ | ~~0%~~ → **100%** ✅ | DONE |
| ~~`components/positions/*`~~ | ~~0–3%~~ → **86%** ✅ | DONE |

---

## Como rodar

```bash
# Python
source venv/Scripts/activate
pytest tests/ --cov=src --cov-report=term --cov-report=html:coverage_html_python

# Frontend
cd command_center/frontend
npm run test:coverage   # equivalente: npx vitest run --coverage
```

## Quando ligar o gate de 80%

- **Por modulo:** assim que um modulo passa 80%, adicionar no `pyproject.toml`/`vite.config.js` um check que nao deixa regredir.
- **Global:** somente quando baseline global >= 80% — sem forcar antes.

## Log de progresso

| Data | Python | Frontend | Nota |
|---|---:|---:|---|
| 2026-04-15 | 42% | 15.5% | Baseline inicial |
| 2026-04-15 | **44%** | 15.5% | +16 testes em `tests/evaluation/test_cpcv.py` — CPCV 0% → **96%** |
| 2026-04-15 | **47%** | 15.5% | +17 testes em `tests/decision/test_model_selector.py` — model_selector 0% → **84%** |
| 2026-04-15 | **48%** | 15.5% | +25 testes em `tests/decision/test_signal.py` — signal 40% → **99%** + fix bug (dict branch inalcancavel) |
| 2026-04-15 | **51%** | 15.5% | +24 testes em `tests/backtest/test_engine.py` — backtest/engine 12% → **99%**. Todos os P0 Python fechados. |
| 2026-04-15 | **56%** | 15.5% | +40 testes em `tests/evaluation/` — overfitting 19%→**100%**, evaluator 22%→**99%**, feature_importance 23%→**97%**. 3/5 P1 Python fechados. |
| 2026-04-16 | **64%** | 15.5% | +57 testes: backtest_experiments 22%→**92%** (31t), feature_experiments 0%→**95%** (26t). **Todos P1 Python fechados.** |
| 2026-04-16 | **75%** | 15.5% | +84 testes P2: mt5/connection 23%→**99%** (25t), llm/news_sentiment 18%→**71%** (32t), execution/engine 0%→**45%** (16t), execution/loop 0%→**58%** (11t). **Todos P2 Python fechados.** |
| 2026-04-16 | 75% | **22%** | +29 testes Frontend P0: Positions/AIModel→**100%**, Dashboard→**100%**, Backtest→**50%**, useWebSocket→**95%**. **Todos frontend P0 fechados.** |
| 2026-04-16 | 75% | **38%** | +34 testes Frontend P1: SignalRadar→**91%**, SessionPanel→**92%**, AICorePanel→**64%**, DataStream→**63%**, EquityChart→**57%**, ModelDecision→**85%**, news→**100%**, positions→**86%**. **Todos frontend P1 fechados (exceto WorldMap).** |
| 2026-04-16 | 75% | **62%** | +35 testes páginas: News→**69%**, NewsAnalytics→**73%**, Logs→**85%**, Overview→**77%**, Models→**83%**, Experiments→**52%**, Symbols→**41%** + widgets: BotStatus, LogPanel, ControlTowerClock. **Global pages 62%.** |
| 2026-04-16 | 75% | **64.5%** | +24 testes `services/api.js` (HTTP helpers) → **61%**. **148 testes total passando em 19 arquivos. Frontend subiu 15.5% → 64.5% lines (+49 pontos).** |
