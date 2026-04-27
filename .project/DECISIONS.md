# Decisions Log

> Log every significant architectural or product decision here.

---

### [022] - MT5 acessado via HTTP pull (nao webhook/push)

- **Date:** 2026-04-26
- **Status:** implemented (passo 1: servidor)
- **Decision:** Para mover o stack principal pra Linux mantendo o
  terminal MT5 em Windows, expor `MT5Connection` atraves de um servidor
  FastAPI fino (`mt5_api/`) com **pull HTTP**. Outras maquinas (Linux)
  vao consumir `/candles`, `/tick`, `/account` por requisicao, em vez
  de receber webhook/push.
- **Reasoning:**
  - **Backtest e research** precisam de range historico arbitrario
    (`copy_rates_range`) sob demanda. Webhook so cobre tempo real.
  - **Recovery pos-queda** vira trivial: o cliente pede o range que
    perdeu. Com push voce perde silenciosamente.
  - Acoplamento atual ja eh baixo: so `MT5Connection` (e seu
    consumidor `collect_*` + `engine.run_cycle`) toca a lib
    `MetaTrader5`. Trocar para um cliente HTTP com a mesma interface
    eh construtor-only.
  - Push (Redis pub/sub ou WebSocket) pode ser adicionado *depois*
    como otimizacao — a base pull cobre 100% dos casos hoje.
- **Consequences:**
  - Latencia LAN (~1ms) eh irrelevante para M1/M5; em VPS separados
    medir antes.
  - Auth obrigatoria quando expor fora de LAN: VPN
    (Tailscale/WireGuard) + Bearer token (`MT5_API_TOKEN`).
  - Quando entrar execucao, `POST /order` precisa de `client_id`
    idempotente para evitar trade duplicado em retry de rede.
  - A lib `MetaTrader5` **nao eh thread-safe** -> servidor usa lock
    global. Nao escala horizontalmente em uma so instancia, mas o
    terminal MT5 ja eh single-process por natureza.

---

### [021] - Weekend gate em camadas (engine + eval + API + UI)

- **Date:** 2026-04-25
- **Status:** implemented
- **Decision:** Forex fechado (sex 22:00 UTC -> dom 22:00 UTC) e tratado em
  multiplas camadas: features (`is_market_open` zera session features),
  engine (`run_cycle` skipa), avaliador batch (`daily_eval` filtra rows),
  agent_researcher (filtra contexto LLM), API (`/signals/radar` retorna
  `market_closed: true`), UI (`MarketStatusBanner` no Control Tower).
- **Reasoning:**
  - Defesa em profundidade: cada camada protege a proxima. Se uma falhar,
    a seguinte ainda gateia.
  - Sinal de venda visivel em sabado erodia confianca da UI; pior, predicoes
    de fim de semana viravam linhas em `eval_*.parquet` e contaminavam
    `daily_eval` (sem proxima vela real, `hit_t1` vira ruido) e o contexto
    que o agente OpenCode usa para propor hipoteses.
  - Quando o bot real existir (decisao [017]), `is_market_open` sera o
    primeiro hard gate antes de qualquer ordem, somado ao gate implicito
    do broker.
- **Consequences:**
  - Testes que exercitam `/signals/radar` precisam mockar
    `src.features.session.is_market_open` para nao virarem flaky por dia da
    semana. Padrao adotado: fixture `_force_market_open` em cada arquivo.
  - Janela escolhida e conservadora (alguns brokers reabrem dom 21:00 UTC
    no verao do hemisferio norte). Trade-off aceitavel: alguns minutos de
    sinais filtrados a mais, em troca de cobertura simples e segura.

---

### [020] - Agent OpenCode customizado com tools restritos

- **Date:** 2026-04-25
- **Status:** implemented
- **Decision:** A chamada LLM do `agent_researcher` roda atraves de um agente
  OpenCode dedicado `autotrader-researcher`, registrado em
  `~/.config/opencode/opencode.jsonc`, com tools allow somente `read`, `list`,
  `glob`, `grep`, `webfetch`, `websearch`. `write`, `edit`, `patch`, `bash`
  ficam explicitamente desligados.
- **Implementation:**
  - O agente le repo e web, nao escreve nada.
  - Toda escrita real continua sendo do orchestrator Python
    (`vault_writer.py`, `strategy_manager.py`, `state_manager.py`), que segue
    a fronteira definida em [019].
  - Em runtime no Windows, `OpenCodeClient` chama `node` direto com
    `node_modules/opencode-ai/bin/opencode`, pulando o shim `.CMD` que
    mutilava `--model`. Prompt entregue via stdin.
