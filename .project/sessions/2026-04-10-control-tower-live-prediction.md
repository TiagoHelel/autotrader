# Session — Control Tower KPI reorg + Live Prediction Chart

**Date:** 2026-04-10
**Goal:** Reorganizar KPIs (6→7 cards, mini sparkline 30d) e transformar o gráfico central da Control Tower em "Live Price + Model Prediction" (candles reais + 3 candles previstos via ensemble).

---

## What was done

### Backend
- `src/api/predictions.py`: novo endpoint `GET /api/predict/predictions/latest?symbol=X`
  - Lê o último timestamp de `data/predictions/{symbol}.parquet`
  - Calcula ensemble = média dos modelos para `pred_t1/t2/t3`
  - Calcula `confidence = 1 - (dispersão entre modelos / current_price * 500)` (clamp [0,1])
  - Retorna: `symbol, timestamp, current_price, ensemble, models[], n_models, confidence`

### Frontend
- `services/api.js`: `getLatestPrediction(symbol)` adicionado.
- `components/dashboard/KPICards.jsx`: grid `xl:grid-cols-6` → `xl:grid-cols-7`. Card #7 = `<TrendSparklineCard label="30D Trend" />`.
- `components/dashboard/TrendSparklineCard.jsx`: NOVO. SVG sparkline (sem eixos), gradient fill + glow neon, cor por sinal (verde/vermelho), variação % no rodapé. Fonte: `/api/equity/history` (60s).
- `components/control_tower/LivePredictionChart.jsx`: NOVO. Usa `lightweight-charts`.
  - Fetch paralelo: candles (10) + latest prediction (60s polling, sincronizado com loop M5)
  - Constrói candles previstos: `open=prev_close, close=ensemble_tN, high=max, low=min`
  - 2 séries de candlestick: real (verde/vermelho) + previsto (azul/roxo, semi-transparente)
  - Marker "NOW" no último candle real
  - Tooltip custom (OHLC real + ensemble + confidence)
  - Barra de confidence no header
  - Empty/error/waiting fallbacks
  - `memo()` para evitar re-renders quando o pai re-renderiza
- `components/control_tower/SessionPanel.jsx`: aceita props `selectedSymbol` + `onSymbolChange` (controlled), com fallback interno mantido.
- `pages/ControlTower.jsx`: estado `selectedSymbol` lifted; SessionPanel + LivePredictionChart compartilham. EquityChart removido da row central (agora vive como sparkline no KPI strip).

### Build
- `npm install lightweight-charts` (added 2 packages, no vulns).
- `npm run build` ✅. Novo chunk lazy `LivePredictionChart-*.js` ~163 KB (52 KB gzip).

---

## Decisions made
- **Ensemble único** (não múltiplas linhas) — registrado em DECISIONS.md [007]
- **lightweight-charts** em vez de Recharts custom — registrado em DECISIONS.md [008]
- **State lifting na ControlTower page** (não Context global) — escopo limitado, simples
- **Sparkline data source** = `/api/equity/history` (mesma do EquityChart antigo)
- **Backend ensemble endpoint** (não compute no frontend) — JSON pronto, menos lógica duplicada

---

## Next session pickup
- Considerar adicionar **WebSocket push** para predições novas (em vez de polling 60s)
- Adicionar **histórico de previsões vs realizado** no LivePredictionChart (overlay de erro)
- Avaliar se o `confidence` de fórmula heurística deve ser substituído por algo do tracker
- Monitorar bundle: o chunk lazy de lightweight-charts está OK, mas o `index.js` principal está em 774KB — candidatos a code-split
