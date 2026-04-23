"""
Configuracoes globais do AutoTrader.
Carrega variaveis de ambiente do .env e expoe como dataclass.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env do root do projeto
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class MT5Config:
    account: int = field(default_factory=lambda: int(os.getenv("MT5_ACCOUNT", "0")))
    password: str = field(default_factory=lambda: os.getenv("MT5_PASSWORD", ""))
    password_read: str = field(default_factory=lambda: os.getenv("MT5_PASSWORD_READ", ""))
    server: str = field(default_factory=lambda: os.getenv("MT5_SERVER", ""))


@dataclass
class S3Config:
    access_key_id: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", ""))


@dataclass
class LLMConfig:
    """Configuracao do LLM unico (Qwen 3.5 9B local via Chat Completions).

    Sem cadeia de fallback remoto — se o endpoint local falhar, cai direto
    para a heuristica em `_fallback_sentiment` (used_fallback=True).
    """
    api_url: str = field(default_factory=lambda: os.getenv("LLM_API_URL", ""))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen/qwen3.5:9b"))
    api_kind: str = field(default_factory=lambda: os.getenv("LLM_API_KIND", "chat-completions"))
    disable_thinking: bool = field(default_factory=lambda: os.getenv("LLM_DISABLE_THINKING", "true").lower() == "true")


@dataclass
class Settings:
    """Configuracoes centralizadas do projeto."""
    mt5: MT5Config = field(default_factory=MT5Config)
    s3: S3Config = field(default_factory=S3Config)
    llm: LLMConfig = field(default_factory=LLMConfig)
    news_api_key: str = field(default_factory=lambda: os.getenv("NEWS_API_KEY", ""))

    # Timeframe padrao
    timeframe: str = "M5"

    # Prediction config
    input_window: int = 10       # ultimos N candles como input
    output_horizon: int = 3      # prever N candles futuros
    min_candles: int = 500       # minimo de candles para coleta
    prediction_interval: int = 5  # minutos entre execucoes

    # News embargo (anti look-ahead bias)
    # Features ex-post (sentiment/LLM) so sao consideradas conhecidas apos
    # timestamp_agendado + news_post_release_lag_min. Features ex-ante
    # (impact, schedule) usam timestamp agendado direto.
    news_post_release_lag_min: int = field(
        default_factory=lambda: int(os.getenv("NEWS_POST_RELEASE_LAG_MIN", "5"))
    )

    # Data directories
    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def features_dir(self) -> Path:
        return self.data_dir / "features"

    @property
    def predictions_dir(self) -> Path:
        return self.data_dir / "predictions"

    @property
    def metrics_dir(self) -> Path:
        return self.data_dir / "metrics"

    @property
    def experiments_dir(self) -> Path:
        return self.data_dir / "experiments"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    # Diretorio raiz do projeto
    project_root: Path = PROJECT_ROOT


# Instancia global
settings = Settings()
