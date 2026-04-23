"""Coverage push for src/data/news/investing.py - covers branches not exercised
by tests/test_collector_and_news.py (cache, impact parsing variants, fallbacks,
run_news_ingestion pipeline)."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.data.news import investing
from src.data.news.investing import (
    InvestingCalendarAPI,
    fetch_news,
    run_news_ingestion,
    load_news_raw,
    save_news_raw,
)


# ---------- helpers ----------


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def make_dummy_client(pages):
    """pages: list of html strings; returns empty after exhausting."""

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.i = 0

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, uri, data):
            if self.i < len(pages):
                payload = {"data": pages[self.i]}
            else:
                payload = {"data": ""}
            self.i += 1
            return DummyResponse(payload)

    return DummyClient


# ---------- _parse_impact variants ----------


def test_parse_impact_high_volatility_title():
    api = InvestingCalendarAPI()
    html = '<tr><td class="sentiment" title="High Volatility Expected"></td></tr>'
    from bs4 import BeautifulSoup
    row = BeautifulSoup(html, "html.parser").find("tr")
    assert api._parse_impact(row) == 3


def test_parse_impact_moderate_and_low_volatility():
    api = InvestingCalendarAPI()
    from bs4 import BeautifulSoup
    row_mod = BeautifulSoup(
        '<tr><td class="sentiment" title="Moderate Volatility"></td></tr>',
        "html.parser",
    ).find("tr")
    row_low = BeautifulSoup(
        '<tr><td class="sentiment" title="Low Volatility"></td></tr>',
        "html.parser",
    ).find("tr")
    assert api._parse_impact(row_mod) == 2
    assert api._parse_impact(row_low) == 1


def test_parse_impact_data_img_key():
    api = InvestingCalendarAPI()
    from bs4 import BeautifulSoup
    for key, expected in [("bull3", 3), ("bull2", 2), ("bull1", 1)]:
        row = BeautifulSoup(
            f'<tr><td class="sentiment" data-img_key="{key}"></td></tr>',
            "html.parser",
        ).find("tr")
        assert api._parse_impact(row) == expected


def test_parse_impact_fallback_no_sentiment_cell():
    """Linhas sem td sentiment/importance caem no fallback."""
    api = InvestingCalendarAPI()
    from bs4 import BeautifulSoup
    row = BeautifulSoup(
        '<tr><td><i class="grayFullBullishIcon"></i>'
        '<i class="grayFullBullishIcon"></i></td></tr>',
        "html.parser",
    ).find("tr")
    assert api._parse_impact(row) == 2


def test_parse_impact_icons_empty_and_full_mixed():
    api = InvestingCalendarAPI()
    from bs4 import BeautifulSoup
    row = BeautifulSoup(
        '<tr><td class="sentiment">'
        '<i class="grayFullBullishIcon"></i>'
        '<i class="grayEmptyBullishIcon"></i>'
        '<i></i>'
        '</td></tr>',
        "html.parser",
    ).find("tr")
    # 1 full, 1 empty ignored, 1 sem attrs ignored
    assert api._parse_impact(row) == 1


# ---------- _parse_row edge cases ----------


def test_parse_row_no_link_returns_none():
    api = InvestingCalendarAPI()
    from bs4 import BeautifulSoup
    row = BeautifulSoup("<tr><td>no link here</td></tr>", "html.parser").find("tr")
    assert api._parse_row(row, date_from="2026-04-08") is None


def test_parse_row_signal_bad_redfont():
    api = InvestingCalendarAPI()
    from bs4 import BeautifulSoup
    html = """
    <tr>
      <td class="time">12:30</td>
      <td class="event"><a href="/x">PMI</a></td>
      <td class="bold redFont">1.0</td>
    </tr>
    """
    row = BeautifulSoup(html, "html.parser").find("tr")
    ev = api._parse_row(row, date_from="2026-04-08")
    assert ev["signal"] == "bad"


def test_parse_row_invalid_time_timestamp_none():
    api = InvestingCalendarAPI()
    from bs4 import BeautifulSoup
    # horario presente mas combinacao invalida com data
    html = '<tr><td>99:99</td><td><a href="/x">E</a></td></tr>'
    row = BeautifulSoup(html, "html.parser").find("tr")
    ev = api._parse_row(row, date_from="not-a-date")
    assert ev is not None
    assert ev["timestamp"] is None


# ---------- fetch (API layer) ----------


def test_fetch_empty_response_returns_empty_df(monkeypatch):
    monkeypatch.setattr(investing.httpx, "Client", make_dummy_client([]))
    api = InvestingCalendarAPI()
    df = api.fetch(date_from="2026-04-08")
    assert df.empty


def test_fetch_default_dates(monkeypatch):
    """date_from=None deve usar hoje."""
    monkeypatch.setattr(investing.httpx, "Client", make_dummy_client([]))
    api = InvestingCalendarAPI()
    df = api.fetch()  # sem datas
    assert df.empty


# ---------- _clean_dataframe edge ----------


def test_clean_dataframe_empty_returns_same():
    api = InvestingCalendarAPI()
    empty = pd.DataFrame()
    assert api._clean_dataframe(empty).empty


# ---------- fetch_news cache ----------


@pytest.fixture(autouse=True)
def _clear_cache():
    investing._cache.clear()
    investing._cache_time.clear()
    yield
    investing._cache.clear()
    investing._cache_time.clear()


def test_fetch_news_cache_hit(monkeypatch):
    """Segunda chamada dentro do TTL retorna copia do cache sem chamar API."""
    sample = pd.DataFrame([{"name": "X", "country": "US"}])
    investing._cache["2026-04-08"] = sample
    investing._cache_time["2026-04-08"] = datetime.now()

    def boom(*a, **kw):
        raise AssertionError("should not hit API on cache hit")

    monkeypatch.setattr(InvestingCalendarAPI, "fetch", boom)

    got = fetch_news(date_from="2026-04-08")
    assert len(got) == 1
    assert got.iloc[0]["name"] == "X"


def test_fetch_news_cache_expired_refetches(monkeypatch):
    investing._cache["2026-04-08"] = pd.DataFrame([{"name": "OLD"}])
    investing._cache_time["2026-04-08"] = datetime.now() - timedelta(seconds=999)

    new_df = pd.DataFrame([{"name": "NEW"}])
    monkeypatch.setattr(InvestingCalendarAPI, "fetch", lambda self, **kw: new_df)

    got = fetch_news(date_from="2026-04-08")
    assert got.iloc[0]["name"] == "NEW"
    assert investing._cache["2026-04-08"].iloc[0]["name"] == "NEW"


def test_fetch_news_force_bypasses_cache(monkeypatch):
    investing._cache["2026-04-08"] = pd.DataFrame([{"name": "CACHED"}])
    investing._cache_time["2026-04-08"] = datetime.now()

    new_df = pd.DataFrame([{"name": "FRESH"}])
    monkeypatch.setattr(InvestingCalendarAPI, "fetch", lambda self, **kw: new_df)

    got = fetch_news(date_from="2026-04-08", force=True)
    assert got.iloc[0]["name"] == "FRESH"


def test_fetch_news_empty_does_not_populate_cache(monkeypatch):
    monkeypatch.setattr(
        InvestingCalendarAPI, "fetch", lambda self, **kw: pd.DataFrame()
    )
    got = fetch_news(date_from="2026-04-08")
    assert got.empty
    assert "2026-04-08" not in investing._cache


# ---------- load_news_raw fallback paths ----------


def test_load_news_raw_falls_back_to_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(investing, "NEWS_RAW_DIR", tmp_path)
    alias = tmp_path / "raw.parquet"
    pd.DataFrame([{"name": "A"}]).to_parquet(alias, index=False)
    # arquivo diario nao existe, deve cair no alias
    got = load_news_raw("2099-01-01")
    assert len(got) == 1
    assert got.iloc[0]["name"] == "A"


def test_load_news_raw_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(investing, "NEWS_RAW_DIR", tmp_path)
    got = load_news_raw("2099-01-01")
    assert got.empty


# ---------- run_news_ingestion pipeline ----------


def test_run_news_ingestion_saves_when_not_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(investing, "NEWS_RAW_DIR", tmp_path)
    df = pd.DataFrame(
        [{"timestamp": "2026-04-08 10:00:00", "name": "CPI", "country": "US"}]
    )
    monkeypatch.setattr(InvestingCalendarAPI, "fetch", lambda self, **kw: df)

    out = run_news_ingestion(date_from="2026-04-08", force=True)
    assert len(out) == 1
    assert (tmp_path / "raw_2026-04-08.parquet").exists()
    assert (tmp_path / "raw.parquet").exists()


def test_run_news_ingestion_empty_skips_save(tmp_path, monkeypatch):
    monkeypatch.setattr(investing, "NEWS_RAW_DIR", tmp_path)
    monkeypatch.setattr(
        InvestingCalendarAPI, "fetch", lambda self, **kw: pd.DataFrame()
    )
    out = run_news_ingestion(date_from="2026-04-08", force=True)
    assert out.empty
    assert not any(tmp_path.iterdir())
