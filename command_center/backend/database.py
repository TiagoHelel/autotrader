"""
AutoTrader Command Center - SQLite Mock Database
Generates realistic FOREX trading data for the dashboard.
"""

import sqlite3
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "autotrader_cc.db"

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
    "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "XAUUSD",
]

# Realistic mid-prices for each symbol
BASE_PRICES: dict[str, float] = {
    "EURUSD": 1.1520,
    "GBPUSD": 1.3080,
    "USDJPY": 160.25,
    "USDCHF": 0.8740,
    "AUDUSD": 0.6620,
    "USDCAD": 1.3560,
    "NZDUSD": 0.6150,
    "EURGBP": 0.8810,
    "EURJPY": 184.60,
    "GBPJPY": 209.45,
    "XAUUSD": 4620.50,
}

# Pip size per symbol (used for realistic spread / SL / TP)
PIP_SIZE: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "USDCHF": 0.0001,
    "AUDUSD": 0.0001,
    "USDCAD": 0.0001,
    "NZDUSD": 0.0001,
    "EURGBP": 0.0001,
    "EURJPY": 0.01,
    "GBPJPY": 0.01,
    "XAUUSD": 0.01,
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _rand_price(symbol: str, spread_pips: float = 0) -> float:
    """Return a price near the base with small random noise."""
    base = BASE_PRICES[symbol]
    pip = PIP_SIZE[symbol]
    noise = random.gauss(0, 15) * pip
    return round(base + noise + spread_pips * pip, 5 if pip < 0.001 else 3 if pip < 0.1 else 2)


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS account_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            balance REAL NOT NULL,
            equity REAL NOT NULL,
            pnl_daily REAL NOT NULL,
            pnl_total REAL NOT NULL,
            drawdown REAL NOT NULL,
            winrate REAL NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('BUY','SELL')),
            volume REAL NOT NULL,
            open_price REAL NOT NULL,
            current_price REAL NOT NULL,
            sl REAL,
            tp REAL,
            pnl REAL NOT NULL,
            open_time TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('BUY','SELL')),
            volume REAL NOT NULL,
            open_price REAL NOT NULL,
            close_price REAL NOT NULL,
            pnl REAL NOT NULL,
            open_time TEXT NOT NULL,
            close_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal TEXT NOT NULL CHECK(signal IN ('BUY','SELL','HOLD')),
            confidence REAL NOT NULL,
            timestamp TEXT NOT NULL,
            model_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            currency TEXT NOT NULL,
            impact TEXT NOT NULL CHECK(impact IN ('HIGH','MEDIUM','LOW')),
            sentiment TEXT NOT NULL CHECK(sentiment IN ('POSITIVE','NEGATIVE','NEUTRAL')),
            score REAL NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL CHECK(level IN ('INFO','WARNING','ERROR')),
            message TEXT NOT NULL,
            module TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS model_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            accuracy REAL NOT NULL,
            precision_val REAL NOT NULL,
            recall REAL NOT NULL,
            f1 REAL NOT NULL,
            auc REAL NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feature_importance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            importance REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS equity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equity REAL NOT NULL,
            timestamp TEXT NOT NULL
        );
    """)


def _seed_account(conn: sqlite3.Connection) -> None:
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO account_state (balance, equity, pnl_daily, pnl_total, drawdown, winrate, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (10000.0, 10245.30, 127.50, 245.30, 3.2, 62.5, now),
    )


def _seed_positions(conn: sqlite3.Connection) -> None:
    position_specs = [
        ("EURUSD", "BUY", 0.10),
        ("USDJPY", "SELL", 0.05),
        ("GBPUSD", "BUY", 0.08),
        ("XAUUSD", "BUY", 0.02),
        ("AUDUSD", "SELL", 0.12),
    ]
    now = datetime.utcnow()
    for symbol, side, volume in position_specs:
        pip = PIP_SIZE[symbol]
        open_price = _rand_price(symbol)
        # Current price slightly moved
        move = random.gauss(0, 20) * pip
        current_price = round(open_price + move, 5 if pip < 0.001 else 3 if pip < 0.1 else 2)

        if side == "BUY":
            pnl = round((current_price - open_price) / pip * volume * 10, 2)
            sl = round(open_price - random.randint(30, 60) * pip, 5 if pip < 0.001 else 3 if pip < 0.1 else 2)
            tp = round(open_price + random.randint(40, 80) * pip, 5 if pip < 0.001 else 3 if pip < 0.1 else 2)
        else:
            pnl = round((open_price - current_price) / pip * volume * 10, 2)
            sl = round(open_price + random.randint(30, 60) * pip, 5 if pip < 0.001 else 3 if pip < 0.1 else 2)
            tp = round(open_price - random.randint(40, 80) * pip, 5 if pip < 0.001 else 3 if pip < 0.1 else 2)

        open_time = (now - timedelta(minutes=random.randint(10, 480))).isoformat()
        conn.execute(
            "INSERT INTO positions (symbol, type, volume, open_price, current_price, sl, tp, pnl, open_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (symbol, side, volume, open_price, current_price, sl, tp, pnl, open_time),
        )


def _seed_trade_history(conn: sqlite3.Connection) -> None:
    now = datetime.utcnow()
    for i in range(50):
        symbol = random.choice(SYMBOLS)
        side = random.choice(["BUY", "SELL"])
        volume = round(random.choice([0.01, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20]), 2)
        pip = PIP_SIZE[symbol]

        open_price = _rand_price(symbol)
        # Slight bias toward winners (62% win-rate)
        is_win = random.random() < 0.625
        move_pips = random.randint(5, 60) if is_win else -random.randint(5, 45)
        if side == "SELL":
            move_pips = -move_pips

        close_price = round(open_price + move_pips * pip, 5 if pip < 0.001 else 3 if pip < 0.1 else 2)
        pnl = round(move_pips * volume * 10, 2) if side == "BUY" else round(-move_pips * volume * 10, 2)

        duration = random.randint(3, 720)
        close_time = now - timedelta(minutes=random.randint(0, 10080))  # last 7 days
        open_time = close_time - timedelta(minutes=duration)

        conn.execute(
            "INSERT INTO trade_history (symbol, type, volume, open_price, close_price, pnl, open_time, close_time, duration_minutes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (symbol, side, volume, open_price, close_price, pnl, open_time.isoformat(), close_time.isoformat(), duration),
        )


def _seed_predictions(conn: sqlite3.Connection) -> None:
    models = ["XGBoost", "LightGBM", "RandomForest"]
    now = datetime.utcnow()
    for i in range(20):
        symbol = random.choice(SYMBOLS)
        signal = random.choices(["BUY", "SELL", "HOLD"], weights=[0.35, 0.35, 0.30])[0]
        confidence = round(random.uniform(0.52, 0.94), 4)
        ts = (now - timedelta(minutes=random.randint(0, 1440))).isoformat()
        model = random.choice(models)
        conn.execute(
            "INSERT INTO predictions (symbol, signal, confidence, timestamp, model_name) "
            "VALUES (?, ?, ?, ?, ?)",
            (symbol, signal, confidence, ts, model),
        )


def _seed_news(conn: sqlite3.Connection) -> None:
    headlines = [
        ("Fed Holds Rates Steady, Signals Patience on Future Cuts", "Reuters", "USD", "HIGH", "NEUTRAL", 0.05),
        ("ECB Lagarde Hints at Gradual Rate Reduction Path", "Bloomberg", "EUR", "HIGH", "NEGATIVE", -0.35),
        ("US Non-Farm Payrolls Beat Expectations at 256K", "CNBC", "USD", "HIGH", "POSITIVE", 0.72),
        ("BOJ Maintains Ultra-Loose Policy Despite Yen Weakness", "Nikkei", "JPY", "HIGH", "NEGATIVE", -0.48),
        ("UK CPI Inflation Falls to 2.3%, Below Forecast", "BBC", "GBP", "HIGH", "POSITIVE", 0.55),
        ("Swiss National Bank Surprises With 25bp Rate Cut", "SWI", "CHF", "HIGH", "NEGATIVE", -0.62),
        ("Australian Employment Data Exceeds Expectations", "AFR", "AUD", "MEDIUM", "POSITIVE", 0.41),
        ("Bank of Canada Signals End of Tightening Cycle", "Globe", "CAD", "HIGH", "NEGATIVE", -0.30),
        ("RBNZ Holds OCR at 5.50%, Hawkish Tone Persists", "NZ Herald", "NZD", "MEDIUM", "POSITIVE", 0.28),
        ("Gold Surges Past $4600 on Safe-Haven Demand", "Kitco", "XAU", "MEDIUM", "POSITIVE", 0.65),
        ("Eurozone PMI Contracts for Third Consecutive Month", "Markit", "EUR", "MEDIUM", "NEGATIVE", -0.52),
        ("US ISM Services Index Rises to 54.1, Beats Consensus", "MarketWatch", "USD", "MEDIUM", "POSITIVE", 0.38),
        ("China Trade Surplus Widens, Boosting AUD Sentiment", "SCMP", "AUD", "MEDIUM", "POSITIVE", 0.33),
        ("Oil Prices Slide 3% on Demand Concerns", "Reuters", "CAD", "MEDIUM", "NEGATIVE", -0.40),
        ("UK GDP Growth Stalls at 0.1% in Q4", "FT", "GBP", "HIGH", "NEGATIVE", -0.58),
        ("US Consumer Confidence Hits 6-Month High", "Conference Board", "USD", "MEDIUM", "POSITIVE", 0.44),
        ("Japan Core CPI Rises 2.8%, Above BOJ Target", "Reuters", "JPY", "MEDIUM", "POSITIVE", 0.35),
        ("German IFO Business Climate Drops Below Expectations", "IFO", "EUR", "MEDIUM", "NEGATIVE", -0.30),
        ("FOMC Minutes Reveal Division on Rate Path", "Fed", "USD", "HIGH", "NEUTRAL", -0.08),
        ("Swiss Franc Strengthens on Global Risk Aversion", "FXStreet", "CHF", "LOW", "POSITIVE", 0.22),
        ("AUD/USD Rebounds on Iron Ore Price Rally", "DailyFX", "AUD", "LOW", "POSITIVE", 0.18),
        ("Canadian Housing Starts Decline 5% MoM", "StatsCan", "CAD", "LOW", "NEGATIVE", -0.15),
        ("NZ Dairy Auction Prices Rise 2.1%", "GDT", "NZD", "LOW", "POSITIVE", 0.20),
        ("ECB Economic Bulletin Warns of Persistent Weakness", "ECB", "EUR", "MEDIUM", "NEGATIVE", -0.42),
        ("US Initial Jobless Claims Fall to 210K", "DoL", "USD", "MEDIUM", "POSITIVE", 0.30),
        ("BOE Bailey Warns Markets Against Premature Rate Cut Bets", "Reuters", "GBP", "HIGH", "POSITIVE", 0.48),
        ("Gold ETF Inflows Hit 2-Year High Amid Geopolitical Tensions", "WGC", "XAU", "LOW", "POSITIVE", 0.55),
        ("USD/JPY Breaks 160 Amid Carry Trade Resurgence", "Bloomberg", "JPY", "MEDIUM", "NEGATIVE", -0.38),
        ("Eurozone Retail Sales Surprise to the Upside", "Eurostat", "EUR", "LOW", "POSITIVE", 0.25),
        ("US Treasury Yields Climb on Strong Economic Data", "WSJ", "USD", "MEDIUM", "POSITIVE", 0.32),
    ]
    now = datetime.utcnow()
    for i, (title, source, currency, impact, sentiment, score) in enumerate(headlines):
        ts = (now - timedelta(minutes=random.randint(0, 4320))).isoformat()  # last 3 days
        conn.execute(
            "INSERT INTO news (title, source, currency, impact, sentiment, score, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, source, currency, impact, sentiment, score, ts),
        )


def _seed_logs(conn: sqlite3.Connection) -> None:
    log_templates = [
        ("INFO", "Position opened: {symbol} {side} {vol} lots @ {price}", "TradeExecutor"),
        ("INFO", "Position closed: {symbol} PnL={pnl}", "TradeExecutor"),
        ("INFO", "Prediction generated: {symbol} {signal} (conf={conf})", "MLEngine"),
        ("INFO", "Model inference completed in {ms}ms", "MLEngine"),
        ("INFO", "Market data received: {symbol} tick", "DataFeed"),
        ("INFO", "News processed: {currency} impact={impact}", "NewsSentiment"),
        ("INFO", "WebSocket client connected", "WSManager"),
        ("INFO", "Heartbeat OK - all systems operational", "HealthCheck"),
        ("INFO", "Feature extraction completed for {symbol}", "FeatureEngine"),
        ("INFO", "Risk check passed: drawdown={dd}%", "RiskManager"),
        ("WARNING", "Spread widened on {symbol}: {spread} pips", "RiskManager"),
        ("WARNING", "High drawdown alert: {dd}% exceeds threshold", "RiskManager"),
        ("WARNING", "MT5 connection latency: {ms}ms", "MT5Bridge"),
        ("WARNING", "Model confidence below threshold for {symbol}: {conf}", "MLEngine"),
        ("WARNING", "News sentiment spike detected for {currency}", "NewsSentiment"),
        ("ERROR", "MT5 connection timeout after 30s - reconnecting", "MT5Bridge"),
        ("ERROR", "Order execution failed: requote on {symbol}", "TradeExecutor"),
        ("ERROR", "Model prediction timeout for {symbol}", "MLEngine"),
    ]
    now = datetime.utcnow()
    for i in range(100):
        level, template, module = random.choice(log_templates)
        msg = template.format(
            symbol=random.choice(SYMBOLS),
            side=random.choice(["BUY", "SELL"]),
            vol=random.choice([0.01, 0.05, 0.10]),
            price=round(random.uniform(0.6, 210), 4),
            pnl=round(random.uniform(-50, 80), 2),
            signal=random.choice(["BUY", "SELL", "HOLD"]),
            conf=round(random.uniform(0.5, 0.95), 2),
            ms=random.randint(12, 850),
            currency=random.choice(["USD", "EUR", "GBP", "JPY"]),
            impact=random.choice(["HIGH", "MEDIUM", "LOW"]),
            spread=round(random.uniform(1.2, 8.5), 1),
            dd=round(random.uniform(1.0, 6.0), 1),
        )
        ts = (now - timedelta(seconds=random.randint(0, 86400))).isoformat()
        conn.execute(
            "INSERT INTO logs (level, message, module, timestamp) VALUES (?, ?, ?, ?)",
            (level, msg, module, ts),
        )


def _seed_model_metrics(conn: sqlite3.Connection) -> None:
    models = {
        "XGBoost": {"accuracy": 0.648, "precision_val": 0.662, "recall": 0.631, "f1": 0.646, "auc": 0.712},
        "LightGBM": {"accuracy": 0.635, "precision_val": 0.641, "recall": 0.628, "f1": 0.634, "auc": 0.698},
        "RandomForest": {"accuracy": 0.612, "precision_val": 0.625, "recall": 0.598, "f1": 0.611, "auc": 0.673},
    }
    now = datetime.utcnow().isoformat()
    for model_name, m in models.items():
        conn.execute(
            "INSERT INTO model_metrics (model_name, accuracy, precision_val, recall, f1, auc, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (model_name, m["accuracy"], m["precision_val"], m["recall"], m["f1"], m["auc"], now),
        )


def _seed_feature_importance(conn: sqlite3.Connection) -> None:
    features = {
        "rsi": 0.142,
        "macd": 0.128,
        "ema_20": 0.108,
        "bollinger": 0.095,
        "atr": 0.088,
        "volume": 0.078,
        "spread": 0.072,
        "hour_of_day": 0.065,
        "day_of_week": 0.052,
        "news_sentiment": 0.048,
        "momentum": 0.038,
        "stochastic": 0.032,
        "adx": 0.025,
        "williams_r": 0.018,
        "cci": 0.011,
    }
    for model in ["XGBoost", "LightGBM", "RandomForest"]:
        for feat, imp in features.items():
            # Add slight variation per model
            variation = round(imp + random.uniform(-0.015, 0.015), 4)
            conn.execute(
                "INSERT INTO feature_importance (model_name, feature_name, importance) VALUES (?, ?, ?)",
                (model, feat, max(0.001, variation)),
            )


def _seed_equity_history(conn: sqlite3.Connection) -> None:
    """Generate 30 days of equity values with realistic random-walk fluctuation."""
    now = datetime.utcnow()
    equity = 9800.0
    target = 10245.30
    days = 30
    drift = (target - equity) / days

    for i in range(days):
        day = now - timedelta(days=days - i)
        daily_noise = random.gauss(0, 35)
        equity += drift + daily_noise
        equity = max(9500, equity)  # floor
        conn.execute(
            "INSERT INTO equity_history (equity, timestamp) VALUES (?, ?)",
            (round(equity, 2), day.strftime("%Y-%m-%d")),
        )
    # Ensure the last value matches account equity
    conn.execute(
        "INSERT INTO equity_history (equity, timestamp) VALUES (?, ?)",
        (10245.30, now.strftime("%Y-%m-%d")),
    )


def init_db() -> None:
    """Create all tables and seed with mock data. Drops existing data."""
    conn = _get_conn()
    try:
        # Drop all tables to start fresh
        for table in [
            "account_state", "positions", "trade_history", "predictions",
            "news", "logs", "model_metrics", "feature_importance", "equity_history",
        ]:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()

        _create_tables(conn)
        _seed_account(conn)
        _seed_positions(conn)
        _seed_trade_history(conn)
        _seed_predictions(conn)
        _seed_news(conn)
        _seed_logs(conn)
        _seed_model_metrics(conn)
        _seed_feature_importance(conn)
        _seed_equity_history(conn)
        conn.commit()
    finally:
        conn.close()


def get_conn() -> sqlite3.Connection:
    """Public accessor for a database connection."""
    return _get_conn()
