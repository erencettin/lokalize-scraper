from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from clients.backend_client import BackendClient
from clients.serpapi_trends_client import SerpApiTrendsClient
from config import settings
from utils.constants import TREND_CATEGORIES, TREND_CITIES

_logger = logging.getLogger(__name__)

_TRENDS_GEO = "TR"


def _normalize(text: str) -> str:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return text.lower().translate(tr_map)


class TrendAnalysisService:
    """
    Builds the weekly "this week in your city" trend report.

    Strategy:
    - One related-topics call per category (12 total) to get Knowledge Graph
      entities (artist names, venue names, event titles) trending in Turkey.
    - One backend call per (city × category) to fetch candidate events.
    - Events are scored by fuzzy word overlap against trending topic titles.
    - If no trending match found for a category, falls back to top upcoming
      events from the backend so every category always appears in the report.

    Total SerpAPI budget: 12 requests/week.
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

        # Step 1: get trending topic titles per category (one SerpAPI call each)
        category_topics: Dict[str, List[str]] = {}
        for cat in TREND_CATEGORIES:
            topics = self._get_topic_titles(cat["query"])
            category_topics[cat["id"]] = topics
            _logger.info(
                "Kategori '%s' için %d trending topic: %s",
                cat["label"], len(topics), topics[:5],
            )

        # Step 2: for each city, match topics against backend events
        cities_report: Dict[str, List[Dict[str, Any]]] = {}
        for city in TREND_CITIES:
            city_candidates = []
            for cat in TREND_CATEGORIES:
                topics = category_topics[cat["id"]]
                events, is_trending = self._fetch_and_match(
                    city=city,
                    backend_type=cat["backendType"],
                    topics=topics,
                    date_from=week_from,
                    date_to=week_to,
                )
                city_candidates.append({
                    "category":      cat["id"],
                    "label":         cat["label"],
                    "trendingTopics": topics[:10] if is_trending else [],
                    "isTrending":    is_trending,
                    "events":        events,
                })
            cities_report[city] = city_candidates

        return {"cities": cities_report, "requestCount": self._client.request_count}

    def _get_topic_titles(self, query: str) -> List[str]:
        try:
            related = self._client.related_topics(
                query=query,
                geo=_TRENDS_GEO,
                lookback_days=settings.trends_lookback_days,
            )
        except RuntimeError as exc:
            _logger.warning("Related topics başarısız query=%s: %s", query, exc)
            return []

        titles: List[str] = []
        for section in ("rising", "top"):
            for item in related.get(section) or []:
                title = (item.get("topic") or {}).get("title", "").strip()
                if title and title not in titles:
                    titles.append(title)
        return titles

    def _fetch_and_match(
        self,
        *,
        city: str,
        backend_type: str,
        topics: List[str],
        date_from: date,
        date_to: date,
    ) -> tuple[List[Dict[str, Any]], bool]:
        raw = self._backend.get_trend_candidates(city=city, category=backend_type, limit=50)
        in_week = [e for e in raw if self._in_week(e, date_from, date_to)]

        # Try trending match first
        if topics:
            scored = []
            for event in in_week:
                score = self._match_score(event.get("title", ""), topics)
                if score > 0:
                    scored.append((score, event))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                return [e for _, e in scored[:5]], True

        # Fallback: top upcoming events, no trending match
        return in_week[:5], False

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
    def _match_score(title: str, topics: List[str]) -> int:
        title_words = set(w for w in _normalize(title).split() if len(w) > 2)
        score = 0
        for topic in topics:
            topic_words = set(w for w in _normalize(topic).split() if len(w) > 2)
            score += len(topic_words & title_words)
        return score