- **Reasoning:**
  - `opencode run` e um agente, nao endpoint de completion. Sem agente custom
    o default `build` tem Edit/Bash e tenta editar o proprio codigo do projeto
    durante a "geracao de hipoteses".
  - Manter `webfetch`/`websearch` enriquece o raciocinio do agente sem dar
    nenhuma capacidade de escrita, mantendo a fronteira [019] intacta
    independente do prompt.
- **Consequences:**
  - Config do agente vive no home do usuario, fora do repo. Setup precisa ser
    documentado.
  - Se opencode mudar a API de tools, o registro precisa ser revalidado;
    falha rapida via stderr capturado em raw_output_*.log.

---

### [019] - Agent researcher isolado com escrita propria

- **Date:** 2026-04-25
- **Status:** implemented
- **Decision:** O agente autonomo de pesquisa vive em `src/agent_researcher/` e
  pode ler o repositorio inteiro, mas em runtime so escreve em
  `src/agent_researcher/**` e `vault/AgentResearch/**`.
- **Implementation:**
  - LLM via OpenCode CLI (`opencode chat --model qwen --input <prompt_file>`),
    sem SDK Python.
  - Prompt files, estado, estrategias ativas/rejeitadas e tracking de holdout
    ficam dentro de `src/agent_researcher/`.
  - Notas Obsidian geradas ficam em `vault/AgentResearch/{hypotheses,logs,learnings}/`.
  - `conditional_analysis.evaluate_filter` e reutilizado com `log=False`, para
    impedir escrita em `data/research/` pelo agente.
  - Scheduler roda o agente as 03:00 UTC, apos upload (01:00 UTC) e daily_eval
    (02:00 UTC).
- **Reasoning:** O agente automatiza pesquisa, mas nao pode contaminar dados,
  logs estatisticos globais ou notas humanas fora da area dele. A fronteira de
  escrita torna falhas reversiveis e auditaveis.
- **Consequences:** Holdout protection do agente e propria (`state.json`).
  O `filter_log.parquet` existente continua sendo contexto read-only para
  Bonferroni awareness, nao destino de escrita.

---

### [018] — Avaliador batch diario (camada 1) com auto-execucao de hipoteses

- **Date:** 2026-04-24
- **Status:** implemented
- **Decision:** Avaliador automatico de estrategias eh **batch diario**, nao streaming. Implementado em `src/evaluation/daily_eval.py`. Camada 1 (deterministica) cruza pred vs real, segmenta por contexto, detecta drift vs baseline 30d, **auto-executa hipoteses** declaradas em `vault/Hypotheses/*.md` com `filters` no YAML frontmatter, e gera relatorio markdown em `vault/Research/eval-daily/{date}.md`. Camada 2 (LLM priorization) fica para fase futura.
- **Alternatives considered:**
  - **(A) Streaming/online evaluation:** desperdicio de compute (CPCV/Bonferroni precisam de volume amostral acumulado), perde reprodutibilidade (replay vira pesadelo), inflaciona LLM cost.
  - **(B) Avaliador no mesmo processo do predictor:** acopla research a runtime de predicao. Bug em pandas analytics derruba ciclo de predicao.
  - **(C, escolhida) Batch end-of-day separado, idempotente, com archive local:** baixo custo, alta replay-ability, falha isolada do predictor, semantica clara de "fechamento do dia".
- **Reasoning:**
  - **Edge discovery e estatisticamente lento.** CI95 mexe pouco entre minutos. 1x/dia eh suficiente.
  - **Reproducibilidade > latencia.** Toda metrica precisa ser re-derivavel a partir dos parquets — batch garante isso.
  - **Auto-rodar hipoteses no daily eval e seguro** porque (a) escreve em "Daily eval log" no fim da nota, nao no bloco "Resultado" (esse continua reservado pro `evaluate_filter` formal com holdout), (b) Wilson CI95 simplificado, (c) verdict tracking eh tendencia diaria, nao decisao final.
