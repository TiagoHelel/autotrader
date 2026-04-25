# Legacy Changelog

> Notas historicas movidas do README.md em 2026-04-23 (estavam poluindo o README).
> Cobre os sprints de 2026-04-07 a 2026-04-13. Para atualizacoes posteriores,
> ver [`CHANGELOG.md`](CHANGELOG.md).

---

## Atualizacoes de Hoje (historico)

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
