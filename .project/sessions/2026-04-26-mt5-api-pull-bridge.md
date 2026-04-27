# 2026-04-26 — MT5 HTTP pull bridge (passo 1)

## Goal

Comecar a desacoplar o MT5 do resto do sistema. Hoje toda chamada ao
MetaTrader 5 importa `MetaTrader5` direto e por isso o stack inteiro
precisa rodar em Windows. Objetivo final: rodar tudo (Linux) consumindo
candles/tick/account de uma maquina Windows que segura o terminal MT5.

Este passo cobre apenas o servidor FastAPI fino com **pull HTTP**. Sem
push/webhook, sem WebSocket, sem execucao de ordens. So leitura.

## What was missing

- Nao havia camada HTTP em volta do `MT5Connection`. Qualquer outra
  maquina precisaria importar `MetaTrader5` (Windows-only).
- `startup.bat` nao subia o servico novo.

## Solution

Pasta nova `mt5_api/` na raiz do projeto:

- `mt5_api/__init__.py`
- `mt5_api/main.py` — FastAPI com lifespan que conecta no MT5 no startup
  e desconecta no shutdown. Compartilha um unico `MT5Connection` entre
  requests, protegido por `threading.Lock` (a lib `MetaTrader5` nao eh
  thread-safe).

### Endpoints (todos GET)

| Rota | O que faz |
|---|---|
| `/health` | Sem auth. Reporta `connected: true/false`. |
| `/account` | `account_info()` |
| `/terminal` | `terminal_info()` |
| `/symbols?group=*USD*` | Lista simbolos visiveis no broker |
| `/symbols/{symbol}` | Info do simbolo (bid/ask/spread/digits/...) |
| `/symbols/{symbol}/tick` | Ultimo tick (time ISO + bid/ask/last/volume) |
| `/candles/{symbol}?tf=M1&count=1000` | Ultimos N candles |
| `/candles/{symbol}?tf=M1&date_from=...&date_to=...` | Range temporal |

Datas chegam como `datetime` (FastAPI parse de query string ISO).
Resposta de candles converte `time` para string ISO antes do
`to_dict(orient="records")`.

### Auth

Bearer token opcional via env `MT5_API_TOKEN`. Se setado, todas as rotas
exceto `/health` exigem `Authorization: Bearer <token>`. Sem o env,
servidor abre sem auth (uso em LAN/VPN). Recomendado VPN
(Tailscale/WireGuard) + token quando expor.

### Config via env

- `MT5_API_HOST` (default `0.0.0.0`)
- `MT5_API_PORT` (default `8002` — fora do 8000 do command_center backend)
- `MT5_API_TOKEN` (opcional)
- Reaproveita `MT5_ACCOUNT/PASSWORD/SERVER` ja usados por `MT5Connection`.

### startup.bat

Nova linha:

```bat
start "AutoTrader MT5 API" cmd /k "call venv/Scripts/activate && python -m mt5_api.main"
```

Posicionada logo apos o backend do command_center.

## Validation

- `ruff check mt5_api/` ok.
- Carregamento da app validado com stub de `MetaTrader5` — todas as
  rotas registradas: `/health, /account, /terminal, /symbols,
  /symbols/{symbol}, /symbols/{symbol}/tick, /candles/{symbol}`.
- Nao subiu contra terminal MT5 real ainda (sera feito no proximo
  start manual).

## Update (mesma data) — passo 2: cliente + factory

- `src/mt5/remote_client.py`: `MT5RemoteClient` com a mesma interface
  publica do `MT5Connection` (subset usado pelos consumidores). Usa
  `httpx.Client` reaproveitando conexoes; valida `/health` no
  `connect()` e exige `connected: true` antes de aceitar requests.
  Bearer token e base URL via `settings.mt5.api_token` / `api_url`.
- `src/mt5/__init__.py`: nova factory `get_mt5_connection()` que
  retorna `MT5Connection` ou `MT5RemoteClient` com base em
  `settings.mt5.backend` ("local" default, "remote" para HTTP).
- `config/settings.py` (`MT5Config`): ganhou `backend`, `api_url`
  (default `http://localhost:8002`), `api_token`. Defaults sensatos —
  sem mexer no `.env`, comportamento atual fica identico.
- `src/execution/loop.py`: trocou `MT5Connection()` por
  `get_mt5_connection()`. Unico ponto de instanciacao em runtime.
- **Validacao end-to-end com API real** (`mt5_api` no ar em
  `localhost:8002`, `MT5_BACKEND=remote`): account_info,
  get_available_symbols, get_candles e get_tick retornaram dados
  corretos do terminal MT5. Default `local` continua devolvendo
  `MT5Connection`. `tests/mt5/` 25/25 passando.

## Notes / next steps

- Quando portar pra Linux: instalar `httpx` (ja no requirements), setar
  no `.env`:
  ```
  MT5_BACKEND=remote
  MT5_API_URL=http://<ip-windows>:8002
  MT5_API_TOKEN=<se servidor exigir>
  ```
- Proxima area natural: testar o `loop.py` ponta a ponta em modo remote
  + medir latencia LAN. Se quiser trocar a Windows-box por VPS
  separada, considerar HTTPS na frente (Caddy/Traefik) ou Tailscale.
- **Quando entrar execucao de ordens:** `POST /order` com `client_id`
  para idempotencia, e novo metodo no `MT5RemoteClient`/`MT5Connection`.
- **Quando entrar execucao de ordens:** adicionar `POST /order` com
  `client_id` para idempotencia (proteger contra retry duplicado em
  falha de rede).
- **Backup pra recovery:** servidor pode opcionalmente fazer cache
  parquet local dos ultimos N candles servidos, pro Linux sincronizar
  apos queda — nao implementado nesta sessao.
- Nao foi adicionado teste automatizado ainda; testar so faz sentido
  com mock pesado da `MetaTrader5` ou com terminal real. Avaliar.