- **Consequences:**
  - Pipeline simples: `python -m src.evaluation.daily_eval --date YYYY-MM-DD`. Idempotente.
  - Cada hipotese com `filters` no frontmatter ganha tendencia diaria automatica.
  - Validacao formal continua manual via `conditional_analysis.evaluate_filter` (holdout protegido, Bonferroni cumulativo).
  - Drift detection > 10pp gera flag no relatorio mas nao age — humano revisa.

---

### [017] — Bot de execucao e research sao processos/repos separados (faseamento 0-3)

- **Date:** 2026-04-24
- **Status:** decided (placeholder em `vault/Ideas/2026-04-24-trading-bot-architecture.md`)
- **Decision:** Quando o AutoTrader for evoluir para execucao real de ordens, o bot ficara em **repo/processo separado** (`trading-bot/`). O AutoTrader atual continua sendo **plataforma de research e geracao de sinais**. Comunicacao via file-drop (signals JSON) ou HTTP polling. Faseamento obrigatorio antes de dinheiro real:
  - **Fase 0 (semanas 1-2):** acumular dados + rodar `daily_eval` manual diario. Sem bot ainda.
  - **Fase 1 (semanas 3-4):** se H1 (confidence-gate 0.85) ou outras hipoteses ficarem PROMISING em 14d, bot vira paper-trading (zero ordem real, simula execucao com spread real).
  - **Fase 2 (semanas 5-8):** demo account no broker. Aparecem slippage real, latencia, requote.
  - **Fase 3 (semanas 9+):** conta real, position size minima ($100 risk/trade), 30 dias. Se PnL bater com demo, sobe size devagar.
- **Alternatives considered:**
  - **(A) Bot integrado ao AutoTrader (mesmo processo):** mais simples mas mistura SLAs incompativeis. Bug em research crash o order router. Surface de codigo enorme em algo que precisa ser pequeno e auditavel. Recusado.
  - **(B) Microservices completos (OMS dedicado, risk service separado):** over-engineering para solo trader. Recusado.
  - **(C, escolhida) Dois processos, dois repos, comunicacao por arquivo/HTTP:** separacao real, simples para 1 pessoa manter, padrao da industria adaptado a escala individual.
- **Reasoning:**
  - **Bot precisa ser pequeno (~500-1500 LOC).** Order router + risk gate + position manager + state machine + kill switch + reconciliation. Cada linha auditavel.
  - **Diferenca de SLA:** research pode crashar e re-rodar. Bot com posicao aberta nao pode crashar.
  - **Faseamento elimina classe diferente de bug a cada fase:** paper -> lifecycle de ordem sem dinheiro; demo -> slippage/latency real; real-mini -> psicologia + custos.
  - **Construir bot antes de ter edge confirmado = motor sem combustivel.** Prioridade absoluta: validar H1 em janela 30d antes de qualquer linha de codigo de execucao real.
- **Consequences:**
  - Bot fica em repo separado quando vier (visibilidade de mudancas, deploy independente).
  - AutoTrader expoe sinais via API existente ou file-drop em `data/signals_pending/`.
  - **Nada de codigo de execucao real neste repo ate H1 validar em holdout 30d.**

---

### [001] — Validacao com CPCV (Purge + Embargo)

- **Date:** 2026-04-07 (decided) / 2026-04-13 (implemented)
- **Status:** implemented
- **Decision:** Todo treinamento de modelo deve usar Combinatorial Purged Cross-Validation (CPCV) com purge e embargo, conforme publicacoes do Professor Marcos Lopez de Prado.
- **Implementation:** `src/evaluation/cpcv.py` — 5 folds temporais, 2% embargo, purge automatico. Integrado no `execution/engine.py`. Resultados salvos em `data/metrics/validation_results.parquet`. API: `GET /api/predict/models/validation`.
- **Alternatives considered:** K-Fold tradicional, Walk-Forward, TimeSeriesSplit
- **Reasoning:** Series temporais financeiras possuem autocorrelacao. Metodos tradicionais de CV causam data leakage. CPCV eh o metodo mais robusto para evitar overfitting em dados financeiros, mantendo a estrutura temporal e removendo amostras contaminadas.
- **Consequences:** Treinamentos mais lentos mas resultados confiaveis. Split simples 80/20 eliminado. Accuracy reportada agora e conservadora e realista.

---

### [016] — Edge discovery via conditional analysis com protecoes anti-snooping

