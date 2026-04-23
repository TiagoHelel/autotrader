# Setup Guide

> How to get this project running locally from scratch.

---

## Prerequisites

- Python 3.10+
- MetaTrader 5 instalado e rodando (Windows)
- Conta MT5 (demo ou real)
- AWS CLI configurado (para S3)
- LLM de 9B rodando na rede local

---

## Environment variables

```bash
# Copie .env.example para .env e preencha:
MT5_ACCOUNT=         # Numero da conta MT5
MT5_PASSWORD=        # Senha da conta MT5
MT5_PASSWORD_READ=   # Senha de leitura MT5
MT5_SERVER=          # Servidor MT5 (ex: MetaQuotes-Demo)

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
S3_BUCKET=

LLM_API_URL=         # Endpoint da LLM local
LLM_API_KEY=         # Key da LLM (se necessario)

NEWS_API_KEY=        # API de noticias FOREX
```

---

## Install & run

```bash
# 1. Ativar ambiente virtual
venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Verificar conexao com MT5
python -c "import MetaTrader5 as mt5; mt5.initialize(); print(mt5.terminal_info()); mt5.shutdown()"
```

---

## Common errors & fixes

| Error | Fix |
|---|---|
| `mt5.initialize() retorna False` | Verificar se o MetaTrader 5 esta aberto e logado |
| `ModuleNotFoundError: MetaTrader5` | `pip install MetaTrader5` |
| `Timeout na conexao MT5` | Verificar firewall e se o terminal MT5 esta respondendo |

---

## Useful commands

```bash
venv\Scripts\activate          # Ativar venv
pip install -r requirements.txt # Instalar deps
pip freeze > requirements.txt   # Atualizar requirements
python main.py                  # Executar (futuro)
pytest                          # Rodar testes
```
