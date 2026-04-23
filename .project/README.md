# AutoTrader

> Sistema de trading algoritmico para FOREX em M1 (1 minuto), utilizando ML, LLM local e integracao com MetaTrader 5.

---

## What is this?

Plataforma automatizada de trading para o mercado FOREX. Combina multiplos algoritmos de ML com uma LLM local para analise de noticias e contexto de mercado. O sistema coleta, armazena e processa candles, treina modelos com validacao rigorosa, executa operacoes via MetaTrader 5 e expoe um Command Center com temas visuais selecionaveis.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python |
| Broker Integration | MetaTrader 5 (mt5 python lib) |
| ML/DL | scikit-learn, XGBoost, LightGBM, PyTorch |
| LLM | Qwen 3.5 9B local |
| Storage | AWS S3 + parquet local |
| Data | pandas, numpy |
| Validacao | CPCV com purge e embargo |
| News | Investing.com economic calendar |
| Config | python-dotenv (.env) |
| Frontend | React + Vite + Tailwind + theme system |

---

## Navigation

| File | What's inside |
|---|---|
| `CONTEXT.md` | Current project state - start here every session |
| `DECISIONS.md` | Why things are built the way they are |
| `SETUP.md` | How to run this locally |
| `CHANGELOG.md` | History of what changed |
| `sessions/` | Per-session problem logs |
| `master-prompts/` | Step-by-step implementation prompts |

---

## Current Phase

Active development - sistema completo com previsao, decisao, backtest, ranking, selecao automatica de modelos, session intelligence e Control Tower HUD.

## Operational Notes

- Frontend bot status polling: 10s
- WebSocket reconnect interval: 10s
- Tema Matrix agora e um modo terminal dedicado, sem alterar Default/Cyberpunk
- Data Stream no Matrix foi promovido para visual de terminal hacker real
- Todos os componentes do Control Tower seguem o padrao Matrix (Forex Sessions, Session Intelligence, Signal Board, AI Core, LivePredictionChart, WorldMap, DataStream)
- Candles no Matrix: up=#00ff41, down=#006622, previstos verde transparente

---

## Ativos Alvo (Top 10 FOREX + Gold)

1. EUR/USD
2. GBP/USD
3. USD/JPY
4. USD/CHF
5. AUD/USD
6. USD/CAD
7. NZD/USD
8. EUR/GBP
9. EUR/JPY
10. GBP/JPY
11. XAU/USD (Gold)

---

## Out of Scope

- Trading em timeframes acima de M1 (por enquanto)
- Mercados fora de FOREX (acoes, crypto)
- Deploy em cloud do sistema de execucao
