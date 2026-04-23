# AutoTrader - FOREX Algorithmic Trading System

Sistema completo de trading algoritmico para FOREX e commodities (ouro) com predicao multi-modelo, analise de sentimento via LLM, regime de mercado e dashboard em tempo real.

---

## Visao Geral

O AutoTrader e um sistema end-to-end que:

1. **Coleta dados** de candles M5 via MetaTrader 5
2. **Gera 44 features** (tecnicas, regime, sessoes, noticias — sem look-ahead bias)
3. **Treina 5 modelos** de ML com regularizacao e early stopping
4. **Valida com CPCV** (Combinatorial Purged Cross-Validation, 5 folds, 2% embargo)
5. **Detecta overfitting** automaticamente (train vs validation gap)
6. **Preve precos** futuros (t+1, t+2, t+3)
7. **Gera sinais** de trade automaticamente (BUY/SELL/HOLD) com session awareness
8. **Detecta sessoes** Forex ativas e adapta comportamento por ativo/horario
9. **Simula backtest** com PnL real, spread e metricas financeiras
10. **Testa features** automaticamente em diferentes combinacoes
11. **Rankeia modelos** por score composto (PnL, Sharpe, Drawdown)
12. **Seleciona modelos** automaticamente por regime de mercado E sessao
13. **Avalia performance** com metricas de direcao, MAE e MAPE
14. **Tracked feature importance** (XGBoost gain + RF impurity)
15. **Analisa noticias** do calendario economico (Investing.com)
16. **Processa sentimento** via LLM local (Qwen 3.5 9B) com fallback heuristico
17. **Expoe tudo via API** REST (FastAPI, 36+ endpoints)
18. **Visualiza** em dashboard React com 12 paginas (incluindo Control Tower HUD + Session Intelligence + Live Prediction Chart)
19. **Descobre edges condicionais** (`conditional_analysis`) com protecoes anti-snooping: holdout temporal, filter log, Bonferroni automatica, Wilson CI95, binomial p-value

---

## Arquitetura

```
MT5 Terminal
    |
    v
MT5Connection.get_candles() -----> data/raw/{symbol}.parquet
    |
    v
compute_features() (20 tecnicas) + compute_market_regime() (4 regime)
    |
    v
add_session_features() (8 session) -----> session_score por ativo
    |
    v
build_news_features() (12 news, ex-ante/ex-post embargo) -----> 44 features totais
    |
    v
CPCV validation (5 folds, purge+embargo) -----> cpcv_score, overfit_gap
    |
    v
ModelRegistry.train_all() -----> 5 modelos (regularizados, early stopping)
    |
    v
ModelRegistry.predict_all() -----> pred_t1, pred_t2, pred_t3
    |
    v
generate_signals(session_score) -> BUY / SELL / HOLD (session-filtered + ensemble)
    |
    v
evaluate_predictions() -----> data/metrics/{symbol}.parquet
    |
    v
run_backtest() -----> PnL, Sharpe, Drawdown, Winrate
    |
    v
rank_models() -----> score = pnl - (dd*0.5) + (sharpe*0.3)
    |
    v
select_model(session) --> melhor modelo por regime + sessao
    |
    v
FastAPI (32+ endpoints) + WebSocket -----> React Dashboard (12 paginas)
```

---

## Simbolos Suportados

### Primarios (11)
| Simbolo | Descricao |
|---------|-----------|
| EURUSD  | Euro / US Dollar |
| GBPUSD  | British Pound / US Dollar |
| USDJPY  | US Dollar / Japanese Yen |
| USDCHF  | US Dollar / Swiss Franc |
| AUDUSD  | Australian Dollar / US Dollar |
| USDCAD  | US Dollar / Canadian Dollar |
| NZDUSD  | New Zealand Dollar / US Dollar |
| EURGBP  | Euro / British Pound |
| EURJPY  | Euro / Japanese Yen |
| GBPJPY  | British Pound / Japanese Yen |
| XAUUSD  | Gold / US Dollar |

### Fallback
AUDCAD, AUDNZD, EURCHF, EURAUD

---

## Features Pipeline (44 totais)

### Features Tecnicas (20)
| Feature | Descricao |
|---------|-----------|
| open, high, low, close, tick_volume | OHLCV raw |
| return_simple, return_log | Retornos de preco |
| rsi_14 | Relative Strength Index (14 periodos) |
| ema_9, ema_21, ema_50, ema_200 | Medias moveis exponenciais |
| atr_14 | Average True Range (volatilidade) |
| vol_10, vol_20 | Volatilidade rolling (std dev) |
| spread_feature | Bid-ask spread |
| hour_sin, hour_cos | Hora do dia (encoding ciclico) |
| ema_50_200_diff | Cruzamento EMA longo prazo |
| ema_9_21_diff | Cruzamento EMA curto prazo |

### Features de Regime (4)
| Feature | Descricao |
|---------|-----------|
| trend | EMA50 > EMA200 = 1 (bull), < = -1 (bear) |
| volatility_regime | std_20 normalizada: 0 (baixo), 1 (medio), 2 (alto) |
| momentum | Retorno acumulado ultimos 10 candles |
| range_flag | ATR baixo + baixa variacao = 1 (lateral) |

### Features de Noticias (12)
| Feature | Tipo | Descricao |
|---------|------|-----------|
| news_sentiment_base | ex-post | Sentimento medio moeda base (basic, via greenFont/redFont) |
| news_sentiment_quote | ex-post | Sentimento medio moeda quote (basic) |
| news_impact_base | ex-ante | Soma impacto moeda base |
| news_impact_quote | ex-ante | Soma impacto moeda quote |
| news_llm_sentiment_base | ex-post | Sentimento LLM moeda base |
| news_llm_sentiment_quote | ex-post | Sentimento LLM moeda quote |
| news_volatility_base | ex-post | Impacto volatilidade LLM base |
| news_volatility_quote | ex-post | Impacto volatilidade LLM quote |
| minutes_since_last_news | ex-ante | Minutos desde ultima noticia (horario agendado) |
| high_impact_flag | ex-ante | 1 se ha noticia de alto impacto |
| news_sentiment_final_base | ex-post | Hibrido: 0.7*LLM + 0.3*basic (base) |
| news_sentiment_final_quote | ex-post | Hibrido: 0.7*LLM + 0.3*basic (quote) |

> **Anti look-ahead bias (duas janelas):**
> - **Ex-ante** (impact, schedule): usa `timestamp <= current_time`. Horario e importancia sao publicados no calendario antes da release.
> - **Ex-post** (sentiment, LLM): usa `timestamp + NEWS_POST_RELEASE_LAG_MIN <= current_time` (default 5 min). O `signal` (greenFont/redFont) so e conhecido **apos** a divulgacao do `actual`; o embargo modela a latencia de disseminacao e evita que o modelo "veja" o resultado da release no proprio instante agendado.
>
> Configuravel via env `NEWS_POST_RELEASE_LAG_MIN` ou override explicito em `build_news_features(..., post_release_lag_min=N)`. `minutes_to_next_news` continua removido (usava futuro).

