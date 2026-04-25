# 2026-04-25 — Agent researcher: integracao OpenCode end-to-end

## Goal

Fazer o `src/agent_researcher/orchestrator.py` rodar end-to-end no Windows
contra o LM Studio + qwen3.5:9b hospedado em Mac mini (192.168.100.191:3032),
sem quebrar a fronteira de escrita do agente nem contaminar arquivos do projeto.

## What was tried

1. **`opencode chat --input <file>`** (codigo herdado): subcomando inexistente,
   o CLI de hoje usa `opencode run`. Erro original: help do CLI no stderr.
2. **`opencode run --prompt <texto>`**: estourou limite de 8 KB de linha de
   comando do Windows com prompt JSON cheio. `Linha de comando muito longa`.
3. **stdin via `subprocess.run(input=prompt)`**: bypass do limite. Funciona
   isoladamente, mas a chamada via shim `opencode.CMD` dentro de `cmd.exe`
   mutilava o valor do `--model`: `qwen/qwen/qwen3.5:9b` chegava ao yargs como
   `qwen/`. Resultado: `ProviderModelNotFoundError modelID=""`.
4. **`bash -lc "..."`** roteando pelo `bash` do PATH: o `bash` resolvido era o
   do WSL (`/mnt/c/...`), e o WSL nao tinha `node` instalado. RC=127.
5. **`node <script_js>` direto, pulando o shim `.CMD`**: Funciona. O script real
   esta em `C:\Users\Tiago\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode`
   e `subprocess.run([node, script, "run", "--model", "qwen/qwen/qwen3.5:9b"])`
   preserva o token corretamente.

Apos chegar la, dois problemas adicionais:

6. **`OpenCodeClient(model="qwen")` hardcoded em `orchestrator.py`** sobrescrevia
   o default novo `qwen/qwen/qwen3.5:9b`. Removido o argumento.
7. **`opencode run` e agentico, nao completion**: o agente padrao `build` tem
   tools Edit/Bash, gastou minutos explorando o repo, propondo edicoes em
   `hypothesis_generator.py`/`llm_interface.py`/`vault_reader.py` (vistas no
   TUI do opencode mas nao aplicadas em disco). Nao retornava JSON.

## Solution

- **Agente customizado registrado em `~/.config/opencode/opencode.jsonc`**:
  `autotrader-researcher` com tools so de leitura e web (`read`, `list`, `glob`,
  `grep`, `webfetch`, `websearch`). `write`, `edit`, `patch`, `bash` desligados.
  Permission tambem fecha edit/write/bash. Prompt do agente reforca: pesquisar,
  ler vault e dataset, opcionalmente buscar contexto na web, e ao final emitir
  **apenas** um array JSON.
- **`OpenCodeClient` agora aceita `agent` (default `autotrader-researcher`,
  override via `AGENT_RESEARCH_OPENCODE_AGENT`)** e injeta `--agent` no comando.
- **No Windows, o cliente chama `node <opencode-bin>`** em vez do shim `.CMD`,
  resolvendo `node` via `shutil.which`/`AGENT_RESEARCH_NODE_EXE` e o script
  via `AGENT_RESEARCH_OPENCODE_SCRIPT` (auto-detect ao lado do `.CMD` quando
  nao setado). Bypassa a mutilação de argumentos do shim.
- **stdin entrega o prompt** (sem limite de 8 KB).
- **`timeout_seconds` agora `None` por padrao** — qwen 9B no Mac mini pode
  demorar minutos. Memoria do usuario salva: nao colocar timeout em chamadas
  ao LLM local.
- **Encoding `utf-8` com `errors="replace"`** pra nao explodir com mojibake do
  ANSI no stderr do opencode.
- **`_dump_raw` salva stdout/stderr crus em
  `src/agent_researcher/tmp/prompts/raw_output_*.log`** quando o subprocess
  falha ou o parse de JSON nao acha array — chave pra debug do shim.
- **Bumps moderados de contexto** (cabem em 100k):
  - `hypothesis_generator.load_daily_eval_summary`: 5 -> 15 arquivos, com
    breakdowns adicionais por symbol/trend/volatility_regime/hour_utc.
  - `hypothesis_generator.load_filter_log_summary`: 50 -> 200 linhas.
  - `vault_reader.load_context`: 20 -> 50 arquivos por categoria,
    snippet 4 KB -> 8 KB.
- **Mensagem inicial do prompt** instrui explicitamente o agente a usar a
  janela de 100k tokens e cruzar referencias do vault/daily_eval/filter_log
  antes de propor.

## End-to-end run

```
python -m src.agent_researcher.orchestrator --max-hypotheses 1
```

Resultado:

- Hipotese gerada: *"H5 - Confidence >= 0.75 combined with Tokyo session
  (tokyo, tokyo,london) and signal=1 improves hit_t1 to >62% with positive
  PnL"*.
- Filtros: `confidence_min=0.75`, `session=['tokyo','tokyo,london']`, `signal=1`.
- Filter hash: `e84fbf339819`.
- Verdict no research split: `REJECTED_N` (n=0). Holdout **nao** consumido
  (gate research nao passou).
- Estrategia nao persistida (correto).

Suite completa rodada: `pytest -q` -> **511 passed, 2 warnings** (warnings
pre-existentes, nao relacionadas).

## What I learned

- `opencode run` e um agente real. Sem agente custom com tools restritos, ele
  vira loop infinito de exploracao de codigo. O design original do modulo
  assumia completion API, nao agente.
- Shims `.CMD` no Windows mutilam valores que contem `/` e `:` quando passados
  via cmd.exe + list2cmdline. Fugir do shim e mais simples que tentar enquadrar
  o quoting.
- WSL bash entra no PATH antes do Git Bash em algumas configuracoes — usar
  `bash` para invocar exes de Windows e armadilha.
- Prompt do agent_researcher hoje fica em ~2.6k tokens com vault quase vazio.
  Aumentar bumps fica seguro ate o vault crescer; quando passar de ~50k, vale
  truncar ou paginar.

## Next session should

- Acumular >=14 dias de daily_eval para o agente ter sample real (hoje filter
  retornou n=0).
- Avaliar ligar `--dangerously-skip-permissions` se opencode comecar a pedir
  aprovacao em websearch/webfetch (com tools restritos teoricamente nao deveria).
- Considerar `--format json` do opencode para parse mais resiliente que o
  bracket extractor atual.
- Confirmar que o scheduler 03:00 UTC esta vivo no host onde rodara em prod.
