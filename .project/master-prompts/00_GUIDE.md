# AutoTrader — Implementation Guide

> This is the entry-point document for any AI agent implementing this project.
> Read this file first, then execute the Master Prompts in the order listed below.

---

## 1. What This Project Does

Sistema de trading algoritmico para FOREX em M1. Conecta ao MetaTrader 5 via Python, baixa e armazena candles historicos no S3, treina modelos de ML com CPCV (purge + embargo), integra noticias FOREX via LLM local de 9B, e executa trades automaticamente. O estado final eh um bot autonomo que analisa mercado, noticias e sinais de multiplos modelos para tomar decisoes de trading.

---

## 2. Execution Order

| Order | Prompt File | Creates | Depends On |
|-------|-------------|---------|------------|
| 1st | `STEP_1_PROJECT_STRUCTURE.txt` | Estrutura de pastas, config, conexao MT5 | Nada |
| 2nd | `STEP_2_DATA_PIPELINE.txt` | Download de candles MT5 + upload S3 | Step 1 |
| 3rd | `STEP_3_FEATURE_ENGINEERING.txt` | Features/indicadores tecnicos | Step 2 |
| 4th | `STEP_4_CPCV_VALIDATION.txt` | Framework CPCV com purge e embargo | Step 3 |
| 5th | `STEP_5_ML_MODELS.txt` | Modelos de ML (XGBoost, LGBM, etc) | Step 3, 4 |
| 6th | `STEP_6_NEWS_LLM.txt` | Integracao noticias + LLM 9B | Step 1 |
| 7th | `STEP_7_SIGNAL_ENGINE.txt` | Motor de sinais (combina modelos + noticias) | Step 5, 6 |
| 8th | `STEP_8_EXECUTION.txt` | Execucao de ordens no MT5 | Step 1, 7 |
| 9th | `STEP_9_MONITORING.txt` | Monitoramento, logging, alertas | Step 8 |

---

## 3. Repository Conventions

### File naming
- Modulos: `src/{module_name}/{file_name}.py`
- Testes: `tests/test_{module_name}.py`
- Configs: `config/`
- Notebooks exploratórios: `notebooks/`

### Precision / numeric rules
- Usar `float` para precos (MT5 retorna float). Nao eh necessario Decimal para FOREX.
- Sempre arredondar pips para 5 casas decimais (4 para JPY pairs).

### Libraries
- MT5: `MetaTrader5`
- Data: `pandas`, `numpy`
- ML: `scikit-learn`, `xgboost`, `lightgbm`, `pytorch`
- AWS: `boto3`
- Config: `python-dotenv`
- News: a definir
- Sempre atualizar `requirements.txt` apos instalar qualquer lib

### Testing conventions
- `pytest` como framework de testes
- Todo modulo tem teste correspondente em `tests/`

### Validacao de modelos
- **OBRIGATORIO**: Todo treinamento usa CPCV com purge e embargo
- Referencia: Marcos Lopez de Prado — "Advances in Financial Machine Learning"
- NUNCA usar K-Fold, TimeSeriesSplit ou qualquer CV que ignore estrutura temporal

### Ambiente virtual
- Sempre ativar: `venv\Scripts\activate`
- Sempre atualizar `requirements.txt` apos `pip install`

---

## 4. Key Reference Files

| File | Purpose |
|------|---------|
| `.env` | Credenciais MT5, AWS, LLM |
| `config/symbols.py` | Lista de ativos FOREX alvo |
| `config/settings.py` | Configuracoes globais (timeframes, parametros) |
| `requirements.txt` | Dependencias Python |

---

## 5. Notes & Gotchas

- MT5 so roda em Windows. A lib `MetaTrader5` requer que o terminal esteja aberto.
- `mt5.initialize()` pode falhar silenciosamente — sempre checar retorno.
- Dados de M1 do MT5 tem limite historico (~2 anos dependendo do broker).
- Para historico maior, considerar fontes alternativas.
- CPCV eh computacionalmente caro — planejar tempo de treinamento.
- LLM de 9B na rede local — verificar latencia antes de usar em tempo real.
- Conta demo: spreads e execucao podem diferir da conta real.