### Features de Sessao (8)
| Feature | Descricao |
|---------|-----------|
| session_sydney | 1 se Sydney ativa (22:00-07:00 UTC) |
| session_tokyo | 1 se Tokyo ativa (00:00-09:00 UTC) |
| session_london | 1 se London ativa (08:00-17:00 UTC) |
| session_new_york | 1 se New York ativa (13:00-22:00 UTC) |
| session_overlap_london_ny | 1 se London + NY overlap (13:00-17:00 UTC) |
| session_overlap_tokyo_london | 1 se Tokyo + London overlap (08:00-09:00 UTC) |
| session_strength | 0-3: quantidade de sessoes ativas |
| session_score | 0-1: score ponderado por ativo (SESSION_WEIGHTS) |

**Session Weights por Ativo:**
- EURUSD: London=0.9, NY=0.8, Tokyo=0.2, Sydney=0.1
- USDJPY: Tokyo=0.95, NY=0.6, London=0.5, Sydney=0.3
- AUDUSD: Sydney=0.9, Tokyo=0.7, NY=0.5, London=0.4
- XAUUSD: NY=0.9, London=0.85, Tokyo=0.3, Sydney=0.15
- *(pesos completos em `src/features/session.py`)*

**Comportamento Adaptativo:**
- `session_score >= 0.6` → threshold reduzido em 30% (mais sinais em alta liquidez)
- `0.3 <= session_score < 0.6` → threshold normal
- `session_score < 0.3` → HOLD forcado (evita operar em baixa liquidez)

---

## Modelos de ML (5)

| Modelo | Tipo | Descricao |
|--------|------|-----------|
| naive | Baseline | Repete ultimo close para t+1, t+2, t+3 |
| linear | Regressao Linear | Ridge regression (alpha=1.0) |
| random_forest | Ensemble | 100 estimadores, max_depth=8, min_samples_leaf=10 |
| xgboost | Gradient Boosting | 200 estimadores, lr=0.1, depth=4, subsample=0.7, colsample=0.7, reg_lambda=1.0, early_stopping=20 |
| ema_heuristic | Regra | EMA50 vs EMA200 + momentum factor |

**Input:** 10 candles x N features (flattened)
**Output:** 3 precos futuros (t+1, t+2, t+3 candles M5)

### Validacao (CPCV)
- **Metodo:** Combinatorial Purged Cross-Validation (Marcos Lopez de Prado)
- **Folds:** 5 splits temporais
- **Embargo:** 2% do dataset apos cada bloco de teste
- **Metricas:** mean_accuracy, std_accuracy (estabilidade), overfit_gap (train - val)
- **Early Stopping (XGBoost):** para treino quando val_loss para de melhorar (20 rounds)
- **Overfitting Detection:** warning automatico quando gap > 10%
- **Feature Importance:** salva gain (XGBoost) e impurity (RF) em `data/metrics/feature_importance.parquet`

---

## Research & Edge Discovery (`conditional_analysis`)

Modelos base em FX M5 raramente tem edge **em media** (val_acc ~48-50%, coin flip). Edge real costuma existir **condicional** a regime, hora, sessao, confidence. O modulo `src/research/conditional_analysis.py` fornece um framework honesto pra testar essas hipoteses sem auto-enganacao por multiple testing.

### Conceito

1. **Gera um research dataset** juntando predicoes salvas + candles raw + contexto (sessao, regime, hora, confidence). Reusa o que ja existe — nao re-treina, nao re-preve.
2. **Split holdout temporal** (default: ultimos 20%). Holdout fica inviolado ate validacao final.
3. **Testa filtros** (symbol, hour, session, regime, confidence_min) e recebe metricas + p-value + verdict.
4. **Protecoes anti-snooping automaticas:** filter log persistente, Bonferroni correction, bloqueio de reuso do holdout.

### 3 funcoes publicas

| Funcao | Uso |
|---|---|
| `build_prediction_dataset(symbols, start, end, model)` | Gera parquet em `data/research/predictions_{model}_{timestamp}.parquet`. Uma vez; reaproveita em todas as analises. |
| `split_holdout(df, holdout_pct=0.20, method="temporal")` | Split temporal (default) ou random. Retorna `(df_research, df_holdout)`. |
| `evaluate_filter(df, filters, hypothesis, holdout=False)` | Aplica filtros, printa sumario, persiste no log, retorna `FilterResult`. |

### Filtros suportados

```python
filters = {
    "symbol": "XAUUSD",               # exact match
    "model": "xgboost",               # exact match
    "hour_utc": (14, 15),             # [min, max), 24h
    "session": "london_ny_overlap",   # ou list[str] para OR logico
    "signal": "BUY",                  # ou list[str]
    "trend": 1,                       # 1=bull, -1=bear, 0=neutral
    "volatility_regime": 2,           # 0=baixo, 1=medio, 2=alto
    "confidence": (0.80, 1.0),        # faixa
    "confidence_min": 0.85,           # atalho
    "session_score": (0.6, 1.0),      # faixa
}
```

### Verdicts

| Verdict | Criterio | Acao |
|---|---|---|
| `REJECTED_N` | N = 0 apos filtro | Relaxe o filtro |
| `UNDERPOWERED` | N < 30 | Mais dados ou menos filtros |
| `REJECTED_WR` | WR <= 50% | Hipotese refutada |
| `WEAK` | WR > 50% mas CI95 inclui 50% | Inconclusivo — mais dados |
| `PROMISING` | CI95 > 50% e p < 0.05 | Candidato a validar no holdout |
| `STRONG` | CI95 > 50% e p < 0.01 | Idem, alta confianca |

### Fluxo tipico (passo a passo)

**1. Gera o dataset (uma vez):**
```bash
python -m src.research.conditional_analysis build \
    --symbols XAUUSD,EURUSD,USDJPY \
    --start 2025-01-01 --end 2026-04-01 \
    --model xgboost
```
Saida: `data/research/predictions_xgboost_{timestamp}.parquet`.

**2. Exploracao (Python script / Jupyter):**
```python
import pandas as pd
from src.research.conditional_analysis import split_holdout, evaluate_filter

df = pd.read_parquet("data/research/predictions_xgboost_20260414_103000.parquet")
df_research, df_holdout = split_holdout(df, holdout_pct=0.20)

evaluate_filter(
    df_research,
    filters={"symbol": "XAUUSD", "hour_utc": (14, 15), "confidence_min": 0.85},
    hypothesis="London fix + NY open criam fluxo direcional em XAU",
)
```

Printa no stdout:
```
[FILTER] symbol=XAUUSD, hour_utc=(14, 15), confidence_min=0.85
  Hypothesis: London fix + NY open criam fluxo direcional em XAU
  N=142 | WR=58.0% [49.0-66.0%] | PnL_net=1.8 pips/trade | Sharpe=0.91 | MaxDD=-24.0 pips
  p-value vs coinflip: 0.031
  Bonferroni ajustado (12 testes previos): p = 0.403 → NAO significativo
  Verdict: PROMISING
```

**3. Validacao final no holdout (UMA VEZ por filtro aprovado):**
```python
evaluate_filter(
    df_holdout,
    filters={"symbol": "XAUUSD", "hour_utc": (14, 15), "confidence_min": 0.85},
    hypothesis="validacao final h1",
    holdout=True,
)
```
Se tentar rodar o mesmo `filter_hash` no holdout duas vezes, dispara warning e invalida o resultado.

**4. Via CLI (alternativa):**
```bash
python -m src.research.conditional_analysis test \
    --dataset data/research/predictions_xgboost_20260414.parquet \
    --filter '{"symbol":"XAUUSD","hour_utc":[14,15],"confidence_min":0.85}' \
    --hypothesis "NY open flow em XAU"
```
Flag `--holdout` valida no holdout; sem a flag, usa df_research.