- **Date:** 2026-04-14
- **Status:** implemented
- **Decision:** Descoberta de edges condicionais (ex: "XAU entre 14-15 UTC") deve passar por framework dedicado (`src/research/conditional_analysis.py`) com:
  - Dataset pre-computado (predictions + outcomes + contexto) reaproveitavel.
  - Holdout temporal de 20% inviolado ate validacao final.
  - Log persistente de TODOS os filtros testados (filter_log.parquet).
  - Wilson CI95 + binomial two-sided test vs p=0.5.
  - Bonferroni correction automatica baseada em N testes previos.
  - Bloqueio de reuso do mesmo filter_hash no holdout.
  - Verdicts padronizados: REJECTED_N / UNDERPOWERED (N<30) / WEAK / PROMISING / STRONG / REJECTED_WR.
- **Alternatives considered:**
  - **(A) Rodar analises ad-hoc em notebook:** sem log central, sem holdout inviolado, sem Bonferroni. Rota mais rapida de auto-enganacao.
  - **(B) Extender `src/backtest/engine.py`:** engine atual foca em equity curve de estrategia fixa. Misturar com exploracao de filtros polui a responsabilidade.
  - **(C) Hyperparameter search automatico (grid/bayesian) sobre filtros:** fere a regra "hipotese antes do teste" — otimizar automaticamente e a definicao operacional de data snooping.
- **Reasoning:**
  - Val_acc medio de 48-49% dos modelos atuais e coin flip. Edge em FX M5 raramente existe em media — existe condicional a regime/hora/sessao. Descoberta honesta requer infraestrutura, nao disciplina humana (que falha).
  - Bonferroni + holdout + log sao defesas em camadas: mesmo que voce esqueca de uma, as outras pegam. Melhor que um unico gate.
  - Reutilizar predicoes ja salvas (em vez de re-prever) permite ciclo de analise rapido — 1s por teste de filtro. Encoraja testar mais hipoteses, em vez de desistir por fricção.
  - Dataset intermediario separado do codigo de treino/backtest evita contaminacao: research so le parquet, nao toca modelo em produção.
- **Consequences:**
  - Qualquer "edge" descoberto no futuro tem metadata rastreavel (quem testou, quando, com que hipotese, quantos testes previos).
  - Bonferroni agressivo pode parecer pessimista — esperado e desejavel. Edges reais passam; ruido nao.
  - Requires disciplina: formular hipotese antes do teste. Log nao impede snooping mas torna visivel.

---

### [015] — Embargo pos-release em features ex-post de noticias

- **Date:** 2026-04-14
- **Status:** implemented
- **Decision:** `build_news_features` aplica duas janelas. Features ex-ante (impact, schedule, high_impact_flag, minutes_since_last_news) usam `timestamp <= current_time`. Features ex-post (sentiment basic/LLM, volatility, sentiment_final) usam `timestamp + NEWS_POST_RELEASE_LAG_MIN <= current_time`. Default 5 min, configuravel via env e override por parametro.
- **Alternatives considered:**
  - **(A) Scraper com delay:** so gravar `raw_{date}.parquet` apos T+N da release. Simples, mas acopla scraping a logica de feature e nao e retroativo em dados ja coletados.
  - **(B) Campo `signal_known_at`:** gravar timestamp real da primeira observacao de greenFont/redFont. Teoricamente mais preciso, mas exige scraper de alta frequencia rodando 24/7, nao funciona retroativamente (todo historico perderia `signal_known_at`), e expoe assimetria treino/producao.
  - **(C, escolhida) Duas janelas com lag fixo:** filtro aplicado na leitura, funciona em todos os parquets existentes, semantica unica entre treino e live, custo de implementacao baixo.
- **Reasoning:** O `signal` do Investing e derivado de `greenFont/redFont` aplicado ao `actual` **apos** a release. Usar como feature antes do lag de disseminacao e vazamento puro — CPCV nao protege, pois o futuro esta codificado na propria linha. Opcao C cobre 90%+ do risco com fracao do custo de B. B fica como upgrade futuro se migrar para M1/tick.
- **Consequences:** Features ex-post zeram nos primeiros 5 min apos cada release (comportamento correto). Modelos treinados antes do fix ainda carregam o vies — fica 100% efetivo apos proximo re-treino. Possivel degradacao temporaria de sinal em janelas news-driven ate re-treinar.

---

### [013] — Eliminacao de look-ahead bias no news pipeline

