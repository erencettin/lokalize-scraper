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


class TrendAnalysisService:
    """
    Builds the weekly "this week in your city" trend report.

    Strategy (no Trending Now — every category is always covered):
    - One interest-over-time call per category (12 total) to get a Turkey-wide
      trend score for each category's representative search term.
    - One backend call per (city × category) to fetch matching events.

    Total SerpAPI budget: 12 requests/week, predictable and well within the
    free-tier quota of 250/month.
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

        # Step 1: score all 12 categories via interest-over-time (one call each)
        scored: List[Dict[str, Any]] = []
        for cat in TREND_CATEGORIES:
            score = self._score_category(cat["query"])
            scored.append({
                "id":         cat["id"],
                "label":      cat["label"],
                "backendType":cat["backendType"],
                "query":      cat["query"],
                "trendScore": score,
            })
            _logger.info("Kategori skoru — %s (%s): %s", cat["label"], cat["query"], score)

        scored.sort(key=lambda c: c["trendScore"], reverse=True)

        # Step 2: for each city, fetch matching events per category
        week_from, week_to = self._compute_week_range()
        _logger.info("Haftalık tarama aralığı: %s – %s", week_from, week_to)

        cities_report: Dict[str, List[Dict[str, Any]]] = {}
        for city in TREND_CITIES:
            city_candidates = []
            for cat in scored:
                events = self._fetch_matching_events(
                    city=city,
                    backend_type=cat["backendType"],
                    date_from=week_from,
                    date_to=week_to,
                )
                city_candidates.append({
                    "category":   cat["id"],
                    "label":      cat["label"],
                    "term":       cat["query"],
                    "trendScore": cat["trendScore"],
                    "events":     events,
                })
            cities_report[city] = city_candidates

        return {"cities": cities_report, "requestCount": self._client.request_count}

    def _score_category(self, query: str) -> int:
        try:
            timeline = self._client.interest_over_time(
                query=query,
                geo=_TRENDS_GEO,
                lookback_days=settings.trends_lookback_days,
            )
        except RuntimeError as exc:
            _logger.warning("Interest-over-time basarisiz query=%s: %s", query, exc)
            return 0

        values: List[int] = []
        for point in timeline:
            for series in point.get("values", []):
                extracted = series.get("extracted_value")
                if isinstance(extracted, int):
                    values.append(extracted)

        return max(values) if values else 0

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

    def _fetch_matching_events(
        self, *, city: str, backend_type: str, date_from: date, date_to: date
    ) -> List[Dict[str, Any]]:
        raw = self._backend.get_trend_candidates(city=city, category=backend_type, limit=20)
        filtered = [e for e in raw if self._in_week(e, date_from, date_to)]
        return filtered[:5]