### Regra de ouro: hipotese **antes** do teste

O log so protege se voce usar honestamente. Formular a hipotese depois de olhar os numeros (HARKing — *hypothesizing after results known*) derrota todas as protecoes.

### Persistencia

| Arquivo | Conteudo |
|---|---|
| `data/research/predictions_{model}_{timestamp}.parquet` | Research dataset (predictions + outcomes + contexto) |
| `data/research/filter_log.parquet` | Log de TODOS os testes: timestamp, filter_hash, filters_json, hypothesis, metricas, holdout flag |
| `data/research/holdout_usage.parquet` | Historico de filter_hashes validados no holdout (anti-reuso) |

Para resetar Bonferroni (ex: comecar experimento novo com dados novos), delete `filter_log.parquet` manualmente — com consciencia de que esta zerando a protecao.

### O que o modulo NAO faz

- **Nao substitui `src/backtest/engine.py`.** O backtest simula equity curve de estrategia fixa (spread, stops, position sizing). `conditional_analysis` e trade-a-trade pra descoberta de edge. Filtros PROMISING → vao pro backtest pra simulacao completa.
- **Nao treina modelo, nao preve.** Consome predicoes ja salvas. Se re-treinar, regenera o dataset.
- **Nao opera.** Research offline puro, zero risco de afetar producao.

---

## News Pipeline

### Fluxo
```
Investing.com (Economic Calendar)
    |
    v
InvestingCalendar.fetch() -----> POST AJAX endpoint getCalendarFilteredData
    |
    v
normalize_news() -----> country -> currency, impact, sentiment_basic
    |
    v
process_news_with_llm() -----> LLM failover chain
    |                           sentiment_score, confidence,
    |                           event_type, volatility_impact,
    |                           reasoning_short, used_fallback,
    |                           llm_backend
    v
build_news_features() -----> Agregacao temporal (janela 3h)
    |                         por moeda base/quote do par
    v
Sentiment hibrido: 0.7 * LLM + 0.3 * basic
```

### LLM Integration
- **Backend unico:** Qwen 3.5 9B local (`qwen/qwen3.5:9b`) via Chat Completions
- **Configuracao:** Tudo vem do `.env` (`LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`), sem credenciais hardcoded no codigo
- **Cache:** Em memoria (hash MD5 do texto) + persistencia em parquet
- **Fallback final:** Se o endpoint local falhar, usa heuristica local com `used_fallback=True`
- **Persistencia:** `data/news/llm_features.parquet`
- **Auditoria:** cada classificacao salva `reasoning_short`, `used_fallback` e `llm_backend`

### Refresh
- **Automatico:** A cada 5 minutos no loop principal de execucao
- **Manual:** Botao "Refresh News" no frontend ou `POST /api/news/refresh`
- **Status:** `GET /api/news/refresh/status`
- **Comportamento:** refresh manual roda em background para nao travar o frontend
- **Persistencia diaria:** o snapshot do dia e sobrescrito em `data/news/raw_YYYY-MM-DD.parquet`
- **Alias ativo:** `data/news/raw.parquet` sempre aponta para a versao mais nova do dia

### Frontend Polling / Health
- **Bot status polling:** 10 segundos
- **WebSocket reconnect:** 10 segundos
- **Objetivo:** reduzir spam de requests e reconnect agressivo quando o backend estiver parado ou reiniciando

---

## Atualizacoes de Hoje

### 1. Correcao de simbolos validados
- O pipeline estava truncando a lista final de simbolos para 10 ativos.
- Como `XAUUSD` era o 11o simbolo desejado, ele ficava fora da coleta, treino e inferencia.
- A validacao foi corrigida para respeitar o total real de `DESIRED_SYMBOLS`.
- Resultado: `XAUUSD` agora participa da coleta de candles, engenharia de features, treino e predicao como os demais ativos principais.

### 2. Downloader de noticias refeito
- O scraper antigo baseado em HTML estava quebrando com redirect/instabilidade.
- O downloader foi reimplementado em `src/data/news/investing.py` usando o endpoint AJAX do calendario economico:
  - `POST /economic-calendar/Service/getCalendarFilteredData`
  - paginacao por `limit_from`
  - filtro de paises principais
  - filtro de impacto 1/2/3
- O parser extrai:
  - `time`
  - `country`
  - `impact`
  - `name`
  - `actual`
  - `forecast`
  - `previous`
- O arquivo do dia e sempre sobrescrito com a versao mais recente do refresh.
- O parse de impacto foi corrigido para contar apenas marcadores ativos do Investing.
- Antes, o scraper somava qualquer icone contendo `bull`, inclusive icones vazios, o que fazia muitos eventos sairem incorretamente com `impact=3`.

### 3. Noticias a cada 5 minutos
- O loop principal foi alinhado com o comportamento esperado no projeto.
- Antes, noticias eram atualizadas no startup e depois em janela muito maior.
- Agora o refresh de noticias roda na mesma cadencia do ciclo M5 do sistema.
- Isso vale tanto para ingestao automatica quanto para o uso das features em inferencia.

### 4. Frontend de News destravado
- O endpoint `POST /api/news/refresh` podia ficar bloqueado por muitos minutos enquanto o LLM processava noticias em serie.
- Isso fazia o botao do frontend ficar preso em `Fetching...`.
- A API foi alterada para:
  - aceitar o refresh imediatamente
  - executar o trabalho pesado em background
  - expor um endpoint de status
- O frontend (`/news` e `/news-analytics`) passou a consultar o status do refresh antes de recarregar os dados.

### 5. Backend LLM unico
- O classificador LLM usa apenas o endpoint local Qwen 3.5 9B (`qwen/qwen3.5:9b`) via Chat Completions.
- Se ele falhar, entra heuristica local com:
  - `used_fallback=True`
  - `llm_backend=heuristic_fallback`
- Credenciais centralizadas no `.env` (`LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`).
- O codigo nao mantem secrets embutidos.

### 6. Auditoria melhor das classificacoes
- O pipeline salva metadados extras por noticia:
  - `reasoning_short`
  - `used_fallback`
  - `llm_backend`
- Isso ajuda a medir:
  - taxa de fallback
  - backend que respondeu
  - classificacoes neutras suspeitas

### 6.1 Correcao de impacto das noticias
- Foi identificado um bug no scraper do Investing:
  - o HTML de impacto renderiza 3 marcadores por linha
  - parte deles pode estar vazia/inativa
  - o parser antigo contava todos os marcadores com `bull`
- O parser agora tenta, nesta ordem:
  1. `title` ou `aria-label` da celula
  2. `data-img_key`
  3. contagem apenas de icones `full/active`
- Isso evita que `/api/news/latest` e as features de noticias tratem tudo como `high impact`.

### 7. Merge correto de noticias repetidas
- Havia colapso de eventos com mesmo `timestamp` e mesmo `name`.
- Isso quebrava casos em que a mesma noticia existia em paises diferentes.
- O merge/persistencia passou a considerar `timestamp + name + country`.
- Resultado:
  - menos perda de eventos no parquet de LLM
  - analytics mais confiavel
  - features por moeda mais consistentes

