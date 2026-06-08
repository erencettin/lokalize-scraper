from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from clients.backend_client import BackendClient
from clients.serpapi_trends_client import SerpApiTrendsClient
from config import settings
from utils.constants import TREND_CATEGORIES, TREND_CITIES, TREND_CITY_GEO

_logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return text.lower().translate(tr_map)


class TrendAnalysisService:
    """
    Builds the weekly "this week in your city" trend report.

    Strategy:
    - One Trending Now call per city (7 total) to get what people are actually
      searching for right now in that city (e.g. "Tarkan", "Doğu Demirkol").
    - One backend call per (city × category) to fetch candidate events.
    - Events are scored by fuzzy word overlap against the city's trending terms.
    - If no trending match found for a category, falls back to top upcoming
      events so every category always appears in the report.

    Total SerpAPI budget: 7 requests/week.
    """

    def __init__(
        self,
        trends_client: Optional[SerpApiTrendsClient] = None,
        backend_client: Optional[BackendClient] = None,
    ) -> None:
        self._client = trends_client or SerpApiTrendsClient()
        self._backend = backend_client or BackendClient(base_url=settings.backend_url)

    def build_report(self) -> Dict[str, Any]:
        if not self._client.is_enabled:
            _logger.warning("[WARN] SERPAPI_API_KEY tanimli degil. Trend analizi atlandi.")
            return {"cities": {}, "requestCount": 0}

        week_from, week_to = self._compute_week_range()
        _logger.info("Haftalık tarama aralığı: %s – %s", week_from, week_to)

        cities_report: Dict[str, List[Dict[str, Any]]] = {}
        for city in TREND_CITIES:
            geo = TREND_CITY_GEO.get(city, "TR")
            trending_terms = self._get_trending_now(geo)
            _logger.info(
                "Şehir '%s' için %d trending terim: %s",
                city, len(trending_terms), trending_terms[:5],
            )

            city_candidates = []
            for cat in TREND_CATEGORIES:
                events, is_trending, matched_terms = self._fetch_and_match(
                    city=city,
                    backend_type=cat["backendType"],
                    trending_terms=trending_terms,
                    date_from=week_from,
                    date_to=week_to,
                )
                city_candidates.append({
                    "category":      cat["id"],
                    "label":         cat["label"],
                    "trendingTopics": matched_terms,
                    "isTrending":    is_trending,
                    "events":        events,
                })
            cities_report[city] = city_candidates

        return {"cities": cities_report, "requestCount": self._client.request_count}

    def _get_trending_now(self, geo: str) -> List[str]:
        try:
            results = self._client.trending_now(geo=geo)
            return [item.get("query", "").strip() for item in results if item.get("query")]
        except RuntimeError as exc:
            _logger.warning("Trending now başarısız geo=%s: %s", geo, exc)
            return []

    def _fetch_and_match(
        self,
        *,
        city: str,
        backend_type: str,
        trending_terms: List[str],
        date_from: date,
        date_to: date,
    ) -> tuple[List[Dict[str, Any]], bool, List[str]]:
        raw = self._backend.get_trend_candidates(city=city, category=backend_type, limit=50)
        in_week = [e for e in raw if self._in_week(e, date_from, date_to)]

        if trending_terms:
            scored = []
            for event in in_week:
                score = self._match_score(event.get("title", ""), trending_terms)
                if score > 0:
                    scored.append((score, event))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                matched_events = [e for _, e in scored[:5]]
                matched_terms = self._matched_terms(
                    [e.get("title", "") for e in matched_events],
                    trending_terms,
                )
                return matched_events, True, matched_terms

        return in_week[:5], False, []

    @staticmethod
    def _matched_terms(titles: List[str], trending_terms: List[str]) -> List[str]:
        all_title_words = set()
        for t in titles:
            all_title_words.update(w for w in _normalize(t).split() if len(w) > 2)
        result = []
        for term in trending_terms:
            term_words = set(w for w in _normalize(term).split() if len(w) > 2)
            if term_words & all_title_words:
                result.append(term)
        return result[:5]

    @staticmethod
    def _compute_week_range() -> tuple[date, date]:
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        return next_monday, next_monday + timedelta(days=6)

    @staticmethod
    def _in_week(event: Dict[str, Any], date_from: date, date_to: date) -> bool:
        raw = event.get("nextDate")
        if not raw:
            return True
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            d = dt.date()
            return d.year >= 2050 or date_from <= d <= date_to
        except Exception:
            return True

    @staticmethod
    def _match_score(title: str, terms: List[str]) -> int:
        title_words = set(w for w in _normalize(title).split() if len(w) > 2)
        score = 0
        for term in terms:
            term_words = set(w for w in _normalize(term).split() if len(w) > 2)
            score += len(term_words & title_words)
        return score