- **Date:** 2026-04-13
- **Status:** implemented
- **Decision:** Janela de noticias deve usar apenas dados passados `[t-3h, t]`. Feature `minutes_to_next_news` removida completamente do pipeline. Nenhuma feature pode usar informacao posterior ao timestamp do candle.
- **Alternatives considered:** (a) Manter minutes_to_next_news em dataset separado para analise offline; (b) Manter janela futura com flag
- **Reasoning:** Look-ahead bias invalida qualquer resultado de backtest e validacao. Em producao, o modelo nao tera acesso a noticias futuras. Manter a feature mesmo em dataset separado cria risco de reintroducao acidental.
- **Consequences:** 45→44 features. Metricas podem parecer piores, mas sao agora realistas.

---

### [014] — Regularizacao e early stopping obrigatorios

- **Date:** 2026-04-13
- **Status:** implemented
- **Decision:** XGBoost usa early_stopping_rounds=20, subsample=0.7, colsample_bytree=0.7, reg_lambda=1.0, max_depth=4. Random Forest usa min_samples_leaf=10, max_depth=8.
- **Alternatives considered:** (a) Manter defaults originais; (b) Hyperparameter tuning automatico
- **Reasoning:** Modelos sem regularizacao memorizavam noise dos dados de treino. Early stopping evita overfit no XGBoost. Parametros conservadores priorizam generalizacao sobre performance no treino.
- **Consequences:** Performance no treino vai cair. Performance out-of-sample deve estabilizar ou melhorar. Resultados mais confiaveis para trading real.

---

### [002] — Python + MetaTrader 5 como stack unica

- **Date:** 2026-04-07
- **Status:** decided
- **Decision:** Projeto inteiro em Python, usando a lib mt5 para integracao com MetaTrader 5.
- **Alternatives considered:** C++ direto no MT5, MQL5, Node.js com API bridge
- **Reasoning:** Python tem o melhor ecossistema de ML/data science. A lib mt5 oficial permite controle total do terminal. MT5 ja esta rodando na maquina do usuario.
- **Consequences:** Dependencia do Windows (MT5 so roda em Windows). Latencia um pouco maior que MQL5 nativo, mas aceitavel para M1.

---

### [003] — Armazenamento de candles no S3

- **Date:** 2026-04-07
- **Status:** decided
- **Decision:** Todos os candles historicos serao baixados e armazenados no AWS S3.
- **Alternatives considered:** Banco local (SQLite/Postgres), arquivos locais (parquet)
- **Reasoning:** S3 oferece durabilidade, acesso de qualquer lugar, e custo baixo para armazenamento. Permite reprocessamento e retreino sem depender do MT5 para dados historicos.
- **Consequences:** Necessita credenciais AWS. Custo mensal (baixo). Latencia de leitura maior que disco local — pode ser necessario cache local para treinamento.

---

### [004] — LLM local de 9B para analise de noticias

- **Date:** 2026-04-07
- **Status:** decided
- **Decision:** Usar LLM de 9B rodando na rede local para processar e analisar noticias FOREX.
- **Alternatives considered:** APIs externas (OpenAI, Anthropic), modelos menores, sem analise de noticias
- **Reasoning:** LLM local garante privacidade, sem custo por request, e baixa latencia na rede local. 9B eh um bom equilibrio entre capacidade e velocidade de inferencia.
- **Consequences:** Necessita hardware adequado na rede local. Qualidade de analise limitada pelo tamanho do modelo.

---

### [006] — Session-aware trading (features + decision + model selection)

- **Date:** 2026-04-09
- **Status:** decided
- **Decision:** Integrar sessoes de mercado Forex como: (1) features no modelo ML, (2) fator de decisao com threshold adaptativo, (3) criterio de selecao de modelo.
- **Alternatives considered:** Usar apenas hora do dia (sin/cos), ignorar sessoes, usar somente como filtro pos-sinal
- **Reasoning:** Sessoes Forex determinam liquidez, volatilidade e spread. Cada ativo tem sessoes primarias diferentes (USDJPY→Tokyo, EURUSD→London/NY). Usar sessoes como feature permite ao modelo aprender padroes por horario. Threshold adaptativo evita sinais em momentos de baixa liquidez. Model selection por sessao permite modelos especializados.
- **Consequences:** 8 features adicionais no pipeline (45 total). Signals filtrados para HOLD quando session_score < 0.3. Pesos por ativo podem precisar de ajuste fino com dados historicos reais.

---

### [010] — Matrix theme prioritizes terminal authenticity over dashboard polish