### 8. Uso de noticias como feature de modelo
- As noticias ja entram no dataset final de modelos supervisionados.
- As features de noticias sao agregadas por janela temporal e moeda base/quote.
- Modelos que usam essas features:
  - `linear_regression`
  - `random_forest`
  - `xgboost`
- Modelos que nao usam noticias diretamente:
  - `naive`
  - `ema_heuristic`

### 9. Frontend de Symbols e escala do grafico
- O grafico de preco estava sendo achatado por predicoes fora da faixa plausivel.
- A pagina `/symbols` foi ajustada para:
  - filtrar outliers de predicao
  - adaptar a escala ao ativo exibido
  - evitar que o eixo Y colapse para `0`
- Isso e especialmente importante para ativos com escala muito diferente, como `EURUSD` vs `XAUUSD`.

### 10. Estado atual esperado apos restart
- Backend novo deve expor:
  - `/api/news/refresh/status`
  - `/api/news/llm`
  - `/api/news/analytics`
- O arquivo `data/news/raw.parquet` deve existir e ser atualizado no refresh.
- O arquivo `data/news/llm_features.parquet` deve reaparecer apos o processamento LLM terminar.
- O frontend `/news` nao deve mais ficar travado indefinidamente em `Fetching...`.

### 11. Polling reduzido no frontend
- O status do bot no sidebar e dashboard foi alterado de 5s para 10s.
- A reconexao automatica do WebSocket foi alterada de 3s para 10s.
- Isso reduz ruido visual, spam de logs e trafego desnecessario quando o backend esta indisponivel.

