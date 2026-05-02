"""
News ingestion do Economic Calendar do Investing.com.
Usa o endpoint AJAX do calendario e persiste um snapshot atualizado do dia.
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from config.settings import settings

logger = logging.getLogger(__name__)

NEWS_RAW_DIR = settings.data_dir / "news"
CALENDAR_URL = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
CACHE_TTL_SECONDS = 300  # 5 minutos

_cache: dict[str, pd.DataFrame] = {}
_cache_time: dict[str, datetime] = {}


class InvestingCalendarAPI:
    """Cliente do endpoint AJAX do calendario economico."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "Origin": "https://www.investing.com",
        "Referer": "https://www.investing.com/economic-calendar/",
    }

    COUNTRIES = [
        "25",  # USA
        "72",  # Eurozone
        "4",   # UK
        "35",  # Japan
        "6",   # Switzerland
        "5",   # Australia
        "7",   # Canada
        "43",  # New Zealand
    ]

    def __init__(self, url: str = CALENDAR_URL):
        self.url = url

    def fetch(self, date_from: str | None = None, date_to: str | None = None) -> pd.DataFrame:
        """Baixa todos os eventos do dia/intervalo via endpoint AJAX."""
        if not date_from:
            date_from = datetime.now().strftime("%Y-%m-%d")
        if not date_to:
            date_to = date_from

        all_events: list[dict] = []
        limit = 0

        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=self.HEADERS,
        ) as client:
            while True:
                payload = {
                    "country[]": self.COUNTRIES,
                    "importance[]": ["1", "2", "3"],
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "dateFilter": "day",
                    "timeZone": "55",
                    "currentTab": "custom",
                    "limit_from": str(limit),
                }

                response = client.post(self.url, data=payload)
                response.raise_for_status()

                data = response.json()
                html = data.get("data", "")
                events = self._parse_html(html, date_from=date_from)

                logger.info(f"Investing AJAX offset={limit} -> {len(events)} eventos")

                if not events:
                    break

                all_events.extend(events)
                limit += 50
                time.sleep(0.4)

        if not all_events:
            return pd.DataFrame()

        df = pd.DataFrame(all_events)
        df = self._clean_dataframe(df)
        logger.info(f"Investing AJAX total: {len(df)} eventos")
        return df

    def _parse_html(self, html: str, date_from: str) -> list[dict]:
        """Extrai eventos do fragmento HTML retornado pela API."""
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")

        events = []
        for row in rows:
            event = self._parse_row(row, date_from=date_from)
            if event:
                events.append(event)

        return events

    def _parse_row(self, row, date_from: str) -> dict | None:
        """Extrai um evento individual."""
        try:
            link = row.find("a")
            if not link:
                return None

            full_text = row.get_text(" ", strip=True)
            time_match = re.search(r"\b\d{2}:\d{2}\b", full_text)
            time_text = time_match.group() if time_match else None

            name = link.get_text(strip=True)
            country = None
            flag = row.find("span", title=True)
            if flag:
                country = flag.get("title")

            impact = self._parse_impact(row)

            text = re.sub(r"\b\d{2}:\d{2}\b", "", full_text)
            text = text.replace(name, "")
            numbers = re.findall(r"[-+]?\d+\.\d+[MK]|[-+]?\d+\.\d+%?|[-+]?\d+%?", text)

            timestamp = None
            if time_text:
                timestamp = pd.to_datetime(f"{date_from} {time_text}", errors="coerce")
                if pd.notna(timestamp):
                    timestamp = timestamp.to_pydatetime()
                else:
                    timestamp = None

            signal = "unknown"
            actual_cell = row.find("td", class_=re.compile(r"\b(actual|bold)\b", re.IGNORECASE))
            if actual_cell:
                classes = actual_cell.get("class", [])
                if "greenFont" in classes:
                    signal = "good"
                elif "redFont" in classes:
                    signal = "bad"

            return {
                "timestamp": timestamp,
                "time": time_text,
                "country": country,
                "impact": impact,
                "url": link.get("href"),
                "name": name,
                "actual": numbers[0] if len(numbers) > 0 else None,
                "forecast": numbers[1] if len(numbers) > 1 else None,
                "previous": numbers[2] if len(numbers) > 2 else None,
                "signal": signal,
                "event_type": None,
            }

        except Exception as e:
            logger.debug(f"Erro ao parsear evento: {e}")
            return None

    def _parse_impact(self, row) -> int:
        """
        Extrai impacto real do evento.

        O HTML do Investing costuma renderizar sempre 3 marcadores de impacto,
        misturando icones "full" e "empty". O parser antigo contava qualquer
        classe contendo "bull", o que transformava praticamente tudo em 3.
        """
        impact_cell = row.find("td", class_=re.compile(r"(sentiment|importance)", re.IGNORECASE))
        if not impact_cell:
            # fallback conservador
            icons = row.find_all(["i", "span"], class_=re.compile("bull", re.IGNORECASE))
            return min(len(icons), 3)

        cell_text = impact_cell.get("title") or impact_cell.get("aria-label") or ""
        cell_text = str(cell_text).strip().lower()
        if "high volatility" in cell_text:
            return 3
        if "moderate volatility" in cell_text or "medium volatility" in cell_text:
            return 2
        if "low volatility" in cell_text:
            return 1

        data_img_key = str(impact_cell.get("data-img_key", "")).strip().lower()
        if data_img_key:
            if data_img_key.endswith("3") or "high" in data_img_key:
                return 3
            if data_img_key.endswith("2") or "mod" in data_img_key or "medium" in data_img_key:
                return 2
            if data_img_key.endswith("1") or "low" in data_img_key:
                return 1

        icons = impact_cell.find_all(["i", "span"])
        full_score = 0
        for icon in icons:
            class_names = " ".join(icon.get("class", [])).lower()
            title_text = str(icon.get("title", "")).lower()
            aria_text = str(icon.get("aria-label", "")).lower()
            attrs_blob = " ".join([class_names, title_text, aria_text]).strip()

            if not attrs_blob:
                continue

            # Ignora explicitamente marcadores vazios/inativos
            if any(token in attrs_blob for token in ["empty", "none", "inactive", "grayempty"]):
                continue

            # Conta apenas marcadores cheios/ativos
            if any(token in attrs_blob for token in ["full", "active", "grayfull", "bull", "bullish"]):
                full_score += 1

        return max(0, min(full_score, 3))

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza colunas e remove duplicatas."""
        if df.empty:
            return df

        df = df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        dedup_cols = [c for c in ["timestamp", "time", "country", "name"] if c in df.columns]
        if dedup_cols:
            df = df.drop_duplicates(subset=dedup_cols, keep="last")

        sort_cols = [c for c in ["timestamp", "country", "name"] if c in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols).reset_index(drop=True)

        return df


def _get_daily_filepath(target_date: str | None = None) -> Path:
    date_str = target_date or datetime.now().strftime("%Y-%m-%d")
    return NEWS_RAW_DIR / f"raw_{date_str}.parquet"


def fetch_news(date_from: str | None = None, date_to: str | None = None, force: bool = False) -> pd.DataFrame:
    """
    Busca noticias do Investing.
    Usa cache em memoria de 5 minutos para evitar downloads desnecessarios.
    """
    cache_key = date_from or datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()

    if (
        not force
        and cache_key in _cache
        and not _cache[cache_key].empty
        and cache_key in _cache_time
        and (now - _cache_time[cache_key]).total_seconds() < CACHE_TTL_SECONDS
    ):
        logger.info(f"News cache hit para {cache_key}")
        return _cache[cache_key].copy()

    api = InvestingCalendarAPI()
    df = api.fetch(date_from=date_from, date_to=date_to)

    if not df.empty:
        _cache[cache_key] = df.copy()
        _cache_time[cache_key] = now

    return df


def save_news_raw(df: pd.DataFrame, target_date: str | None = None) -> Path:
    """
    Salva o snapshot atualizado do dia.
    Sobrescreve o arquivo diario e atualiza tambem o alias raw.parquet.
    """
    NEWS_RAW_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = _get_daily_filepath(target_date)
    raw_alias = NEWS_RAW_DIR / "raw.parquet"

    df_to_save = df.copy()
    if "timestamp" in df_to_save.columns:
        df_to_save["timestamp"] = pd.to_datetime(df_to_save["timestamp"], errors="coerce")

    df_to_save.to_parquet(daily_path, index=False)
    df_to_save.to_parquet(raw_alias, index=False)
    logger.info(f"News raw salvo: {daily_path} ({len(df_to_save)} eventos)")
    return daily_path


def load_news_raw(target_date: str | None = None) -> pd.DataFrame:
    """Carrega o snapshot de noticias do dia solicitado."""
    daily_path = _get_daily_filepath(target_date)
    raw_alias = NEWS_RAW_DIR / "raw.parquet"

    if daily_path.exists():
        return pd.read_parquet(daily_path)
    if raw_alias.exists():
        return pd.read_parquet(raw_alias)
    return pd.DataFrame()


def run_news_ingestion(date_from: str | None = None, date_to: str | None = None, force: bool = False) -> pd.DataFrame:
    """Pipeline completo: baixa e sobrescreve o snapshot do dia."""
    df = fetch_news(date_from=date_from, date_to=date_to, force=force)
    if not df.empty:
        save_news_raw(df, target_date=date_from)
    return df