- **Date:** 2026-04-13
- **Status:** decided
- **Decision:** O tema `Matrix` deve ser tratado como um modo visual proprio de terminal hacker autentico, e nao como uma variante "bonita" do dashboard neon.
- **Alternatives considered:** manter apenas palette verde no tema atual, reaproveitar glassmorphism com tint verde, aproximar Matrix do Cyberpunk
- **Reasoning:** O objetivo do Matrix e passar sensacao de console vivo e leitura tecnica rapida. Quando o tema fica moderno demais, ele perde identidade. Data Stream, header e signal surfaces precisam parecer terminais de verdade.
- **Consequences:** No Matrix, preto puro + verde neon puro, tipografia mono, labels CLI, bordas finas e remocao de blur/gradiente devem ter prioridade. Se houver conflito entre "mais bonito" e "mais terminal", vencer o mais terminal.

---

### [005] — Conta demo para desenvolvimento

- **Date:** 2026-04-07
- **Status:** decided
- **Decision:** Usar conta demo MT5 (960082881) para todo o desenvolvimento e testes.
- **Alternatives considered:** Paper trading customizado, backtesting puro
- **Reasoning:** Conta demo permite testar execucao real de ordens sem risco financeiro. Ambiente identico ao real.
- **Consequences:** Dados de mercado podem ter leve diferenca do real. Slippage e execucao podem nao refletir 100% a conta real.

---

### [007] — Ensemble (media) para Live Prediction Chart na Control Tower

- **Date:** 2026-04-10
- **Status:** decided
- **Decision:** O LivePredictionChart da Control Tower exibe **uma unica linha de previsao = media (ensemble) das previsoes de todos os modelos** para t+1, t+2, t+3, em vez de plotar uma linha por modelo.
- **Alternatives considered:** (a) Plotar 5 linhas (uma por modelo); (b) Mostrar so o melhor modelo por simbolo
- **Reasoning:** UI limpa, leitura rapida, menos poluicao visual. O ensemble e estatisticamente mais robusto que escolher 1 modelo. A confidence (1 - dispersao normalizada entre os modelos) ainda sinaliza divergencia visualmente.
- **Consequences:** Backend precisa expor `/api/predict/predictions/latest` com ensemble pre-calculado. Detalhe por modelo continua disponivel via `/api/predict/predictions`.

---

### [009] — Signal Radar usa exclusivamente ensemble signal

- **Date:** 2026-04-13
- **Status:** decided
- **Decision:** O Signal Radar da Control Tower exibe apenas sinais ensemble (media de todos os modelos → `generate_signal()`), nunca sinais de modelos individuais. Novo endpoint dedicado `/api/predict/signals/radar` retorna todos os 11 simbolos.
- **Alternatives considered:** (a) Continuar usando `signals.csv` (sinais per-model); (b) Mostrar sinal do best model por simbolo
- **Reasoning:** Sinais per-model no radar causavam inconsistencia com o resto da Control Tower (que usa ensemble). Mostrar 1 modelo poderia ser enganoso se houver divergencia entre modelos. Ensemble e mais robusto e coerente com a filosofia do sistema. O endpoint dedicado garante cobertura de TODOS os 11 simbolos (antes limitado ao que existia em signals.csv).
- **Consequences:** Radar agora depende de previsoes existentes em `data/predictions/`. Simbolos sem previsoes aparecem como HOLD/0. Backend faz `generate_signal()` on-the-fly para cada request (leve, 11 simbolos max).

---

### [010] — Signal Board (ticker panel) substitui Signal Radar

- **Date:** 2026-04-13
- **Status:** decided
- **Decision:** Substituir o Signal Radar (radar circular SVG animado) por Signal Board — painel tipo ticker/order book com lista vertical de sinais ordenados por confidence DESC.
- **Alternatives considered:** (a) Manter radar e melhorar labels; (b) Criar tabela simples sem visual; (c) Heat map
- **Reasoning:** Radar era visualmente impressionante mas lento para leitura operacional. Em contexto de trading, clareza > estetica. Lista vertical ordenada por forca permite decisao instantanea. Inspirado em order books e terminais profissionais. Barra de progresso + badge colorido mantem visual rico sem sacrificar leitura.
- **Consequences:** SignalRadar.jsx permanece no repo mas nao e mais importado. SignalBoard.jsx usa mesmo endpoint `/api/predict/signals/radar`. Flash animation ao mudar sinal ajuda a detectar mudancas.