### 15. Signal Board + Theme System (2026-04-13)
- **Signal Radar → Signal Board:** Substituido o radar circular por painel tipo ticker/order book (`SignalBoard.jsx`). Lista vertical ordenada por confidence DESC. 3 colunas: Symbol | Signal (badge colorido com glow) | Confidence (barra horizontal + %). Flash animation em mudanca de sinal. Header com "Active Signals: 11" + breakdown BUY/SELL/HOLD.
- **Theme System:** Novo `src/theme/ThemeProvider.jsx` com React Context. 3 temas: Default (atual), Matrix (verde neon #00ff41, fundo preto, terminal), Cyberpunk (azul #00d4ff + roxo #7a00ff, glow forte). Toggle no header, persistencia localStorage. CSS variables aplicadas globalmente (`--theme-bg`, `--theme-accent`, `--theme-text`, etc.). Afeta: glass-card, neon-border, sidebar, headings, todos os panels do Control Tower.
- **Decisao:** Clareza > estetica. Signal Board prioriza leitura rapida de decisoes de trading.

### 19. Matrix Theme — Full Visual Uniformization (2026-04-13)
- **Componentes corrigidos:** ControlTowerClock (Forex Sessions), SessionPanel (Session Intelligence), LivePredictionChart (candles). Todos agora usam `useTheme()` + condicional `isMatrix`.
- **Forex Sessions:** relogio SVG com cores verdes, barras sem gradiente, borda-left em sessao ativa, labels CLI com prefixo `>`, rounded-sm.
- **Session Intelligence:** dropdown terminal (fundo preto, borda verde), barras solidas, regime CLI (`> bull | vol: low`), ScoreBadge sem cores modernas.
- **Live Prediction Chart:** candles up=#00ff41, down=#006622, previstos verde transparente, grid verde, marker `> NOW` verde, tooltip verde monospace.
- **CSS global:** scanline overlay em themed-card/glass-card via ::after, tipografia h1-h6 monospace forcada.
- **Regra:** mudancas somente quando `theme === "matrix"`. Default e Cyberpunk intactos.
- **Decisao [012]:** CSS global nao alcanca inline styles — necessario condicional JS nos componentes.

### 18. WorldMap Globe 3D — Matrix Theme Visual Upgrade (2026-04-13)
- **Globo Matrix:** No tema Matrix, o globo 3D foi transformado de estilo realista (textura Terra) para estilo digital/hacker:
  - Textura realista removida (`globeImageUrl` desativado)
  - Material do globo: fundo escuro `#001a00` com emissive verde neon `#00ff41` via Three.js mesh traversal
  - Paises renderizados como dots verdes (hex polygons: `hexPolygonResolution=3`, `hexPolygonMargin=0.6`, cor `rgba(0,255,65,0.12)`)
  - Atmosfera verde: `#00ff41`, altitude 0.25
  - Arcos: verde neon (BUY), vermelho (SELL), verde dim (HOLD), stroke proporcional a confidence
  - Labels: `#00ff41`, tamanho 1.2
  - Tooltips: `USD / Sentiment: Strong / Flow: High`
  - Fundo: `radial-gradient(circle, #001a00, #000000)`
  - Matrix Rain: canvas com caracteres japoneses/hex em baixa opacidade (~15fps)
  - Rotacao: `autoRotateSpeed=0.3`
- **Dados intactos:** arcsData, pointsData, labelsData, currencyStrength sem alteracao
- **Condicional:** mudancas aplicadas apenas quando `theme === "matrix"`, Default e Cyberpunk preservados
- **Nova dep:** `topojson-client` + GeoJSON carregado sob demanda (fetch) apenas no Matrix

### 16. Matrix Theme Deep Upgrade (2026-04-13)
- **Escopo isolado:** upgrade aplicado somente ao tema `Matrix`, preservando `Default` e `Cyberpunk`.
- **Paleta real de terminal:** fundo preto puro (`#000000`), verde neon real (`#00ff41`), verde dim (`#008f2a`), sem tons azulados e sem gradientes modernos no Matrix.
- **Tipografia:** tema Matrix agora prioriza `JetBrains Mono` / `Fira Code`, tracking levemente maior e leitura mais compacta.
- **Data Stream refeito:** `DataStream.jsx` virou o centro estetico do Matrix.
  - formato CLI real: `[12:21:06] [HEALTH] OK`
  - scanlines leves
  - cursor piscando `> _`
  - typewriter na ultima linha
  - auto-follow permanente
  - sem glass, sem rounded grande, sem card moderno
- **Signal Board adaptado no Matrix:** sinais exibidos como `[BUY] [SELL] [HOLD]`, tudo em verde com intensidade variando por confidence.
- **AI Core adaptado no Matrix:** removidos azul, gradientes e badges modernas. O painel agora usa diagnostico tecnico monocromatico, labels CLI, barras simples e intensidade visual baseada em confidence.
- **Header CLI:** no Matrix, header do layout/control tower exibe `AUTOTRADER v1.0` / `SYSTEM: ONLINE`.
- **Cards/KPIs no Matrix:** bordas finas verdes, glow minimo, sem blur, sem gradiente e com leitura tecnica.
- **Diretriz final:** se algum componente parecer "bonito demais" no Matrix, simplificar primeiro.

### 17. Signal Board polling alinhado ao M5 (2026-04-13)
- O `SignalBoard` do Control Tower deixou de consultar `/api/predict/signals/radar` em loop agressivo.
- Como os sinais dependem de candles M5, o polling foi desacelerado para `60s`.
- O `AI Core` e o `WorldMap` tambem tiveram polling de sinais reduzido para `60s`.
- O backend de `/api/predict/signals/radar` agora mantem cache curto de `60s`.
- Objetivo: reduzir ruido nos logs, requests desnecessarias e recomputacao de sinal entre fechamentos de candle.

### 14. Signal Radar — Ensemble-only + All 11 Symbols (2026-04-13)
- **Backend — novo endpoint:** `GET /api/predict/signals/radar` em `src/api/predictions.py`. Calcula ensemble (media dos modelos) para cada simbolo, gera sinal BUY/SELL/HOLD via `generate_signal()`, retorna todos os 11 DESIRED_SYMBOLS com confidence, expected_return e breakdown (BUY/SELL/HOLD counts).
- **Frontend — SignalRadar.jsx reescrito:**
  - Agora consome `/api/predict/signals/radar` (ensemble-only) em vez de `/api/signals/latest` (per-model signals.csv)
  - Exibe TODOS os 11 simbolos distribuidos uniformemente em circulo (`angle = index/total * 2pi`)
  - Labels aumentados (fontSize 5px → 7.5px/9px), com glow filter e contraste melhorado
  - Dots maiores (r=4 → r=6) com pulse animation e glow proporcional a confidence
  - Tooltip on hover: symbol, signal, confidence%, expected return em pips, n_models, source: Ensemble
  - Contador atualizado: "11 symbols tracked" + breakdown "5 BUY | 3 SELL | 3 HOLD"
  - SVG viewBox expandido (200→240) para acomodar labels sem sobreposicao
  - Confidence zones labeladas nos rings (0.25, 0.50, 0.75, 1.00)
- **Decisao [009] (DECISIONS.md):** Radar usa exclusivamente sinal ensemble, nunca sinais por modelo individual.

### 13. Control Tower — KPI Reorg + Live Prediction Chart (2026-04-10)
- **KPI strip 7 cards:** grid alterado para 7 colunas. Adicionado o card **"30D Trend"** — mini sparkline SVG do equity 30 dias com glow neon, cor por sinal (verde/vermelho), variacao percentual no rodape. O `EquityChart` grande foi removido da row central.
- **Live Prediction Chart:** novo componente `components/control_tower/LivePredictionChart.jsx` (lightweight-charts). Mostra os ultimos 10 candles M5 reais + 3 candles previstos (ensemble dos 5 modelos) em cores diferenciadas (azul/roxo, semi-transparente). Marker "NOW" no ultimo candle real. Tooltip custom com OHLC real e ensemble + confidence. Barra de confidence no header. Atualiza a cada 60s alinhado ao loop M5.
- **Backend — novo endpoint:** `GET /api/predict/predictions/latest?symbol=X` em `src/api/predictions.py`. Retorna a previsao mais recente do simbolo com ensemble (media de pred_t1/t2/t3 dos modelos), lista de modelos, n_models e confidence (1 - dispersao normalizada).
- **Symbol lifting:** `selectedSymbol` agora vive em `pages/ControlTower.jsx` e e compartilhado entre `SessionPanel` (controlado via props) e `LivePredictionChart`. Selecionar um par no Session Intelligence atualiza o chart.
- **Decisao [007] (DECISIONS.md):** Ensemble unico em vez de plotar 5 linhas — UI limpa, leitura rapida.
- **Decisao [008] (DECISIONS.md):** lightweight-charts em vez de Recharts custom para candles — chunk lazy ~163 KB isolado.

### 12. Control Tower — Correcao de consistencia (7 partes)
- **Healthcheck:** Intervalo alterado de 3s para 10s. Agora verifica o unico endpoint LLM configurado (Qwen 3.5 9B local). Adiciona status do prediction engine (ultimo timestamp de predictions.csv).
- **Session Clock:** Horarios UTC-3 do ControlTowerClock corrigidos para alinhar com session.py (UTC). Sydney 19-4, Tokyo 21-6, London 5-14, NY 10-19. Overlaps: Tokyo+London 5-6, London+NY 10-14.
- **Signal Radar:** Componente esperava array direto mas API retornava `{signals: [...]}`. Adicionado unwrapping.
- **AI Core Panel:** Mesma correcao de unwrapping para signals e performance ranking.
- **World Map (Globe 3D):** Caminho de dados corrigido — API retorna `analytics.by_currency.{CUR}.sentiment_llm_avg`, nao `currency_scores`.
- **Signals API:** `get_latest_signals()` reescrito para ler `signals.csv` (colunas estruturadas) como fonte primaria, com fallback para `decisions.csv`.
- **WebSocket logs:** `get_recent_logs()` expandido para incluir signals.csv, session_metrics.csv, backtest_trades.csv.

---

## API Endpoints

### Prediction System (`/api/predict/`)
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/predict/symbols` | Lista simbolos ativos (inclui pendentes) |
| GET | `/api/predict/metrics?symbol=X` | Metricas de avaliacao agregadas |
| GET | `/api/predict/predictions?symbol=X&model=Y` | Previsoes recentes |
| GET | `/api/predict/predictions/latest?symbol=X` | Ultima previsao com **ensemble** (media dos modelos) + confidence |
| GET | `/api/predict/predictions/detail?symbol=X` | Previsoes com valores reais |
| GET | `/api/predict/signals/radar` | Sinais ensemble para TODOS os 11 simbolos (Signal Radar) |
| GET | `/api/predict/models/performance` | Ranking de modelos |
| GET | `/api/predict/models/performance/over-time` | Performance temporal |
| GET | `/api/predict/models/info` | Info dos modelos |
| GET | `/api/predict/experiments` | Historico de experimentos |
| GET | `/api/predict/experiments/summary` | Resumo agregado |
| GET | `/api/predict/candles?symbol=X` | Candles raw |
| GET | `/api/predict/system/status` | Status do sistema |
| GET | `/api/predict/logs/recent` | Logs recentes |

### News & Regime
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/news/latest?limit=50` | Ultimas noticias normalizadas |
| GET | `/api/news/features?symbol=EURUSD` | Features de noticias por simbolo |
| GET | `/api/news/llm?limit=50` | Features LLM das noticias |
| GET | `/api/news/by-symbol?symbol=EURUSD` | Noticias filtradas por par |
| GET | `/api/news/analytics` | Analytics: por moeda, impacto, basic vs LLM |
| POST | `/api/news/refresh` | Dispara refresh manual em background |
| GET | `/api/news/refresh/status` | Status do refresh manual/automatico |
| GET | `/api/regime/current?symbol=EURUSD` | Regime de mercado atual |

### Session
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/session/current?symbol=EURUSD` | Sessoes ativas, score, regime, weights |
| GET | `/api/session/weights` | Pesos de sessao para todos os ativos |

### Backtest & Experiments
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/backtest/results?symbol=X&model=Y` | Trades simulados |
| GET | `/api/backtest/summary` | Resumo de backtest por modelo |
| POST | `/api/backtest/run?symbol=X` | Dispara backtest em background |
| GET | `/api/backtest/equity?symbol=X&model=Y` | Equity curve |
| GET | `/api/experiments/results?symbol=X&feature_set=Y` | Resultados de feature experiments |
| GET | `/api/experiments/ranking?symbol=X` | Ranking de modelos por score |
| GET | `/api/experiments/ranking/feature-sets` | Ranking por feature set |
| POST | `/api/experiments/run?symbol=X&force=true` | Dispara experimentos em background |
| GET | `/api/models/best?symbol=X` | Melhor modelo global ou por simbolo |
| GET | `/api/models/by-regime?symbol=X` | Melhor modelo por regime |
| GET | `/api/models/select?symbol=X&trend=1` | Selecao de modelo por regime |
| GET | `/api/signals/latest?symbol=X` | Sinais de trade recentes |

### Command Center (Mock Data)
| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/account` | Estado da conta |
| GET | `/api/positions` | Posicoes abertas |
| GET | `/api/positions/history` | Historico de trades |
| GET | `/api/predictions` | Previsoes (mock) |
| GET | `/api/predictions/latest` | Ultima previsao por simbolo |
| GET | `/api/news` | News feed (mock) |
| GET | `/api/model/metrics` | Metricas de modelo |
| GET | `/api/model/features` | Feature importance |
| GET | `/api/equity/history` | Curva de equity |
| GET | `/api/logs` | Logs do sistema |
| GET | `/api/bot/status` | Status do bot |
| WS | `/ws` | WebSocket (ticks, KPIs, real-time CSV logs, healthcheck 10s) |

---

## Frontend (Command Center)

### Tech Stack
- **React** 19.0 + **Vite** 6.0
- **Tailwind CSS** 4.0
- **Recharts** 2.15 (graficos gerais)
- **lightweight-charts** (TradingView — candles do Live Prediction Chart)
- **Lucide React** (icones)
- **React Router** 7.1
- **Three.js** + **react-globe.gl** (globo 3D)

### Paginas (12)

| Pagina | Rota | Descricao |
|--------|------|-----------|
| Control Tower | `/control-tower` | HUD principal: 7 KPIs (incl. 30D Trend sparkline), Session Clock, Session Intelligence, **Signal Board (ticker panel, confidence bars, sorted DESC)**, AI Core, World Map 3D, **Live Prediction Chart (candles + ensemble)**, Data Stream. **Theme System:** toggle Default/Matrix/Cyberpunk no header |
| Dashboard | `/dashboard` | KPIs, equity curve, bot status, best model card |
| Overview | `/overview` | Performance global + sentiment por moeda |
| Symbols | `/symbols` | Analise por simbolo: price chart, regime, news, predictions, melhor modelo por regime |
| Models | `/models` | Ranking de modelos (accuracy + PnL), comparacao por feature set |
| Backtest | `/backtest` | Equity curve, drawdown chart, trades simulados, PnL por modelo |
| Positions | `/positions` | Posicoes abertas e historico de trades |
| AI / Model | `/ai` | Feature importance, predictions detail |
| Experiments | `/experiments` | Historico de treinos + feature experiments (PnL, Sharpe, charts comparativos) |
| News | `/news` | Feed de noticias + currency sentiment + botao refresh |
| News Analytics | `/news-analytics` | Analytics: filtros, charts, basic vs LLM, tabela eventos |
| Logs | `/logs` | System log viewer |

### Symbols Page - Cards Integrados
- **Market Regime:** Trend (bull/bear), Volatility (low/med/high), Momentum, Range (trending/ranging)
- **News Indicators:** Sentiment base/quote, LLM sentiment, Impact, High Impact flag
- **Recent News:** Lista de eventos filtrada pelas moedas do par

---

## Estrutura de Diretorios

```
autotrader/
├── config/
│   └── settings.py              # Configuracoes centralizadas (dataclass + .env)
│
├── src/
│   ├── api/
│   │   ├── predictions.py       # FastAPI router: predicoes (12 endpoints)
│   │   ├── news_regime.py       # FastAPI router: news + regime + session (9 endpoints)
│   │   └── backtest_experiments.py # FastAPI router: backtest + experiments + ranking (12 endpoints)
│   ├── decision/
│   │   ├── signal.py            # Geracao de sinais (BUY/SELL/HOLD) com session awareness
│   │   └── model_selector.py    # Auto-selecao de modelo por regime + sessao
│   ├── backtest/
│   │   └── engine.py            # Backtest engine (PnL, Sharpe, Drawdown)
│   ├── research/
│   │   ├── feature_experiments.py # Teste automatico de combinacoes de features
│   │   └── model_ranking.py     # Ranking inteligente de modelos
│   ├── data/
│   │   ├── collector.py         # Coleta M5 candles via MT5
│   │   └── news/
│   │       └── investing.py     # Scraper Investing.com economic calendar
│   ├── features/
│   │   ├── engineering.py       # Feature engineering (45 features)
│   │   ├── regime.py            # Regime de mercado (trend, vol, momentum, range)
│   │   ├── session.py           # Sessoes Forex (4 sessoes, 2 overlaps, strength, score, weights)
│   │   └── news_features.py     # Normalizacao + agregacao temporal de noticias
│   ├── llm/
│   │   └── news_sentiment.py    # LLM sentiment via HTTP + cache + fallback
│   ├── models/
│   │   ├── base.py              # BasePredictor interface
│   │   ├── naive.py             # Naive predictor
│   │   ├── linear.py            # Linear regression
│   │   ├── random_forest.py     # Random forest
│   │   ├── xgboost_model.py     # XGBoost
│   │   ├── ema_heuristic.py     # EMA heuristic
│   │   └── registry.py          # ModelRegistry (gerencia todos)
│   ├── execution/
│   │   ├── engine.py            # PredictionEngine (orquestrador)
│   │   └── loop.py              # Loop 24/7 + news pipeline diario
│   ├── evaluation/
│   │   ├── evaluator.py         # Metricas: direcao, MAE, MAPE
│   │   └── tracker.py           # Experiment tracking
│   ├── mt5/
│   │   ├── connection.py        # MT5Connection (context manager)
│   │   └── symbols.py           # Simbolos, COUNTRY_CURRENCY_MAP
│   └── utils/
│       └── logging.py           # CSV logging (system, predictions, decisions, signals, backtest)
│
├── command_center/
│   ├── backend/
│   │   ├── main.py              # FastAPI app + news background task
│   │   ├── database.py          # SQLite mock data
│   │   └── ws_manager.py        # WebSocket manager
│   └── frontend/
│       ├── src/
│       │   ├── App.jsx          # React Router (12 paginas)
│       │   ├── pages/           # ControlTower, Dashboard, Overview, Symbols,
│       │   │                    # Models, Backtest, Positions, AIModel,
│       │   │                    # Experiments, News, NewsAnalytics, Logs
│       │   ├── components/      # Layout, Sidebar, KPICard, charts, etc.
│       │   ├── hooks/           # useApi, useWebSocket
│       │   └── services/api.js  # API client (35+ metodos)
│       ├── package.json
│       └── vite.config.js
│
├── data/                        # Runtime data (gitignored)
│   ├── raw/                     # Candles M5 (*.parquet)
│   ├── features/                # Features computadas (*.parquet)
│   ├── predictions/             # Predicoes (*.parquet)
│   ├── metrics/                 # Metricas de avaliacao (*.parquet)
│   ├── experiments/             # Historico de treinos + feature experiments + ranking
│   ├── backtest/                # Trades simulados + metricas por modelo
│   ├── news/                    # Noticias raw + LLM features (*.parquet)
│   └── logs/                    # CSV logs (system, predictions, decisions, signals, backtest)
│
├── tests/
│   ├── conftest.py              # fixtures sample_data / sample_features / sample_dataset
│   ├── test_mt5_connection.py   # 16 testes
│   ├── test_collector_and_news.py
│   ├── test_conditional_analysis.py
│   └── models/                  # Suite ML: 32 testes (treino, predicao, registry,
│       │                        #            ensemble, anti-leakage, estabilidade)
│       ├── test_models_basic.py
│       ├── test_models_predictions.py
│       ├── test_registry.py
│       ├── test_ensemble.py
│       ├── test_no_leakage.py
│       └── test_training_stability.py
│
├── .env                         # Credenciais (MT5, LLM, AWS)
├── .project/                    # Documentacao do projeto
├── requirements.txt             # Python deps
└── README.md
```

---

## Setup Local

### Pre-requisitos
- Python 3.11+
- Node.js 18+
- MetaTrader 5 terminal instalado (Windows)
- LLM local rodando (opcional, para sentiment avancado)

### 1. Backend (Python)

```bash
# Clonar e entrar no diretorio
cd autotrader

# Criar e ativar venv
python -m venv venv
source venv/Scripts/activate  # Windows/Git Bash
# ou: venv\Scripts\activate   # Windows CMD

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar .env

```env
MT5_ACCOUNT=your_account
MT5_PASSWORD=your_password
MT5_PASSWORD_READ=your_read_password
MT5_SERVER=your_broker_server

# LLM (opcional - se nao configurar, usa fallback)
LLM_API_URL=http://192.168.100.191:3032/v1
LLM_API_KEY=your_key
LLM_MODEL=qwen/qwen3.5:9b
```

### 3. Frontend

```bash
cd command_center/frontend
npm install
```

### 4. Executar

```bash
# Terminal 1 - Backend (API + news auto-refresh)
cd command_center/backend
source ../../venv/Scripts/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Frontend
cd command_center/frontend
npm run dev

# Terminal 3 - Loop de predicao (opcional, requer MT5)
source venv/Scripts/activate
python -m src.execution.loop
```

O dashboard estara disponivel em `http://localhost:5173`

---

## Dependencias Python

| Pacote | Versao | Uso |
|--------|--------|-----|
| fastapi | 0.135.3 | Web framework / API |
| uvicorn | 0.44.0 | ASGI server |
| metatrader5 | 5.0.5735 | Conexao com broker |
| pandas | 2.3.3 | Manipulacao de dados |
| numpy | 2.2.6 | Computacao numerica |
| scikit-learn | 1.7.2 | ML (linear, random forest) |
| xgboost | 3.2.0 | Gradient boosting |
| beautifulsoup4 | 4.14.3 | HTML parsing (news scraping) |
| arrow | 1.4.0 | Datetime parsing |
| httpx | 0.28.1 | HTTP client (LLM calls) |
| pyarrow | 23.0.1 | Parquet I/O |
| python-dotenv | 1.2.2 | Env vars |

---

## Data Flow

### Ciclo de Predicao (a cada 5 min)
1. `collect_update()` — Busca ultimos 50 candles M5 via MT5
2. `compute_features()` — Gera 20 features tecnicas + 4 regime
3. `build_news_features()` — Agrega 13 features de noticias (janela 3h)
4. `prepare_dataset()` — Cria input 10x37 flattened = 370-dim
5. `registry.train_all()` — Treina 5 modelos (1a vez ou a cada 50 ciclos)
6. `registry.predict_all()` — Gera previsoes t+1, t+2, t+3
7. `generate_signals()` — Gera sinais BUY/SELL/HOLD por modelo + ensemble
8. `evaluate_predictions()` — Compara previsoes anteriores com reais
9. `run_backtest()` — Auto-backtest a cada 50 ciclos
10. Salva tudo em parquet + CSV logs (predictions, decisions, signals, backtest)

### Ciclo de Noticias (a cada 5 min)
1. `InvestingCalendar.fetch()` — Scraping do calendario economico
2. `save_news_raw()` — Persiste em `data/news/raw.parquet`
3. `normalize_news()` — Mapeia country -> currency, calcula sentiment basic
4. `process_news_with_llm()` — Envia cada noticia para LLM local
5. `save_llm_features()` — Persiste em `data/news/llm_features.parquet`

---

## Avaliacao

### Metricas por Modelo
- **Direction Accuracy** — O modelo acertou a direcao (subiu/desceu)?
- **MAE** — Mean Absolute Error
- **MAPE** — Mean Absolute Percentage Error

### Por Horizonte
Metricas calculadas separadamente para t+1, t+2, t+3.

### Tech Debt Conhecido
- Modelos usam train/test split simples 80/20
- Planejado: **CPCV** (Combinatorial Purged Cross-Validation) com purge + embargo (Marcos Lopez de Prado)

---

## Testes

> **Status (2026-04-17):** 501 testes Python + 245 testes frontend passando. Cobertura: CRITICAL 96.6%, ML 80.3%, overall 85.1%. Ver [Como rodar tudo](#como-rodar-tudo) abaixo.

### Como rodar tudo

**Quick check (todos os testes, sem coverage):**
```bash
# Python
source venv/Scripts/activate     # Linux/Mac: venv/bin/activate
pytest -q                        # ~90s, 501 passed

# Frontend
cd command_center/frontend
npm test                         # ~10s, 245 passed
```

**Com coverage + gate tierado (CI-style):**
```bash
# Python: coverage + gate por tier (critical 90% / ml 80% / overall 75%)
source venv/Scripts/activate
pytest --cov=src --cov-report=xml --cov-report=term --cov-config=.coveragerc
python scripts/check_coverage_tiers.py    # sai com codigo != 0 se qualquer tier regredir

# Frontend: coverage com gate global
cd command_center/frontend
npm run test:coverage            # reporta em coverage/index.html
```

**Subset por area (mais rapido durante desenvolvimento):**
```bash
pytest tests/execution/          # ~3s
pytest tests/decision/           # ~2s
pytest tests/backtest/           # ~2s
pytest tests/evaluation/         # ~4s
pytest tests/models/             # ~47s (treino sintetico)
pytest tests/api/                # ~5s
pytest tests/property/           # ~12s (hypothesis)
```

**Property-based tests (hypothesis):**
```bash
pytest tests/property/ -q        # 17 testes, ~12s
# Roda milhares de casos randomizados por invariante.
# Ajuste exemplos via HYPOTHESIS_PROFILE=ci (default local = 200/prop).
```

**Mutation testing (gate de qualidade pre-release):**
```bash
# Pega cada operador em src/decision/signal.py, execution/engine.py, etc.
# e verifica se algum teste falha quando o codigo eh mutado.
# Mutante sobrevivente = teste fraco que precisa ser reforcado.
mutmut run                       # lento (~30min-2h); rode antes de release
mutmut results                   # resumo killed/survived
mutmut show <id>                 # inspecionar um sobrevivente especifico
mutmut html                      # relatorio HTML em html/index.html
```

Modulos cobertos por `mutmut` (declarados em `pyproject.toml`):
`src/decision/signal.py`, `src/decision/ensemble.py`, `src/execution/engine.py`, `src/backtest/engine.py`, `src/evaluation/cpcv.py`. **Meta:** survival rate < 15% por modulo.

### Tiered coverage gates (`scripts/check_coverage_tiers.py`)

Gate de CI que le `coverage.xml` e enforce thresholds diferentes por tier de risco:

| Tier | Modulos | Threshold | Atual |
|---|---|---:|---:|
| **CRITICAL** | `execution/`, `decision/signal.py`, `decision/ensemble.py`, `decision/model_selector.py`, `backtest/engine.py`, `mt5/connection.py`, `evaluation/cpcv.py` | **90%** | **96.6%** |
| **ML** | `models/`, `features/`, `evaluation/`, `research/` | **80%** | **80.3%** |
| **OVERALL** | tudo em `src/` | **75%** | **85.1%** |

Por que tierado? Modulos que roteiam dinheiro real (execution/decision/backtest) tem gate mais apertado que pipeline de pesquisa. Gate global de 80% igual pra todos mascararia buracos em areas criticas.

### Estrutura dos testes

```
tests/
├── api/                         # 35 testes — endpoints FastAPI
├── backtest/                    # 24 testes — engine de PnL
├── decision/                    # 42 testes — signal + model_selector
├── evaluation/                  # 56 testes — CPCV, overfitting, evaluator
├── execution/                   # 47 testes — engine + loop (com mocks MT5)
├── features/                    # 38 testes — engineering, session
├── models/                      # 32 testes — modelos ML, ensemble, no-leakage
├── property/                    # 17 testes — hypothesis (invariantes)
├── research/                    # testes de feature_experiments, conditional_analysis
└── ...
```

### Suite de Modelos ML (`tests/models/`)
Suite completa de 32 testes validando o pipeline de modelos:

| Arquivo | Cobertura |
|---------|-----------|
| `test_models_basic.py` | Os 5 modelos treinam sem erro; isolamento por simbolo |
| `test_models_predictions.py` | Shape (n, 3), valores finitos, faixa plausivel |
| `test_registry.py` | Nomes esperados, cache por simbolo, get_model_info |
| `test_ensemble.py` | `compute_ensemble` — media simples, ponderada, NaN-safe |
| `test_no_leakage.py` | Bloqueia colunas `next_*`/`future_*`/`*_ahead`; target = close futuro |
| `test_training_stability.py` | Sem NaN/Inf, overfit gap razoavel, determinismo, feature_importance |

**Executar:**
```bash
pytest tests/models/        # ~47s, 32 passed
```

**Politica:** testes usam dataset sintetico (500 barras M5, random walk + sazonalidade), nao dependem de MT5, API externa ou LLM. Se um teste falhar, **corrigir o pipeline**, nao o teste.

### Novo modulo
- `src/models/ensemble.py` — `compute_ensemble(predictions, weights=None)` extrai logica de ensemble (antes inline em `src/api/predictions.py`). Aceita `dict[name, array(n,3)]` ou `dict[name, [t1,t2,t3]]`.

### Suite de API Backend (`tests/api/`)
Suite de 35 testes cobrindo endpoints FastAPI + integracao com pipeline de dados/ML:

| Arquivo | Cobertura |
|---------|-----------|
| `test_predictions.py` | `/api/predict/symbols`, `/predictions/latest` (ensemble shape t+1/t+2/t+3, confidence, models), 404 para symbol invalido, 422 para query faltante |
| `test_signals.py` | `/api/predict/signals/radar` — 11 DESIRED_SYMBOLS, values em {BUY,SELL,HOLD}, confidence in [0,1], breakdown consistente |
| `test_models.py` | `/models/performance`, `/models/best`, `/models/info`, `/models/feature-importance` |
| `test_news.py` | `/api/news/latest`, `/features` (contem `news_sentiment_base`), `/by-symbol` (base/quote currency), `/analytics` |
| `test_session.py` | `/api/session/current` (session_score in [0,1]), regime dict, `/session/weights` |
| `test_system.py` | `/system/status`, `/logs/recent`, `/metrics` |
| `test_data_integrity.py` | Consistencia predicao↔signal, sem NaN/Inf em JSON, current_price positivo, radar == DESIRED_SYMBOLS, session_score estavel |

**Setup:** app de teste em `tests/api/conftest.py` monta apenas os routers (sem lifespan de news/ws), usando `SafeJSONResponse` identica a producao (sanitiza NaN/Inf).

**Executar:**
```bash
pytest tests/api/           # ~5s, 35 passed
```

**Politica:** testes gracefully-skip se `data/predictions/*.parquet` ausente. Sem dependencia de MT5, LLM ou rede. Tests verificam o contrato real dos endpoints — **corrigir backend, nao o teste**.

---

## Logging

Cinco arquivos CSV persistentes em `data/logs/`:

| Arquivo | Conteudo |
|---------|----------|
| `system.csv` | Logs gerais (timestamp, level, module, message) |
| `predictions.csv` | Cada predicao (timestamp, symbol, model, prices) |
| `decisions.csv` | Decisoes do sistema (startup, cycles, signals, backtest) |
| `signals.csv` | Sinais gerados (timestamp, symbol, model, signal, confidence, expected_return) — fonte primaria da API |
| `backtest_trades.csv` | Trades simulados (timestamp, symbol, model, direction, entry, exit, pnl) |
| `session_metrics.csv` | Metricas por sessao (symbol, session, session_score, signal, model, confidence) |

Registros incluem:
- Sinais de trade (BUY/SELL/HOLD) por modelo e ensemble
- Trades simulados de backtest
- Sentiment (basic + LLM + hibrido) por noticia
- Regime de mercado no momento da predicao

---

## Glossario

| Termo | Significado |
|-------|-------------|
| M5 | Timeframe de 5 minutos |
| CPCV | Combinatorial Purged Cross-Validation |
| MT5 | MetaTrader 5 |
| Pip | Menor variacao de preco em FOREX |
| ATR | Average True Range (volatilidade) |
| EMA | Exponential Moving Average |
| RSI | Relative Strength Index |
| Regime | Classificacao do estado do mercado |
| LLM Sentiment | Analise de sentimento via Large Language Model |
| Hybrid Sentiment | 0.7 * LLM + 0.3 * basic sentiment |

---

## Frontend Tests (Command Center)

Suite completa em Vitest + Testing Library + MSW em `command_center/frontend/src/tests/`.
**Status: 245 testes em 24 arquivos, ~10s, cobertura 80.4% lines.**

### Rodar

```bash
cd command_center/frontend
npm test                 # roda uma vez (~10s, 245 passed)
npm run test:watch       # modo watch (re-roda em cada save)
npm run test:coverage    # roda + gera coverage/index.html
```

### Cobertura atual (24 arquivos)

**Paginas (todas ≥ 50%):** App, ControlTower, Dashboard, Backtest, Positions, AIModel, News, NewsAnalytics, Logs, Overview, Models, Experiments, Symbols.

**Componentes (control tower, dashboard, news, positions):** SignalBoard, SignalRadar, SessionPanel, AICorePanel, DataStream, LivePredictionChart, EquityChart, ModelDecision, TrendSparklineCard, Sidebar, etc.

**Services / hooks:** `services/api.js` (45+ endpoints), `hooks/useWebSocket.js`, `hooks/useApi.js`, `theme/ThemeProvider.jsx`.

### Setup

- `src/tests/setupTests.js` — registra `jest-dom`, stubs de `matchMedia`/`ResizeObserver`/`IntersectionObserver`.
- `src/tests/mocks/handlers.js` + `server.js` — MSW handlers para os endpoints usados pelo Command Center.
- `vite.config.js` tem o bloco `test` (jsdom + include `src/tests/**/test_*.jsx`).

### Regras

- **Nunca bater API real.** Componentes que usam `fetch`/`api` sao mockados via `vi.mock` ou MSW.
- **Componentes pesados (WebGL, lightweight-charts)** sao stubados no nivel do import para manter testes < 6s totais.
- Se um teste falha, **corrigir o componente** — nao silenciar o teste.

---

## Licenca

Projeto privado - uso interno.
