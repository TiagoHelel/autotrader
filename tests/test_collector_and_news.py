from src.data.collector import validate_symbols
from src.data.news import investing
from src.data.news.investing import InvestingCalendarAPI, save_news_raw, load_news_raw
from src.features.news_features import normalize_news, build_news_features
from src.mt5.symbols import DESIRED_SYMBOLS


class DummyConnection:
    def __init__(self, symbols):
        self._symbols = symbols

    def get_available_symbols(self, group="*"):
        return self._symbols


def test_validate_symbols_keeps_xauusd_when_available():
    conn = DummyConnection(DESIRED_SYMBOLS)

    validated = validate_symbols(conn)

    assert validated == DESIRED_SYMBOLS
    assert "XAUUSD" in validated


def test_investing_calendar_api_parses_ajax_response(monkeypatch):
    html = """
    <html>
      <body>
        <tr>
          <td class="time">12:30</td>
          <td class="flagCur"><span title="United States"></span></td>
          <td class="sentiment"><i class="grayFullBullishIcon"></i><i class="grayFullBullishIcon"></i></td>
          <td class="event"><a href="/news/test">CPI</a></td>
          <td class="bold greenFont">3.2%</td>
          <td class="fore">3.0%</td>
          <td class="prev">2.9%</td>
        </tr>
      </body>
    </html>
    """

    class DummyResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

        def raise_for_status(self):
            return None

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, uri, data):
            assert "getCalendarFilteredData" in uri
            self.calls += 1
            payload = {"data": html} if self.calls == 1 else {"data": ""}
            return DummyResponse(payload)

    monkeypatch.setattr(investing.httpx, "Client", DummyClient)

    calendar = InvestingCalendarAPI()
    events = calendar.fetch(date_from="2026-04-08")

    assert len(events) == 1
    assert events.iloc[0]["country"] == "United States"
    assert events.iloc[0]["name"] == "CPI"
    assert events.iloc[0]["impact"] == 2
    assert str(events.iloc[0]["timestamp"]) == "2026-04-08 12:30:00"
    assert events.iloc[0]["signal"] == "good"


def test_save_news_raw_overwrites_daily_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(investing, "NEWS_RAW_DIR", tmp_path)

    first = save_news_raw(investing.pd.DataFrame([
        {"timestamp": "2026-04-08 10:00:00", "name": "A", "country": "United States"}
    ]), target_date="2026-04-08")

    second = save_news_raw(investing.pd.DataFrame([
        {"timestamp": "2026-04-08 11:00:00", "name": "B", "country": "Euro Zone"}
    ]), target_date="2026-04-08")

    loaded = load_news_raw("2026-04-08")

    assert first == second
    assert len(loaded) == 1
    assert loaded.iloc[0]["name"] == "B"


def test_news_llm_merge_keeps_same_name_for_different_countries():
    news_df = investing.pd.DataFrame([
        {
            "timestamp": "2026-04-08 15:00:00",
            "country": "Canada",
            "impact": 3,
            "name": "Thomson Reuters IPSOS PCSI  (Apr)",
            "signal": "unknown",
        },
        {
            "timestamp": "2026-04-08 15:00:00",
            "country": "United States",
            "impact": 3,
            "name": "Thomson Reuters IPSOS PCSI  (Apr)",
            "signal": "unknown",
        },
    ])
    normalized = normalize_news(news_df)

    llm_df = investing.pd.DataFrame([
        {
            "timestamp": "2026-04-08 15:00:00",
            "name": "Thomson Reuters IPSOS PCSI  (Apr)",
            "country": "Canada",
            "sentiment_score": -0.2,
            "confidence": 0.9,
            "volatility_impact": 0.4,
            "used_fallback": False,
        },
        {
            "timestamp": "2026-04-08 15:00:00",
            "name": "Thomson Reuters IPSOS PCSI  (Apr)",
            "country": "United States",
            "sentiment_score": 0.6,
            "confidence": 0.9,
            "volatility_impact": 0.4,
            "used_fallback": False,
        },
    ])
    llm_df["timestamp"] = investing.pd.to_datetime(llm_df["timestamp"])

    features = build_news_features(
        symbol="USDCAD",
        # Apos o embargo ex-post default (5 min) para incorporar sentiment/LLM
        current_time=investing.pd.Timestamp("2026-04-08 15:10:00").to_pydatetime(),
        news_df=normalized,
        llm_df=llm_df,
    )

    # USDCAD: base=USD (United States=0.6), quote=CAD (Canada=-0.2)
    assert features["news_llm_sentiment_base"] == 0.6
    assert features["news_llm_sentiment_quote"] == -0.2


def test_news_post_release_embargo_blocks_sentiment_before_lag():
    """
    Ex-post (sentiment/LLM) NAO deve aparecer dentro da janela de embargo.
    Ex-ante (impact, high_impact_flag) DEVE aparecer no instante agendado.
    """
    news_df = investing.pd.DataFrame([
        {
            "timestamp": "2026-04-08 15:00:00",
            "country": "United States",
            "impact": 3,
            "name": "CPI",
            "signal": "good",  # so seria conhecido pos-release
        },
    ])
    normalized = normalize_news(news_df)

    # current_time exatamente no horario agendado (t = release)
    feats_at_release = build_news_features(
        symbol="EURUSD",
        current_time=investing.pd.Timestamp("2026-04-08 15:00:00").to_pydatetime(),
        news_df=normalized,
    )
    # Ex-post bloqueado
    assert feats_at_release["news_sentiment_quote"] == 0.0
    # Ex-ante disponivel
    assert feats_at_release["news_impact_quote"] == 3.0
    assert feats_at_release["high_impact_flag"] == 1

    # Apos o lag default (5 min) + folga, sentiment deve aparecer
    feats_after_lag = build_news_features(
        symbol="EURUSD",
        current_time=investing.pd.Timestamp("2026-04-08 15:06:00").to_pydatetime(),
        news_df=normalized,
    )
    assert feats_after_lag["news_sentiment_quote"] == 1.0  # signal="good"

    # Override explicito do lag desabilita embargo
    feats_no_lag = build_news_features(
        symbol="EURUSD",
        current_time=investing.pd.Timestamp("2026-04-08 15:00:00").to_pydatetime(),
        news_df=normalized,
        post_release_lag_min=0,
    )
    assert feats_no_lag["news_sentiment_quote"] == 1.0