---

### [011] — Theme system com CSS variables + React Context

- **Date:** 2026-04-13
- **Status:** decided
- **Decision:** Implementar sistema de temas (Default/Matrix/Cyberpunk) via React Context + CSS variables, com persistencia em localStorage.
- **Alternatives considered:** (a) Tailwind dark mode classes; (b) CSS-in-JS (styled-components); (c) Apenas um tema fixo
- **Reasoning:** CSS variables permitem troca instantanea sem re-render. React Context evita prop drilling. localStorage preserva escolha entre sessoes. Approach funciona com Tailwind sem conflito. Fallback values nos CSS vars garantem que componentes que nao foram migrados continuem funcionando.
- **Consequences:** Novos componentes devem usar `var(--theme-*)` em vez de cores hardcoded. `.glass-card` e `.neon-border` ja herdaram as vars automaticamente. Temas futuros podem ser adicionados editando apenas ThemeProvider.jsx.

---

### [008] — lightweight-charts para candles (em vez de Recharts)

- **Date:** 2026-04-10
- **Status:** decided
- **Decision:** Para o LivePredictionChart usar `lightweight-charts` (TradingView) em vez de Recharts.
- **Alternatives considered:** Recharts custom (ja em uso na app), Chart.js, ApexCharts
- **Reasoning:** Recharts nao tem suporte nativo a candles e exigiria shapes customizadas. lightweight-charts e dedicado a financial charts, tem candles nativos, performance superior, visual profissional. O custo e ~150KB extra mas isolado em chunk lazy (LivePredictionChart-*.js).
- **Consequences:** Nova dependencia no frontend. Outros graficos da app continuam em Recharts. Migracao futura para mais charts financeiros fica facilitada.

---

### [012] — Matrix theme: uniformizacao visual completa de todos os componentes

- **Date:** 2026-04-13
- **Status:** decided
- **Decision:** Todos os componentes do Control Tower devem seguir o mesmo padrao visual quando `theme === "matrix"`: fundo preto puro, texto verde neon (#00ff41), tipografia monospace, barras solidas sem gradiente, bordas finas verdes, scanlines, sem blur/glass/sombras suaves. Componentes corrigidos: ControlTowerClock (Forex Sessions), SessionPanel (Session Intelligence), LivePredictionChart (candles). Candles reais: up=#00ff41, down=#006622. Candles previstos: verde transparente. NOW marker verde. Todas as mudancas condicionais a `theme === "matrix"` — Default e Cyberpunk intactos.
- **Alternatives considered:** Usar apenas CSS global (data-theme selectors) sem mudancas em componentes
- **Reasoning:** CSS global nao alcanca propriedades inline dos componentes (cores de SVG, opcoes do lightweight-charts, badges com cores hardcoded). Necessario condicional JS nos componentes para uniformizar completamente.
- **Consequences:** Componentes agora importam `useTheme()` e verificam `isMatrix`. Codigo levemente mais longo mas com separacao clara de estilos por tema.

### [013] — Suite de testes do frontend: Vitest + Testing Library + MSW

- **Date:** 2026-04-15
- **Status:** implemented
- **Decision:** Adotar Vitest (test runner), @testing-library/react (renderizacao + queries), MSW (mock HTTP network) como stack oficial de testes do Command Center em `command_center/frontend/src/tests/`.
- **Alternatives considered:** Jest (mais maduro mas ESM/Vite friction), Cypress/Playwright (integracao real no browser — lento, exige backend up), RTL sem MSW (mocks de fetch manuais).
- **Reasoning:** Vitest compartilha config/transform com Vite (zero duplicacao). MSW intercepta na camada de rede, permitindo testar o caminho real `fetch → api.js → component` sem chamar backend. Testing Library foca em comportamento, nao em detalhes de implementacao.
- **Convention:** Componentes com WebGL/canvas (`lightweight-charts`, `react-globe.gl`) sao stubados via `vi.mock(...)` no import. Hooks de rede (`useWebSocket`, `useApi`) sao mockados em testes unitarios; MSW fica reservado ao arquivo `test_api_integration.jsx`.
- **Consequences:** Suite roda em ~5s, nao depende de backend nem de browser, e cobre contratos de dados (confidence range, signal enum, OHLC). Se teste falhar, corrigir componente — nao relaxar o teste.
